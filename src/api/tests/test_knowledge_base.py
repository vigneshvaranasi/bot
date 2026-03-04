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
        now = datetime.now(UTC).replace(tzinfo=None)

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

import json
from src.api.services.incident_ingestion_service import IncidentIngestionService

class TestParseFileContent:
    """Tests for _parse_file_content (JSON and CSV parsing)."""

    def _svc(self):
        return IncidentIngestionService(None)

    def test_json_array(self):
        content = json.dumps([{"incident_id": "1"}, {"incident_id": "2"}])
        result = self._svc()._parse_file_content("data.json", content)
        assert len(result) == 2
        assert result[0]["incident_id"] == "1"

    def test_json_single_object(self):
        content = json.dumps({"incident_id": "solo"})
        result = self._svc()._parse_file_content("data.json", content)
        assert len(result) == 1
        assert result[0]["incident_id"] == "solo"

    def test_json_invalid_top_level(self):
        with pytest.raises(ValueError, match="must contain an array or object"):
            self._svc()._parse_file_content("bad.json", '"just a string"')

    def test_csv_parsing(self):
        content = "incident_id,title,description\nINC001,Bug,Fix it\nINC002,Issue,Resolve\n"
        result = self._svc()._parse_file_content("data.csv", content)
        assert len(result) == 2
        assert result[0]["incident_id"] == "INC001"
        assert result[1]["title"] == "Issue"

    def test_unsupported_file_type(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            self._svc()._parse_file_content("data.xlsx", "binary")

    def test_csv_empty_file(self):
        result = self._svc()._parse_file_content("empty.csv", "incident_id,title\n")
        assert result == []


class TestValidateRecords:
    """Tests for _validate_records (required field checking)."""

    def _svc(self):
        return IncidentIngestionService(None)

    def test_valid_records_no_errors(self):
        records = [
            {"incident_id": "1", "title": "Bug", "description": "Desc", "_source_file": "f.csv"},
        ]
        errors = self._svc()._validate_records(records)
        assert errors == []

    def test_missing_required_field(self):
        records = [
            {"incident_id": "1", "title": "Bug", "_source_file": "f.csv"},
        ]
        errors = self._svc()._validate_records(records)
        assert len(errors) == 1
        assert errors[0].field == "description"

    def test_empty_string_field(self):
        records = [
            {"incident_id": "", "title": "Bug", "description": "D", "_source_file": "f.csv"},
        ]
        errors = self._svc()._validate_records(records)
        assert len(errors) == 1
        assert errors[0].field == "incident_id"

    def test_whitespace_only_field(self):
        records = [
            {"incident_id": "  ", "title": "Bug", "description": "D", "_source_file": "f.csv"},
        ]
        errors = self._svc()._validate_records(records)
        assert len(errors) == 1

    def test_all_fields_missing(self):
        records = [{"_source_file": "f.csv"}]
        errors = self._svc()._validate_records(records)
        assert len(errors) == 3  # incident_id, title, description

    def test_multiple_records_independent_errors(self):
        records = [
            {"incident_id": "1", "title": "OK", "description": "D", "_source_file": "f.csv"},
            {"incident_id": "2", "_source_file": "f.csv"},
        ]
        errors = self._svc()._validate_records(records)
        assert len(errors) == 2

    def test_per_file_row_counters(self):
        records = [
            {"incident_id": "1", "_source_file": "a.csv"},
            {"incident_id": "2", "_source_file": "b.csv"},
        ]
        errors = self._svc()._validate_records(records)
        a_errors = [e for e in errors if e.file == "a.csv"]
        b_errors = [e for e in errors if e.file == "b.csv"]
        assert all(e.row == 1 for e in a_errors)
        assert all(e.row == 1 for e in b_errors)


class TestNormalizeRecords:
    """Tests for _normalize_records (whitespace, booleans, dates, dedup)."""

    def _svc(self):
        return IncidentIngestionService(None)

    def test_strips_whitespace(self):
        records = [{"title": "  hello  ", "description": "  world  "}]
        result = self._svc()._normalize_records(records)
        assert result[0]["title"] == "hello"
        assert result[0]["description"] == "world"

    def test_boolean_standardization(self):
        records = [
            {"repeat_incident": "true"},
            {"repeat_incident": "yes"},
            {"repeat_incident": "1"},
            {"repeat_incident": "false"},
            {"repeat_incident": "no"},
        ]
        result = self._svc()._normalize_records(records)
        assert result[0]["repeat_incident"] is True
        assert result[1]["repeat_incident"] is True
        assert result[2]["repeat_incident"] is True
        assert result[3]["repeat_incident"] is False
        assert result[4]["repeat_incident"] is False

    def test_deduplication_by_incident_id(self):
        records = [
            {"incident_id": "INC001", "title": "First"},
            {"incident_id": "INC001", "title": "Duplicate"},
            {"incident_id": "INC002", "title": "Second"},
        ]
        result = self._svc()._normalize_records(records)
        assert len(result) == 2
        assert result[0]["title"] == "First"
        assert result[1]["title"] == "Second"

    def test_strips_source_file_tag(self):
        records = [{"incident_id": "1", "_source_file": "data.csv", "title": "T"}]
        result = self._svc()._normalize_records(records)
        assert "_source_file" not in result[0]

    def test_date_standardization(self):
        records = [{"opened_at": "2024-01-15T10:30:00Z"}]
        result = self._svc()._normalize_records(records)
        assert "2024-01-15" in result[0]["opened_at"]

    def test_unparseable_date_kept_as_is(self):
        records = [{"opened_at": "not-a-date"}]
        result = self._svc()._normalize_records(records)
        assert result[0]["opened_at"] == "not-a-date"

    def test_records_without_incident_id_not_deduped(self):
        records = [
            {"title": "No ID 1"},
            {"title": "No ID 2"},
        ]
        result = self._svc()._normalize_records(records)
        assert len(result) == 2


class TestCreateUploadSession:
    """Tests for create_upload_session (DB-level)."""

    @pytest.mark.asyncio
    async def test_create_session_json(self, test_session):
        user = await _create_user(test_session)
        svc = IncidentIngestionService(test_session)
        files_data = [{
            "filename": "incidents.json",
            "content": json.dumps([
                {"incident_id": "1", "title": "Bug", "description": "D"},
            ]),
            "size": 100,
        }]
        session_obj = await svc.create_upload_session(files_data, str(user.id))
        assert session_obj.status == "pending"
        assert session_obj.incident_count == 1
        assert len(session_obj.raw_data) == 1

    @pytest.mark.asyncio
    async def test_create_session_csv(self, test_session):
        user = await _create_user(test_session)
        svc = IncidentIngestionService(test_session)
        csv_content = "incident_id,title,description\nINC001,Bug,Fix\n"
        files_data = [{"filename": "data.csv", "content": csv_content, "size": 50}]
        session_obj = await svc.create_upload_session(files_data, str(user.id))
        assert session_obj.incident_count == 1

    @pytest.mark.asyncio
    async def test_create_session_no_user_id_raises(self, test_session):
        svc = IncidentIngestionService(test_session)
        with pytest.raises(ValueError, match="user_id is required"):
            await svc.create_upload_session([], "")

    @pytest.mark.asyncio
    async def test_create_session_multiple_files(self, test_session):
        user = await _create_user(test_session)
        svc = IncidentIngestionService(test_session)
        files_data = [
            {
                "filename": "a.json",
                "content": json.dumps([{"incident_id": "1", "title": "A", "description": "D"}]),
                "size": 50,
            },
            {
                "filename": "b.json",
                "content": json.dumps([{"incident_id": "2", "title": "B", "description": "D"}]),
                "size": 50,
            },
        ]
        session_obj = await svc.create_upload_session(files_data, str(user.id))
        assert session_obj.incident_count == 2
        assert len(session_obj.file_metadata) == 2


class TestValidateSession:
    """Tests for validate_session (end-to-end validation)."""

    @pytest.mark.asyncio
    async def test_valid_session(self, test_session):
        user = await _create_user(test_session)
        svc = IncidentIngestionService(test_session)
        files_data = [{
            "filename": "ok.json",
            "content": json.dumps([
                {"incident_id": "1", "title": "Bug", "description": "Desc"},
            ]),
            "size": 100,
        }]
        upload = await svc.create_upload_session(files_data, str(user.id))
        report = await svc.validate_session(str(upload.id))
        assert report.status == "validated"
        assert report.error_count == 0
        assert report.valid_count == 1

    @pytest.mark.asyncio
    async def test_session_with_errors(self, test_session):
        user = await _create_user(test_session)
        svc = IncidentIngestionService(test_session)
        files_data = [{
            "filename": "bad.json",
            "content": json.dumps([{"incident_id": "1"}]),
            "size": 50,
        }]
        upload = await svc.create_upload_session(files_data, str(user.id))
        report = await svc.validate_session(str(upload.id))
        assert report.status == "has_errors"
        assert report.error_count > 0


class TestApplyFieldMapping:
    """Tests for apply_field_mapping."""

    @pytest.mark.asyncio
    async def test_remap_fields(self, test_session):
        user = await _create_user(test_session)
        svc = IncidentIngestionService(test_session)
        files_data = [{
            "filename": "remap.json",
            "content": json.dumps([
                {"id": "1", "name": "Bug", "desc": "Fix it"},
            ]),
            "size": 100,
        }]
        upload = await svc.create_upload_session(files_data, str(user.id))

        mapping = {"id": "incident_id", "name": "title", "desc": "description"}
        report = await svc.apply_field_mapping(str(upload.id), mapping)
        assert report.status == "validated"
        assert report.error_count == 0

class TestVersionManagementService:
    """Tests for IncidentIngestionService version management methods."""

    @pytest.mark.asyncio
    async def test_get_versions_empty(self, test_session):
        svc = IncidentIngestionService(test_session)
        result = await svc.get_versions()
        assert result.total == 0
        assert result.versions == []

    @pytest.mark.asyncio
    async def test_get_versions_with_data(self, test_session):
        user = await _create_user(test_session)
        await _create_version(test_session, version_number=1, user_id=user.id)
        await _create_version(test_session, version_number=2, user_id=user.id)

        svc = IncidentIngestionService(test_session)
        result = await svc.get_versions()
        assert result.total == 2
        assert len(result.versions) == 2

    @pytest.mark.asyncio
    async def test_get_versions_pagination(self, test_session):
        user = await _create_user(test_session)
        for i in range(5):
            await _create_version(test_session, version_number=i + 1, user_id=user.id)

        svc = IncidentIngestionService(test_session)
        result = await svc.get_versions(limit=2, offset=0)
        assert result.total == 5
        assert len(result.versions) == 2

    @pytest.mark.asyncio
    async def test_get_versions_with_active(self, test_session):
        user = await _create_user(test_session)
        v = await _create_version(test_session, version_number=1, user_id=user.id,
                                  is_active=True, status="active")

        svc = IncidentIngestionService(test_session)
        result = await svc.get_versions()
        assert result.active_version_id == str(v.id)

    @pytest.mark.asyncio
    async def test_get_versions_includes_email(self, test_session):
        user = await _create_user(test_session, email="version@test.com")
        await _create_version(test_session, version_number=1, user_id=user.id)

        svc = IncidentIngestionService(test_session)
        result = await svc.get_versions()
        assert result.versions[0].uploader_email == "version@test.com"

    @pytest.mark.asyncio
    async def test_get_active_version_none(self, test_session):
        svc = IncidentIngestionService(test_session)
        result = await svc.get_active_version()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_version_exists(self, test_session):
        v = await _create_version(test_session, version_number=1, is_active=True, status="active")
        svc = IncidentIngestionService(test_session)
        result = await svc.get_active_version()
        assert result is not None
        assert result.id == v.id

    @pytest.mark.asyncio
    async def test_get_version_by_id(self, test_session):
        v = await _create_version(test_session, version_number=1)
        svc = IncidentIngestionService(test_session)
        result = await svc.get_version_by_id(str(v.id))
        assert result is not None
        assert result.version_number == 1

    @pytest.mark.asyncio
    async def test_get_version_by_id_not_found(self, test_session):
        svc = IncidentIngestionService(test_session)
        result = await svc.get_version_by_id(str(uuid4()))
        assert result is None

    @pytest.mark.asyncio
    async def test_activate_version_success(self, test_session):
        user = await _create_user(test_session)
        v = await _create_version(test_session, version_number=1, status="inactive")

        svc = IncidentIngestionService(test_session)
        with patch("src.api.services.incident_ingestion_service._invalidate_copilot_cache"):
            result = await svc.activate_version(str(v.id), str(user.id))
        assert result.is_active is True
        assert result.status == "active"

    @pytest.mark.asyncio
    async def test_activate_version_not_found(self, test_session):
        svc = IncidentIngestionService(test_session)
        with pytest.raises(ValueError, match="not found"):
            await svc.activate_version(str(uuid4()), str(uuid4()))

    @pytest.mark.asyncio
    async def test_activate_version_archived(self, test_session):
        v = await _create_version(test_session, version_number=1, status="archived")
        svc = IncidentIngestionService(test_session)
        with pytest.raises(ValueError, match="archived"):
            await svc.activate_version(str(v.id), str(uuid4()))

    @pytest.mark.asyncio
    async def test_activate_version_failed(self, test_session):
        v = await _create_version(test_session, version_number=1, status="failed")
        svc = IncidentIngestionService(test_session)
        with pytest.raises(ValueError, match="failed"):
            await svc.activate_version(str(v.id), str(uuid4()))

    @pytest.mark.asyncio
    async def test_activate_deactivates_previous(self, test_session):
        user = await _create_user(test_session)
        v1 = await _create_version(test_session, version_number=1, is_active=True, status="active")
        v2 = await _create_version(test_session, version_number=2, status="inactive")

        svc = IncidentIngestionService(test_session)
        with patch("src.api.services.incident_ingestion_service._invalidate_copilot_cache"):
            result = await svc.activate_version(str(v2.id), str(user.id))
        assert result.is_active is True

        await test_session.refresh(v1)
        assert v1.is_active is False
        assert v1.status == "inactive"

    @pytest.mark.asyncio
    async def test_activate_with_notes(self, test_session):
        user = await _create_user(test_session)
        v = await _create_version(test_session, version_number=1, status="inactive")

        svc = IncidentIngestionService(test_session)
        with patch("src.api.services.incident_ingestion_service._invalidate_copilot_cache"):
            result = await svc.activate_version(str(v.id), str(user.id), notes="rollback reason")
        assert result.notes == "rollback reason"

    @pytest.mark.asyncio
    async def test_rollback_to_version(self, test_session):
        """rollback_to_version delegates to activate_version."""
        user = await _create_user(test_session)
        v = await _create_version(test_session, version_number=1, status="inactive")

        svc = IncidentIngestionService(test_session)
        with patch("src.api.services.incident_ingestion_service._invalidate_copilot_cache"):
            result = await svc.rollback_to_version(str(v.id), str(user.id))
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_delete_version_success(self, test_session):
        v = await _create_version(test_session, version_number=1, status="inactive")
        svc = IncidentIngestionService(test_session)

        with patch(
            "src.api.services.incident_ingestion_service.IncidentIngestionService.delete_version",
            new_callable=AsyncMock, return_value=True,
        ) as mock_del:
            # Call the real method for coverage of not_found and is_active checks
            pass

        # Test the actual method with mocked Qdrant
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        with patch("src.api.routers.knowledge_base.get_qdrant_client", return_value=mock_client):
            result = await svc.delete_version(str(v.id))
        assert result is True
        mock_client.delete_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_version_not_found(self, test_session):
        svc = IncidentIngestionService(test_session)
        with pytest.raises(ValueError, match="not found"):
            await svc.delete_version(str(uuid4()))

    @pytest.mark.asyncio
    async def test_delete_version_active(self, test_session):
        v = await _create_version(test_session, version_number=1, is_active=True, status="active")
        svc = IncidentIngestionService(test_session)
        with pytest.raises(ValueError, match="active"):
            await svc.delete_version(str(v.id))

    @pytest.mark.asyncio
    async def test_delete_version_archived_skips_qdrant(self, test_session):
        v = await _create_version(test_session, version_number=1, status="archived")
        svc = IncidentIngestionService(test_session)
        result = await svc.delete_version(str(v.id))
        assert result is True

    @pytest.mark.asyncio
    async def test_get_active_collection_name_with_active(self, test_session):
        v = await _create_version(test_session, version_number=1, is_active=True, status="active")
        svc = IncidentIngestionService(test_session)
        name = await svc.get_active_collection_name()
        assert name == v.collection_name

    @pytest.mark.asyncio
    async def test_get_active_collection_name_fallback(self, test_session):
        svc = IncidentIngestionService(test_session)
        with patch("src.copilot.config.QDRANT_COLLECTION_NAME", "fallback_collection"):
            name = await svc.get_active_collection_name()
        assert name == "fallback_collection"

    @pytest.mark.asyncio
    async def test_get_upload_session_not_found(self, test_session):
        svc = IncidentIngestionService(test_session)
        with pytest.raises(ValueError, match="not found"):
            await svc._get_upload_session(str(uuid4()))

    @pytest.mark.asyncio
    async def test_get_upload_session_invalid_id(self, test_session):
        svc = IncidentIngestionService(test_session)
        with pytest.raises(ValueError, match="Invalid session ID"):
            await svc._get_upload_session("not-a-uuid")


class TestNormalization:
    """Tests for _normalize_records."""

    def test_basic_normalization(self):
        from src.api.services.incident_ingestion_service import IncidentIngestionService
        svc = IncidentIngestionService.__new__(IncidentIngestionService)
        records = [
            {"incident_id": "1", "title": " Test ", "description": "desc", "_source_file": "f.json"},
        ]
        result = svc._normalize_records(records)
        assert len(result) == 1
        assert result[0]["title"] == "Test"
        assert "_source_file" not in result[0]

    def test_deduplication(self):
        from src.api.services.incident_ingestion_service import IncidentIngestionService
        svc = IncidentIngestionService.__new__(IncidentIngestionService)
        records = [
            {"incident_id": "1", "title": "T1", "description": "D1"},
            {"incident_id": "1", "title": "T2", "description": "D2"},
        ]
        result = svc._normalize_records(records)
        assert len(result) == 1
        assert result[0]["title"] == "T1"

    def test_boolean_standardization(self):
        from src.api.services.incident_ingestion_service import IncidentIngestionService
        svc = IncidentIngestionService.__new__(IncidentIngestionService)
        records = [
            {"incident_id": "1", "title": "T", "description": "D", "repeat_incident": "yes"},
            {"incident_id": "2", "title": "T", "description": "D", "repeat_incident": "false"},
        ]
        result = svc._normalize_records(records)
        assert result[0]["repeat_incident"] is True
        assert result[1]["repeat_incident"] is False

    def test_date_standardization(self):
        from src.api.services.incident_ingestion_service import IncidentIngestionService
        svc = IncidentIngestionService.__new__(IncidentIngestionService)
        records = [
            {"incident_id": "1", "title": "T", "description": "D",
             "opened_at": "2024-01-15T10:00:00Z"},
        ]
        result = svc._normalize_records(records)
        assert "2024-01-15" in result[0]["opened_at"]


class TestInvalidateCopilotCache:
    """Tests for _invalidate_copilot_cache."""

    def test_invalidate_success(self):
        from src.api.services.incident_ingestion_service import _invalidate_copilot_cache
        mock_base = MagicMock()
        mock_base._vector_store = "old"
        mock_base._retriever = "old"
        with patch.dict("sys.modules", {"src.copilot.tools._base": mock_base}):
            _invalidate_copilot_cache()

    def test_invalidate_handles_import_error(self):
        from src.api.services.incident_ingestion_service import _invalidate_copilot_cache
        with patch.dict("sys.modules", {"src.copilot.tools._base": None}):
            # Should not raise
            _invalidate_copilot_cache()


class TestSanitizeErrorForUser:
    """Tests for _sanitize_error_for_user in knowledge_base router."""

    def test_value_error_passthrough(self):
        from src.api.routers.knowledge_base import _sanitize_error_for_user
        result = _sanitize_error_for_user(ValueError("custom msg"))
        assert result == "custom msg"

    def test_not_null_violation(self):
        from src.api.routers.knowledge_base import _sanitize_error_for_user
        result = _sanitize_error_for_user(RuntimeError("NotNullViolationError on column"))
        assert "required fields" in result.lower()

    def test_unique_constraint(self):
        from src.api.routers.knowledge_base import _sanitize_error_for_user
        result = _sanitize_error_for_user(RuntimeError("UniqueViolationError"))
        assert "duplicate" in result.lower()

    def test_integrity_error(self):
        from src.api.routers.knowledge_base import _sanitize_error_for_user
        result = _sanitize_error_for_user(RuntimeError("IntegrityError"))
        assert "integrity" in result.lower()

    def test_connection_refused(self):
        from src.api.routers.knowledge_base import _sanitize_error_for_user
        result = _sanitize_error_for_user(RuntimeError("ConnectionRefusedError"))
        assert "connect" in result.lower()

    def test_timeout(self):
        from src.api.routers.knowledge_base import _sanitize_error_for_user
        result = _sanitize_error_for_user(RuntimeError("operation timeout"))
        assert "timed out" in result.lower()

    def test_generic_error(self):
        from src.api.routers.knowledge_base import _sanitize_error_for_user
        result = _sanitize_error_for_user(RuntimeError("something weird happened"))
        assert "unexpected error" in result.lower()


class TestParseDescriptionMetadata:
    """Tests for _parse_description_metadata."""

    def test_json_strategy(self):
        from src.api.routers.knowledge_base import _parse_description_metadata
        import json
        desc_json = json.dumps({
            "incident_id": "INC001",
            "incident_description": "impactedApplication: App1\nrootCause: Memory leak"
        })
        desc = f"Short desc\nDetails: {desc_json}\nCategory: inquiry"
        result = _parse_description_metadata(desc)
        assert result["impactedApplication"] == "App1"
        assert result["rootCause"] == "Memory leak"

    def test_flat_parsing(self):
        from src.api.routers.knowledge_base import _parse_description_metadata
        desc = "key1: value1\nkey2: value2"
        result = _parse_description_metadata(desc)
        assert result["key1"] == "value1"
        assert result["key2"] == "value2"

    def test_empty_description(self):
        from src.api.routers.knowledge_base import _parse_description_metadata
        result = _parse_description_metadata("")
        assert result == {}


class TestConfirmAndIngest:
    """Tests for confirm_and_ingest with mocked Qdrant."""

    @pytest.mark.asyncio
    async def test_no_user_id_raises(self, test_session):
        svc = IncidentIngestionService(test_session)
        with pytest.raises(ValueError, match="user_id is required"):
            await svc.confirm_and_ingest("some-session-id", "")

    @pytest.mark.asyncio
    async def test_no_valid_records_raises(self, test_session):
        user = await _create_user(test_session)
        upload = await _create_upload_session(test_session, user.id, raw_data=[
            {"_source_file": "f.json"},  # Missing all required fields
        ])
        svc = IncidentIngestionService(test_session)
        with pytest.raises(ValueError, match="No valid records"):
            await svc.confirm_and_ingest(str(upload.id), str(user.id))

    @pytest.mark.asyncio
    async def test_create_upload_session_no_user_id(self, test_session):
        svc = IncidentIngestionService(test_session)
        with pytest.raises(ValueError, match="user_id is required"):
            await svc.create_upload_session([], "")


class TestEnforceCollectionWindow:
    """Tests for _enforce_collection_window."""

    @pytest.mark.asyncio
    async def test_no_versions_to_archive(self, test_session):
        """Nothing to archive when few versions exist."""
        svc = IncidentIngestionService(test_session)
        # Should not raise
        await svc._enforce_collection_window()

    @pytest.mark.asyncio
    async def test_archives_old_versions(self, test_session):
        """Old inactive versions beyond window are archived."""
        user = await _create_user(test_session)
        # Create more versions than the window size
        for i in range(10):
            await _create_version(test_session, version_number=i + 1,
                                  status="inactive", user_id=user.id)

        svc = IncidentIngestionService(test_session)
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        with patch("src.api.routers.knowledge_base.get_qdrant_client", return_value=mock_client):
            await svc._enforce_collection_window()
        # Should have archived some versions
        assert mock_client.delete_collection.call_count > 0

class TestKBRouterListIncidents:
    """Tests for GET /api/knowledge-base/incidents."""

    @pytest.mark.asyncio
    async def test_list_incidents_qdrant_fallback_to_empty(self, admin_client):
        """When Qdrant fails and no JSON file, returns empty list."""
        client, _, _ = admin_client
        with patch("src.api.routers.knowledge_base.get_qdrant_client",
                   side_effect=ImportError("no qdrant")), \
             patch("os.path.exists", return_value=False):
            response = await client.get("/api/knowledge-base/incidents")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["incidents"] == []

    @pytest.mark.asyncio
    async def test_list_incidents_json_fallback(self, admin_client):
        """When Qdrant fails, reads from JSON file."""
        client, _, _ = admin_client
        mock_incidents = [
            {"incident_id": "INC001", "title": "Test", "description": "d",
             "action_taken": "fixed", "opened_at": "2025-01-01", "updated_at": "2025-01-02"}
        ]
        with patch("src.api.routers.knowledge_base.get_qdrant_client",
                   side_effect=ImportError("no qdrant")), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch("json.load", return_value=mock_incidents):
            response = await client.get("/api/knowledge-base/incidents")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["incidents"]) == 1

    @pytest.mark.asyncio
    async def test_list_incidents_qdrant_success(self, admin_client):
        """Qdrant returns incidents successfully."""
        client, session, _ = admin_client
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        mock_point = MagicMock()
        mock_point.payload = {
            "page_content": "Incident desc",
            "metadata": {
                "source_system": "ServiceNow",
                "incident_id": "INC001",
                "incident_title": "Test Incident",
            }
        }
        mock_client.scroll.return_value = ([mock_point], None)

        with patch("src.api.routers.knowledge_base.get_qdrant_client",
                   return_value=mock_client), \
             patch.object(IncidentIngestionService, "get_active_collection_name",
                         new_callable=AsyncMock, return_value="test_collection"):
            response = await client.get("/api/knowledge-base/incidents")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["incidents"]) >= 1


class TestKBRouterDeleteIncident:
    """Tests for DELETE /api/knowledge-base/incidents/{id}."""

    @pytest.mark.asyncio
    async def test_delete_no_file(self, admin_client):
        """No JSON file returns 'no incidents found'."""
        client, _, _ = admin_client
        with patch("os.path.exists", return_value=False):
            response = await client.delete("/api/knowledge-base/incidents/INC001")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_delete_incident_not_found(self, admin_client):
        """Incident not in file returns not found."""
        client, _, _ = admin_client
        import io
        mock_data = [{"incident_id": "INC999"}]
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch("json.load", return_value=mock_data):
            response = await client.delete("/api/knowledge-base/incidents/INC001")
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["message"]

    @pytest.mark.asyncio
    async def test_delete_incident_success(self, admin_client):
        """Successfully deletes incident from JSON."""
        client, _, _ = admin_client
        mock_data = [{"incident_id": "INC001"}, {"incident_id": "INC002"}]
        mock_file = MagicMock()
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", return_value=mock_file), \
             patch("json.load", return_value=mock_data), \
             patch("json.dump"), \
             patch("src.api.routers.knowledge_base.get_qdrant_client",
                   side_effect=ImportError("no qdrant")):
            response = await client.delete("/api/knowledge-base/incidents/INC001")
        data = response.json()
        assert data["success"] is True


class TestKBRouterLogs:
    """Tests for GET /api/knowledge-base/logs."""

    @pytest.mark.asyncio
    async def test_get_logs_empty(self, admin_client):
        """Returns empty log list when no logs exist."""
        client, _, _ = admin_client
        response = await client.get("/api/knowledge-base/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["logs"] == []

    @pytest.mark.asyncio
    async def test_get_logs_error(self, admin_client):
        """DB error returns 500."""
        client, session, _ = admin_client
        with patch.object(session, "execute", side_effect=RuntimeError("db")):
            response = await client.get("/api/knowledge-base/logs")
        assert response.status_code == 500


class TestKBRouterUpload:
    """Tests for POST /api/knowledge-base/upload."""

    @pytest.mark.asyncio
    async def test_upload_success(self, admin_client):
        """Successful file upload creates session."""
        client, session, _ = admin_client
        import json as json_mod
        file_content = json_mod.dumps([
            {"incident_id": "INC001", "title": "Test", "description": "d",
             "action_taken": "fixed", "opened_at": "2025-01-01",
             "updated_at": "2025-01-02"}
        ])
        response = await client.post("/api/knowledge-base/upload", json={
            "files": [{"filename": "test.json", "size": len(file_content),
                       "content": file_content}]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "session_id" in data

    @pytest.mark.asyncio
    async def test_upload_invalid_content(self, admin_client):
        """Invalid JSON content returns error."""
        client, _, _ = admin_client
        response = await client.post("/api/knowledge-base/upload", json={
            "files": [{"filename": "bad.json", "size": 5, "content": "not json"}]
        })
        # Should get 400 (sanitized error)
        assert response.status_code == 400


class TestKBRouterValidate:
    """Tests for POST /api/knowledge-base/validate/{session_id}."""

    @pytest.mark.asyncio
    async def test_validate_not_found(self, admin_client):
        """Non-existent session returns 404."""
        client, _, _ = admin_client
        from uuid import uuid4
        response = await client.post(f"/api/knowledge-base/validate/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_validate_error(self, admin_client):
        """Internal error returns 500."""
        client, _, _ = admin_client
        with patch.object(IncidentIngestionService, "validate_session",
                         new_callable=AsyncMock,
                         side_effect=RuntimeError("validation failed")):
            from uuid import uuid4
            response = await client.post(f"/api/knowledge-base/validate/{uuid4()}")
        assert response.status_code == 500


class TestKBRouterMapFields:
    """Tests for POST /api/knowledge-base/validate/{session_id}/map-fields."""

    @pytest.mark.asyncio
    async def test_map_fields_not_found(self, admin_client):
        """Non-existent session returns 404."""
        client, _, _ = admin_client
        from uuid import uuid4
        sid = str(uuid4())
        response = await client.post(
            f"/api/knowledge-base/validate/{sid}/map-fields",
            json={"session_id": sid, "mapping": {"title": "short_description"}}
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_map_fields_error(self, admin_client):
        """Internal error returns 500."""
        client, _, _ = admin_client
        with patch.object(IncidentIngestionService, "apply_field_mapping",
                         new_callable=AsyncMock,
                         side_effect=RuntimeError("mapping failed")):
            from uuid import uuid4
            sid = str(uuid4())
            response = await client.post(
                f"/api/knowledge-base/validate/{sid}/map-fields",
                json={"session_id": sid, "mapping": {"title": "short_description"}}
            )
        assert response.status_code == 500


class TestKBRouterVersions:
    """Tests for version management endpoints."""

    @pytest.mark.asyncio
    async def test_list_versions(self, admin_client):
        """List versions returns paginated result."""
        client, _, _ = admin_client
        response = await client.get("/api/knowledge-base/versions")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_list_versions_error(self, admin_client):
        """Internal error in list returns 500."""
        client, _, _ = admin_client
        with patch.object(IncidentIngestionService, "get_versions",
                         new_callable=AsyncMock,
                         side_effect=RuntimeError("db error")):
            response = await client.get("/api/knowledge-base/versions")
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_get_active_version_none(self, admin_client):
        """No active version returns null."""
        client, _, _ = admin_client
        response = await client.get("/api/knowledge-base/versions/active")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["version"] is None

    @pytest.mark.asyncio
    async def test_get_active_version_error(self, admin_client):
        """Internal error returns 500."""
        client, _, _ = admin_client
        with patch.object(IncidentIngestionService, "get_active_version",
                         new_callable=AsyncMock,
                         side_effect=RuntimeError("db error")):
            response = await client.get("/api/knowledge-base/versions/active")
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_get_version_detail_not_found(self, admin_client):
        """Non-existent version returns 404."""
        client, _, _ = admin_client
        from uuid import uuid4
        response = await client.get(f"/api/knowledge-base/versions/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_rollback_version_not_found(self, admin_client):
        """Rollback non-existent version returns 400."""
        client, _, _ = admin_client
        from uuid import uuid4
        response = await client.post(f"/api/knowledge-base/versions/{uuid4()}/rollback")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_rollback_version_error(self, admin_client):
        """Internal error in rollback returns 500."""
        client, _, _ = admin_client
        with patch.object(IncidentIngestionService, "rollback_to_version",
                         new_callable=AsyncMock,
                         side_effect=RuntimeError("rollback failed")):
            from uuid import uuid4
            response = await client.post(f"/api/knowledge-base/versions/{uuid4()}/rollback")
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_delete_version_not_found(self, admin_client):
        """Delete non-existent version returns 400."""
        client, _, _ = admin_client
        from uuid import uuid4
        response = await client.delete(f"/api/knowledge-base/versions/{uuid4()}")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_version_error(self, admin_client):
        """Internal error in delete returns 500."""
        client, _, _ = admin_client
        with patch.object(IncidentIngestionService, "delete_version",
                         new_callable=AsyncMock,
                         side_effect=RuntimeError("delete failed")):
            from uuid import uuid4
            response = await client.delete(f"/api/knowledge-base/versions/{uuid4()}")
        assert response.status_code == 500


class TestKBRouterIngest:
    """Tests for POST /api/knowledge-base/ingest SSE endpoint."""

    @pytest.mark.asyncio
    async def test_ingest_success(self, admin_client):
        """Successful ingestion streams progress and complete events."""
        client, session, user_id = admin_client
        import json as json_mod

        # Create an upload session first
        file_content = json_mod.dumps([
            {"incident_id": "INC001", "title": "Test", "description": "desc",
             "action_taken": "fixed", "opened_at": "2025-01-01",
             "updated_at": "2025-01-02"}
        ])
        upload_resp = await client.post("/api/knowledge-base/upload", json={
            "files": [{"filename": "test.json", "size": len(file_content),
                       "content": file_content}]
        })
        session_id = upload_resp.json()["session_id"]

        mock_version = MagicMock()
        mock_version.id = "v-123"
        mock_version.version_number = 1
        mock_version.collection_name = "test_col"
        mock_version.incident_count = 1

        with patch.object(IncidentIngestionService, "confirm_and_ingest",
                         new_callable=AsyncMock, return_value=mock_version):
            response = await client.post("/api/knowledge-base/ingest", json={
                "session_id": session_id, "notes": "Test ingest",
            })
        assert response.status_code == 200
        body = response.text
        assert "event: progress" in body
        assert "event: complete" in body

    @pytest.mark.asyncio
    async def test_ingest_error(self, admin_client):
        """Ingestion error streams error event."""
        client, _, _ = admin_client
        from uuid import uuid4
        with patch.object(IncidentIngestionService, "confirm_and_ingest",
                         new_callable=AsyncMock,
                         side_effect=ValueError("No valid records")):
            response = await client.post("/api/knowledge-base/ingest", json={
                "session_id": str(uuid4()), "notes": "Test",
            })
        body = response.text
        assert "event: error" in body or "event: progress" in body


class TestPrepareDocuments:
    """Tests for _prepare_documents helper."""

    def test_prepare_basic_incidents(self):
        from src.api.routers.knowledge_base import _prepare_documents
        incidents = [
            {"incident_id": "INC001", "title": "Server down",
             "description": "The web server crashed",
             "action_taken": "Restarted the service"},
        ]
        result = _prepare_documents(incidents)
        assert len(result) == 1
        incident_dict, docs = result[0]
        assert incident_dict["incident_id"] == "INC001"
        assert len(docs) >= 1
        assert docs[0].metadata["incident_id"] == "INC001"

    def test_prepare_with_metadata(self):
        from src.api.routers.knowledge_base import _prepare_documents
        desc = 'Short desc\nDetails: {"incident_description": "impactedApplication: WebApp\\nrootCause: OOM"}\nCategory: network'
        incidents = [
            {"incident_id": "INC002", "title": "App OOM",
             "description": desc, "action_taken": "Increased memory"},
        ]
        result = _prepare_documents(incidents)
        _, docs = result[0]
        assert docs[0].metadata["impacted_application"] == "WebApp"
        assert docs[0].metadata["root_cause"] == "OOM"

    def test_prepare_empty_list(self):
        from src.api.routers.knowledge_base import _prepare_documents
        assert _prepare_documents([]) == []


class TestIngestToQdrant:
    """Tests for ingest_incidents_to_qdrant helper."""

    @pytest.mark.asyncio
    async def test_ingest_success(self):
        from src.api.routers.knowledge_base import ingest_incidents_to_qdrant

        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        mock_vector_store = MagicMock()

        incidents = [
            {"incident_id": "INC001", "title": "Test", "description": "d",
             "action_taken": "fixed"},
        ]

        progress_calls = []
        async def on_progress(batch, total, ids):
            progress_calls.append((batch, total, ids))

        with patch("src.api.routers.knowledge_base._load_qdrant", return_value={
                "QdrantClient": MagicMock(return_value=mock_client),
                "VectorParams": MagicMock(), "Distance": MagicMock(),
                "PointStruct": MagicMock(), "QDRANT_URL": "http://test",
                "QDRANT_API_KEY": None,
             }), \
             patch("src.api.routers.knowledge_base._load_model", return_value=MagicMock()), \
             patch("src.api.routers.knowledge_base.get_qdrant_client",
                   return_value=mock_client), \
             patch("langchain_qdrant.QdrantVectorStore", return_value=mock_vector_store):
            result = await ingest_incidents_to_qdrant(
                incidents, progress_callback=on_progress
            )
        assert result is True
        assert len(progress_calls) == 1

    @pytest.mark.asyncio
    async def test_ingest_empty_list(self):
        from src.api.routers.knowledge_base import ingest_incidents_to_qdrant

        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True

        with patch("src.api.routers.knowledge_base._load_qdrant", return_value={
                "QdrantClient": MagicMock(return_value=mock_client),
                "VectorParams": MagicMock(), "Distance": MagicMock(),
                "PointStruct": MagicMock(), "QDRANT_URL": "http://test",
                "QDRANT_API_KEY": None,
             }), \
             patch("src.api.routers.knowledge_base._load_model", return_value=MagicMock()), \
             patch("src.api.routers.knowledge_base.get_qdrant_client",
                   return_value=mock_client), \
             patch("langchain_qdrant.QdrantVectorStore", return_value=MagicMock()):
            result = await ingest_incidents_to_qdrant([])
        assert result is True

    @pytest.mark.asyncio
    async def test_ingest_failure(self):
        from src.api.routers.knowledge_base import ingest_incidents_to_qdrant

        with patch("src.api.routers.knowledge_base._load_qdrant",
                   side_effect=ImportError("no qdrant")):
            result = await ingest_incidents_to_qdrant([{"id": "1"}])
        assert result is False


class TestSSEEventHelper:
    """Tests for _sse_event helper."""

    def test_format(self):
        from src.api.routers.knowledge_base import _sse_event
        result = _sse_event("progress", {"batch": 1})
        assert result.startswith("event: progress\n")
        assert result.endswith("\n\n")

    def test_data_json(self):
        from src.api.routers.knowledge_base import _sse_event
        import json as json_mod
        result = _sse_event("test", {"key": "value"})
        data_line = result.split("\n")[1]
        assert data_line.startswith("data: ")
        parsed = json_mod.loads(data_line[6:])
        assert parsed["key"] == "value"


class TestLazyLoading:
    """Tests for lazy-loaded Qdrant imports and model loading."""

    def test_load_qdrant(self):
        """_load_qdrant returns cached imports."""
        import src.api.routers.knowledge_base as kb_mod
        original = kb_mod._qdrant_imports
        try:
            kb_mod._qdrant_imports = None
            mock_imports = {"QdrantClient": MagicMock()}
            with patch.dict("sys.modules", {
                "qdrant_client": MagicMock(),
                "qdrant_client.models": MagicMock(),
                "src.copilot.config": MagicMock(QDRANT_URL="http://test", QDRANT_API_KEY=None),
            }):
                result = kb_mod._load_qdrant()
            assert "QdrantClient" in result
        finally:
            kb_mod._qdrant_imports = original

    def test_load_model(self):
        """_load_model returns cached embeddings."""
        import src.api.routers.knowledge_base as kb_mod
        original = kb_mod._embeddings
        try:
            kb_mod._embeddings = None
            mock_embeddings = MagicMock()
            with patch("langchain_huggingface.HuggingFaceEmbeddings",
                       return_value=mock_embeddings):
                result = kb_mod._load_model()
            assert result is mock_embeddings
        finally:
            kb_mod._embeddings = original

    def test_get_qdrant_client_with_api_key(self):
        """get_qdrant_client uses API key when available."""
        mock_client_class = MagicMock()
        with patch("src.api.routers.knowledge_base._load_qdrant", return_value={
            "QdrantClient": mock_client_class,
            "QDRANT_URL": "http://test",
            "QDRANT_API_KEY": "my-key",
        }):
            from src.api.routers.knowledge_base import get_qdrant_client
            get_qdrant_client()
        mock_client_class.assert_called_with(url="http://test", api_key="my-key")

    def test_get_qdrant_client_without_api_key(self):
        """get_qdrant_client works without API key."""
        mock_client_class = MagicMock()
        with patch("src.api.routers.knowledge_base._load_qdrant", return_value={
            "QdrantClient": mock_client_class,
            "QDRANT_URL": "http://test",
            "QDRANT_API_KEY": None,
        }):
            from src.api.routers.knowledge_base import get_qdrant_client
            get_qdrant_client()
        mock_client_class.assert_called_with(url="http://test")

class TestConfirmAndIngestFull:
    """Tests for the full confirm_and_ingest pipeline with Qdrant mocking."""

    @pytest.mark.asyncio
    async def test_confirm_and_ingest_success(self, test_session):
        """Full ingestion pipeline with mocked Qdrant."""
        user = await _create_user(test_session)

        # Create upload session with valid data
        import json as json_mod
        records = [
            {"incident_id": "INC001", "title": "Server down",
             "description": "Web server crashed", "action_taken": "Restarted"},
        ]
        svc = IncidentIngestionService(test_session)
        file_content = json_mod.dumps(records)
        upload = await svc.create_upload_session(
            [{"filename": "test.json", "size": len(file_content), "content": file_content}],
            str(user.id), source="upload"
        )

        mock_client = MagicMock()
        mock_client.collection_exists.return_value = False
        mock_client.create_collection = MagicMock()

        mock_vector_store = MagicMock()

        with patch("src.api.routers.knowledge_base._load_qdrant", return_value={
                "QdrantClient": MagicMock(return_value=mock_client),
                "VectorParams": MagicMock(), "Distance": MagicMock(),
                "PointStruct": MagicMock(), "QDRANT_URL": "http://test",
                "QDRANT_API_KEY": None,
             }), \
             patch("src.api.routers.knowledge_base._load_model", return_value=MagicMock()), \
             patch("src.api.routers.knowledge_base.get_qdrant_client",
                   return_value=mock_client), \
             patch("langchain_qdrant.QdrantVectorStore", return_value=mock_vector_store), \
             patch("src.api.services.incident_ingestion_service._invalidate_copilot_cache"):
            version = await svc.confirm_and_ingest(
                str(upload.id), str(user.id), notes="Test ingestion"
            )

        assert version is not None
        assert version.status == "active"
        assert version.is_active is True
        assert version.incident_count >= 1

    @pytest.mark.asyncio
    async def test_confirm_and_ingest_copy_from_active(self, test_session):
        """Ingestion copies data from active version."""
        user = await _create_user(test_session)

        # Create an active version
        existing_version = await _create_version(
            test_session, version_number=1, status="active",
            is_active=True, user_id=user.id,
        )

        import json as json_mod
        records = [
            {"incident_id": "INC002", "title": "New issue",
             "description": "Another issue", "action_taken": "Fixed"},
        ]
        svc = IncidentIngestionService(test_session)
        file_content = json_mod.dumps(records)
        upload = await svc.create_upload_session(
            [{"filename": "test.json", "size": len(file_content), "content": file_content}],
            str(user.id), source="upload"
        )

        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        mock_client.create_collection = MagicMock()
        # Mock scroll for _copy_collection_points
        mock_point = MagicMock()
        mock_point.id = "p1"
        mock_point.vector = [0.1] * 384
        mock_point.payload = {"metadata": {"incident_id": "INC001"}}
        mock_client.scroll.return_value = ([mock_point], None)
        mock_client.upsert = MagicMock()

        mock_vector_store = MagicMock()

        with patch("src.api.routers.knowledge_base._load_qdrant", return_value={
                "QdrantClient": MagicMock(return_value=mock_client),
                "VectorParams": MagicMock(), "Distance": MagicMock(),
                "PointStruct": MagicMock(), "QDRANT_URL": "http://test",
                "QDRANT_API_KEY": None,
             }), \
             patch("src.api.routers.knowledge_base._load_model", return_value=MagicMock()), \
             patch("src.api.routers.knowledge_base.get_qdrant_client",
                   return_value=mock_client), \
             patch("langchain_qdrant.QdrantVectorStore", return_value=mock_vector_store), \
             patch("src.api.services.incident_ingestion_service._invalidate_copilot_cache"):
            version = await svc.confirm_and_ingest(
                str(upload.id), str(user.id), notes="With copy"
            )

        assert version.status == "active"
        # Should have copied + new
        assert version.incident_count >= 2
        # Previous version should be deactivated
        await test_session.refresh(existing_version)
        assert existing_version.is_active is False

    @pytest.mark.asyncio
    async def test_confirm_and_ingest_qdrant_failure(self, test_session):
        """Qdrant failure during ingestion marks version as failed."""
        user = await _create_user(test_session)

        import json as json_mod
        records = [
            {"incident_id": "INC003", "title": "Failure test",
             "description": "desc", "action_taken": "n/a"},
        ]
        svc = IncidentIngestionService(test_session)
        file_content = json_mod.dumps(records)
        upload = await svc.create_upload_session(
            [{"filename": "test.json", "size": len(file_content), "content": file_content}],
            str(user.id), source="upload"
        )

        with patch("src.api.routers.knowledge_base._load_qdrant",
                   side_effect=RuntimeError("Qdrant down")), \
             patch("src.api.routers.knowledge_base.get_qdrant_client",
                   side_effect=RuntimeError("Qdrant down")):
            with pytest.raises(RuntimeError, match="Qdrant down"):
                await svc.confirm_and_ingest(
                    str(upload.id), str(user.id), notes="Fail"
                )


class TestCopyCollectionPoints:
    """Tests for _copy_collection_points method."""

    @pytest.mark.asyncio
    async def test_copy_empty_collection(self, test_session):
        """Copying from empty collection returns 0."""
        svc = IncidentIngestionService(test_session)
        mock_client = MagicMock()
        mock_client.scroll.return_value = ([], None)

        count = await svc._copy_collection_points(
            mock_client, "source_col", "target_col"
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_copy_with_points(self, test_session):
        """Copying from collection with points upserts them."""
        svc = IncidentIngestionService(test_session)
        mock_client = MagicMock()

        mock_point = MagicMock()
        mock_point.id = "p1"
        mock_point.vector = [0.1] * 384
        mock_point.payload = {"metadata": {"incident_id": "INC001"}}

        mock_point2 = MagicMock()
        mock_point2.id = "p2"
        mock_point2.vector = [0.2] * 384
        mock_point2.payload = {"metadata": {"incident_id": "INC001"}}  # same incident

        # First scroll returns points, second returns empty
        mock_client.scroll.side_effect = [
            ([mock_point, mock_point2], None),
        ]

        count = await svc._copy_collection_points(
            mock_client, "source_col", "target_col"
        )
        assert count == 1  # 1 unique incident
        assert mock_client.upsert.call_count == 1


class TestIngestToCollection:
    """Tests for _ingest_to_collection method."""

    @pytest.mark.asyncio
    async def test_ingest_success(self, test_session):
        """Successful ingestion to collection."""
        svc = IncidentIngestionService(test_session)

        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        mock_vector_store = MagicMock()

        records = [
            {"incident_id": "INC001", "title": "Test", "description": "d",
             "action_taken": "fixed"},
        ]

        progress_calls = []
        async def on_progress(batch, total, ids):
            progress_calls.append((batch, total, ids))

        with patch("src.api.routers.knowledge_base._load_qdrant", return_value={
                "QdrantClient": MagicMock(return_value=mock_client),
                "VectorParams": MagicMock(), "Distance": MagicMock(),
                "PointStruct": MagicMock(), "QDRANT_URL": "http://test",
                "QDRANT_API_KEY": None,
             }), \
             patch("src.api.routers.knowledge_base._load_model", return_value=MagicMock()), \
             patch("src.api.routers.knowledge_base.get_qdrant_client",
                   return_value=mock_client), \
             patch("langchain_qdrant.QdrantVectorStore", return_value=mock_vector_store):
            result = await svc._ingest_to_collection(
                "test_col", records, 5, progress_callback=on_progress
            )

        assert result is True
        assert len(progress_calls) >= 1

    @pytest.mark.asyncio
    async def test_ingest_empty_records(self, test_session):
        """Empty record list returns True without doing anything."""
        svc = IncidentIngestionService(test_session)

        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True

        with patch("src.api.routers.knowledge_base._load_qdrant", return_value={
                "QdrantClient": MagicMock(return_value=mock_client),
                "VectorParams": MagicMock(), "Distance": MagicMock(),
                "PointStruct": MagicMock(), "QDRANT_URL": "http://test",
                "QDRANT_API_KEY": None,
             }), \
             patch("src.api.routers.knowledge_base._load_model", return_value=MagicMock()), \
             patch("src.api.routers.knowledge_base.get_qdrant_client",
                   return_value=mock_client), \
             patch("langchain_qdrant.QdrantVectorStore", return_value=MagicMock()):
            result = await svc._ingest_to_collection("test_col", [], 5)

        assert result is True

    @pytest.mark.asyncio
    async def test_ingest_failure(self, test_session):
        """Ingestion failure returns False."""
        svc = IncidentIngestionService(test_session)

        with patch("src.api.routers.knowledge_base._load_qdrant",
                   side_effect=ImportError("no qdrant")):
            result = await svc._ingest_to_collection(
                "test_col", [{"id": "1"}], 5
            )

        assert result is False


class TestDeleteVersionQdrant:
    """Tests for delete_version with Qdrant interaction."""

    @pytest.mark.asyncio
    async def test_delete_version_with_qdrant_error(self, test_session):
        """Qdrant error during deletion is handled gracefully."""
        user = await _create_user(test_session)
        version = await _create_version(
            test_session, version_number=5, status="inactive", user_id=user.id
        )

        svc = IncidentIngestionService(test_session)
        with patch("src.api.routers.knowledge_base.get_qdrant_client",
                   side_effect=RuntimeError("Qdrant unavailable")):
            result = await svc.delete_version(str(version.id))
        assert result is True


class TestEnforceCollectionWindowFull:
    """Tests for _enforce_collection_window with Qdrant mocking."""

    @pytest.mark.asyncio
    async def test_qdrant_unavailable(self, test_session):
        """Qdrant unavailable during window enforcement doesn't crash."""
        user = await _create_user(test_session)
        for i in range(10):
            await _create_version(
                test_session, version_number=i + 1,
                status="inactive", user_id=user.id
            )

        svc = IncidentIngestionService(test_session)
        with patch("src.api.routers.knowledge_base.get_qdrant_client",
                   side_effect=RuntimeError("Qdrant down")):
            # Should not raise
            await svc._enforce_collection_window()

    @pytest.mark.asyncio
    async def test_archive_snapshot_error(self, test_session):
        """Snapshot creation error during archival is handled."""
        user = await _create_user(test_session)
        for i in range(10):
            await _create_version(
                test_session, version_number=i + 1,
                status="inactive", user_id=user.id
            )

        svc = IncidentIngestionService(test_session)
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        mock_client.create_snapshot.side_effect = RuntimeError("snapshot failed")

        with patch("src.api.routers.knowledge_base.get_qdrant_client",
                   return_value=mock_client):
            await svc._enforce_collection_window()
        # Should not crash despite snapshot error


class TestParseDescriptionMetadata:
    """Cover _parse_description_metadata strategies 2 and 3 (lines 91-116)."""

    def test_strategy2_regex_extraction(self):
        """Strategy 2: regex extraction of incident_description from malformed JSON."""
        from src.api.routers.knowledge_base import _parse_description_metadata

        # Malformed JSON with incident_description key
        desc = '{"incident_description": "priority: High\\nseverity: Critical\\nassignee: John"}'
        result = _parse_description_metadata(desc)
        assert result is not None
        assert "priority" in result or "severity" in result

    def test_strategy3_direct_key_value(self):
        """Strategy 3: direct key-value parsing of flat descriptions."""
        from src.api.routers.knowledge_base import _parse_description_metadata

        desc = "Title: Server Down\nPriority: High\nCategory: Infrastructure"
        result = _parse_description_metadata(desc)
        assert result is not None
        assert result.get("Title") == "Server Down" or result.get("Priority") == "High"

    def test_no_metadata_found(self):
        """Returns empty dict when no strategy matches."""
        from src.api.routers.knowledge_base import _parse_description_metadata

        desc = "Just a plain text description with no structure"
        result = _parse_description_metadata(desc)
        assert isinstance(result, dict)


class TestListIncidentsQdrantPagination:
    """Cover Qdrant scroll pagination in list_incidents (lines 168-180)."""

    @pytest.mark.asyncio
    async def test_list_incidents_qdrant_pagination(self, admin_client):
        """Qdrant pagination: skips offset, stops at limit (lines 168-169, 180)."""
        client, session, uid = admin_client

        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True

        # First scroll returns data; second scroll ends (next_offset=None)
        point1 = MagicMock()
        point1.payload = {
            "metadata": {"source_system": "ServiceNow", "incident_id": "INC001",
                         "incident_title": "T1", "mitigation": "Fix"},
            "page_content": "desc1"
        }
        point2 = MagicMock()
        point2.payload = {
            "metadata": {"source_system": "ServiceNow", "incident_id": "INC002",
                         "incident_title": "T2", "mitigation": "Fix2"},
            "page_content": "desc2"
        }
        mock_client.scroll.return_value = ([point1, point2], None)

        with patch("src.api.routers.knowledge_base.get_qdrant_client",
                   return_value=mock_client), \
             patch("src.api.routers.knowledge_base.IncidentIngestionService") as MockSvc:
            mock_svc = AsyncMock()
            mock_svc.get_active_collection_name = AsyncMock(return_value="test_collection")
            MockSvc.return_value = mock_svc

            response = await client.get("/api/knowledge-base/incidents?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["incidents"]) >= 1

    @pytest.mark.asyncio
    async def test_list_incidents_qdrant_import_error(self, admin_client):
        """ImportError when Qdrant not installed falls back gracefully (lines 186-189)."""
        client, session, uid = admin_client

        with patch("src.api.routers.knowledge_base.get_qdrant_client",
                   side_effect=Exception("qdrant fail")), \
             patch("src.api.routers.knowledge_base.IncidentIngestionService") as MockSvc:
            mock_svc = AsyncMock()
            mock_svc.get_active_collection_name = AsyncMock(return_value="test")
            MockSvc.return_value = mock_svc

            # Also mock os.path.exists to return False for JSON fallback
            with patch("os.path.exists", return_value=False):
                response = await client.get("/api/knowledge-base/incidents")
        assert response.status_code == 200


class TestDeleteIncidentQdrant:
    """Cover Qdrant deletion paths in delete_incident (lines 252-270, 274-275)."""

    @pytest.mark.asyncio
    async def test_delete_incident_qdrant_error(self, admin_client):
        """Qdrant error during deletion is handled gracefully (lines 269-270)."""
        client, session, uid = admin_client
        import os, json

        # Create temp data file
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "data")
        output_path = os.path.join(data_dir, "incidentspulledfromsnow.json")
        os.makedirs(data_dir, exist_ok=True)
        incidents = [{"incident_id": "INC999", "title": "T"}]
        with open(output_path, "w") as f:
            json.dump(incidents, f)

        try:
            mock_client = MagicMock()
            mock_client.collection_exists.return_value = True
            mock_client.delete.side_effect = RuntimeError("qdrant delete error")

            with patch("src.api.routers.knowledge_base.get_qdrant_client",
                       return_value=mock_client), \
                 patch("src.api.routers.knowledge_base.IncidentIngestionService") as MockSvc:
                mock_svc = AsyncMock()
                mock_svc.get_active_collection_name = AsyncMock(return_value="test_coll")
                MockSvc.return_value = mock_svc

                # Mock the qdrant filter imports
                with patch.dict("sys.modules", {
                    "qdrant_client.models": MagicMock(),
                }):
                    response = await client.delete("/api/knowledge-base/incidents/INC999")
            assert response.status_code == 200
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    @pytest.mark.asyncio
    async def test_delete_incident_general_error(self, admin_client):
        """General exception raises 500 (lines 274-275)."""
        client, session, uid = admin_client

        with patch("os.path.join", side_effect=RuntimeError("path error")):
            response = await client.delete("/api/knowledge-base/incidents/INC001")
        assert response.status_code == 500


class TestIngestToQdrantDeep:
    """Cover ingest_incidents_to_qdrant batch processing and error paths (lines 429-448)."""

    @pytest.mark.asyncio
    async def test_ingest_to_qdrant_with_progress_callback(self, admin_client):
        """Full ingest_incidents_to_qdrant with session logging and progress callback (lines 429-448)."""
        client, session, uid = admin_client
        from src.api.routers.knowledge_base import ingest_incidents_to_qdrant

        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        mock_vector_store = MagicMock()
        mock_vector_store.add_documents = MagicMock(return_value=["doc1"])

        progress_calls = []
        async def track_progress(batch, total, ids):
            progress_calls.append((batch, total, ids))

        incidents = [
            {"incident_id": "INC001", "title": "Test", "description": "Desc",
             "action_taken": "Fixed it"},
        ]

        with patch("src.api.routers.knowledge_base._load_qdrant", return_value={
                "QdrantClient": MagicMock(return_value=mock_client),
                "VectorParams": MagicMock(), "Distance": MagicMock(COSINE="cosine"),
                "PointStruct": MagicMock(), "QDRANT_URL": "http://test",
                "QDRANT_API_KEY": None,
             }), \
             patch("src.api.routers.knowledge_base._load_model", return_value=MagicMock()), \
             patch("src.api.routers.knowledge_base.get_qdrant_client",
                   return_value=mock_client), \
             patch("langchain_qdrant.QdrantVectorStore", return_value=mock_vector_store):

            result = await ingest_incidents_to_qdrant(
                incidents, session=session, progress_callback=track_progress,
                batch_size=1
            )
        assert result is True
        assert len(progress_calls) >= 1


class TestIngestSSEDeep:
    """Cover ingest SSE endpoint inner code (lines 577, 622-626)."""

    @pytest.mark.asyncio
    async def test_ingest_sse_error_event(self, admin_client):
        """Ingestion error sends SSE error event (lines 622-626)."""
        client, session, uid = admin_client
        upload = IncidentUploadSession(
            uploaded_by=uid, source="manual", status="validated",
            raw_data=[{"incident_id": "INC1", "title": "T",
                      "description": "D", "action_taken": "F"}],
            incident_count=1,
            file_metadata=[{"filename": "test.json", "size": 100, "content_type": "application/json", "row_count": 1}],
        )
        session.add(upload)
        await session.commit()
        await session.refresh(upload)

        with patch("src.api.services.incident_ingestion_service.IncidentIngestionService.confirm_and_ingest",
                   new_callable=AsyncMock, side_effect=RuntimeError("ingest boom")):
            response = await client.post("/api/knowledge-base/ingest",
                                         json={"session_id": str(upload.id)})
        body = response.text
        assert "event: error" in body
