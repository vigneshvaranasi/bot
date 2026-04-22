import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.api.auth.dependencies import require_permission
from src.api.db.models.integration import Integration
from src.api.db.session import get_session
from src.api.schemas.integration_schema import (
    IntegrationBase,
    IntegrationCreate,
)
from src.api.services.incident_ingestion_service import IncidentIngestionService
from src.automation.registry import get_connector, resolve_connector_type

logger = logging.getLogger(__name__)
router = APIRouter()

# Sensitive fields that should never be returned in API responses
SENSITIVE_CONFIG_FIELDS = {"password", "api_key", "secret", "token", "api_token", "access_token", "refresh_token"}
MASK_PLACEHOLDER = "********"

_sync_locks: dict[str, asyncio.Lock] = {}


def _get_sync_lock(integration_id: str) -> asyncio.Lock:
    if integration_id not in _sync_locks:
        _sync_locks[integration_id] = asyncio.Lock()
    return _sync_locks[integration_id]

def _derive_connector_type_for_save(
    incoming: str | None, service_name: str | None
) -> str:
    """Resolve a connector slug at create/update time.

    Tries, in order: the client-supplied slug, a prefix-match on service_name,
    then falls back to the lowercased service_name. The row is saved either
    way; a slug not in the registry simply fails at sync time.
    """
    try:
        return resolve_connector_type(incoming, service_name)
    except ValueError:
        return (incoming or service_name or "").strip().lower() or "unknown"

def split_public_and_secret_config(config: dict | None) -> tuple[dict | None, list[str]]:
    """Split config into public fields and configured secret field names."""
    if config is None:
        return None, []
    public_config = {}
    configured_secrets: list[str] = []
    for key, value in config.items():
        if is_sensitive_config_key(key):
            if value not in (None, ""):
                configured_secrets.append(key)
            continue
        public_config[key] = value
    return public_config, configured_secrets


def mask_sensitive_config(config: dict | None) -> dict | None:
    """Return a copy of *config* with sensitive values replaced by a placeholder.

    Used for logging and any response shape that prefers a flat dict over the
    split public/secret form produced by :func:`split_public_and_secret_config`.
    """
    if config is None:
        return None
    masked: dict = {}
    for key, value in config.items():
        if is_sensitive_config_key(key) and value not in (None, ""):
            masked[key] = MASK_PLACEHOLDER
        else:
            masked[key] = value
    return masked


def mask_integration_response(integration) -> dict:
    """Create a masked version of an integration for API responses."""
    public_config, configured_secrets = split_public_and_secret_config(integration.config)
    return {
        "id": str(integration.id),
        "service_name": integration.service_name,
        "connector_type": integration.connector_type,
        "auth_type": integration.auth_type,
        "config": public_config,
        "configured_secrets": configured_secrets,
        "is_active": integration.is_active,
        "last_synced_at": integration.last_synced_at.isoformat() + "Z" if integration.last_synced_at else None,
        "last_sync_status": integration.last_sync_status,
        "last_sync_error": integration.last_sync_error,
        "updated_at": integration.updated_at.isoformat() + "Z" if integration.updated_at else None,
        "user_id": str(integration.user_id) if integration.user_id else None,
    }


def is_sensitive_config_key(key: str) -> bool:
    """Return True when key likely contains a secret value."""
    lowered = key.lower()
    return (
        lowered in SENSITIVE_CONFIG_FIELDS
        or "password" in lowered
        or "secret" in lowered
        or "token" in lowered
    )


def _is_mask_placeholder(value) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return len(stripped) >= len(MASK_PLACEHOLDER) and set(stripped) == {"*"}


def merge_integration_config(
    existing_config: dict | None,
    incoming_config: dict | None,
    *,
    auth_type_changed: bool,
) -> dict:
    """Merge partial config updates while preserving existing secrets by omission."""
    incoming = incoming_config or {}
    for key, value in incoming.items():
        if is_sensitive_config_key(key) and _is_mask_placeholder(value):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid value for sensitive field '{key}'. "
                    "Send a real value to update the secret."
                ),
            )

    if auth_type_changed:
        return incoming.copy()

    merged = (existing_config or {}).copy()
    merged.update(incoming)
    return merged


# GET All Integrations
@router.get("/all")
async def get_integrations(
    session: AsyncSession = Depends(get_session), current_user=Depends(require_permission("integration.view"))
):
    try:
        result = await session.execute(select(Integration))
        integrations = result.scalars().all()
        masked_integrations = [mask_integration_response(i) for i in integrations]
        return {"success": True, "integrations": masked_integrations}
    except Exception as e:
        return {
            "success": False,
            "message": f"Error occurred while retrieving integrations: {e}",
        }
    

# GET Integration by ID
@router.get("/id/{integration_id}")
async def get_integration(
    integration_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("integration.view")),
):
    try:
        result = await session.execute(
            select(Integration).where(Integration.id == integration_id)
        )
        integration = result.scalars().first()
        if not integration:
            return {"success": False, "message": "Integration not found"}
        return {"success": True, "integration": mask_integration_response(integration)}
    except Exception as e:
        return {
            "success": False,
            "message": f"Error occurred while retrieving integration of ID {integration_id}: {e}",
        }
    

# POST Create Integration
@router.post("/create")
async def create_integration(
    integration: IntegrationCreate,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("integration.create")),
):
    try:
        user_id = current_user["user_id"] if current_user else None
        if user_id is None:
            return {"success": False, "message": "User not authenticated"}
        connector_type = _derive_connector_type_for_save(
            integration.connector_type, integration.service_name
        )
        new_integration = Integration(
            service_name=integration.service_name,
            connector_type=connector_type,
            auth_type=integration.auth_type,
            config=integration.config,
            is_active=integration.is_active,
            user_id=user_id,
        )

        session.add(new_integration)
        await session.commit()
        await session.refresh(new_integration)
        return {"success": True, "integration": mask_integration_response(new_integration)}
    except Exception as e:
        await session.rollback()
        return {
            "success": False,
            "message": f"Error occurred while creating integration: {e}",
        }
    

# DELETE Integration by ID
@router.delete("/delete/{integration_id}")
async def delete_integration(
    integration_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("integration.delete")),
):
    try:
        result = await session.execute(
            select(Integration).where(Integration.id == integration_id)
        )
        integration = result.scalars().first()
        if not integration:
            return {"success": False, "message": "Integration not found"}
        await session.delete(integration)
        await session.commit()
        return {"success": True, "message": "Integration deleted successfully"}
    except Exception as e:
        await session.rollback()
        return {
            "success": False,
            "message": f"Error occurred while deleting integration of ID {integration_id}: {e}",
        }
    

# PUT Update Integration by ID
@router.put("/update/{integration_id}")
async def update_integration(
    integration_id: str,
    integration_data: IntegrationBase,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("integration.edit")),
):
    try:
        result = await session.execute(
            select(Integration).where(Integration.id == integration_id)
        )
        integration = result.scalars().first()
        if not integration:
            return {"success": False, "message": "Integration not found"}

        new_connector_type = _derive_connector_type_for_save(
            integration_data.connector_type, integration_data.service_name
        )
        connector_changed = integration.connector_type != new_connector_type
        auth_type_changed = integration.auth_type != integration_data.auth_type
        integration.service_name = integration_data.service_name
        integration.connector_type = new_connector_type
        integration.auth_type = integration_data.auth_type
        integration.config = merge_integration_config(
            integration.config,
            integration_data.config,
            auth_type_changed=auth_type_changed or connector_changed,
        )
        integration.is_active = integration_data.is_active

        session.add(integration)
        await session.commit()
        await session.refresh(integration)

        return {"success": True, "integration": mask_integration_response(integration)}
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        return {
            "success": False,
            "message": f"Error occurred while updating integration of ID {integration_id}: {e}",
        }
    

def _sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# POST Sync Integration by ID  (SSE stream)
@router.post("/sync/{integration_id}")
async def sync_integration(
    integration_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("integration.sync")),
):
    """Sync an integration by fetching incidents from the external source.

    Returns an SSE stream with progress events:
      event: progress   - { batch, totalBatches, message, ... }
      event: complete   - { success, integration, stats }
      event: error      - { success: false, message }
    """
    result = await session.execute(
        select(Integration).where(Integration.id == integration_id)
    )
    integration = result.scalars().first()
    if not integration:
        return StreamingResponse(
            iter([_sse_event("error", {"success": False, "message": "Integration not found"})]),
            media_type="text/event-stream",
        )

    try:
        connector_type = resolve_connector_type(
            integration.connector_type, integration.service_name
        )
    except ValueError as e:
        return StreamingResponse(
            iter([_sse_event("error", {"success": False, "message": str(e)})]),
            media_type="text/event-stream",
        )

    config = integration.config or {}
    auth_type = integration.auth_type or "basic_auth"
    last_synced = config.get("lastSynced") or config.get("last_synced") or "1970-01-01 00:00:00"
    svc_for_active = IncidentIngestionService(session)
    active_version = await svc_for_active.get_active_version()
    if active_version is None or (active_version.source or "").lower() != connector_type.lower():
        logger.info(
            "Forcing full sync for integration %s: active version source=%s, connector=%s",
            integration_id,
            active_version.source if active_version else None,
            connector_type,
        )
        last_synced = "1970-01-01 00:00:00"

    try:
        connector = get_connector(connector_type, {**config, "auth_type": auth_type})
    except (ValueError, PermissionError) as e:
        return StreamingResponse(
            iter([_sse_event("error", {"success": False, "message": str(e)})]),
            media_type="text/event-stream",
        )

    lock = _get_sync_lock(integration_id)

    async def _stream():
        if lock.locked():
            yield _sse_event("error", {
                "success": False,
                "message": "A sync is already in progress for this integration. Please wait.",
            })
            return

        async with lock:
            service_label = integration.service_name or connector_type.title()
            yield _sse_event("progress", {
                "batch": 0,
                "totalBatches": 0,
                "message": f"Fetching incidents from {service_label}...",
            })
            await asyncio.sleep(0)

            try:
                normalized = await asyncio.to_thread(
                    connector.fetch_and_normalize, last_synced
                )
            except Exception as e:
                logger.error("Connector fetch failed for %s: %s", integration_id, e)
                integration.last_sync_status = "error"
                integration.last_sync_error = str(e)[:500]
                await session.commit()
                yield _sse_event("error", {"success": False, "message": str(e)})
                return

            if not normalized:
                now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                new_last_synced = now_utc.strftime("%Y-%m-%d %H:%M:%S")
                integration.last_synced_at = now_utc
                integration.last_sync_status = "success"
                integration.last_sync_error = None
                integration.updated_at = now_utc
                # Create a new dict to ensure SQLAlchemy detects the change
                integration.config = {**config, "lastSynced": new_last_synced}
                session.add(integration)
                await session.commit()
                await session.refresh(integration)

                yield _sse_event("complete", {
                    "success": True,
                    "integration": mask_integration_response(integration),
                    "stats": {"added": 0, "total": 0, "last_synced": new_last_synced},
                })
                return

            import math
            batch_size = 5
            total_batches = math.ceil(len(normalized) / batch_size)

            yield _sse_event("progress", {
                "batch": 0,
                "totalBatches": total_batches,
                "totalIncidents": len(normalized),
                "message": f"Ingesting {len(normalized)} incidents in {total_batches} batch(es)...",
            })
            await asyncio.sleep(0)

            # Use an asyncio.Queue so progress events stream in real-time
            progress_queue: asyncio.Queue = asyncio.Queue()

            async def on_batch_progress(batch_num, total_batches, incident_ids, message=None):
                event: dict = {
                    "incidents": incident_ids,
                    "totalIncidents": len(normalized),
                }
                if batch_num is not None:
                    event["batch"] = batch_num
                if total_batches is not None:
                    event["totalBatches"] = total_batches
                if message is not None:
                    event["message"] = message
                elif batch_num is not None and total_batches is not None:
                    event["message"] = (
                        f"Batch {batch_num} of {total_batches} processed "
                        f"({len(incident_ids)} incidents)"
                    )
                else:
                    event["message"] = "Processing..."
                await progress_queue.put(event)

            async def _run_ingestion():
                try:
                    svc = IncidentIngestionService(session)
                    user_id = current_user["user_id"] if current_user else None

                    upload_session = await svc.create_upload_session(
                        files_data=[{
                            "filename": f"{connector_type}_sync.json",
                            "size": len(json.dumps(normalized)),
                            "content": json.dumps(normalized),
                        }],
                        user_id=user_id,
                        source=connector_type,
                    )

                    version = await svc.confirm_and_ingest(
                        str(upload_session.id),
                        user_id,
                        notes=f"{service_label} sync - {len(normalized)} incidents",
                        progress_callback=on_batch_progress,
                        source=connector_type,
                        integration_id=integration_id,
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
                            break
                        elif kind == "error":
                            logger.error("Ingestion error: %s", payload)
                            yield _sse_event("error", {"success": False, "message": f"Ingestion error: {payload}"})
                            return
                    else:
                        yield _sse_event("progress", item)
                        await asyncio.sleep(0)
            except Exception as e:
                ingestion_task.cancel()
                logger.error("Ingestion error: %s", e)
                yield _sse_event("error", {"success": False, "message": f"Ingestion error: {e}"})
                return

            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            new_last_synced = now_utc.strftime("%Y-%m-%d %H:%M:%S")
            integration.last_synced_at = now_utc
            integration.last_sync_status = "success"
            integration.last_sync_error = None
            integration.updated_at = now_utc
            integration.config = {**config, "lastSynced": new_last_synced}

            session.add(integration)
            await session.commit()
            await session.refresh(integration)

            yield _sse_event("complete", {
                "success": True,
                "integration": mask_integration_response(integration),
                "stats": {
                    "added": len(normalized),
                    "total": len(normalized),
                    "last_synced": new_last_synced,
                },
            })

    return StreamingResponse(_stream(), media_type="text/event-stream")