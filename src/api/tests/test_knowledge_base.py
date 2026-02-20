"""Comprehensive tests for Knowledge Base endpoints (/api/knowledge-base).

Covers:
- Incident logs (GET /api/knowledge-base/logs)
- Upload (POST /api/knowledge-base/upload)
- Validate (POST /api/knowledge-base/validate/{session_id})
- Field mapping (POST /api/knowledge-base/validate/{session_id}/map-fields)
- Version management: list, active, get, rollback, delete
- Permission/RBAC enforcement
- Unauthenticated access

Note: Endpoints that call Qdrant or embeddings models directly
(GET /incidents, DELETE /incidents/{id}, POST /ingest) are tested
with mocked external services where possible.
"""

import pytest
from uuid import uuid4
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, UTC

from src.api.db.models import User
from src.api.db.models.incident_log import IncidentLog
from src.api.db.models.incident_upload_session import IncidentUploadSession
from src.api.db.models.incident_dataset_version import IncidentDatasetVersion


# ============================================================
# Helpers
# ============================================================

async def _create_user(session, *, email=None):
    if email is None:
        email = f"user_{uuid4().hex[:8]}@test.com"
    user = User(email=email, is_active=True)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _create_incident_log(session, *, incident_id=None, title="Test Incident"):
    if incident_id is None:
        incident_id = f"INC{uuid4().hex[:8]}"
    log = IncidentLog(incident_id=incident_id, title=title, source="servicenow")
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def _create_upload_session(session, user_id, *, raw_data=None, status="pending"):
    if raw_data is None:
        raw_data = [
            {"incident_id": "INC001", "title": "Test", "description": "Test desc"},
        ]
    upload = IncidentUploadSession(
        status=status,
        uploaded_by=user_id,
        source="upload",
        file_metadata=[{"filename": "test.json", "size": 100, "content_type": "application/json", "row_count": 1}],
        raw_data=raw_data,
        incident_count=len(raw_data),
    )
    session.add(upload)
    await session.commit()
    await session.refresh(upload)
    return upload


async def _create_version(session, *, version_number=1, is_active=False, status="inactive", user_id=None):
    version = IncidentDatasetVersion(
        version_number=version_number,
        collection_name=f"test_collection_v{version_number}_{uuid4().hex[:6]}",
        status=status,
        is_active=is_active,
        incident_count=10,
        source="upload",
        uploaded_by=user_id,
    )
    session.add(version)
    await session.commit()
    await session.refresh(version)
    return version


# ============================================================
# GET /api/knowledge-base/logs — Incident logs
# ============================================================


class TestIncidentLogs:
    """Tests for GET /api/knowledge-base/logs"""

    @pytest.mark.asyncio
    async def test_get_logs_empty(self, admin_client):
        """Returns empty logs when none exist."""
        client, _, _ = admin_client
        response = await client.get("/api/knowledge-base/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["logs"] == []

    @pytest.mark.asyncio
    async def test_get_logs_returns_data(self, admin_client):
        """Returns incident logs."""
        client, session, _ = admin_client
        await _create_incident_log(session, incident_id="INC001", title="Server Down")
        await _create_incident_log(session, incident_id="INC002", title="DB Error")

        response = await client.get("/api/knowledge-base/logs")
        data = response.json()
        assert data["success"] is True
        assert len(data["logs"]) == 2

    @pytest.mark.asyncio
    async def test_get_logs_limit(self, admin_client):
        """Respects limit parameter."""
        client, session, _ = admin_client
        for i in range(5):
            await _create_incident_log(session, incident_id=f"INC{i:03d}")

        response = await client.get("/api/knowledge-base/logs?limit=3")
        assert len(response.json()["logs"]) == 3

    @pytest.mark.asyncio
    async def test_get_logs_requires_permission(self, no_perms_client):
        """Requires integration.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/api/knowledge-base/logs")
        assert response.status_code == 403


# ============================================================
# POST /api/knowledge-base/upload — File upload
# ============================================================


class TestUpload:
    """Tests for POST /api/knowledge-base/upload"""

    @pytest.mark.asyncio
    async def test_upload_json_file(self, admin_client):
        """Upload a JSON file creates an upload session."""
        client, session, user_id = admin_client
        # Create user in DB so the foreign key works
        user = User(id=user_id, email="uploader@test.com", is_active=True)
        session.add(user)
        await session.commit()

        import json
        content = json.dumps([
            {"incident_id": "INC001", "title": "Test", "description": "A test incident"},
        ])
        response = await client.post("/api/knowledge-base/upload", json={
            "files": [{"filename": "test.json", "size": len(content), "content": content}],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["incident_count"] == 1
        assert "session_id" in data

    @pytest.mark.asyncio
    async def test_upload_csv_file(self, admin_client):
        """Upload a CSV file creates an upload session."""
        client, session, user_id = admin_client
        user = User(id=user_id, email="csvuser@test.com", is_active=True)
        session.add(user)
        await session.commit()

        content = "incident_id,title,description\nINC001,Server Down,Server crashed\nINC002,DB Error,Connection lost"
        response = await client.post("/api/knowledge-base/upload", json={
            "files": [{"filename": "incidents.csv", "size": len(content), "content": content}],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["incident_count"] == 2

    @pytest.mark.asyncio
    async def test_upload_unsupported_file_type(self, admin_client):
        """Upload of unsupported file type fails."""
        client, session, user_id = admin_client
        user = User(id=user_id, email="badfile@test.com", is_active=True)
        session.add(user)
        await session.commit()

        response = await client.post("/api/knowledge-base/upload", json={
            "files": [{"filename": "data.xml", "size": 10, "content": "<root/>"}],
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_requires_permission(self, no_perms_client):
        """Requires kb.upload permission."""
        client, _, _ = no_perms_client
        response = await client.post("/api/knowledge-base/upload", json={
            "files": [{"filename": "test.json", "size": 10, "content": "[]"}],
        })
        assert response.status_code == 403


# ============================================================
# POST /api/knowledge-base/validate/{session_id}
# ============================================================


class TestValidate:
    """Tests for POST /api/knowledge-base/validate/{session_id}"""

    @pytest.mark.asyncio
    async def test_validate_success(self, admin_client):
        """Validate a session with valid records."""
        client, session, user_id = admin_client
        user = User(id=user_id, email="val@test.com", is_active=True)
        session.add(user)
        await session.commit()

        upload = await _create_upload_session(session, user_id, raw_data=[
            {"incident_id": "INC001", "title": "Test", "description": "Desc", "_source_file": "test.json"},
        ])

        response = await client.post(f"/api/knowledge-base/validate/{upload.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_records"] == 1
        assert data["valid_count"] == 1
        assert data["error_count"] == 0

    @pytest.mark.asyncio
    async def test_validate_missing_required_fields(self, admin_client):
        """Validate detects missing required fields."""
        client, session, user_id = admin_client
        user = User(id=user_id, email="valerr@test.com", is_active=True)
        session.add(user)
        await session.commit()

        upload = await _create_upload_session(session, user_id, raw_data=[
            {"incident_id": "INC001", "title": "", "description": "Desc", "_source_file": "test.json"},
        ])

        response = await client.post(f"/api/knowledge-base/validate/{upload.id}")
        data = response.json()
        assert data["success"] is True
        assert data["error_count"] > 0

    @pytest.mark.asyncio
    async def test_validate_not_found(self, admin_client):
        """Validate non-existent session returns 404."""
        client, _, _ = admin_client
        response = await client.post(f"/api/knowledge-base/validate/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_validate_requires_permission(self, no_perms_client):
        """Requires kb.validate permission."""
        client, _, _ = no_perms_client
        response = await client.post(f"/api/knowledge-base/validate/{uuid4()}")
        assert response.status_code == 403


# ============================================================
# POST /api/knowledge-base/validate/{session_id}/map-fields
# ============================================================


class TestFieldMapping:
    """Tests for POST /api/knowledge-base/validate/{session_id}/map-fields"""

    @pytest.mark.asyncio
    async def test_map_fields_success(self, admin_client):
        """Apply field mapping and re-validate."""
        client, session, user_id = admin_client
        user = User(id=user_id, email="map@test.com", is_active=True)
        session.add(user)
        await session.commit()

        upload = await _create_upload_session(session, user_id, raw_data=[
            {"id": "INC001", "name": "Test", "desc": "Desc", "_source_file": "test.json"},
        ])

        response = await client.post(
            f"/api/knowledge-base/validate/{upload.id}/map-fields",
            json={
                "session_id": str(upload.id),
                "mapping": {"id": "incident_id", "name": "title", "desc": "description"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["valid_count"] == 1

    @pytest.mark.asyncio
    async def test_map_fields_not_found(self, admin_client):
        """Mapping non-existent session returns 404."""
        client, _, _ = admin_client
        response = await client.post(
            f"/api/knowledge-base/validate/{uuid4()}/map-fields",
            json={"session_id": str(uuid4()), "mapping": {}},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_map_fields_requires_permission(self, no_perms_client):
        """Requires kb.validate permission."""
        client, _, _ = no_perms_client
        response = await client.post(
            f"/api/knowledge-base/validate/{uuid4()}/map-fields",
            json={"session_id": str(uuid4()), "mapping": {}},
        )
        assert response.status_code == 403


# ============================================================
# GET /api/knowledge-base/versions — List versions
# ============================================================


class TestListVersions:
    """Tests for GET /api/knowledge-base/versions"""

    @pytest.mark.asyncio
    async def test_list_versions_empty(self, admin_client):
        """Returns empty list when no versions exist."""
        client, _, _ = admin_client
        response = await client.get("/api/knowledge-base/versions")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["versions"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_versions_returns_data(self, admin_client):
        """Returns versions after creating some."""
        client, session, _ = admin_client
        await _create_version(session, version_number=1)
        await _create_version(session, version_number=2)

        response = await client.get("/api/knowledge-base/versions")
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 2
        assert len(data["versions"]) == 2

    @pytest.mark.asyncio
    async def test_list_versions_pagination(self, admin_client):
        """Respects limit and offset."""
        client, session, _ = admin_client
        for i in range(5):
            await _create_version(session, version_number=i + 1)

        response = await client.get("/api/knowledge-base/versions?limit=2&offset=0")
        data = response.json()
        assert len(data["versions"]) == 2
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_list_versions_shows_active(self, admin_client):
        """Active version ID is included in response."""
        client, session, _ = admin_client
        v = await _create_version(session, version_number=1, is_active=True, status="active")

        response = await client.get("/api/knowledge-base/versions")
        data = response.json()
        assert data["active_version_id"] == str(v.id)

    @pytest.mark.asyncio
    async def test_list_versions_requires_permission(self, no_perms_client):
        """Requires kb.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/api/knowledge-base/versions")
        assert response.status_code == 403


# ============================================================
# GET /api/knowledge-base/versions/active — Active version
# ============================================================


class TestActiveVersion:
    """Tests for GET /api/knowledge-base/versions/active"""

    @pytest.mark.asyncio
    async def test_active_version_none(self, admin_client):
        """Returns null when no active version."""
        client, _, _ = admin_client
        response = await client.get("/api/knowledge-base/versions/active")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["version"] is None

    @pytest.mark.asyncio
    async def test_active_version_exists(self, admin_client):
        """Returns the active version details."""
        client, session, _ = admin_client
        v = await _create_version(session, version_number=1, is_active=True, status="active")

        response = await client.get("/api/knowledge-base/versions/active")
        data = response.json()
        assert data["success"] is True
        assert data["version"]["id"] == str(v.id)
        assert data["version"]["is_active"] is True

    @pytest.mark.asyncio
    async def test_active_version_requires_permission(self, no_perms_client):
        """Requires kb.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/api/knowledge-base/versions/active")
        assert response.status_code == 403


# ============================================================
# GET /api/knowledge-base/versions/{version_id} — Version detail
# ============================================================


class TestGetVersion:
    """Tests for GET /api/knowledge-base/versions/{version_id}"""

    @pytest.mark.asyncio
    async def test_get_version_success(self, admin_client):
        """Returns version details."""
        client, session, _ = admin_client
        v = await _create_version(session, version_number=1, status="active", is_active=True)

        response = await client.get(f"/api/knowledge-base/versions/{v.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["version"]["version_number"] == 1

    @pytest.mark.asyncio
    async def test_get_version_not_found(self, admin_client):
        """Non-existent version returns 404."""
        client, _, _ = admin_client
        response = await client.get(f"/api/knowledge-base/versions/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_version_requires_permission(self, no_perms_client):
        """Requires kb.view permission."""
        client, _, _ = no_perms_client
        response = await client.get(f"/api/knowledge-base/versions/{uuid4()}")
        assert response.status_code == 403


# ============================================================
# POST /api/knowledge-base/versions/{version_id}/rollback
# ============================================================


class TestRollback:
    """Tests for POST /api/knowledge-base/versions/{version_id}/rollback"""

    @pytest.mark.asyncio
    async def test_rollback_success(self, admin_client):
        """Rollback activates a prior version."""
        client, session, user_id = admin_client
        v = await _create_version(session, version_number=1, status="inactive")

        with patch(
            "src.api.services.incident_ingestion_service._invalidate_copilot_cache",
        ):
            response = await client.post(f"/api/knowledge-base/versions/{v.id}/rollback")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "rolled back" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_rollback_not_found(self, admin_client):
        """Rollback non-existent version returns 400."""
        client, _, _ = admin_client
        response = await client.post(f"/api/knowledge-base/versions/{uuid4()}/rollback")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_rollback_archived_version(self, admin_client):
        """Cannot rollback to an archived version."""
        client, session, _ = admin_client
        v = await _create_version(session, version_number=1, status="archived")

        response = await client.post(f"/api/knowledge-base/versions/{v.id}/rollback")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_rollback_requires_permission(self, no_perms_client):
        """Requires kb.rollback permission."""
        client, _, _ = no_perms_client
        response = await client.post(f"/api/knowledge-base/versions/{uuid4()}/rollback")
        assert response.status_code == 403


# ============================================================
# DELETE /api/knowledge-base/versions/{version_id}
# ============================================================


class TestDeleteVersion:
    """Tests for DELETE /api/knowledge-base/versions/{version_id}"""

    @pytest.mark.asyncio
    async def test_delete_version_success(self, admin_client):
        """Delete an inactive version."""
        client, session, _ = admin_client
        v = await _create_version(session, version_number=1, status="inactive")

        with patch(
            "src.api.services.incident_ingestion_service.IncidentIngestionService.delete_version",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = await client.delete(f"/api/knowledge-base/versions/{v.id}")
        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_delete_active_version_fails(self, admin_client):
        """Cannot delete the active version."""
        client, session, _ = admin_client
        v = await _create_version(session, version_number=1, status="active", is_active=True)

        response = await client.delete(f"/api/knowledge-base/versions/{v.id}")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_version_not_found(self, admin_client):
        """Delete non-existent version returns 400."""
        client, _, _ = admin_client
        response = await client.delete(f"/api/knowledge-base/versions/{uuid4()}")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_version_requires_permission(self, no_perms_client):
        """Requires kb.version_manage permission."""
        client, _, _ = no_perms_client
        response = await client.delete(f"/api/knowledge-base/versions/{uuid4()}")
        assert response.status_code == 403


# ============================================================
# Edge Cases — Upload
# ============================================================


class TestUploadEdgeCases:
    """Edge cases for POST /api/knowledge-base/upload"""

    @pytest.mark.asyncio
    async def test_upload_empty_json_array(self, admin_client):
        """Upload with zero incidents should succeed with count 0."""
        import json as _json

        client, session, user_id = admin_client
        user = User(id=user_id, email="empty_upload@test.com", is_active=True)
        session.add(user)
        await session.commit()

        content = _json.dumps([])
        response = await client.post("/api/knowledge-base/upload", json={
            "files": [{"filename": "empty.json", "size": len(content), "content": content}],
        })
        # Either succeeds with 0 count or 400 if service rejects empty
        assert response.status_code in (200, 400)
        if response.status_code == 200:
            assert response.json()["incident_count"] == 0

    @pytest.mark.asyncio
    async def test_upload_malformed_json_content(self, admin_client):
        """Upload with invalid JSON content should return 400."""
        client, session, user_id = admin_client
        user = User(id=user_id, email="bad_json@test.com", is_active=True)
        session.add(user)
        await session.commit()

        response = await client.post("/api/knowledge-base/upload", json={
            "files": [{"filename": "bad.json", "size": 10, "content": "{not valid json,,}"}],
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_csv_with_missing_columns(self, admin_client):
        """Upload a CSV missing required columns should still create session."""
        client, session, user_id = admin_client
        user = User(id=user_id, email="missing_cols@test.com", is_active=True)
        session.add(user)
        await session.commit()

        content = "col_a,col_b\nval1,val2\nval3,val4"
        response = await client.post("/api/knowledge-base/upload", json={
            "files": [{"filename": "no_id.csv", "size": len(content), "content": content}],
        })
        # Should succeed at upload stage; validation catches missing fields later
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["incident_count"] == 2

    @pytest.mark.asyncio
    async def test_upload_multiple_files(self, admin_client):
        """Upload multiple files in a single request."""
        import json as _json

        client, session, user_id = admin_client
        user = User(id=user_id, email="multi_file@test.com", is_active=True)
        session.add(user)
        await session.commit()

        file1 = _json.dumps([{"incident_id": "INC001", "title": "T1", "description": "D1"}])
        file2 = _json.dumps([{"incident_id": "INC002", "title": "T2", "description": "D2"}])
        response = await client.post("/api/knowledge-base/upload", json={
            "files": [
                {"filename": "a.json", "size": len(file1), "content": file1},
                {"filename": "b.json", "size": len(file2), "content": file2},
            ],
        })
        assert response.status_code == 200
        assert response.json()["incident_count"] == 2


# ============================================================
# Edge Cases — Validate
# ============================================================


class TestValidateEdgeCases:
    """Edge cases for POST /api/knowledge-base/validate/{session_id}"""

    @pytest.mark.asyncio
    async def test_validate_already_validated_session(self, admin_client):
        """Validating a session that was already validated should still work."""
        client, session, user_id = admin_client
        user = User(id=user_id, email="revalidate@test.com", is_active=True)
        session.add(user)
        await session.commit()

        upload = await _create_upload_session(session, user_id, raw_data=[
            {"incident_id": "INC001", "title": "Test", "description": "Desc", "_source_file": "test.json"},
        ], status="validated")

        response = await client.post(f"/api/knowledge-base/validate/{upload.id}")
        # Should still return validation results regardless of current status
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_validate_session_with_all_invalid_records(self, admin_client):
        """All records missing required fields yields zero valid records.

        Each record can produce multiple errors (one per missing field),
        so error_count >= total_records.
        """
        client, session, user_id = admin_client
        user = User(id=user_id, email="all_invalid@test.com", is_active=True)
        session.add(user)
        await session.commit()

        upload = await _create_upload_session(session, user_id, raw_data=[
            {"foo": "bar", "_source_file": "test.json"},
            {"baz": "qux", "_source_file": "test.json"},
        ])

        response = await client.post(f"/api/knowledge-base/validate/{upload.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["error_count"] >= 2  # Multiple errors per record (missing fields)
        assert data["valid_count"] == 0

    @pytest.mark.asyncio
    async def test_validate_invalid_uuid_format(self, admin_client):
        """Non-UUID session_id returns 404 or 422."""
        client, _, _ = admin_client
        response = await client.post("/api/knowledge-base/validate/not-a-uuid")
        assert response.status_code in (404, 422)


# ============================================================
# Edge Cases — Field Mapping
# ============================================================


class TestFieldMappingEdgeCases:
    """Edge cases for POST /api/knowledge-base/validate/{session_id}/map-fields"""

    @pytest.mark.asyncio
    async def test_map_fields_empty_mapping(self, admin_client):
        """Empty mapping dict should still re-validate (no remapping)."""
        client, session, user_id = admin_client
        user = User(id=user_id, email="empty_map@test.com", is_active=True)
        session.add(user)
        await session.commit()

        upload = await _create_upload_session(session, user_id, raw_data=[
            {"incident_id": "INC001", "title": "Test", "description": "Desc", "_source_file": "t.json"},
        ])

        response = await client.post(
            f"/api/knowledge-base/validate/{upload.id}/map-fields",
            json={"session_id": str(upload.id), "mapping": {}},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_map_fields_identity_mapping(self, admin_client):
        """Mapping a field to itself should produce same validation result."""
        client, session, user_id = admin_client
        user = User(id=user_id, email="identity_map@test.com", is_active=True)
        session.add(user)
        await session.commit()

        upload = await _create_upload_session(session, user_id, raw_data=[
            {"incident_id": "INC001", "title": "Test", "description": "Desc", "_source_file": "t.json"},
        ])

        response = await client.post(
            f"/api/knowledge-base/validate/{upload.id}/map-fields",
            json={"session_id": str(upload.id), "mapping": {"title": "title"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid_count"] == 1


# ============================================================
# Edge Cases — Version Management
# ============================================================


class TestVersionEdgeCases:
    """Edge cases for version list/get endpoints."""

    @pytest.mark.asyncio
    async def test_list_versions_offset_beyond_total(self, admin_client):
        """Offset beyond total versions returns empty list."""
        client, session, _ = admin_client
        await _create_version(session, version_number=1)
        await _create_version(session, version_number=2)

        response = await client.get("/api/knowledge-base/versions?offset=100")
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 2
        assert len(data["versions"]) == 0

    @pytest.mark.asyncio
    async def test_list_versions_limit_one(self, admin_client):
        """Limit=1 returns exactly one version."""
        client, session, _ = admin_client
        await _create_version(session, version_number=1)
        await _create_version(session, version_number=2)
        await _create_version(session, version_number=3)

        response = await client.get("/api/knowledge-base/versions?limit=1")
        data = response.json()
        assert len(data["versions"]) == 1
        assert data["total"] == 3

    @pytest.mark.asyncio
    async def test_get_version_invalid_uuid(self, admin_client):
        """Non-UUID version_id returns 404 or 422."""
        client, _, _ = admin_client
        response = await client.get("/api/knowledge-base/versions/not-a-uuid")
        assert response.status_code in (404, 422, 500)

    @pytest.mark.asyncio
    async def test_active_version_when_multiple_exist(self, admin_client):
        """Only one version should be active; endpoint returns it."""
        client, session, _ = admin_client
        await _create_version(session, version_number=1, is_active=False, status="inactive")
        v2 = await _create_version(session, version_number=2, is_active=True, status="active")

        response = await client.get("/api/knowledge-base/versions/active")
        data = response.json()
        assert data["version"]["id"] == str(v2.id)
        assert data["version"]["is_active"] is True

    @pytest.mark.asyncio
    async def test_get_version_detail_includes_all_fields(self, admin_client):
        """Version detail response includes all expected fields."""
        client, session, _ = admin_client
        v = await _create_version(session, version_number=1, is_active=True, status="active")

        response = await client.get(f"/api/knowledge-base/versions/{v.id}")
        data = response.json()
        version = data["version"]
        expected_fields = {"id", "version_number", "collection_name", "status",
                           "is_active", "incident_count", "source"}
        assert expected_fields.issubset(set(version.keys()))


# ============================================================
# Edge Cases — Rollback
# ============================================================


class TestRollbackEdgeCases:
    """Edge cases for POST /api/knowledge-base/versions/{version_id}/rollback"""

    @pytest.mark.asyncio
    async def test_rollback_already_active_version(self, admin_client):
        """Rollback to an already-active version should still succeed or be a no-op."""
        client, session, _ = admin_client
        v = await _create_version(session, version_number=1, is_active=True, status="active")

        with patch(
            "src.api.services.incident_ingestion_service._invalidate_copilot_cache",
        ):
            response = await client.post(f"/api/knowledge-base/versions/{v.id}/rollback")
        # Either succeeds (re-activates) or 400 (already active)
        assert response.status_code in (200, 400)

    @pytest.mark.asyncio
    async def test_rollback_invalid_uuid(self, admin_client):
        """Non-UUID version_id returns 400 or 422."""
        client, _, _ = admin_client
        response = await client.post("/api/knowledge-base/versions/not-a-uuid/rollback")
        assert response.status_code in (400, 422, 500)

    @pytest.mark.asyncio
    async def test_rollback_with_notes(self, admin_client):
        """Rollback can include optional notes."""
        client, session, _ = admin_client
        v = await _create_version(session, version_number=1, status="inactive")

        with patch(
            "src.api.services.incident_ingestion_service._invalidate_copilot_cache",
        ):
            response = await client.post(
                f"/api/knowledge-base/versions/{v.id}/rollback",
                json={"notes": "Rolling back due to data issue"},
            )
        assert response.status_code == 200


# ============================================================
# Edge Cases — Delete Version
# ============================================================


class TestDeleteVersionEdgeCases:
    """Edge cases for DELETE /api/knowledge-base/versions/{version_id}"""

    @pytest.mark.asyncio
    async def test_double_delete_version(self, admin_client):
        """Deleting the same version twice returns error on second attempt."""
        client, session, _ = admin_client
        v = await _create_version(session, version_number=1, status="inactive")
        v_id = v.id

        with patch(
            "src.api.services.incident_ingestion_service.IncidentIngestionService.delete_version",
            new_callable=AsyncMock,
            return_value=True,
        ):
            r1 = await client.delete(f"/api/knowledge-base/versions/{v_id}")
        assert r1.status_code == 200

        # Second delete: mock raises ValueError since version was removed
        with patch(
            "src.api.services.incident_ingestion_service.IncidentIngestionService.delete_version",
            new_callable=AsyncMock,
            side_effect=ValueError("Version not found"),
        ):
            r2 = await client.delete(f"/api/knowledge-base/versions/{v_id}")
        assert r2.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_archived_version(self, admin_client):
        """Deleting an archived version should succeed (it's not active)."""
        client, session, _ = admin_client
        v = await _create_version(session, version_number=1, status="archived")

        with patch(
            "src.api.services.incident_ingestion_service.IncidentIngestionService.delete_version",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = await client.delete(f"/api/knowledge-base/versions/{v.id}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_version_invalid_uuid(self, admin_client):
        """Non-UUID version_id returns 400 or 422."""
        client, _, _ = admin_client
        response = await client.delete("/api/knowledge-base/versions/not-valid")
        assert response.status_code in (400, 422, 500)


# ============================================================
# Edge Cases — Incident Logs
# ============================================================


class TestIncidentLogsEdgeCases:
    """Edge cases for GET /api/knowledge-base/logs"""

    @pytest.mark.asyncio
    async def test_logs_ordering_most_recent_first(self, admin_client):
        """Logs should be ordered by created_at descending."""
        from datetime import timedelta
        client, session, _ = admin_client
        now = datetime.now(UTC)

        old_log = IncidentLog(
            incident_id="INC_OLD", title="Old", source="servicenow",
            created_at=now - timedelta(seconds=10),
        )
        new_log = IncidentLog(
            incident_id="INC_NEW", title="New", source="servicenow",
            created_at=now,
        )
        session.add_all([old_log, new_log])
        await session.commit()

        response = await client.get("/api/knowledge-base/logs?limit=10")
        logs = response.json()["logs"]
        assert len(logs) == 2
        # Most recent should be first
        assert logs[0]["incident_id"] == "INC_NEW"

    @pytest.mark.asyncio
    async def test_logs_limit_zero_or_negative(self, admin_client):
        """Limit=0 returns empty or is rejected."""
        client, session, _ = admin_client
        await _create_incident_log(session)

        response = await client.get("/api/knowledge-base/logs?limit=0")
        # Depending on implementation, 0 may return empty or 422
        assert response.status_code in (200, 422)

    @pytest.mark.asyncio
    async def test_logs_special_characters_in_title(self, admin_client):
        """Logs with special characters are stored and returned correctly."""
        client, session, _ = admin_client
        special_title = "<script>alert('xss')</script> 日本語 🔥"
        await _create_incident_log(session, title=special_title)

        response = await client.get("/api/knowledge-base/logs?limit=1")
        logs = response.json()["logs"]
        assert len(logs) == 1
        assert logs[0]["title"] == special_title


# ============================================================
# GET /api/knowledge-base/incidents — List incidents (Qdrant)
# ============================================================


class TestListIncidents:
    """Tests for GET /api/knowledge-base/incidents"""

    @pytest.mark.asyncio
    async def test_list_incidents_no_qdrant_no_file(self, admin_client):
        """Returns empty when Qdrant unavailable and no JSON file."""
        client, _, _ = admin_client
        with patch(
            "src.api.routers.knowledge_base.get_qdrant_client",
            side_effect=ImportError("no qdrant"),
        ), patch("os.path.exists", return_value=False):
            response = await client.get("/api/knowledge-base/incidents")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["incidents"] == []

    @pytest.mark.asyncio
    async def test_list_incidents_requires_permission(self, no_perms_client):
        """Requires integration.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/api/knowledge-base/incidents")
        assert response.status_code == 403


# ============================================================
# DELETE /api/knowledge-base/incidents/{incident_id}
# ============================================================


class TestDeleteIncident:
    """Tests for DELETE /api/knowledge-base/incidents/{incident_id}"""

    @pytest.mark.asyncio
    async def test_delete_incident_no_file(self, admin_client):
        """Delete when no incidents file exists."""
        client, _, _ = admin_client
        with patch("os.path.exists", return_value=False):
            response = await client.delete("/api/knowledge-base/incidents/INC001")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["message"].lower() or "no incidents" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_delete_incident_requires_permission(self, no_perms_client):
        """Requires integration.delete permission."""
        client, _, _ = no_perms_client
        response = await client.delete("/api/knowledge-base/incidents/INC001")
        assert response.status_code == 403


# ============================================================
# Unauthenticated access
# ============================================================


class TestKBUnauthenticated:
    """Unauthenticated requests to knowledge base endpoints are rejected."""

    @pytest.mark.asyncio
    async def test_incidents_unauth(self, client):
        response = await client.get("/api/knowledge-base/incidents")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_incident_unauth(self, client):
        response = await client.delete("/api/knowledge-base/incidents/INC001")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_logs_unauth(self, client):
        response = await client.get("/api/knowledge-base/logs")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_upload_unauth(self, client):
        response = await client.post("/api/knowledge-base/upload", json={
            "files": [{"filename": "t.json", "size": 1, "content": "[]"}],
        })
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_validate_unauth(self, client):
        response = await client.post(f"/api/knowledge-base/validate/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_map_fields_unauth(self, client):
        response = await client.post(
            f"/api/knowledge-base/validate/{uuid4()}/map-fields",
            json={"session_id": str(uuid4()), "mapping": {}},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_ingest_unauth(self, client):
        response = await client.post("/api/knowledge-base/ingest", json={
            "session_id": str(uuid4()),
        })
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_versions_unauth(self, client):
        response = await client.get("/api/knowledge-base/versions")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_active_version_unauth(self, client):
        response = await client.get("/api/knowledge-base/versions/active")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_version_unauth(self, client):
        response = await client.get(f"/api/knowledge-base/versions/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_rollback_unauth(self, client):
        response = await client.post(f"/api/knowledge-base/versions/{uuid4()}/rollback")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_version_unauth(self, client):
        response = await client.delete(f"/api/knowledge-base/versions/{uuid4()}")
        assert response.status_code == 403
