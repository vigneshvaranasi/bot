"""Service layer for incident data ingestion and version management."""

import csv
import io
import json
import logging
import math
import uuid
from datetime import datetime, UTC
from typing import List, Optional, Dict, Any

from sqlalchemy import func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.api.db.models import User
from src.api.db.models.incident_upload_session import IncidentUploadSession
from src.api.db.models.incident_dataset_version import IncidentDatasetVersion
from src.api.db.models.incident_log import IncidentLog
from src.api.schemas.knowledge_base_schemas import (
    REQUIRED_FIELDS,
    ValidationErrorItem,
    ValidationReport,
    DatasetVersionResponse,
    DatasetVersionListResponse,
)

logger = logging.getLogger(__name__)

INGEST_BATCH_SIZE = 5
COLLECTION_WINDOW_SIZE = 7


class IncidentIngestionService:
    """Service for incident upload, validation, ingestion, and version management."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Upload & Parsing ─────────────────────────────────────────────

    async def create_upload_session(
        self,
        files_data: List[Dict[str, Any]],
        user_id: str,
        source: str = "upload",
    ) -> IncidentUploadSession:
        """Parse file content and create an upload session with raw records."""
        if not user_id:
            raise ValueError("user_id is required to create an upload session")
        all_records: List[Dict[str, Any]] = []
        file_meta: List[Dict[str, Any]] = []

        for file_info in files_data:
            filename = file_info["filename"]
            content = file_info["content"]
            size = file_info.get("size", len(content))

            records = self._parse_file_content(filename, content)
            # Tag each record with its source file for per-file validation/mapping
            for record in records:
                record["_source_file"] = filename
            file_meta.append({
                "filename": filename,
                "size": size,
                "content_type": "application/json" if filename.endswith(".json") else "text/csv",
                "row_count": len(records),
            })
            all_records.extend(records)

        session_obj = IncidentUploadSession(
            status="pending",
            uploaded_by=uuid.UUID(user_id),
            source=source,
            file_metadata=file_meta,
            raw_data=all_records,
            incident_count=len(all_records),
        )
        self.session.add(session_obj)
        await self.session.commit()
        await self.session.refresh(session_obj)
        return session_obj

    def _parse_file_content(self, filename: str, content: str) -> List[Dict[str, Any]]:
        """Parse JSON or CSV content into a list of record dicts."""
        if filename.lower().endswith(".json"):
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
            raise ValueError(f"JSON file {filename} must contain an array or object")

        if filename.lower().endswith(".csv"):
            reader = csv.DictReader(io.StringIO(content))
            return [dict(row) for row in reader]

        raise ValueError(f"Unsupported file type: {filename}. Expected .json or .csv")

    # ── Validation ───────────────────────────────────────────────────

    async def validate_session(self, session_id: str) -> ValidationReport:
        """Validate raw records against the expected incident schema."""
        upload = await self._get_upload_session(session_id)

        records = upload.raw_data or []
        errors = self._validate_records(records)
        valid_count = len(records) - len({(e.row, e.file) for e in errors})

        # Compute per-file field lists for the mapping UI
        file_fields: Dict[str, set] = {}
        for record in records:
            src = record.get("_source_file", "unknown")
            if src not in file_fields:
                file_fields[src] = set()
            file_fields[src].update(k for k in record.keys() if k != "_source_file")
        file_fields_sorted = {k: sorted(v) for k, v in file_fields.items()}

        # Strip _source_file from preview records
        preview = []
        for r in records[:10]:
            preview.append({k: v for k, v in r.items() if k != "_source_file"})

        report = ValidationReport(
            session_id=str(upload.id),
            status="validated" if not errors else "has_errors",
            total_records=len(records),
            valid_count=valid_count,
            error_count=len(errors),
            errors=[e.model_dump() for e in errors],
            preview=preview,
            file_fields=file_fields_sorted,
        )

        upload.validation_report = report.model_dump()
        upload.status = "validated"
        await self.session.commit()
        return report

    def _validate_records(
        self, records: List[Dict[str, Any]]
    ) -> List[ValidationErrorItem]:
        """Check required fields and basic type validation."""
        errors: List[ValidationErrorItem] = []
        # Track per-file row numbers
        file_row_counters: Dict[str, int] = {}
        for record in records:
            source_file = record.get("_source_file", "unknown")
            file_row_counters[source_file] = file_row_counters.get(source_file, 0) + 1
            row_num = file_row_counters[source_file]

            for field in REQUIRED_FIELDS:
                val = record.get(field)
                if val is None or (isinstance(val, str) and not val.strip()):
                    errors.append(ValidationErrorItem(
                        file=source_file,
                        row=row_num,
                        field=field,
                        message=f"Required field '{field}' is missing or empty",
                        value=str(val) if val is not None else None,
                    ))
        return errors

    # ── Field Mapping ────────────────────────────────────────────────

    async def apply_field_mapping(
        self, session_id: str, mapping: Dict[str, str]
    ) -> ValidationReport:
        """Apply a field mapping to raw records, re-validate, and return updated report."""
        upload = await self._get_upload_session(session_id)
        records = upload.raw_data or []

        mapped_records = []
        for record in records:
            new_record: Dict[str, Any] = {}
            for key, value in record.items():
                if key == "_source_file":
                    new_record[key] = value  # preserve source file tag
                    continue
                target = mapping.get(key, key)
                new_record[target] = value
            mapped_records.append(new_record)

        upload.raw_data = mapped_records
        upload.field_mapping = mapping
        upload.status = "mapping"
        await self.session.commit()

        return await self.validate_session(session_id)

    # ── Normalization ────────────────────────────────────────────────

    def _normalize_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Trim whitespace, standardize dates, unify booleans, deduplicate."""
        seen_ids = set()
        normalized = []

        for record in records:
            cleaned: Dict[str, Any] = {}
            for key, value in record.items():
                if key == "_source_file":
                    continue  # strip internal tagging field
                if isinstance(value, str):
                    value = value.strip()
                cleaned[key] = value

            # Standardize boolean-like fields
            for bool_field in ("repeat_incident",):
                val = cleaned.get(bool_field)
                if isinstance(val, str):
                    cleaned[bool_field] = val.lower() in ("true", "yes", "1")

            # Standardize dates to ISO 8601
            for date_field in ("opened_at", "updated_at"):
                val = cleaned.get(date_field)
                if isinstance(val, str) and val:
                    try:
                        parsed_dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                        cleaned[date_field] = parsed_dt.isoformat()
                    except (ValueError, TypeError):
                        pass  # Keep original if unparseable

            # Deduplicate by incident_id
            inc_id = cleaned.get("incident_id")
            if inc_id and inc_id in seen_ids:
                continue
            if inc_id:
                seen_ids.add(inc_id)

            normalized.append(cleaned)

        return normalized

    # ── Ingestion ────────────────────────────────────────────────────

    async def confirm_and_ingest(
        self,
        session_id: str,
        user_id: str,
        notes: Optional[str] = None,
        progress_callback=None,
    ) -> IncidentDatasetVersion:
        """Normalize, create Qdrant collection, copy existing data, embed/ingest new records, create version record."""
        if not user_id:
            raise ValueError("user_id is required for ingestion")
        upload = await self._get_upload_session(session_id)
        records = upload.raw_data or []

        upload.status = "ingesting"
        await self.session.commit()

        # Normalize
        normalized = self._normalize_records(records)

        # Filter out records still missing required fields (e.g. user skipped mapping)
        valid_records = [
            r for r in normalized
            if all(
                r.get(f) and str(r.get(f, "")).strip()
                for f in REQUIRED_FIELDS
            )
        ]
        skipped = len(normalized) - len(valid_records)
        if skipped:
            logger.info(
                f"Filtered out {skipped} record(s) missing required fields "
                f"({', '.join(REQUIRED_FIELDS)})"
            )
        if not valid_records:
            upload.status = "failed"
            await self.session.commit()
            raise ValueError(
                "No valid records to ingest. All records are missing required fields "
                "(incident_id, title, or description). Please map the fields and try again."
            )

        normalized = valid_records
        upload.normalized_data = normalized
        upload.incident_count = len(normalized)
        await self.session.commit()

        # Determine next version number
        max_ver = await self.session.execute(
            select(func.max(IncidentDatasetVersion.version_number))
        )
        current_max = max_ver.scalar() or 0
        version_number = current_max + 1

        # Generate collection name
        short_id = uuid.uuid4().hex[:8]
        collection_name = f"incidents_v_{version_number}_{short_id}"

        # Determine source collection to copy existing data from.
        # Priority: active version > latest non-failed version > legacy collection
        active_version = await self.get_active_version()
        source_collection = None
        if active_version:
            source_collection = active_version.collection_name
        else:
            # No active version — try the latest non-failed version
            latest_q = await self.session.execute(
                select(IncidentDatasetVersion)
                .where(IncidentDatasetVersion.status.notin_(["failed", "archived"]))
                .order_by(desc(IncidentDatasetVersion.created_at))
                .limit(1)
            )
            latest_version = latest_q.scalars().first()
            if latest_version:
                source_collection = latest_version.collection_name
            else:
                # Fall back to legacy collection (pre-versioning ServiceNow data)
                from src.copilot.config import QDRANT_COLLECTION_NAME
                source_collection = QDRANT_COLLECTION_NAME

        # Create version record (incident_count updated after copy + ingest)
        version = IncidentDatasetVersion(
            version_number=version_number,
            collection_name=collection_name,
            status="ingesting",
            is_active=False,
            incident_count=len(normalized),
            file_metadata=upload.file_metadata,
            source=upload.source,
            upload_session_id=upload.id,
            uploaded_by=uuid.UUID(user_id),
            notes=notes,
        )
        self.session.add(version)
        await self.session.commit()
        await self.session.refresh(version)

        try:
            from src.api.routers.knowledge_base import _load_qdrant, get_qdrant_client
            import asyncio

            q = _load_qdrant()
            client = get_qdrant_client()

            # Create the new collection
            client.create_collection(
                collection_name=collection_name,
                vectors_config=q["VectorParams"](size=384, distance=q["Distance"].COSINE),
            )

            # Copy existing data from source collection, excluding incidents
            # that are being re-ingested (so updated versions replace old ones)
            incoming_ids = {r.get("incident_id") for r in normalized if r.get("incident_id")}
            existing_incident_count = 0
            if source_collection and client.collection_exists(source_collection):
                if progress_callback:
                    await progress_callback(0, 0, ["Copying existing data from active version..."])
                existing_incident_count = await self._copy_collection_points(
                    client, source_collection, collection_name,
                    exclude_incident_ids=incoming_ids,
                )
                logger.info(
                    f"Copied {existing_incident_count} existing incidents from "
                    f"'{source_collection}' to '{collection_name}'"
                )

            # Ingest new records into the (now populated) collection
            success = await self._ingest_to_collection(
                collection_name, normalized, INGEST_BATCH_SIZE, progress_callback,
                integration_id=None,
            )
            if not success:
                version.status = "failed"
                upload.status = "failed"
                await self.session.commit()
                raise RuntimeError(
                    "Ingestion failed. Please check your data and try again."
                )

            # Update total incident count (existing + new)
            version.incident_count = existing_incident_count + len(normalized)
            upload.status = "completed"

            # Auto-activate: deactivate previous active version, make this one active
            # Atomically deactivate all active versions
            await self.session.execute(
                update(IncidentDatasetVersion)
                .where(IncidentDatasetVersion.is_active == True)
                .where(IncidentDatasetVersion.id != version.id)
                .values(is_active=False, status="inactive", updated_at=datetime.now(UTC).replace(tzinfo=None))
            )

            version.is_active = True
            version.status = "active"
            version.activated_at = datetime.now(UTC).replace(tzinfo=None)
            await self.session.commit()
            await self.session.refresh(version)

            logger.info(
                f"Version {version.version_number} auto-activated with "
                f"{version.incident_count} total incidents "
                f"({existing_incident_count} existing + {len(normalized)} new)"
            )

            # Invalidate copilot cache so it uses the new collection
            _invalidate_copilot_cache()

            # Enforce sliding window
            await self._enforce_collection_window()

            return version

        except Exception as e:
            # Rollback any broken transaction state before updating status
            try:
                await self.session.rollback()
                version.status = "failed"
                upload.status = "failed"
                await self.session.commit()
            except Exception as rollback_err:
                logger.error(f"Failed to mark version/upload as failed: {rollback_err}")
            raise

    async def _copy_collection_points(
        self,
        client,
        source_collection: str,
        target_collection: str,
        exclude_incident_ids: set = None,
    ) -> int:
        """Copy vector points from source to target Qdrant collection.

        Skips points whose incident_id is in *exclude_incident_ids* so that
        updated versions of those incidents can be re-ingested without duplicates.

        Returns the number of unique incident_ids copied (for incident_count tracking).
        """
        import asyncio
        from qdrant_client.models import PointStruct

        exclude_incident_ids = exclude_incident_ids or set()
        loop = asyncio.get_event_loop()
        offset = None
        seen_incident_ids: set = set()
        scroll_batch = 100

        while True:
            points, next_offset = await loop.run_in_executor(
                None,
                lambda off=offset: client.scroll(
                    collection_name=source_collection,
                    limit=scroll_batch,
                    offset=off,
                    with_payload=True,
                    with_vectors=True,
                ),
            )

            if not points:
                break

            # Filter out points belonging to incidents that will be re-ingested
            filtered_points = []
            for p in points:
                metadata = (p.payload or {}).get("metadata", {})
                inc_id = metadata.get("incident_id")
                if inc_id and inc_id in exclude_incident_ids:
                    continue
                filtered_points.append(p)
                if inc_id:
                    seen_incident_ids.add(inc_id)

            if filtered_points:
                point_structs = [
                    PointStruct(id=p.id, vector=p.vector, payload=p.payload)
                    for p in filtered_points
                ]
                await loop.run_in_executor(
                    None,
                    lambda ps=point_structs: client.upsert(
                        collection_name=target_collection, points=ps
                    ),
                )

            if next_offset is None:
                break
            offset = next_offset

        return len(seen_incident_ids)

    async def _ingest_to_collection(
        self,
        collection_name: str,
        records: List[Dict[str, Any]],
        batch_size: int,
        progress_callback=None,
        integration_id: Optional[str] = None,
    ) -> bool:
        """Ingest records into a named Qdrant collection. Adapted from knowledge_base.py."""
        try:
            from langchain_qdrant import QdrantVectorStore
            from src.api.routers.knowledge_base import (
                _load_qdrant, _load_model, get_qdrant_client, _prepare_documents,
            )

            q = _load_qdrant()
            embeddings = _load_model()
            client = get_qdrant_client()

            # Create collection if it doesn't exist (e.g. called from ServiceNow sync)
            if not client.collection_exists(collection_name):
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=q["VectorParams"](size=384, distance=q["Distance"].COSINE),
                )

            prepared = _prepare_documents(records)
            if not prepared:
                return True

            vector_store = QdrantVectorStore(
                client=client,
                collection_name=collection_name,
                embedding=embeddings,
            )

            total_batches = math.ceil(len(prepared) / batch_size)
            import asyncio

            for batch_idx in range(total_batches):
                batch_start = batch_idx * batch_size
                batch_items = prepared[batch_start:batch_start + batch_size]

                batch_docs = []
                batch_incidents_raw = []
                for incident_dict, docs in batch_items:
                    batch_docs.extend(docs)
                    batch_incidents_raw.append(incident_dict)

                if batch_docs:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, vector_store.add_documents, batch_docs)

                # Log incidents
                for inc in batch_incidents_raw:
                    log_entry = IncidentLog(
                        incident_id=inc.get("incident_id"),
                        title=inc.get("title", "Unknown"),
                        source="upload",
                        integration_id=integration_id,
                    )
                    self.session.add(log_entry)
                await self.session.flush()

                if progress_callback:
                    await progress_callback(
                        batch_idx + 1,
                        total_batches,
                        [inc.get("incident_id", "?") for inc in batch_incidents_raw],
                    )

            await self.session.commit()
            logger.info(
                f"Ingested {len(records)} incidents into collection '{collection_name}' "
                f"in {total_batches} batches"
            )
            return True

        except Exception as e:
            logger.error(f"Error ingesting to collection {collection_name}: {e}")
            import traceback
            traceback.print_exc()
            # Rollback so the session is usable for status updates by the caller
            await self.session.rollback()
            return False

    # ── Version Management ───────────────────────────────────────────

    async def get_versions(
        self, limit: int = 20, offset: int = 0
    ) -> DatasetVersionListResponse:
        """Get paginated list of dataset versions with uploader email."""
        count_q = select(func.count()).select_from(IncidentDatasetVersion)
        total = (await self.session.execute(count_q)).scalar() or 0

        query = (
            select(IncidentDatasetVersion, User.email)
            .join(User, IncidentDatasetVersion.uploaded_by == User.id, isouter=True)
            .order_by(desc(IncidentDatasetVersion.created_at))
            .offset(offset)
            .limit(limit)
        )
        rows = (await self.session.execute(query)).all()

        active_id = None
        versions = []
        for version, email in rows:
            if version.is_active:
                active_id = str(version.id)
            versions.append(DatasetVersionResponse(
                id=str(version.id),
                version_number=version.version_number,
                collection_name=version.collection_name,
                status=version.status,
                is_active=version.is_active,
                incident_count=version.incident_count,
                file_metadata=version.file_metadata,
                source=version.source,
                snapshot_name=version.snapshot_name,
                upload_session_id=str(version.upload_session_id) if version.upload_session_id else None,
                uploader_email=email,
                notes=version.notes,
                activated_at=version.activated_at.isoformat() + "Z" if version.activated_at else None,
                created_at=version.created_at.isoformat() + "Z" if version.created_at else "",
                updated_at=version.updated_at.isoformat() + "Z" if version.updated_at else "",
            ))

        return DatasetVersionListResponse(
            versions=versions, total=total, active_version_id=active_id
        )

    async def get_active_version(self) -> Optional[IncidentDatasetVersion]:
        """Return the version where is_active=True."""
        result = await self.session.execute(
            select(IncidentDatasetVersion).where(IncidentDatasetVersion.is_active == True)
        )
        return result.scalars().first()

    async def get_version_by_id(self, version_id: str) -> Optional[IncidentDatasetVersion]:
        result = await self.session.execute(
            select(IncidentDatasetVersion).where(
                IncidentDatasetVersion.id == uuid.UUID(version_id)
            )
        )
        return result.scalars().first()

    async def activate_version(
        self, version_id: str, user_id: str, notes: Optional[str] = None
    ) -> IncidentDatasetVersion:
        """Deactivate current active version and activate the target."""
        target = await self.get_version_by_id(version_id)
        if not target:
            raise ValueError("Version not found")
        if target.status == "archived":
            raise ValueError("Cannot activate an archived version (collection deleted)")
        if target.status == "failed":
            raise ValueError("Cannot activate a failed version")

        logger.info(
            f"Activating version {target.version_number} (id={version_id}, "
            f"current_status={target.status}, is_active={target.is_active})"
        )

        # Atomically deactivate all active versions in one query
        await self.session.execute(
            update(IncidentDatasetVersion)
            .where(IncidentDatasetVersion.is_active == True)
            .where(IncidentDatasetVersion.id != uuid.UUID(version_id))
            .values(is_active=False, status="inactive", updated_at=datetime.now(UTC).replace(tzinfo=None))
        )

        # Now safely activate target
        target.is_active = True
        target.status = "active"
        target.activated_at = datetime.now(UTC).replace(tzinfo=None)
        if notes:
            target.notes = notes

        # Single flush with all changes visible
        await self.session.flush()

        logger.info(f"Version {target.version_number} activated successfully")

        # Invalidate copilot cache so it picks up the new active collection
        _invalidate_copilot_cache()

        return target

    async def rollback_to_version(
        self, version_id: str, user_id: str, notes: Optional[str] = None
    ) -> IncidentDatasetVersion:
        """Rollback = activate a prior version (same logic, distinct for audit)."""
        return await self.activate_version(version_id, user_id, notes)

    async def delete_version(self, version_id: str) -> bool:
        """Delete an inactive version and its Qdrant collection."""
        version = await self.get_version_by_id(version_id)
        if not version:
            raise ValueError("Version not found")
        if version.is_active:
            raise ValueError("Cannot delete the active version")

        # Delete Qdrant collection if it exists
        if version.status != "archived":
            try:
                from src.api.routers.knowledge_base import get_qdrant_client
                client = get_qdrant_client()
                if client.collection_exists(version.collection_name):
                    client.delete_collection(version.collection_name)
            except Exception as e:
                logger.warning(f"Failed to delete Qdrant collection {version.collection_name}: {e}")

        await self.session.delete(version)
        await self.session.flush()
        return True

    async def get_active_collection_name(self) -> str:
        """Return the active collection name, or fallback to past_issues_v2."""
        active = await self.get_active_version()
        if active:
            return active.collection_name
        from src.copilot.config import QDRANT_COLLECTION_NAME
        return QDRANT_COLLECTION_NAME

    # ── Sliding Window ───────────────────────────────────────────────

    async def _enforce_collection_window(self) -> None:
        """Keep only the latest COLLECTION_WINDOW_SIZE live collections; archive the rest."""
        result = await self.session.execute(
            select(IncidentDatasetVersion)
            .where(IncidentDatasetVersion.status.notin_(["archived", "failed"]))
            .order_by(desc(IncidentDatasetVersion.created_at))
        )
        all_versions = result.scalars().all()

        # Skip active + latest N inactive
        keep_count = 0
        to_archive: List[IncidentDatasetVersion] = []

        for v in all_versions:
            if v.is_active:
                continue  # Always keep active
            keep_count += 1
            if keep_count > COLLECTION_WINDOW_SIZE:
                to_archive.append(v)

        if not to_archive:
            return

        try:
            from src.api.routers.knowledge_base import get_qdrant_client
            client = get_qdrant_client()
        except Exception as e:
            logger.warning(f"Cannot enforce collection window – Qdrant unavailable: {e}")
            return

        for v in to_archive:
            try:
                snapshot_name = f"v{v.version_number}_{v.created_at.strftime('%Y-%m-%d')}_{v.source}"
                if client.collection_exists(v.collection_name):
                    client.create_snapshot(collection_name=v.collection_name)
                    client.delete_collection(v.collection_name)
                v.snapshot_name = snapshot_name
                v.status = "archived"
                logger.info(f"Archived version {v.version_number} (collection={v.collection_name})")
            except Exception as e:
                logger.warning(f"Failed to archive version {v.version_number}: {e}")

        await self.session.commit()

    # ── Helpers ───────────────────────────────────────────────────────

    async def _get_upload_session(self, session_id: str) -> IncidentUploadSession:
        try:
            session_uuid = uuid.UUID(session_id)
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid session ID: {session_id}")
        result = await self.session.execute(
            select(IncidentUploadSession).where(
                IncidentUploadSession.id == session_uuid
            )
        )
        upload = result.scalars().first()
        if not upload:
            raise ValueError(f"Upload session {session_id} not found")
        return upload


def _invalidate_copilot_cache():
    """Reset the cached vector store and retriever in the copilot tools module."""
    try:
        import src.copilot.tools._base as base_mod
        base_mod._vector_store = None
        base_mod._retriever = None
        logger.info("Invalidated copilot vector store cache")
    except Exception as e:
        logger.warning(f"Failed to invalidate copilot cache: {e}")
