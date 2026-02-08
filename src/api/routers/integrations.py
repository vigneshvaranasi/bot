import json
import logging
import os
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.api.auth.dependencies import get_current_user, require_permission
from src.api.db.models.integration import Integration
from src.api.db.session import get_session
from src.api.schemas.integration_schema import (
    IntegrationBase,
    IntegrationCreate,
    IntegrationResponse,
    IntegrationListResponse,
)
from src.automation.snow import run_servicenow_ingestion

logger = logging.getLogger(__name__)
router = APIRouter()

# Sensitive fields that should be masked in API responses
SENSITIVE_CONFIG_FIELDS = {"password", "api_key", "secret", "token", "api_token", "access_token", "refresh_token"}


def mask_sensitive_config(config: dict) -> dict:
    """Mask sensitive fields in integration config for API responses."""
    if not config:
        return config
    masked = config.copy()
    for key in masked:
        if key.lower() in SENSITIVE_CONFIG_FIELDS or "password" in key.lower() or "secret" in key.lower() or "token" in key.lower():
            masked[key] = "********"
    return masked


def mask_integration_response(integration) -> dict:
    """Create a masked version of an integration for API responses."""
    return {
        "id": str(integration.id),
        "service_name": integration.service_name,
        "auth_type": integration.auth_type,
        "config": mask_sensitive_config(integration.config),
        "is_active": integration.is_active,
        "last_synced_at": integration.last_synced_at,
        "last_sync_status": integration.last_sync_status,
        "last_sync_error": integration.last_sync_error,
        "updated_at": integration.updated_at,
        "user_id": str(integration.user_id) if integration.user_id else None,
    }


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
        new_integration = Integration(
            service_name=integration.service_name,
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

        integration.service_name = integration_data.service_name
        integration.auth_type = integration_data.auth_type
        integration.config = integration_data.config
        integration.is_active = integration_data.is_active

        session.add(integration)
        await session.commit()
        await session.refresh(integration)

        return {"success": True, "integration": mask_integration_response(integration)}
    except Exception as e:
        await session.rollback()
        return {
            "success": False,
            "message": f"Error occurred while updating integration of ID {integration_id}: {e}",
        }
    

# POST Sync Integration by ID
@router.post("/sync/{integration_id}")
async def sync_integration(
    integration_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission("integration.sync")),
):
    try:
        result = await session.execute(
            select(Integration).where(Integration.id == integration_id)
        )
        integration = result.scalars().first()
        if not integration:
            return {"success": False, "message": "Integration not found"}

        # Prepare config defaults
        config = integration.config or {}
        url = config.get("url")
        username = config.get("username")
        password = config.get("password")
        last_synced = config.get("lastSynced") or config.get("last_synced") or "1970-01-01 00:00:00"

        if not (url and username and password):
            return {
                "success": False,
                "message": "Missing ServiceNow configuration (url, username, password)",
            }

        # Run ServiceNow ingestion
        sync_payload = {
            "url": url,
            "username": username,
            "password": password,
            "lastSynced": last_synced,
        }

        try:
            result = run_servicenow_ingestion(sync_payload)
            integration.last_sync_status = "success"
            integration.last_sync_error = None
        except Exception as e:
            integration.last_sync_status = "error"
            integration.last_sync_error = str(e)
            await session.commit()
            return {"success": False, "message": str(e)}

        # Persist incidents to data folder
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
        os.makedirs(data_dir, exist_ok=True)
        output_path = os.path.join(data_dir, "incidentspulledfromsnow.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.get("normalized", []), f, ensure_ascii=False, indent=2)

        # Update integration state
        now_utc = datetime.now(timezone.utc)
        integration.last_synced_at = now_utc
        integration.updated_at = now_utc
        config["lastSynced"] = result.get("last_synced")
        integration.config = config

        session.add(integration)
        await session.commit()
        await session.refresh(integration)

        return {
            "success": True,
            "integration": mask_integration_response(integration),
            "stats": {
                "added": result.get("added"),
                "total": result.get("total"),
                "last_synced": result.get("last_synced"),
            },
        }
    except Exception as e:
        await session.rollback()
        return {
            "success": False,
            "message": f"Error occurred while syncing integration of ID {integration_id}: {e}",
        }
    

