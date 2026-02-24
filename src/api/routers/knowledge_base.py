import asyncio
import json
import logging
import os
import re
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth.dependencies import require_permission
from src.api.db.models.incident_log import IncidentLog
from src.api.db.session import get_session
from src.api.schemas.knowledge_base_schemas import (
    FieldMappingRequest,
    FileUploadRequest,
    IngestionConfirmRequest,
    RollbackVersionRequest,
)
from src.api.services.incident_ingestion_service import IncidentIngestionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge-base", tags=["knowledge-base"])

# Lazy-loaded dependencies (qdrant_client / sentence_transformers may not be installed)
_qdrant_imports = None
_embeddings = None

def _load_qdrant():
    global _qdrant_imports
    if _qdrant_imports is None:
        from qdrant_client import QdrantClient
        from qdrant_client.models import VectorParams, Distance, PointStruct
        from src.copilot.config import QDRANT_URL, QDRANT_API_KEY
        _qdrant_imports = {
            "QdrantClient": QdrantClient,
            "VectorParams": VectorParams,
            "Distance": Distance,
            "PointStruct": PointStruct,
            "QDRANT_URL": QDRANT_URL,
            "QDRANT_API_KEY": QDRANT_API_KEY,
        }
    return _qdrant_imports

def _load_model():
    """Load HuggingFace embeddings model (same as copilot uses)."""
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


def _parse_description_metadata(description: str) -> Dict[str, str]:
    """
    Parse structured metadata (impactedApplication, rootCause, etc.) from
    ServiceNow incident descriptions.
    
    ServiceNow descriptions (via snow.py normalize) look like:
        short_description
        Details: {"incident_id": "...", "incident_description": "impactedApplication: X\\nrootCause: Y\\n..."}
        Category: inquiry
        Priority: 3
    
    The actual metadata keys are inside the incident_description field of the embedded JSON.
    """
    metadata = {}
    
    # Strategy 1: Parse the JSON blob from "Details: {json}" 
    details_match = re.search(r'Details:\s*(\{.*\})', description, re.DOTALL)
    if details_match:
        try:
            details_json = json.loads(details_match.group(1))
            inner_desc = details_json.get("incident_description", "")
            if inner_desc:
                for line in inner_desc.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        k, v = key.strip(), value.strip()
                        if k and v:
                            metadata[k] = v
                if metadata:
                    return metadata
        except (json.JSONDecodeError, ValueError):
            pass
    
    # Strategy 2: Regex extraction of incident_description value (handles malformed JSON)
    regex_match = re.search(
        r'"incident_description"\s*:\s*"((?:[^"\\]|\\.)*)"', description
    )
    if regex_match:
        inner = regex_match.group(1).replace('\\n', '\n').replace('\\"', '"')
        for line in inner.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                k, v = key.strip(), value.strip()
                if k and v and k[0].islower():  # camelCase keys only
                    metadata[k] = v
        if metadata:
            return metadata
    
    # Strategy 3: Direct key-value parsing (for flat descriptions like original ingestion)
    for line in description.split('\n'):
        if ':' in line:
            try:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()
            except ValueError:
                pass
    return metadata

def get_qdrant_client():
    """Get Qdrant client with authentication if configured."""
    q = _load_qdrant()
    if q["QDRANT_API_KEY"]:
        return q["QdrantClient"](url=q["QDRANT_URL"], api_key=q["QDRANT_API_KEY"])
    else:
        return q["QdrantClient"](url=q["QDRANT_URL"])


# GET list of incidents from knowledge base
@router.get("/incidents")
async def list_incidents(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("integration.view")),
):
    """List all ServiceNow incidents from Qdrant vector database."""
    try:
        # Try to read from Qdrant first (shows all historical incidents)
        try:
            client = get_qdrant_client()
            svc = IncidentIngestionService(session)
            collection_name = await svc.get_active_collection_name()
            
            if client.collection_exists(collection_name):
                # Get all ServiceNow incidents from Qdrant
                scroll_result = client.scroll(
                    collection_name=collection_name,
                    limit=10000,
                    with_payload=True
                )
                
                result = []
                seen_ids = set()
                for point in scroll_result[0]:
                    payload = point.payload or {}
                    # LangChain format: metadata is nested
                    metadata = payload.get("metadata", {})
                    source = metadata.get("source_system", "").lower()
                    
                    # Check if this is a ServiceNow incident (LangChain format)
                    if "servicenow" in source:
                        inc_id = metadata.get("incident_id", "")
                        if inc_id not in seen_ids:
                            seen_ids.add(inc_id)
                            result.append({
                                "incident_id": inc_id,
                                "title": metadata.get("incident_title", ""),
                                "description": payload.get("page_content", ""),
                                "action_taken": metadata.get("mitigation", ""),
                                "opened_at": metadata.get("opened_at"),
                                "updated_at": metadata.get("updated_at"),
                                "source": "servicenow"
                            })
                
                return {"success": True, "incidents": result}
        except ImportError:
            # Qdrant client not available, fall back to JSON file
            pass
        except Exception as e:
            logger.warning(f"Failed to read from Qdrant: {e}")
        
        # Fallback: Read from JSON file (only shows latest sync)
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
        output_path = os.path.join(data_dir, "incidentspulledfromsnow.json")
        
        if not os.path.exists(output_path):
            return {"success": True, "incidents": []}
        
        with open(output_path, "r", encoding="utf-8") as f:
            incidents = json.load(f)
        
        result = []
        for inc in incidents:
            result.append({
                "incident_id": inc.get("incident_id"),
                "title": inc.get("title"),
                "description": inc.get("description"),
                "action_taken": inc.get("action_taken"),
                "opened_at": inc.get("opened_at"),
                "updated_at": inc.get("updated_at"),
                "source": "servicenow"
            })
        
        return {"success": True, "incidents": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# DELETE incident from knowledge base
@router.delete("/incidents/{incident_id}")
async def delete_incident(
    incident_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("integration.delete")),
):
    """Delete an incident from the knowledge base."""
    try:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
        output_path = os.path.join(data_dir, "incidentspulledfromsnow.json")

        if not os.path.exists(output_path):
            return {"success": False, "message": "No incidents found"}

        # Load current incidents
        with open(output_path, "r", encoding="utf-8") as f:
            incidents = json.load(f)

        # Find and remove the incident
        original_count = len(incidents)
        incidents = [inc for inc in incidents if inc.get("incident_id") != incident_id]

        if len(incidents) == original_count:
            return {"success": False, "message": "Incident not found"}

        # Save updated incidents
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(incidents, f, ensure_ascii=False, indent=2)

        # Delete from Qdrant (best-effort, requires qdrant_client)
        try:
            client = get_qdrant_client()
            svc = IncidentIngestionService(session)
            collection_name = await svc.get_active_collection_name()
            
            if client.collection_exists(collection_name):
                scroll_result = client.scroll(
                    collection_name=collection_name,
                    limit=10000,
                    with_payload=True
                )
                
                points_to_delete = []
                for point in scroll_result[0]:
                    payload = point.payload or {}
                    metadata = payload.get("metadata", {})
                    # LangChain format: incident_id is in metadata
                    if metadata.get("incident_id") == incident_id:
                        points_to_delete.append(point.id)
                
                if points_to_delete:
                    client.delete(
                        collection_name=collection_name,
                        points_selector=points_to_delete
                    )
        except ImportError:
            logger.warning("qdrant_client not installed, skipping Qdrant deletion")
        except Exception as e:
            logger.warning(f"Failed to delete from Qdrant: {e}")
            # Continue even if Qdrant deletion fails
        
        return {"success": True, "message": "Incident deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs")
async def get_incident_logs(
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("integration.view")),
):
    """Get recent incident logs."""
    try:
        query = select(IncidentLog).order_by(desc(IncidentLog.created_at)).limit(limit)
        result = await session.execute(query)
        logs = result.scalars().all()
        
        return {
            "success": True,
            "logs": [
                {
                    "id": str(log.id),
                    "incident_id": log.incident_id,
                    "title": log.title,
                    "source": log.source,
                    "created_at": log.created_at.isoformat() + "Z" if log.created_at else None
                }
                for log in logs
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


INGEST_BATCH_SIZE = 5  # Number of incidents per batch (not chunks)


def _prepare_documents(incidents: List[dict]) -> List:
    """Convert raw incidents into LangChain Documents with proper metadata.
    
    Returns list of (incident_dict, list_of_Document) tuples.
    """
    from langchain.schema import Document
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )

    results = []
    for incident in incidents:
        description = incident.get("description", "")
        action_taken = incident.get("action_taken", "No actions recorded")
        title = incident.get("title", "No title")

        source_text = f"""
        Incident Title: {title}
        Incident Description: {description}
        Action Taken and Resolution: {action_taken}
        """

        desc_metadata = _parse_description_metadata(description)

        doc_metadata = {
            "incident_id": incident.get("incident_id", "N/A"),
            "incident_title": title,
            "impacted_application": desc_metadata.get("impactedApplication", "N/A"),
            "root_cause": desc_metadata.get("rootCause", "N/A"),
            "mitigation": desc_metadata.get("mitigation", action_taken),
            "accountable_party": desc_metadata.get("accountableParty", "N/A"),
            "source_system": "ServiceNow",
            "repeat_incident": desc_metadata.get("repeatIncident", "False"),
            "opened_at": incident.get("opened_at"),
            "updated_at": incident.get("updated_at"),
        }

        chunks = text_splitter.split_text(source_text)
        docs = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = doc_metadata.copy()
            chunk_metadata["chunk_number"] = i
            docs.append(Document(page_content=chunk, metadata=chunk_metadata))

        results.append((incident, docs))
    return results


async def ingest_incidents_to_qdrant(
    incidents: List[dict],
    session: AsyncSession = None,
    integration_id: str = None,
    batch_size: int = INGEST_BATCH_SIZE,
    progress_callback=None,
):
    """Ingest incidents into Qdrant in batches.

    Args:
        incidents: List of normalized incident dicts from ServiceNow.
        session: DB session for logging (optional).
        integration_id: Integration UUID string (optional).
        batch_size: Number of incidents per batch.
        progress_callback: async callable(batch_num, total_batches, batch_incidents)
                           called after each batch is ingested.

    Returns True on success, False on failure.
    """
    try:
        from langchain_qdrant import QdrantVectorStore
        import math

        q = _load_qdrant()
        embeddings = _load_model()
        client = get_qdrant_client()
        collection_name = "past_issues_v2"

        if not client.collection_exists(collection_name):
            client.create_collection(
                collection_name=collection_name,
                vectors_config=q["VectorParams"](size=384, distance=q["Distance"].COSINE),
            )

        prepared = _prepare_documents(incidents)
        if not prepared:
            return True

        vector_store = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=embeddings,
        )

        total_batches = math.ceil(len(prepared) / batch_size)
        total_chunks = 0

        for batch_idx in range(total_batches):
            batch_start = batch_idx * batch_size
            batch_items = prepared[batch_start : batch_start + batch_size]

            # Collect all documents for this batch
            batch_docs = []
            batch_incidents_raw = []
            for incident_dict, docs in batch_items:
                batch_docs.extend(docs)
                batch_incidents_raw.append(incident_dict)

            # Ingest batch into Qdrant (run in executor to avoid blocking the event loop)
            if batch_docs:
                import asyncio
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, vector_store.add_documents, batch_docs)
                total_chunks += len(batch_docs)

            # Log each incident in this batch
            if session:
                for inc in batch_incidents_raw:
                    log_entry = IncidentLog(
                        incident_id=inc.get("incident_id"),
                        title=inc.get("title", "Unknown"),
                        source="servicenow",
                        integration_id=integration_id,
                    )
                    session.add(log_entry)
                await session.flush()

            # Notify caller about progress
            if progress_callback:
                await progress_callback(
                    batch_idx + 1,
                    total_batches,
                    [inc.get("incident_id", "?") for inc in batch_incidents_raw],
                )

        if session:
            await session.commit()

        logger.info(f"Successfully ingested {total_chunks} chunks from {len(incidents)} incidents in {total_batches} batches")
        return True
    except Exception as e:
        logger.error(f"Error ingesting to Qdrant: {e}", exc_info=True)
        return False


# ── Upload & Validation Endpoints ────────────────────────────────

def _sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _sanitize_error_for_user(exc: Exception) -> str:
    """Convert internal exceptions to user-friendly messages.

    Prevents raw SQL, tracebacks, and internal details from leaking
    into the UI while still being helpful for debugging.
    """
    msg = str(exc)

    # ValueError messages are already user-crafted
    if isinstance(exc, ValueError):
        return msg

    # Database integrity errors (NOT NULL, unique constraint, etc.)
    if "NotNullViolationError" in msg or "not-null constraint" in msg.lower():
        return (
            "Some records are missing required fields (e.g. incident_id, title, or description). "
            "Please map your file fields to the required schema and try again."
        )
    if "UniqueViolationError" in msg or "unique constraint" in msg.lower():
        return "Duplicate records detected. Please remove duplicates and try again."
    if "IntegrityError" in msg:
        return "A data integrity issue prevented ingestion. Please check your data and try again."

    # Connection / infra errors
    if "ConnectionRefusedError" in msg or "connection refused" in msg.lower():
        return "Could not connect to the vector database. Please try again later."
    if "timeout" in msg.lower():
        return "The operation timed out. Please try again."

    # Generic fallback — log the real error, return a safe message
    logger.error(f"Unhandled ingestion error: {msg}")
    return "An unexpected error occurred during ingestion. Please try again or contact support."


@router.post("/upload")
async def upload_incident_files(
    body: FileUploadRequest,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("kb.upload")),
):
    """Accept file content, create upload session, return preview."""
    try:
        svc = IncidentIngestionService(session)
        files_data = [
            {"filename": f.filename, "size": f.size, "content": f.content}
            for f in body.files
        ]
        upload_session = await svc.create_upload_session(
            files_data, current_user["user_id"], source="upload"
        )
        return {
            "success": True,
            "session_id": str(upload_session.id),
            "status": upload_session.status,
            "incident_count": upload_session.incident_count,
            "file_metadata": upload_session.file_metadata,
            "preview": (upload_session.raw_data or [])[:10],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=_sanitize_error_for_user(e))


@router.post("/validate/{session_id}")
async def validate_upload_session(
    session_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("kb.validate")),
):
    """Run schema validation on upload session."""
    try:
        svc = IncidentIngestionService(session)
        report = await svc.validate_session(session_id)
        return {"success": True, **report.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=_sanitize_error_for_user(e))


@router.post("/validate/{session_id}/map-fields")
async def apply_field_mapping(
    session_id: str,
    body: FieldMappingRequest,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("kb.validate")),
):
    """Apply field mapping and re-validate."""
    try:
        svc = IncidentIngestionService(session)
        report = await svc.apply_field_mapping(session_id, body.mapping)
        return {"success": True, **report.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=_sanitize_error_for_user(e))


# ── Ingestion (SSE) ─────────────────────────────────────────────

@router.post("/ingest")
async def ingest_confirmed_session(
    body: IngestionConfirmRequest,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("kb.ingest")),
):
    """Confirm & ingest. Returns SSE stream with progress events."""
    async def _stream():
        yield _sse_event("progress", {"batch": 0, "totalBatches": 0, "message": "Starting ingestion..."})
        await asyncio.sleep(0)

        progress_queue: asyncio.Queue = asyncio.Queue()

        async def on_batch_progress(batch_num, total_batches, incident_ids):
            await progress_queue.put({
                "batch": batch_num,
                "totalBatches": total_batches,
                "incidents": incident_ids,
                "message": f"Batch {batch_num} of {total_batches} processed",
            })

        _SENTINEL = object()

        async def _run_ingestion():
            try:
                svc = IncidentIngestionService(session)
                version = await svc.confirm_and_ingest(
                    body.session_id,
                    current_user["user_id"],
                    notes=body.notes,
                    progress_callback=on_batch_progress,
                )
                await progress_queue.put(("done", version))
            except Exception as exc:
                await progress_queue.put(("error", exc))

        ingestion_task = asyncio.create_task(_run_ingestion())

        try:
            while True:
                item = await progress_queue.get()
                if isinstance(item, tuple):
                    kind, payload = item
                    if kind == "done":
                        yield _sse_event("complete", {
                            "success": True,
                            "version_id": str(payload.id),
                            "version_number": payload.version_number,
                            "collection_name": payload.collection_name,
                            "incident_count": payload.incident_count,
                        })
                        return
                    elif kind == "error":
                        yield _sse_event("error", {
                            "success": False,
                            "message": _sanitize_error_for_user(payload),
                        })
                        return
                else:
                    yield _sse_event("progress", item)
                    await asyncio.sleep(0)
        except Exception as e:
            ingestion_task.cancel()
            yield _sse_event("error", {
                "success": False,
                "message": _sanitize_error_for_user(e),
            })

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ── Version Management ───────────────────────────────────────────

@router.get("/versions")
async def list_versions(
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("kb.view")),
):
    """List all dataset versions (paginated)."""
    try:
        svc = IncidentIngestionService(session)
        result = await svc.get_versions(limit, offset)
        return {"success": True, **result.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_sanitize_error_for_user(e))


@router.get("/versions/active")
async def get_active_version(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("kb.view")),
):
    """Get the currently active dataset version."""
    try:
        svc = IncidentIngestionService(session)
        active = await svc.get_active_version()
        if not active:
            return {"success": True, "version": None}
        return {
            "success": True,
            "version": {
                "id": str(active.id),
                "version_number": active.version_number,
                "collection_name": active.collection_name,
                "status": active.status,
                "is_active": active.is_active,
                "incident_count": active.incident_count,
                "source": active.source,
                "activated_at": active.activated_at.isoformat() + "Z" if active.activated_at else None,
                "created_at": active.created_at.isoformat() + "Z" if active.created_at else None,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=_sanitize_error_for_user(e))


@router.get("/versions/{version_id}")
async def get_version_detail(
    version_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("kb.view")),
):
    """Get a single version's details."""
    try:
        svc = IncidentIngestionService(session)
        version = await svc.get_version_by_id(version_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        return {
            "success": True,
            "version": {
                "id": str(version.id),
                "version_number": version.version_number,
                "collection_name": version.collection_name,
                "status": version.status,
                "is_active": version.is_active,
                "incident_count": version.incident_count,
                "file_metadata": version.file_metadata,
                "source": version.source,
                "snapshot_name": version.snapshot_name,
                "notes": version.notes,
                "activated_at": version.activated_at.isoformat() + "Z" if version.activated_at else None,
                "created_at": version.created_at.isoformat() + "Z" if version.created_at else None,
                "updated_at": version.updated_at.isoformat() + "Z" if version.updated_at else None,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_sanitize_error_for_user(e))


@router.post("/versions/{version_id}/rollback")
async def rollback_version(
    version_id: str,
    body: Optional[RollbackVersionRequest] = None,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("kb.rollback")),
):
    """Rollback to a prior version (activates it)."""
    try:
        notes = body.notes if body else None
        svc = IncidentIngestionService(session)
        version = await svc.rollback_to_version(version_id, current_user["user_id"], notes)
        return {
            "success": True,
            "message": f"Rolled back to version {version.version_number}",
            "version_id": str(version.id),
        }
    except ValueError as e:
        logger.warning(f"Rollback to version {version_id} failed (ValueError): {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Rollback to version {version_id} failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=_sanitize_error_for_user(e))


@router.delete("/versions/{version_id}")
async def delete_version(
    version_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("kb.version_manage")),
):
    """Delete an inactive version and its Qdrant collection."""
    try:
        svc = IncidentIngestionService(session)
        await svc.delete_version(version_id)
        return {"success": True, "message": "Version deleted"}
    except ValueError as e:
        logger.warning(f"Delete version {version_id} failed (ValueError): {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Delete version {version_id} failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=_sanitize_error_for_user(e))
