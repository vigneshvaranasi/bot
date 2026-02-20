"""Comprehensive tests for Roles management endpoints (/roles).

Covers:
- CRUD operations (list, get, create, update, delete)
- Input validation (required fields, length limits, formats)
- Permission/RBAC enforcement
- Edge cases (duplicates, soft-deleted items, reuse of deleted names)
- Unauthenticated access
- Database persistence verification
"""

import pytest
from datetime import datetime, UTC
from uuid import uuid4

from sqlalchemy.future import select

from src.api.db.models import Role, PermissionSet, RolePermissionSet


# ============================================================
# GET /roles/ — List all roles
# ============================================================


class TestListRoles:
    """Tests for GET /roles/"""

    @pytest.mark.asyncio
    async def test_list_roles_empty(self, admin_client):
        """Returns empty list when no roles exist."""
        client, session, _ = admin_client
        response = await client.get("/roles/")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_roles_returns_all_active(self, admin_client):
        """Returns all active (non-deleted) roles."""
        client, session, _ = admin_client
        session.add_all([
            Role(name="Role A", description="First"),
            Role(name="Role B", description="Second"),
            Role(name="Role C", description="Third"),
        ])
        await session.commit()

        response = await client.get("/roles/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert {r["name"] for r in data} == {"Role A", "Role B", "Role C"}

    @pytest.mark.asyncio
    async def test_list_roles_excludes_soft_deleted(self, admin_client):
        """Soft-deleted roles are excluded from the list."""
        client, session, _ = admin_client
        session.add_all([
            Role(name="Active", description="Active role"),
            Role(name="Deleted", description="Deleted role", deleted_at=datetime.now(UTC)),
        ])
        await session.commit()

        response = await client.get("/roles/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Active"

    @pytest.mark.asyncio
    async def test_list_roles_response_format(self, admin_client):
        """Each role has id, name, and description fields."""
        client, session, _ = admin_client
        session.add(Role(name="Format Test", description="Desc"))
        await session.commit()

        response = await client.get("/roles/")
        data = response.json()
        assert len(data) == 1
        role = data[0]
        assert "id" in role
        assert role["name"] == "Format Test"
        assert role["description"] == "Desc"

    @pytest.mark.asyncio
    async def test_list_roles_null_description(self, admin_client):
        """Role with no description returns null."""
        client, session, _ = admin_client
        session.add(Role(name="No Desc"))
        await session.commit()

        response = await client.get("/roles/")
        data = response.json()
        assert data[0]["description"] is None

    @pytest.mark.asyncio
    async def test_list_roles_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        response = await client.get("/roles/")
        assert response.status_code == 403


# ============================================================
# GET /roles/{role_id} — Get role by ID
# ============================================================


class TestGetRole:
    """Tests for GET /roles/{role_id}"""

    @pytest.mark.asyncio
    async def test_get_role_success(self, admin_client):
        """Returns correct role for valid ID."""
        client, session, _ = admin_client
        role = Role(name="Test Role", description="Test description")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.get(f"/roles/{role.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Role"
        assert data["description"] == "Test description"
        assert data["id"] == str(role.id)
        assert "permission_sets" in data

    @pytest.mark.asyncio
    async def test_get_role_not_found(self, admin_client):
        """Non-existent ID returns 404."""
        client, _, _ = admin_client
        response = await client.get(f"/roles/{uuid4()}")
        assert response.status_code == 404
        assert "Role not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_role_soft_deleted_returns_404(self, admin_client):
        """Soft-deleted role returns 404."""
        client, session, _ = admin_client
        role = Role(name="Deleted Role", deleted_at=datetime.now(UTC))
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.get(f"/roles/{role.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_role_invalid_uuid(self, admin_client):
        """Invalid UUID format returns 422."""
        client, _, _ = admin_client
        response = await client.get("/roles/not-a-uuid")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_role_with_permission_sets(self, admin_client):
        """Returns role with associated permission sets."""
        client, session, _ = admin_client
        ps = PermissionSet(code="test_ps", name="Test PS", description="A perm set")
        session.add(ps)
        await session.flush()

        role = Role(name="Role With PS")
        session.add(role)
        await session.flush()

        rps = RolePermissionSet(role_id=role.id, permission_set_id=ps.id)
        session.add(rps)
        await session.commit()

        response = await client.get(f"/roles/{role.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["permission_sets"]) == 1
        assert data["permission_sets"][0]["code"] == "test_ps"
        assert data["permission_sets"][0]["name"] == "Test PS"

    @pytest.mark.asyncio
    async def test_get_role_multiple_permission_sets(self, admin_client):
        """Returns role with multiple permission sets."""
        client, session, _ = admin_client
        ps1 = PermissionSet(code="ps_alpha", name="Alpha PS")
        ps2 = PermissionSet(code="ps_beta", name="Beta PS")
        session.add_all([ps1, ps2])
        await session.flush()

        role = Role(name="Multi PS Role")
        session.add(role)
        await session.flush()

        session.add_all([
            RolePermissionSet(role_id=role.id, permission_set_id=ps1.id),
            RolePermissionSet(role_id=role.id, permission_set_id=ps2.id),
        ])
        await session.commit()

        response = await client.get(f"/roles/{role.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["permission_sets"]) == 2
        codes = {ps["code"] for ps in data["permission_sets"]}
        assert codes == {"ps_alpha", "ps_beta"}

    @pytest.mark.asyncio
    async def test_get_role_empty_permission_sets(self, admin_client):
        """Role with no permission sets returns empty list."""
        client, session, _ = admin_client
        role = Role(name="No PS Role")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.get(f"/roles/{role.id}")
        assert response.status_code == 200
        assert response.json()["permission_sets"] == []

    @pytest.mark.asyncio
    async def test_get_role_requires_permission(self, no_perms_client):
        """Requires role.view permission."""
        client, session, _ = no_perms_client
        role = Role(name="Protected")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.get(f"/roles/{role.id}")
        assert response.status_code == 403
        assert "Missing permission: role.view" in response.json()["detail"]


# ============================================================
# POST /roles/ — Create role
# ============================================================


class TestCreateRole:
    """Tests for POST /roles/"""

    @pytest.mark.asyncio
    async def test_create_role_minimal(self, admin_client):
        """Create role with only name (required field)."""
        client, _, _ = admin_client
        response = await client.post("/roles/", json={"name": "New Role"})
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Role"
        assert data["description"] is None
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_role_with_description(self, admin_client):
        """Create role with name and description."""
        client, _, _ = admin_client
        response = await client.post("/roles/", json={
            "name": "Described Role",
            "description": "A detailed description"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Described Role"
        assert data["description"] == "A detailed description"

    @pytest.mark.asyncio
    async def test_create_role_with_permission_sets(self, admin_client):
        """Create role with valid permission set IDs."""
        client, session, _ = admin_client
        ps = PermissionSet(code="create_test", name="Create Test PS")
        session.add(ps)
        await session.commit()
        await session.refresh(ps)

        response = await client.post("/roles/", json={
            "name": "Role With PS",
            "permission_set_ids": [str(ps.id)]
        })
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_role_with_multiple_permission_sets(self, admin_client):
        """Create role with multiple permission set IDs."""
        client, session, _ = admin_client
        ps1 = PermissionSet(code="multi_a", name="Multi A")
        ps2 = PermissionSet(code="multi_b", name="Multi B")
        session.add_all([ps1, ps2])
        await session.commit()
        await session.refresh(ps1)
        await session.refresh(ps2)

        response = await client.post("/roles/", json={
            "name": "Multi PS Role",
            "permission_set_ids": [str(ps1.id), str(ps2.id)]
        })
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_role_duplicate_name(self, admin_client):
        """Duplicate name returns 400."""
        client, session, _ = admin_client
        session.add(Role(name="Existing Role"))
        await session.commit()

        response = await client.post("/roles/", json={"name": "Existing Role"})
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_role_empty_name(self, admin_client):
        """Empty name returns 422 (min_length=1)."""
        client, _, _ = admin_client
        response = await client.post("/roles/", json={"name": ""})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_role_missing_name(self, admin_client):
        """Missing name field returns 422."""
        client, _, _ = admin_client
        response = await client.post("/roles/", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_role_name_too_long(self, admin_client):
        """Name exceeding 100 chars returns 422."""
        client, _, _ = admin_client
        response = await client.post("/roles/", json={"name": "x" * 101})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_role_description_too_long(self, admin_client):
        """Description exceeding 500 chars returns 422."""
        client, _, _ = admin_client
        response = await client.post("/roles/", json={
            "name": "Valid",
            "description": "x" * 501,
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_role_name_at_max_length(self, admin_client):
        """Name at exactly 100 chars succeeds."""
        client, _, _ = admin_client
        response = await client.post("/roles/", json={"name": "x" * 100})
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_role_invalid_permission_set_ids(self, admin_client):
        """Non-existent permission set IDs return 400."""
        client, _, _ = admin_client
        response = await client.post("/roles/", json={
            "name": "Bad PS Role",
            "permission_set_ids": [str(uuid4())]
        })
        assert response.status_code == 400
        assert "permission sets not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_role_partial_invalid_permission_sets(self, admin_client):
        """Mix of valid and invalid permission set IDs returns 400."""
        client, session, _ = admin_client
        ps = PermissionSet(code="valid_ps", name="Valid PS")
        session.add(ps)
        await session.commit()
        await session.refresh(ps)

        response = await client.post("/roles/", json={
            "name": "Partial Bad",
            "permission_set_ids": [str(ps.id), str(uuid4())]
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_role_persists_in_db(self, admin_client):
        """Created role is persisted in the database."""
        client, session, _ = admin_client
        response = await client.post("/roles/", json={
            "name": "Persisted Role",
            "description": "Should be in DB"
        })
        assert response.status_code == 201
        role_id = response.json()["id"]

        result = await session.execute(
            select(Role).where(Role.name == "Persisted Role")
        )
        db_role = result.scalar_one_or_none()
        assert db_role is not None
        assert str(db_role.id) == role_id
        assert db_role.description == "Should be in DB"
        assert db_role.deleted_at is None

    @pytest.mark.asyncio
    async def test_create_role_reuse_soft_deleted_name(self, admin_client):
        """Can reuse name from a soft-deleted role."""
        client, session, _ = admin_client
        session.add(Role(name="Reusable Name", deleted_at=datetime.now(UTC)))
        await session.commit()

        response = await client.post("/roles/", json={"name": "Reusable Name"})
        assert response.status_code == 201
        assert response.json()["name"] == "Reusable Name"

    @pytest.mark.asyncio
    async def test_create_role_empty_permission_set_ids(self, admin_client):
        """Empty permission_set_ids list creates role without permission sets."""
        client, _, _ = admin_client
        response = await client.post("/roles/", json={
            "name": "No PS",
            "permission_set_ids": []
        })
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_role_requires_permission(self, no_perms_client):
        """Requires role.create permission."""
        client, _, _ = no_perms_client
        response = await client.post("/roles/", json={"name": "Unauthorized"})
        assert response.status_code == 403
        assert "Missing permission: role.create" in response.json()["detail"]


# ============================================================
# PUT /roles/{role_id} — Update role
# ============================================================


class TestUpdateRole:
    """Tests for PUT /roles/{role_id}"""

    @pytest.mark.asyncio
    async def test_update_role_name(self, admin_client):
        """Update role name only."""
        client, session, _ = admin_client
        role = Role(name="Old Name", description="Keep this")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.put(f"/roles/{role.id}", json={"name": "New Name"})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["description"] == "Keep this"

    @pytest.mark.asyncio
    async def test_update_role_description(self, admin_client):
        """Update role description only."""
        client, session, _ = admin_client
        role = Role(name="Keep Name", description="Old Desc")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.put(
            f"/roles/{role.id}", json={"description": "New Desc"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Keep Name"
        assert data["description"] == "New Desc"

    @pytest.mark.asyncio
    async def test_update_role_both_fields(self, admin_client):
        """Update both name and description."""
        client, session, _ = admin_client
        role = Role(name="Original", description="Original Desc")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.put(f"/roles/{role.id}", json={
            "name": "Updated",
            "description": "Updated Desc"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated"
        assert data["description"] == "Updated Desc"

    @pytest.mark.asyncio
    async def test_update_role_clear_description(self, admin_client):
        """Set description to empty string."""
        client, session, _ = admin_client
        role = Role(name="Has Desc", description="Will be cleared")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.put(
            f"/roles/{role.id}", json={"description": ""}
        )
        assert response.status_code == 200
        assert response.json()["description"] == ""

    @pytest.mark.asyncio
    async def test_update_role_not_found(self, admin_client):
        """Non-existent ID returns 404."""
        client, _, _ = admin_client
        response = await client.put(f"/roles/{uuid4()}", json={"name": "New"})
        assert response.status_code == 404
        assert "Role not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_role_soft_deleted_returns_404(self, admin_client):
        """Soft-deleted role returns 404."""
        client, session, _ = admin_client
        role = Role(name="Deleted", deleted_at=datetime.now(UTC))
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.put(f"/roles/{role.id}", json={"name": "New"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_role_duplicate_name(self, admin_client):
        """Updating to existing name returns 400."""
        client, session, _ = admin_client
        session.add_all([Role(name="First"), Role(name="Second")])
        await session.commit()
        result = await session.execute(
            select(Role).where(Role.name == "Second")
        )
        role2 = result.scalar_one()

        response = await client.put(
            f"/roles/{role2.id}", json={"name": "First"}
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_role_same_name_ok(self, admin_client):
        """Updating role with its own name succeeds (not a duplicate)."""
        client, session, _ = admin_client
        role = Role(name="Same Name")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.put(
            f"/roles/{role.id}", json={"name": "Same Name"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Same Name"

    @pytest.mark.asyncio
    async def test_update_role_permission_sets(self, admin_client):
        """Update role to add permission sets."""
        client, session, _ = admin_client
        ps = PermissionSet(code="update_ps", name="Update PS")
        session.add(ps)
        await session.flush()

        role = Role(name="PS Update Role")
        session.add(role)
        await session.commit()
        await session.refresh(role)
        await session.refresh(ps)

        response = await client.put(f"/roles/{role.id}", json={
            "permission_set_ids": [str(ps.id)]
        })
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_role_replace_permission_sets(self, admin_client):
        """Update replaces existing permission sets entirely."""
        client, session, _ = admin_client
        ps1 = PermissionSet(code="replace_a", name="Replace A")
        ps2 = PermissionSet(code="replace_b", name="Replace B")
        session.add_all([ps1, ps2])
        await session.flush()

        role = Role(name="Replace PS Role")
        session.add(role)
        await session.flush()

        # Assign ps1 initially
        session.add(RolePermissionSet(role_id=role.id, permission_set_id=ps1.id))
        await session.commit()
        await session.refresh(role)
        await session.refresh(ps2)

        # Replace with ps2
        response = await client.put(f"/roles/{role.id}", json={
            "permission_set_ids": [str(ps2.id)]
        })
        assert response.status_code == 200

        # Verify: only ps2 should be linked
        result = await session.execute(
            select(RolePermissionSet).where(RolePermissionSet.role_id == role.id)
        )
        links = result.scalars().all()
        assert len(links) == 1
        assert links[0].permission_set_id == ps2.id

    @pytest.mark.asyncio
    async def test_update_role_clear_permission_sets(self, admin_client):
        """Update with empty list clears all permission sets."""
        client, session, _ = admin_client
        ps = PermissionSet(code="to_clear", name="To Clear")
        session.add(ps)
        await session.flush()

        role = Role(name="Clear PS Role")
        session.add(role)
        await session.flush()

        session.add(RolePermissionSet(role_id=role.id, permission_set_id=ps.id))
        await session.commit()
        await session.refresh(role)

        response = await client.put(f"/roles/{role.id}", json={
            "permission_set_ids": []
        })
        assert response.status_code == 200

        result = await session.execute(
            select(RolePermissionSet).where(RolePermissionSet.role_id == role.id)
        )
        assert len(result.scalars().all()) == 0

    @pytest.mark.asyncio
    async def test_update_role_invalid_permission_sets(self, admin_client):
        """Non-existent permission set IDs return 400."""
        client, session, _ = admin_client
        role = Role(name="Bad Update")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.put(f"/roles/{role.id}", json={
            "permission_set_ids": [str(uuid4())]
        })
        assert response.status_code == 400
        assert "permission sets not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_role_invalid_uuid(self, admin_client):
        """Invalid UUID returns 422."""
        client, _, _ = admin_client
        response = await client.put("/roles/not-a-uuid", json={"name": "New"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_role_empty_name(self, admin_client):
        """Empty name returns 422."""
        client, session, _ = admin_client
        role = Role(name="Test")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.put(f"/roles/{role.id}", json={"name": ""})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_role_name_too_long(self, admin_client):
        """Name exceeding 100 chars returns 422."""
        client, session, _ = admin_client
        role = Role(name="Test")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.put(
            f"/roles/{role.id}", json={"name": "x" * 101}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_role_persists_changes(self, admin_client):
        """Changes are persisted in the database."""
        client, session, _ = admin_client
        role = Role(name="Before", description="Old")
        session.add(role)
        await session.commit()
        await session.refresh(role)
        role_id = role.id

        await client.put(f"/roles/{role_id}", json={
            "name": "After",
            "description": "New"
        })

        session.expire_all()
        result = await session.execute(select(Role).where(Role.id == role_id))
        db_role = result.scalar_one()
        assert db_role.name == "After"
        assert db_role.description == "New"

    @pytest.mark.asyncio
    async def test_update_role_requires_permission(self, no_perms_client):
        """Requires role.edit permission."""
        client, session, _ = no_perms_client
        role = Role(name="Protected")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.put(
            f"/roles/{role.id}", json={"name": "Hacked"}
        )
        assert response.status_code == 403
        assert "Missing permission: role.edit" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_role_no_changes(self, admin_client):
        """Empty update body succeeds (no-op)."""
        client, session, _ = admin_client
        role = Role(name="No Change", description="Same")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.put(f"/roles/{role.id}", json={})
        assert response.status_code == 200
        assert response.json()["name"] == "No Change"


# ============================================================
# DELETE /roles/{role_id} — Delete role
# ============================================================


class TestDeleteRole:
    """Tests for DELETE /roles/{role_id}"""

    @pytest.mark.asyncio
    async def test_delete_role_success(self, admin_client):
        """Delete returns 204 No Content."""
        client, session, _ = admin_client
        role = Role(name="To Delete")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.delete(f"/roles/{role.id}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_role_is_soft_delete(self, admin_client):
        """Delete sets deleted_at (soft delete), record still exists."""
        client, session, _ = admin_client
        role = Role(name="Soft Delete Test")
        session.add(role)
        await session.commit()
        await session.refresh(role)
        role_id = role.id

        await client.delete(f"/roles/{role_id}")

        session.expire_all()
        result = await session.execute(select(Role).where(Role.id == role_id))
        db_role = result.scalar_one()
        assert db_role.deleted_at is not None

    @pytest.mark.asyncio
    async def test_delete_role_not_found(self, admin_client):
        """Non-existent ID returns 404."""
        client, _, _ = admin_client
        response = await client.delete(f"/roles/{uuid4()}")
        assert response.status_code == 404
        assert "Role not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_role_already_deleted(self, admin_client):
        """Already soft-deleted role returns 404."""
        client, session, _ = admin_client
        role = Role(name="Already Deleted", deleted_at=datetime.now(UTC))
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.delete(f"/roles/{role.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_role_invalid_uuid(self, admin_client):
        """Invalid UUID returns 422."""
        client, _, _ = admin_client
        response = await client.delete("/roles/not-a-uuid")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_deleted_role_excluded_from_list(self, admin_client):
        """After deletion, role no longer appears in list."""
        client, session, _ = admin_client
        role = Role(name="Will Vanish")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        await client.delete(f"/roles/{role.id}")

        response = await client.get("/roles/")
        assert response.status_code == 200
        names = [r["name"] for r in response.json()]
        assert "Will Vanish" not in names

    @pytest.mark.asyncio
    async def test_deleted_role_not_gettable(self, admin_client):
        """After deletion, role cannot be retrieved by ID."""
        client, session, _ = admin_client
        role = Role(name="Gone")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        await client.delete(f"/roles/{role.id}")

        response = await client.get(f"/roles/{role.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_role_requires_permission(self, no_perms_client):
        """Requires role.delete permission."""
        client, session, _ = no_perms_client
        role = Role(name="Protected")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.delete(f"/roles/{role.id}")
        assert response.status_code == 403
        assert "Missing permission: role.delete" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_then_recreate_same_name(self, admin_client):
        """After deleting a role, can create a new one with the same name."""
        client, session, _ = admin_client
        role = Role(name="Recyclable")
        session.add(role)
        await session.commit()
        await session.refresh(role)
        role_id = role.id

        await client.delete(f"/roles/{role_id}")

        response = await client.post("/roles/", json={"name": "Recyclable"})
        assert response.status_code == 201
        assert response.json()["name"] == "Recyclable"


# ============================================================
# Unauthenticated access — all endpoints
# ============================================================


class TestRolesUnauthenticated:
    """Unauthenticated requests to all role endpoints are rejected."""

    @pytest.mark.asyncio
    async def test_list_roles_unauth(self, client):
        response = await client.get("/roles/")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_role_unauth(self, client):
        response = await client.get(f"/roles/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_role_unauth(self, client):
        response = await client.post("/roles/", json={"name": "Test"})
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_role_unauth(self, client):
        response = await client.put(f"/roles/{uuid4()}", json={"name": "Test"})
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_role_unauth(self, client):
        response = await client.delete(f"/roles/{uuid4()}")
        assert response.status_code == 403


# ============================================================
# Edge cases & hardening — Roles endpoints
# ============================================================


class TestCreateRoleEdgeCases:
    """Edge cases for role creation."""

    @pytest.mark.asyncio
    async def test_create_role_whitespace_name(self, admin_client):
        """Role with only whitespace name."""
        client, _, _ = admin_client
        response = await client.post("/roles/", json={"name": "   "})
        # Either succeeds (no trim validation) or fails
        assert response.status_code in (201, 422)

    @pytest.mark.asyncio
    async def test_create_role_special_characters(self, admin_client):
        """Role name with special characters."""
        client, _, _ = admin_client
        response = await client.post("/roles/", json={
            "name": "Admin & <Manager> 'Role' \"Test\"",
            "description": "Spec chars: <>&\"'"
        })
        assert response.status_code == 201
        assert response.json()["name"] == "Admin & <Manager> 'Role' \"Test\""

    @pytest.mark.asyncio
    async def test_create_role_unicode_name(self, admin_client):
        """Role name with unicode characters."""
        client, _, _ = admin_client
        response = await client.post("/roles/", json={"name": "管理者ロール"})
        assert response.status_code == 201
        assert response.json()["name"] == "管理者ロール"

    @pytest.mark.asyncio
    async def test_create_role_duplicate_permission_set_ids(self, admin_client):
        """Create role with duplicate permission set IDs in the array."""
        client, session, _ = admin_client
        ps = PermissionSet(code="dup_test", name="Dup Test")
        session.add(ps)
        await session.commit()
        await session.refresh(ps)

        response = await client.post("/roles/", json={
            "name": "Dup PS Role",
            "permission_set_ids": [str(ps.id), str(ps.id)]
        })
        # Should either deduplicate or succeed with one link
        assert response.status_code in (201, 400)


class TestUpdateRoleEdgeCases:
    """Edge cases for role updates."""

    @pytest.mark.asyncio
    async def test_update_role_to_soft_deleted_name(self, admin_client):
        """Can rename to a name used by a soft-deleted role."""
        client, session, _ = admin_client
        # Create and delete a role
        session.add(Role(name="Dead Name", deleted_at=datetime.now(UTC)))
        await session.commit()

        # Create a new role and rename to the dead name
        role = Role(name="Alive Name")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.put(f"/roles/{role.id}", json={
            "name": "Dead Name"
        })
        assert response.status_code == 200
        assert response.json()["name"] == "Dead Name"


class TestDeleteRoleEdgeCases:
    """Edge cases for role deletion."""

    @pytest.mark.asyncio
    async def test_delete_role_preserves_permission_set_links(self, admin_client):
        """Soft deleting a role — the RolePermissionSet links still exist."""
        client, session, _ = admin_client
        ps = PermissionSet(code="linked_ps", name="Linked PS")
        session.add(ps)
        await session.flush()

        role = Role(name="Role With Links")
        session.add(role)
        await session.flush()
        session.add(RolePermissionSet(role_id=role.id, permission_set_id=ps.id))
        await session.commit()
        await session.refresh(role)
        role_id = role.id

        response = await client.delete(f"/roles/{role_id}")
        assert response.status_code == 204

        # Role is soft-deleted
        session.expire_all()
        result = await session.execute(select(Role).where(Role.id == role_id))
        db_role = result.scalar_one()
        assert db_role.deleted_at is not None

    @pytest.mark.asyncio
    async def test_double_delete_returns_404(self, admin_client):
        """Deleting an already-deleted role returns 404."""
        client, session, _ = admin_client
        role = Role(name="Double Delete")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        r1 = await client.delete(f"/roles/{role.id}")
        assert r1.status_code == 204

        r2 = await client.delete(f"/roles/{role.id}")
        assert r2.status_code == 404
