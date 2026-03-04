"""Comprehensive tests for Permissions endpoints (/permissions).

Covers:
- List permissions (GET /permissions)
- List categories (GET /permissions/categories)
- Get my permissions (GET /permissions/me)
- Permission Sets CRUD (GET/POST/PUT/DELETE /permissions/sets)
- Roles CRUD (GET/POST/PUT/DELETE /permissions/roles)
- Role effective permissions (GET /permissions/roles/{id}/permissions)
- Permission/RBAC enforcement
- Unauthenticated access
"""

import pytest
from uuid import uuid4

from sqlalchemy.future import select

from src.api.db.models import (
    Permission,
    PermissionSet,
    PermissionSetPermission,
    Role,
    RolePermissionSet,
)


# ============================================================
# Helpers
# ============================================================

def _make_permission(*, code="test.view", name="Test View", category="test", **kw):
    """Build a Permission ORM instance."""
    return Permission(code=code, name=name, category=category, is_system=False, **kw)


def _make_permission_set(*, code="test_set", name="Test Set", **kw):
    """Build a PermissionSet ORM instance."""
    return PermissionSet(code=code, name=name, **kw)


# ============================================================
# GET /permissions — List all permissions
# ============================================================


class TestListPermissions:
    """Tests for GET /permissions"""

    @pytest.mark.asyncio
    async def test_list_permissions_empty(self, admin_client):
        """Returns empty list when no permissions exist."""
        client, _, _ = admin_client
        response = await client.get("/permissions")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert isinstance(data["permissions"], list)

    @pytest.mark.asyncio
    async def test_list_permissions_returns_data(self, admin_client):
        """Returns permissions after adding some."""
        client, session, _ = admin_client
        perm = _make_permission(code="test.list", name="Test List")
        session.add(perm)
        await session.commit()

        response = await client.get("/permissions")
        assert response.status_code == 200
        data = response.json()
        assert len(data["permissions"]) >= 1
        codes = {p["code"] for p in data["permissions"]}
        assert "test.list" in codes

    @pytest.mark.asyncio
    async def test_list_permissions_excludes_deleted(self, admin_client):
        """Soft-deleted permissions are excluded."""
        from datetime import datetime, UTC
        client, session, _ = admin_client
        perm = _make_permission(code="test.deleted", name="Deleted Perm")
        perm.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        session.add(perm)
        await session.commit()

        response = await client.get("/permissions")
        codes = {p["code"] for p in response.json()["permissions"]}
        assert "test.deleted" not in codes

    @pytest.mark.asyncio
    async def test_list_permissions_response_format(self, admin_client):
        """Each permission has expected fields."""
        client, session, _ = admin_client
        session.add(_make_permission(code="test.fmt", name="Format Test", description="Desc"))
        await session.commit()

        response = await client.get("/permissions")
        perm = next(p for p in response.json()["permissions"] if p["code"] == "test.fmt")
        assert "id" in perm
        assert perm["code"] == "test.fmt"
        assert perm["name"] == "Format Test"
        assert perm["category"] == "test"
        assert "is_system" in perm

    @pytest.mark.asyncio
    async def test_list_permissions_requires_permission(self, no_perms_client):
        """Requires permission_set.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/permissions")
        assert response.status_code == 403


# ============================================================
# GET /permissions/categories — List categories
# ============================================================


class TestListCategories:
    """Tests for GET /permissions/categories"""

    @pytest.mark.asyncio
    async def test_list_categories(self, admin_client):
        """Returns unique permission categories."""
        client, session, _ = admin_client
        session.add_all([
            _make_permission(code="cat_a.view", name="Cat A View", category="cat_a"),
            _make_permission(code="cat_b.view", name="Cat B View", category="cat_b"),
        ])
        await session.commit()

        response = await client.get("/permissions/categories")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "cat_a" in data["categories"]
        assert "cat_b" in data["categories"]

    @pytest.mark.asyncio
    async def test_list_categories_requires_permission(self, no_perms_client):
        """Requires permission_set.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/permissions/categories")
        assert response.status_code == 403


# ============================================================
# GET /permissions/me — Current user's permissions
# ============================================================


class TestGetMyPermissions:
    """Tests for GET /permissions/me"""

    @pytest.mark.asyncio
    async def test_get_my_permissions(self, admin_client):
        """Returns user_id and permissions list."""
        client, _, user_id = admin_client
        response = await client.get("/permissions/me")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["user_id"] == str(user_id)
        assert isinstance(data["permissions"], list)

    @pytest.mark.asyncio
    async def test_get_my_permissions_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        response = await client.get("/permissions/me")
        assert response.status_code == 403


# ============================================================
# Permission Sets CRUD
# ============================================================


class TestListPermissionSets:
    """Tests for GET /permissions/sets"""

    @pytest.mark.asyncio
    async def test_list_sets_empty(self, admin_client):
        """Returns empty list when no permission sets exist."""
        client, _, _ = admin_client
        response = await client.get("/permissions/sets")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert isinstance(data["permission_sets"], list)

    @pytest.mark.asyncio
    async def test_list_sets_returns_data(self, admin_client):
        """Returns permission sets with their permissions."""
        client, session, _ = admin_client
        ps = _make_permission_set(code="viewer_set", name="Viewer Set")
        session.add(ps)
        await session.commit()

        response = await client.get("/permissions/sets")
        data = response.json()
        codes = {s["code"] for s in data["permission_sets"]}
        assert "viewer_set" in codes

    @pytest.mark.asyncio
    async def test_list_sets_requires_permission(self, no_perms_client):
        """Requires permission_set.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/permissions/sets")
        assert response.status_code == 403


class TestCreatePermissionSet:
    """Tests for POST /permissions/sets"""

    @pytest.mark.asyncio
    async def test_create_permission_set(self, admin_client):
        """Create a permission set with permissions."""
        client, session, _ = admin_client
        # Seed a permission first
        perm = _make_permission(code="ps.create_test", name="PS Create Test")
        session.add(perm)
        await session.commit()

        response = await client.post("/permissions/sets", json={
            "code": "new_set",
            "name": "New Set",
            "description": "A test set",
            "permission_codes": ["ps.create_test"],
        })
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "new_set"
        assert data["name"] == "New Set"
        assert len(data["permissions"]) == 1

    @pytest.mark.asyncio
    async def test_create_permission_set_empty_permissions(self, admin_client):
        """Create a permission set with no permissions."""
        client, _, _ = admin_client
        response = await client.post("/permissions/sets", json={
            "code": "empty_set",
            "name": "Empty Set",
            "permission_codes": [],
        })
        assert response.status_code == 201
        assert response.json()["permissions"] == []

    @pytest.mark.asyncio
    async def test_create_duplicate_code_fails(self, admin_client):
        """Duplicate permission set code returns 400."""
        client, session, _ = admin_client
        session.add(_make_permission_set(code="dup_set", name="Dup Set"))
        await session.commit()

        response = await client.post("/permissions/sets", json={
            "code": "dup_set",
            "name": "Another",
            "permission_codes": [],
        })
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_requires_permission(self, no_perms_client):
        """Requires permission_set.create permission."""
        client, _, _ = no_perms_client
        response = await client.post("/permissions/sets", json={
            "code": "x", "name": "X", "permission_codes": [],
        })
        assert response.status_code == 403


class TestGetPermissionSet:
    """Tests for GET /permissions/sets/{id}"""

    @pytest.mark.asyncio
    async def test_get_permission_set(self, admin_client):
        """Returns a permission set by ID."""
        client, session, _ = admin_client
        ps = _make_permission_set(code="get_set", name="Get Set")
        session.add(ps)
        await session.commit()
        await session.refresh(ps)

        response = await client.get(f"/permissions/sets/{ps.id}")
        assert response.status_code == 200
        assert response.json()["code"] == "get_set"

    @pytest.mark.asyncio
    async def test_get_permission_set_not_found(self, admin_client):
        """Non-existent permission set returns 404."""
        client, _, _ = admin_client
        response = await client.get(f"/permissions/sets/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_permission_set_requires_permission(self, no_perms_client):
        """Requires permission_set.view permission."""
        client, _, _ = no_perms_client
        response = await client.get(f"/permissions/sets/{uuid4()}")
        assert response.status_code == 403


class TestUpdatePermissionSet:
    """Tests for PUT /permissions/sets/{id}"""

    @pytest.mark.asyncio
    async def test_update_permission_set_name(self, admin_client):
        """Update a permission set's name."""
        client, session, _ = admin_client
        ps = _make_permission_set(code="upd_set", name="Old Name")
        session.add(ps)
        await session.commit()
        await session.refresh(ps)

        response = await client.put(f"/permissions/sets/{ps.id}", json={
            "name": "New Name",
        })
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_update_permission_set_permissions(self, admin_client):
        """Update the permissions in a permission set."""
        client, session, _ = admin_client
        perm1 = _make_permission(code="upd.a", name="Upd A")
        perm2 = _make_permission(code="upd.b", name="Upd B")
        ps = _make_permission_set(code="upd_perms_set", name="Upd Perms Set")
        session.add_all([perm1, perm2, ps])
        await session.commit()
        await session.refresh(ps)

        response = await client.put(f"/permissions/sets/{ps.id}", json={
            "permission_codes": ["upd.a", "upd.b"],
        })
        assert response.status_code == 200
        perm_codes = {p["code"] for p in response.json()["permissions"]}
        assert perm_codes == {"upd.a", "upd.b"}

    @pytest.mark.asyncio
    async def test_update_permission_set_not_found(self, admin_client):
        """Non-existent permission set returns 404."""
        client, _, _ = admin_client
        response = await client.put(f"/permissions/sets/{uuid4()}", json={"name": "X"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_requires_permission(self, no_perms_client):
        """Requires permission_set.edit permission."""
        client, _, _ = no_perms_client
        response = await client.put(f"/permissions/sets/{uuid4()}", json={"name": "X"})
        assert response.status_code == 403


class TestDeletePermissionSet:
    """Tests for DELETE /permissions/sets/{id}"""

    @pytest.mark.asyncio
    async def test_delete_permission_set(self, admin_client):
        """Soft-delete a permission set."""
        client, session, _ = admin_client
        ps = _make_permission_set(code="del_set", name="Del Set")
        session.add(ps)
        await session.commit()
        await session.refresh(ps)

        response = await client.delete(f"/permissions/sets/{ps.id}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_permission_set_excluded_from_list(self, admin_client):
        """Deleted permission set no longer appears in list."""
        client, session, _ = admin_client
        ps = _make_permission_set(code="del_excl", name="Del Excl")
        session.add(ps)
        await session.commit()
        await session.refresh(ps)

        await client.delete(f"/permissions/sets/{ps.id}")

        response = await client.get("/permissions/sets")
        codes = {s["code"] for s in response.json()["permission_sets"]}
        assert "del_excl" not in codes

    @pytest.mark.asyncio
    async def test_delete_permission_set_not_found(self, admin_client):
        """Non-existent permission set returns 404."""
        client, _, _ = admin_client
        response = await client.delete(f"/permissions/sets/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_requires_permission(self, no_perms_client):
        """Requires permission_set.delete permission."""
        client, _, _ = no_perms_client
        response = await client.delete(f"/permissions/sets/{uuid4()}")
        assert response.status_code == 403


# ============================================================
# Roles CRUD (under /permissions/roles)
# ============================================================


class TestPermRolesListCreate:
    """Tests for GET/POST /permissions/roles"""

    @pytest.mark.asyncio
    async def test_list_roles_empty(self, admin_client):
        """Returns empty list when no roles exist."""
        client, _, _ = admin_client
        response = await client.get("/permissions/roles")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert isinstance(data["roles"], list)

    @pytest.mark.asyncio
    async def test_create_role_with_permission_sets(self, admin_client):
        """Create a role linked to a permission set."""
        client, session, _ = admin_client
        ps = _make_permission_set(code="role_ps", name="Role PS")
        session.add(ps)
        await session.commit()

        response = await client.post("/permissions/roles", json={
            "name": "Test Role",
            "description": "A test role",
            "permission_set_codes": ["role_ps"],
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Role"
        assert len(data["permission_sets"]) == 1
        assert data["permission_sets"][0]["code"] == "role_ps"

    @pytest.mark.asyncio
    async def test_create_role_duplicate_name_fails(self, admin_client):
        """Duplicate role name returns 400."""
        client, session, _ = admin_client
        session.add(Role(name="Dup Role"))
        await session.commit()

        response = await client.post("/permissions/roles", json={
            "name": "Dup Role",
            "permission_set_codes": [],
        })
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_role_requires_permission(self, no_perms_client):
        """Requires role.create permission."""
        client, _, _ = no_perms_client
        response = await client.post("/permissions/roles", json={
            "name": "X", "permission_set_codes": [],
        })
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_roles_requires_permission(self, no_perms_client):
        """Requires role.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/permissions/roles")
        assert response.status_code == 403


class TestPermRolesGetUpdateDelete:
    """Tests for GET/PUT/DELETE /permissions/roles/{id}"""

    @pytest.mark.asyncio
    async def test_get_role(self, admin_client):
        """Returns a role by ID."""
        client, session, _ = admin_client
        role = Role(name="Get Role", description="Desc")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.get(f"/permissions/roles/{role.id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Get Role"

    @pytest.mark.asyncio
    async def test_get_role_not_found(self, admin_client):
        """Non-existent role returns 404."""
        client, _, _ = admin_client
        response = await client.get(f"/permissions/roles/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_role_name(self, admin_client):
        """Update a role's name."""
        client, session, _ = admin_client
        role = Role(name="Old Role")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.put(f"/permissions/roles/{role.id}", json={
            "name": "New Role",
        })
        assert response.status_code == 200
        assert response.json()["name"] == "New Role"

    @pytest.mark.asyncio
    async def test_update_role_permission_sets(self, admin_client):
        """Update the permission sets on a role."""
        client, session, _ = admin_client
        ps = _make_permission_set(code="role_upd_ps", name="Role Upd PS")
        role = Role(name="Upd Role PS")
        session.add_all([ps, role])
        await session.commit()
        await session.refresh(role)

        response = await client.put(f"/permissions/roles/{role.id}", json={
            "permission_set_codes": ["role_upd_ps"],
        })
        assert response.status_code == 200
        ps_codes = {p["code"] for p in response.json()["permission_sets"]}
        assert "role_upd_ps" in ps_codes

    @pytest.mark.asyncio
    async def test_update_role_not_found(self, admin_client):
        """Non-existent role returns 404."""
        client, _, _ = admin_client
        response = await client.put(f"/permissions/roles/{uuid4()}", json={"name": "X"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_role(self, admin_client):
        """Soft-delete a role."""
        client, session, _ = admin_client
        role = Role(name="Del Role")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.delete(f"/permissions/roles/{role.id}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_role_excluded_from_list(self, admin_client):
        """Deleted role no longer appears in list."""
        client, session, _ = admin_client
        role = Role(name="Del Excl Role")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        await client.delete(f"/permissions/roles/{role.id}")

        response = await client.get("/permissions/roles")
        names = {r["name"] for r in response.json()["roles"]}
        assert "Del Excl Role" not in names

    @pytest.mark.asyncio
    async def test_delete_role_not_found(self, admin_client):
        """Non-existent role returns 404."""
        client, _, _ = admin_client
        response = await client.delete(f"/permissions/roles/{uuid4()}")
        assert response.status_code == 404


# ============================================================
# GET /permissions/roles/{id}/permissions — Effective perms
# ============================================================


class TestRoleEffectivePermissions:
    """Tests for GET /permissions/roles/{id}/permissions"""

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Raw SQL text() queries pass str(uuid) with dashes but SQLite stores UUIDs as hex without dashes")
    async def test_role_effective_permissions(self, admin_client):
        """Returns all permission codes resolved through permission sets."""
        client, session, _ = admin_client
        # Create permission + permission set + role with all junction rows
        perm = _make_permission(code="eff.view", name="Eff View")
        ps = _make_permission_set(code="eff_set", name="Eff Set")
        role = Role(name="Eff Role")
        session.add_all([perm, ps, role])
        await session.flush()

        session.add(PermissionSetPermission(
            permission_set_id=ps.id, permission_id=perm.id
        ))
        session.add(RolePermissionSet(role_id=role.id, permission_set_id=ps.id))
        await session.commit()

        response = await client.get(f"/permissions/roles/{role.id}/permissions")
        assert response.status_code == 200
        data = response.json()
        assert data["role_name"] == "Eff Role"
        assert "eff.view" in data["permissions"]

    @pytest.mark.asyncio
    async def test_role_effective_permissions_empty(self, admin_client):
        """Role with no permission sets returns empty permissions."""
        client, session, _ = admin_client
        role = Role(name="Empty Eff Role")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.get(f"/permissions/roles/{role.id}/permissions")
        assert response.status_code == 200
        assert response.json()["permissions"] == []

    @pytest.mark.asyncio
    async def test_role_effective_permissions_not_found(self, admin_client):
        """Non-existent role returns 404."""
        client, _, _ = admin_client
        response = await client.get(f"/permissions/roles/{uuid4()}/permissions")
        assert response.status_code == 404


# ============================================================
# Unauthenticated access
# ============================================================


class TestPermissionsUnauthenticated:
    """Unauthenticated requests to permissions endpoints are rejected."""

    @pytest.mark.asyncio
    async def test_list_permissions_unauth(self, client):
        response = await client.get("/permissions")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_categories_unauth(self, client):
        response = await client.get("/permissions/categories")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_my_permissions_unauth(self, client):
        response = await client.get("/permissions/me")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_sets_unauth(self, client):
        response = await client.get("/permissions/sets")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_set_unauth(self, client):
        response = await client.post("/permissions/sets", json={
            "code": "x", "name": "X", "permission_codes": [],
        })
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_set_unauth(self, client):
        response = await client.get(f"/permissions/sets/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_set_unauth(self, client):
        response = await client.put(f"/permissions/sets/{uuid4()}", json={"name": "X"})
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_set_unauth(self, client):
        response = await client.delete(f"/permissions/sets/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_roles_unauth(self, client):
        response = await client.get("/permissions/roles")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_role_unauth(self, client):
        response = await client.post("/permissions/roles", json={
            "name": "X", "permission_set_codes": [],
        })
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_role_unauth(self, client):
        response = await client.get(f"/permissions/roles/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_role_unauth(self, client):
        response = await client.put(f"/permissions/roles/{uuid4()}", json={"name": "X"})
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_role_unauth(self, client):
        response = await client.delete(f"/permissions/roles/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_role_permissions_unauth(self, client):
        response = await client.get(f"/permissions/roles/{uuid4()}/permissions")
        assert response.status_code == 403


# ============================================================
# Edge cases & hardening — Permissions endpoints
# ============================================================


class TestPermissionSetEdgeCases:
    """Edge cases for permission set operations."""

    @pytest.mark.asyncio
    async def test_create_permission_set_invalid_permission_code(self, admin_client):
        """Creating a permission set with non-existent permission code.

        Documents current behavior: endpoint does NOT validate permission
        codes against existing permissions, so it succeeds (201) and silently
        ignores the invalid code.
        """
        client, _, _ = admin_client
        response = await client.post("/permissions/sets", json={
            "code": "bad_perms_set",
            "name": "Bad Perms Set",
            "permission_codes": ["nonexistent.perm"],
        })
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_permission_set_special_chars_in_code(self, admin_client):
        """Permission set code with special characters."""
        client, _, _ = admin_client
        response = await client.post("/permissions/sets", json={
            "code": "set-with_special.chars",
            "name": "Special Set",
            "permission_codes": [],
        })
        assert response.status_code == 201
        assert response.json()["code"] == "set-with_special.chars"

    @pytest.mark.asyncio
    async def test_update_permission_set_replace_permissions(self, admin_client):
        """Updating permissions appends (does not replace) the existing set.

        Documents current behavior: PUT on permission set APPENDS new
        permission codes to existing ones rather than replacing.
        """
        client, session, _ = admin_client
        perm_a = _make_permission(code="replace.a", name="Replace A")
        perm_b = _make_permission(code="replace.b", name="Replace B")
        ps = _make_permission_set(code="replace_set", name="Replace Set")
        session.add_all([perm_a, perm_b, ps])
        await session.flush()
        # Link perm_a initially
        session.add(PermissionSetPermission(permission_set_id=ps.id, permission_id=perm_a.id))
        await session.commit()
        await session.refresh(ps)

        # Update to add perm_b
        response = await client.put(f"/permissions/sets/{ps.id}", json={
            "permission_codes": ["replace.b"],
        })
        assert response.status_code == 200
        codes = {p["code"] for p in response.json()["permissions"]}
        # Both perm_a and perm_b are present (append behavior)
        assert "replace.b" in codes
        assert "replace.a" in codes

    @pytest.mark.asyncio
    async def test_delete_permission_set_already_deleted(self, admin_client):
        """Deleting an already-deleted permission set returns 404."""
        client, session, _ = admin_client
        ps = _make_permission_set(code="double_del", name="Double Del")
        session.add(ps)
        await session.commit()
        await session.refresh(ps)

        r1 = await client.delete(f"/permissions/sets/{ps.id}")
        assert r1.status_code == 204

        r2 = await client.delete(f"/permissions/sets/{ps.id}")
        assert r2.status_code == 404


class TestPermRolesEdgeCases:
    """Edge cases for permission roles operations."""

    @pytest.mark.asyncio
    async def test_create_role_with_invalid_permission_set_code(self, admin_client):
        """Creating role with non-existent permission set code.

        Documents current behavior: endpoint does NOT validate permission
        set codes against existing sets, so it succeeds (201) and silently
        ignores the invalid code.
        """
        client, _, _ = admin_client
        response = await client.post("/permissions/roles", json={
            "name": "Bad PS Role",
            "permission_set_codes": ["nonexistent_ps"],
        })
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_update_role_clear_permission_sets(self, admin_client):
        """Update role with empty permission_set_codes — documents current behavior.

        Current behavior: empty permission_set_codes does NOT remove existing
        links; it's treated as a no-op that keeps existing assignments.
        """
        client, session, _ = admin_client
        ps = _make_permission_set(code="clear_ps", name="Clear PS")
        role = Role(name="Clear Role")
        session.add_all([ps, role])
        await session.flush()
        session.add(RolePermissionSet(role_id=role.id, permission_set_id=ps.id))
        await session.commit()
        await session.refresh(role)

        response = await client.put(f"/permissions/roles/{role.id}", json={
            "permission_set_codes": [],
        })
        assert response.status_code == 200
        # Existing permission sets are preserved (not cleared)
        assert len(response.json()["permission_sets"]) >= 1

    @pytest.mark.asyncio
    async def test_delete_role_then_recreate(self, admin_client):
        """After deleting a role, can create a new one with the same name."""
        client, session, _ = admin_client
        role = Role(name="Recyclable Role")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        await client.delete(f"/permissions/roles/{role.id}")

        response = await client.post("/permissions/roles", json={
            "name": "Recyclable Role",
            "permission_set_codes": [],
        })
        assert response.status_code == 201

from unittest.mock import patch, AsyncMock
from src.api.db.models import User, UserPermission, UserPermissionSet, UserRole
from src.api.services.permission_service import (
    get_user_permissions,
    get_role_permissions,
    get_permission_by_code,
    get_permission_by_id,
    get_permission_set_by_code,
    get_role_by_name,
    get_user_direct_permissions,
    assign_permission_to_user,
    remove_permission_from_user,
    set_user_direct_permissions,
    get_user_direct_permission_sets,
    assign_permission_set_to_user,
    remove_permission_set_from_user,
    set_user_direct_permission_sets,
    get_user_permissions_detailed,
)


async def _create_user(session, user_id=None):
    """Create a User record and return its id."""
    uid = user_id or uuid4()
    user = User(id=uid, email=f"user-{str(uid)[:8]}@test.com", is_active=True)
    session.add(user)
    await session.flush()
    return uid


async def _setup_rbac(session, user_id):
    """Create permission → permission_set → role → user_role chain.

    Returns (perm, perm_set, role) so callers can assert against them.
    """
    perm = Permission(code="svc.action", name="Service Action", category="svc", is_system=False)
    session.add(perm)
    await session.flush()

    ps = PermissionSet(code="svc_set", name="Svc Set")
    session.add(ps)
    await session.flush()

    session.add(PermissionSetPermission(permission_set_id=ps.id, permission_id=perm.id))

    role = Role(name="Svc Role")
    session.add(role)
    await session.flush()

    session.add(RolePermissionSet(role_id=role.id, permission_set_id=ps.id))
    session.add(UserRole(user_id=user_id, role_id=role.id))
    await session.commit()
    return perm, ps, role


class TestGetUserPermissions:
    """Direct tests for get_user_permissions()."""

    @pytest.mark.asyncio
    async def test_permissions_from_role(self, test_session):
        """Permissions from role chain are returned."""
        uid = await _create_user(test_session)
        perm, _, _ = await _setup_rbac(test_session, uid)
        perms = await get_user_permissions(uid, test_session)
        assert perm.code in perms

    @pytest.mark.asyncio
    async def test_permissions_from_direct_set(self, test_session):
        """Permissions from direct permission-set assignment are returned."""
        uid = await _create_user(test_session)
        perm = Permission(code="direct_set.view", name="DS View", category="ds", is_system=False)
        session = test_session
        session.add(perm)
        await session.flush()
        ps = PermissionSet(code="direct_ps", name="Direct PS")
        session.add(ps)
        await session.flush()
        session.add(PermissionSetPermission(permission_set_id=ps.id, permission_id=perm.id))
        session.add(UserPermissionSet(user_id=uid, permission_set_id=ps.id))
        await session.commit()

        perms = await get_user_permissions(uid, session)
        assert "direct_set.view" in perms

    @pytest.mark.asyncio
    async def test_permissions_from_direct_permission(self, test_session):
        """Direct permission assignment is returned."""
        uid = await _create_user(test_session)
        perm = Permission(code="direct.action", name="Direct", category="d", is_system=False)
        test_session.add(perm)
        await test_session.flush()
        test_session.add(UserPermission(user_id=uid, permission_id=perm.id))
        await test_session.commit()

        perms = await get_user_permissions(uid, test_session)
        assert "direct.action" in perms

    @pytest.mark.asyncio
    async def test_union_of_all_sources(self, test_session):
        """All three sources are unioned."""
        uid = await _create_user(test_session)
        # Source 1: role chain
        perm1, ps, role = await _setup_rbac(test_session, uid)
        # Source 2: direct permission
        perm2 = Permission(code="direct.perm", name="DP", category="d", is_system=False)
        test_session.add(perm2)
        await test_session.flush()
        test_session.add(UserPermission(user_id=uid, permission_id=perm2.id))
        await test_session.commit()

        perms = await get_user_permissions(uid, test_session)
        assert perm1.code in perms
        assert perm2.code in perms

    @pytest.mark.asyncio
    async def test_empty_when_no_assignments(self, test_session):
        """User with no assignments has empty permission set."""
        uid = await _create_user(test_session)
        perms = await get_user_permissions(uid, test_session)
        assert perms == set()


class TestGetRolePermissions:
    """Direct tests for get_role_permissions()."""

    @pytest.mark.asyncio
    async def test_returns_codes(self, test_session):
        uid = await _create_user(test_session)
        perm, _, role = await _setup_rbac(test_session, uid)
        codes = await get_role_permissions(role.id, test_session)
        assert perm.code in codes

    @pytest.mark.asyncio
    async def test_empty_for_role_without_sets(self, test_session):
        role = Role(name="Empty Role")
        test_session.add(role)
        await test_session.commit()
        codes = await get_role_permissions(role.id, test_session)
        assert codes == set()


class TestPermissionLookup:
    """Tests for get_permission_by_code / get_permission_by_id."""

    @pytest.mark.asyncio
    async def test_by_code_found(self, test_session):
        perm = Permission(code="lookup.view", name="Lookup", category="lk", is_system=False)
        test_session.add(perm)
        await test_session.commit()
        found = await get_permission_by_code("lookup.view", test_session)
        assert found is not None
        assert found.code == "lookup.view"

    @pytest.mark.asyncio
    async def test_by_code_not_found(self, test_session):
        found = await get_permission_by_code("nonexistent.code", test_session)
        assert found is None

    @pytest.mark.asyncio
    async def test_by_id_found(self, test_session):
        perm = Permission(code="lookup.id", name="LookupId", category="lk", is_system=False)
        test_session.add(perm)
        await test_session.commit()
        await test_session.refresh(perm)
        found = await get_permission_by_id(perm.id, test_session)
        assert found is not None
        assert found.id == perm.id

    @pytest.mark.asyncio
    async def test_by_id_not_found(self, test_session):
        found = await get_permission_by_id(uuid4(), test_session)
        assert found is None

    @pytest.mark.asyncio
    async def test_deleted_permission_excluded(self, test_session):
        from datetime import datetime, UTC
        perm = Permission(
            code="del.perm", name="Deleted", category="d", is_system=False,
            deleted_at=datetime.now(UTC).replace(tzinfo=None),
        )
        test_session.add(perm)
        await test_session.commit()
        assert await get_permission_by_code("del.perm", test_session) is None


class TestPermissionSetByCode:
    """Tests for get_permission_set_by_code."""

    @pytest.mark.asyncio
    async def test_found(self, test_session):
        ps = PermissionSet(code="ps_code", name="PS Code")
        test_session.add(ps)
        await test_session.commit()
        found = await get_permission_set_by_code("ps_code", test_session)
        assert found is not None
        assert found.code == "ps_code"

    @pytest.mark.asyncio
    async def test_not_found(self, test_session):
        found = await get_permission_set_by_code("nope", test_session)
        assert found is None


class TestRoleByName:
    """Tests for get_role_by_name."""

    @pytest.mark.asyncio
    async def test_found(self, test_session):
        from src.api.services.permission_service import get_role_by_name
        role = Role(name="FindMe")
        test_session.add(role)
        await test_session.commit()
        found = await get_role_by_name("FindMe", test_session)
        assert found is not None
        assert found.name == "FindMe"

    @pytest.mark.asyncio
    async def test_not_found(self, test_session):
        from src.api.services.permission_service import get_role_by_name
        found = await get_role_by_name("Ghost", test_session)
        assert found is None


class TestDirectPermissionManagement:
    """Tests for assign/remove/set direct user permissions."""

    @pytest.mark.asyncio
    async def test_assign_permission(self, test_session):
        uid = await _create_user(test_session)
        perm = Permission(code="assign.test", name="AT", category="a", is_system=False)
        test_session.add(perm)
        await test_session.commit()
        await test_session.refresh(perm)

        with patch("src.api.services.permission_service.log_rbac_change", new_callable=AsyncMock):
            up = await assign_permission_to_user(uid, perm.id, session=test_session)
        assert up.user_id == uid
        assert up.permission_id == perm.id

    @pytest.mark.asyncio
    async def test_assign_duplicate_returns_existing(self, test_session):
        uid = await _create_user(test_session)
        perm = Permission(code="dup.test", name="Dup", category="d", is_system=False)
        test_session.add(perm)
        await test_session.commit()
        await test_session.refresh(perm)

        with patch("src.api.services.permission_service.log_rbac_change", new_callable=AsyncMock):
            first = await assign_permission_to_user(uid, perm.id, session=test_session)
            second = await assign_permission_to_user(uid, perm.id, session=test_session)
        assert first.user_id == second.user_id
        assert first.permission_id == second.permission_id

    @pytest.mark.asyncio
    async def test_remove_permission(self, test_session):
        uid = await _create_user(test_session)
        perm = Permission(code="rm.test", name="RM", category="r", is_system=False)
        test_session.add(perm)
        await test_session.commit()
        await test_session.refresh(perm)

        with patch("src.api.services.permission_service.log_rbac_change", new_callable=AsyncMock):
            await assign_permission_to_user(uid, perm.id, session=test_session)
            removed = await remove_permission_from_user(uid, perm.id, test_session)
        assert removed is True

    @pytest.mark.asyncio
    async def test_remove_nonexistent_returns_false(self, test_session):
        uid = await _create_user(test_session)
        with patch("src.api.services.permission_service.log_rbac_change", new_callable=AsyncMock):
            result = await remove_permission_from_user(uid, uuid4(), test_session)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_user_direct_permissions_empty(self, test_session):
        uid = await _create_user(test_session)
        result = await get_user_direct_permissions(uid, test_session)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_user_direct_permissions_returns_assigned(self, test_session):
        uid = await _create_user(test_session)
        perm = Permission(code="list.direct", name="LD", category="l", is_system=False)
        test_session.add(perm)
        await test_session.flush()
        test_session.add(UserPermission(user_id=uid, permission_id=perm.id))
        await test_session.commit()

        result = await get_user_direct_permissions(uid, test_session)
        assert len(result) == 1
        assert result[0].permission_id == perm.id

    @pytest.mark.asyncio
    async def test_set_user_direct_permissions_replaces(self, test_session):
        uid = await _create_user(test_session)
        p1 = Permission(code="set.a", name="SA", category="s", is_system=False)
        p2 = Permission(code="set.b", name="SB", category="s", is_system=False)
        test_session.add_all([p1, p2])
        await test_session.flush()
        test_session.add(UserPermission(user_id=uid, permission_id=p1.id))
        await test_session.commit()
        await test_session.refresh(p2)

        result = await set_user_direct_permissions(uid, [p2.id], session=test_session)
        assert len(result) == 1
        assert result[0].permission_id == p2.id


class TestDirectPermissionSetManagement:
    """Tests for assign/remove/set direct user permission sets."""

    @pytest.mark.asyncio
    async def test_assign_permission_set(self, test_session):
        uid = await _create_user(test_session)
        ps = PermissionSet(code="assign_ps", name="APS")
        test_session.add(ps)
        await test_session.commit()
        await test_session.refresh(ps)

        with patch("src.api.services.permission_service.log_rbac_change", new_callable=AsyncMock):
            ups = await assign_permission_set_to_user(uid, ps.id, session=test_session)
        assert ups.user_id == uid
        assert ups.permission_set_id == ps.id

    @pytest.mark.asyncio
    async def test_assign_duplicate_returns_existing(self, test_session):
        uid = await _create_user(test_session)
        ps = PermissionSet(code="dup_ps", name="DPS")
        test_session.add(ps)
        await test_session.commit()
        await test_session.refresh(ps)

        with patch("src.api.services.permission_service.log_rbac_change", new_callable=AsyncMock):
            first = await assign_permission_set_to_user(uid, ps.id, session=test_session)
            second = await assign_permission_set_to_user(uid, ps.id, session=test_session)
        assert first.permission_set_id == second.permission_set_id

    @pytest.mark.asyncio
    async def test_remove_permission_set(self, test_session):
        uid = await _create_user(test_session)
        ps = PermissionSet(code="rm_ps", name="RMPS")
        test_session.add(ps)
        await test_session.commit()
        await test_session.refresh(ps)

        with patch("src.api.services.permission_service.log_rbac_change", new_callable=AsyncMock):
            await assign_permission_set_to_user(uid, ps.id, session=test_session)
            removed = await remove_permission_set_from_user(uid, ps.id, test_session)
        assert removed is True

    @pytest.mark.asyncio
    async def test_remove_nonexistent_returns_false(self, test_session):
        uid = await _create_user(test_session)
        with patch("src.api.services.permission_service.log_rbac_change", new_callable=AsyncMock):
            result = await remove_permission_set_from_user(uid, uuid4(), test_session)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_user_direct_permission_sets_empty(self, test_session):
        uid = await _create_user(test_session)
        result = await get_user_direct_permission_sets(uid, test_session)
        assert result == []

    @pytest.mark.asyncio
    async def test_set_user_direct_permission_sets_replaces(self, test_session):
        uid = await _create_user(test_session)
        ps1 = PermissionSet(code="replace_a", name="RA")
        ps2 = PermissionSet(code="replace_b", name="RB")
        test_session.add_all([ps1, ps2])
        await test_session.flush()
        test_session.add(UserPermissionSet(user_id=uid, permission_set_id=ps1.id))
        await test_session.commit()
        await test_session.refresh(ps2)

        result = await set_user_direct_permission_sets(uid, [ps2.id], session=test_session)
        assert len(result) == 1
        assert result[0].permission_set_id == ps2.id


class TestGetUserPermissionsDetailed:
    """Tests for get_user_permissions_detailed()."""

    @pytest.mark.asyncio
    async def test_empty_user(self, test_session):
        uid = await _create_user(test_session)
        result = await get_user_permissions_detailed(uid, test_session)
        assert result["from_roles"] == []
        assert result["from_direct_sets"] == []
        assert result["from_direct_permissions"] == []
        assert result["effective"] == []

    @pytest.mark.asyncio
    async def test_detailed_breakdown(self, test_session):
        uid = await _create_user(test_session)
        # Source 1: role-based
        perm1, _, _ = await _setup_rbac(test_session, uid)
        # Source 3: direct permission
        perm2 = Permission(code="detail.direct", name="DD", category="d", is_system=False)
        test_session.add(perm2)
        await test_session.flush()
        test_session.add(UserPermission(user_id=uid, permission_id=perm2.id))
        await test_session.commit()

        result = await get_user_permissions_detailed(uid, test_session)
        assert perm1.code in result["from_roles"]
        assert perm2.code in result["from_direct_permissions"]
        assert perm1.code in result["effective"]
        assert perm2.code in result["effective"]

    @pytest.mark.asyncio
    async def test_direct_set_source(self, test_session):
        uid = await _create_user(test_session)
        perm = Permission(code="dset.view", name="DSV", category="ds", is_system=False)
        test_session.add(perm)
        await test_session.flush()
        ps = PermissionSet(code="dset_ps", name="DSP")
        test_session.add(ps)
        await test_session.flush()
        test_session.add(PermissionSetPermission(permission_set_id=ps.id, permission_id=perm.id))
        test_session.add(UserPermissionSet(user_id=uid, permission_set_id=ps.id))
        await test_session.commit()

        result = await get_user_permissions_detailed(uid, test_session)
        assert perm.code in result["from_direct_sets"]
        assert perm.code in result["effective"]

from src.api.services.permission_service import (
    create_permission_set,
    update_permission_set,
    delete_permission_set,
    get_all_roles,
    get_role_by_id,
    create_role,
    update_role,
    delete_role,
    get_permission_set_by_id,
)


class TestCreatePermissionSet:
    """Service-level tests for create_permission_set."""

    @pytest.mark.asyncio
    async def test_create_with_permissions(self, test_session):
        p1 = Permission(code="ps_create.a", name="A", category="c", is_system=False)
        p2 = Permission(code="ps_create.b", name="B", category="c", is_system=False)
        test_session.add_all([p1, p2])
        await test_session.commit()

        ps = await create_permission_set(
            code="new_ps", name="New PS",
            permission_codes=["ps_create.a", "ps_create.b"],
            description="test",
            session=test_session,
        )
        assert ps.code == "new_ps"
        assert ps.name == "New PS"
        assert ps.description == "test"

    @pytest.mark.asyncio
    async def test_create_with_no_matching_permissions(self, test_session):
        ps = await create_permission_set(
            code="empty_ps", name="Empty",
            permission_codes=["nonexistent"],
            session=test_session,
        )
        assert ps.code == "empty_ps"


class TestUpdatePermissionSet:
    """Service-level tests for update_permission_set."""

    @pytest.mark.asyncio
    async def test_update_name(self, test_session):
        ps = PermissionSet(code="upd_ps", name="Old")
        test_session.add(ps)
        await test_session.commit()
        await test_session.refresh(ps)

        result = await update_permission_set(ps.id, name="New", session=test_session)
        assert result is not None
        assert result.name == "New"

    @pytest.mark.asyncio
    async def test_update_not_found(self, test_session):
        result = await update_permission_set(uuid4(), name="X", session=test_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_permission_codes(self, test_session):
        p1 = Permission(code="upd.old", name="Old", category="u", is_system=False)
        p2 = Permission(code="upd.new", name="New", category="u", is_system=False)
        test_session.add_all([p1, p2])
        await test_session.flush()

        ps = PermissionSet(code="upd_codes", name="Upd Codes")
        test_session.add(ps)
        await test_session.flush()
        test_session.add(PermissionSetPermission(permission_set_id=ps.id, permission_id=p1.id))
        await test_session.commit()
        await test_session.refresh(ps)

        result = await update_permission_set(
            ps.id, permission_codes=["upd.new"], session=test_session,
        )
        assert result is not None


class TestDeletePermissionSet:
    """Service-level tests for delete_permission_set."""

    @pytest.mark.asyncio
    async def test_delete_success(self, test_session):
        ps = PermissionSet(code="del_ps", name="Del")
        test_session.add(ps)
        await test_session.commit()
        await test_session.refresh(ps)

        result = await delete_permission_set(ps.id, test_session)
        assert result is True
        # Soft-deleted: not found by get
        found = await get_permission_set_by_id(ps.id, test_session)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_not_found(self, test_session):
        result = await delete_permission_set(uuid4(), test_session)
        assert result is False


class TestRoleCRUDService:
    """Service-level tests for role CRUD."""

    @pytest.mark.asyncio
    async def test_get_all_roles_empty(self, test_session):
        roles = await get_all_roles(test_session)
        assert roles == []

    @pytest.mark.asyncio
    async def test_get_all_roles(self, test_session):
        test_session.add_all([
            Role(name="Role A"),
            Role(name="Role B"),
        ])
        await test_session.commit()
        roles = await get_all_roles(test_session)
        assert len(roles) == 2
        names = [r.name for r in roles]
        assert "Role A" in names
        assert "Role B" in names

    @pytest.mark.asyncio
    async def test_get_role_by_id_found(self, test_session):
        role = Role(name="Find Role")
        test_session.add(role)
        await test_session.commit()
        await test_session.refresh(role)

        found = await get_role_by_id(role.id, test_session)
        assert found is not None
        assert found.name == "Find Role"

    @pytest.mark.asyncio
    async def test_get_role_by_id_not_found(self, test_session):
        found = await get_role_by_id(uuid4(), test_session)
        assert found is None

    @pytest.mark.asyncio
    async def test_create_role_with_permission_sets(self, test_session):
        ps = PermissionSet(code="role_ps", name="Role PS")
        test_session.add(ps)
        await test_session.commit()

        role = await create_role(
            name="New Role",
            permission_set_codes=["role_ps"],
            description="desc",
            session=test_session,
        )
        assert role.name == "New Role"
        assert role.description == "desc"

    @pytest.mark.asyncio
    async def test_create_role_with_no_matching_sets(self, test_session):
        role = await create_role(
            name="Empty Role",
            permission_set_codes=["nonexistent"],
            session=test_session,
        )
        assert role.name == "Empty Role"

    @pytest.mark.asyncio
    async def test_update_role_name(self, test_session):
        role = Role(name="Old Role")
        test_session.add(role)
        await test_session.commit()
        await test_session.refresh(role)

        result = await update_role(role.id, name="New Role", session=test_session)
        assert result is not None
        assert result.name == "New Role"

    @pytest.mark.asyncio
    async def test_update_role_not_found(self, test_session):
        result = await update_role(uuid4(), name="X", session=test_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_role_permission_set_codes(self, test_session):
        ps1 = PermissionSet(code="role_upd_old", name="Old")
        ps2 = PermissionSet(code="role_upd_new", name="New")
        test_session.add_all([ps1, ps2])
        await test_session.flush()

        role = Role(name="Upd Role")
        test_session.add(role)
        await test_session.flush()
        test_session.add(RolePermissionSet(role_id=role.id, permission_set_id=ps1.id))
        await test_session.commit()
        await test_session.refresh(role)

        result = await update_role(
            role.id, permission_set_codes=["role_upd_new"], session=test_session,
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_delete_role_success(self, test_session):
        role = Role(name="Del Role")
        test_session.add(role)
        await test_session.commit()
        await test_session.refresh(role)

        result = await delete_role(role.id, test_session)
        assert result is True
        found = await get_role_by_id(role.id, test_session)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_role_not_found(self, test_session):
        result = await delete_role(uuid4(), test_session)
        assert result is False

    @pytest.mark.asyncio
    async def test_deleted_role_excluded_from_all(self, test_session):
        role = Role(name="Disappearing")
        test_session.add(role)
        await test_session.commit()
        await test_session.refresh(role)

        await delete_role(role.id, test_session)
        roles = await get_all_roles(test_session)
        names = [r.name for r in roles]
        assert "Disappearing" not in names

class TestPermissionSetRouterCRUD:
    """Router-level tests for permission set CRUD."""

    @pytest.mark.asyncio
    async def test_create_permission_set_endpoint(self, admin_client):
        client, session, _ = admin_client
        # Create required permissions first
        session.add(Permission(code="test.view", name="Test View", category="test"))
        await session.commit()

        response = await client.post("/permissions/sets", json={
            "code": "test_router_set",
            "name": "Test Router Set",
            "permission_codes": ["test.view"],
        })
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "test_router_set"
        assert len(data["permissions"]) == 1

    @pytest.mark.asyncio
    async def test_create_permission_set_duplicate(self, admin_client):
        client, session, _ = admin_client
        ps = PermissionSet(code="dup_set", name="Dup")
        session.add(ps)
        await session.commit()

        response = await client.post("/permissions/sets", json={
            "code": "dup_set", "name": "Dup2", "permission_codes": [],
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_permission_set_endpoint(self, admin_client):
        client, session, _ = admin_client
        ps = PermissionSet(code="get_set", name="Get Set")
        session.add(ps)
        await session.commit()
        await session.refresh(ps)

        response = await client.get(f"/permissions/sets/{ps.id}")
        assert response.status_code == 200
        assert response.json()["code"] == "get_set"

    @pytest.mark.asyncio
    async def test_get_permission_set_not_found(self, admin_client):
        client, _, _ = admin_client
        from uuid import uuid4
        response = await client.get(f"/permissions/sets/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_permission_set_endpoint(self, admin_client):
        client, session, _ = admin_client
        ps = PermissionSet(code="upd_set", name="Old Name")
        session.add(ps)
        await session.commit()
        await session.refresh(ps)

        response = await client.put(f"/permissions/sets/{ps.id}", json={
            "name": "New Name",
        })
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_update_permission_set_not_found(self, admin_client):
        client, _, _ = admin_client
        from uuid import uuid4
        response = await client.put(f"/permissions/sets/{uuid4()}", json={"name": "X"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_permission_set_endpoint(self, admin_client):
        client, session, _ = admin_client
        ps = PermissionSet(code="del_set", name="Del")
        session.add(ps)
        await session.commit()
        await session.refresh(ps)

        response = await client.delete(f"/permissions/sets/{ps.id}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_permission_set_not_found(self, admin_client):
        client, _, _ = admin_client
        from uuid import uuid4
        response = await client.delete(f"/permissions/sets/{uuid4()}")
        assert response.status_code == 404


class TestRoleRouterCRUD:
    """Router-level tests for role CRUD."""

    @pytest.mark.asyncio
    async def test_create_role_endpoint(self, admin_client):
        client, session, _ = admin_client
        response = await client.post("/permissions/roles", json={
            "name": "test_router_role",
            "permission_set_codes": [],
        })
        assert response.status_code == 201
        assert response.json()["name"] == "test_router_role"

    @pytest.mark.asyncio
    async def test_create_role_duplicate(self, admin_client):
        client, session, _ = admin_client
        session.add(Role(name="dup_role"))
        await session.commit()

        response = await client.post("/permissions/roles", json={
            "name": "dup_role", "permission_set_codes": [],
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_role_endpoint(self, admin_client):
        client, session, _ = admin_client
        role = Role(name="get_role")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.get(f"/permissions/roles/{role.id}")
        assert response.status_code == 200
        assert response.json()["name"] == "get_role"

    @pytest.mark.asyncio
    async def test_get_role_not_found(self, admin_client):
        client, _, _ = admin_client
        from uuid import uuid4
        response = await client.get(f"/permissions/roles/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_role_endpoint(self, admin_client):
        client, session, _ = admin_client
        role = Role(name="upd_role")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.put(f"/permissions/roles/{role.id}", json={
            "name": "updated_role",
        })
        assert response.status_code == 200
        assert response.json()["name"] == "updated_role"

    @pytest.mark.asyncio
    async def test_update_role_not_found(self, admin_client):
        client, _, _ = admin_client
        from uuid import uuid4
        response = await client.put(f"/permissions/roles/{uuid4()}", json={"name": "X"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_role_endpoint(self, admin_client):
        client, session, _ = admin_client
        role = Role(name="del_role")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.delete(f"/permissions/roles/{role.id}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_role_not_found(self, admin_client):
        client, _, _ = admin_client
        from uuid import uuid4
        response = await client.delete(f"/permissions/roles/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_role_effective_permissions(self, admin_client):
        client, session, _ = admin_client
        role = Role(name="perms_role")
        session.add(role)
        await session.commit()
        await session.refresh(role)

        response = await client.get(f"/permissions/roles/{role.id}/permissions")
        assert response.status_code == 200
        data = response.json()
        assert data["role_name"] == "perms_role"
        assert isinstance(data["permissions"], list)

    @pytest.mark.asyncio
    async def test_get_role_effective_permissions_not_found(self, admin_client):
        client, _, _ = admin_client
        from uuid import uuid4
        response = await client.get(f"/permissions/roles/{uuid4()}/permissions")
        assert response.status_code == 404

class TestPermissionSetErrorPaths:
    """Tests for error handling in permission set CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_integrity_error(self, admin_client):
        """IntegrityError during creation returns 400."""
        client, session, _ = admin_client
        from sqlalchemy.exc import IntegrityError
        with patch(
            "src.api.routers.permissions.permission_service.create_permission_set",
            new_callable=AsyncMock,
            side_effect=IntegrityError("dup", params=None, orig=Exception()),
        ):
            response = await client.post("/permissions/sets", json={
                "code": "err_set", "name": "Err", "permission_codes": [],
            })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_value_error(self, admin_client):
        """ValueError during update returns 400."""
        client, session, _ = admin_client
        with patch(
            "src.api.routers.permissions.permission_service.update_permission_set",
            new_callable=AsyncMock,
            side_effect=ValueError("bad data"),
        ):
            from uuid import uuid4
            response = await client.put(f"/permissions/sets/{uuid4()}", json={
                "name": "Updated",
            })
        assert response.status_code == 400
        assert "bad data" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_value_error(self, admin_client):
        """ValueError during delete returns 400."""
        client, session, _ = admin_client
        with patch(
            "src.api.routers.permissions.permission_service.delete_permission_set",
            new_callable=AsyncMock,
            side_effect=ValueError("cannot delete"),
        ):
            from uuid import uuid4
            response = await client.delete(f"/permissions/sets/{uuid4()}")
        assert response.status_code == 400


class TestRoleErrorPaths:
    """Tests for error handling in role CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_integrity_error(self, admin_client):
        """IntegrityError during role creation returns 400."""
        client, session, _ = admin_client
        from sqlalchemy.exc import IntegrityError
        with patch(
            "src.api.routers.permissions.permission_service.create_role",
            new_callable=AsyncMock,
            side_effect=IntegrityError("dup", params=None, orig=Exception()),
        ):
            response = await client.post("/permissions/roles", json={
                "name": "err_role", "permission_set_codes": [],
            })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_value_error(self, admin_client):
        """ValueError during role update returns 400."""
        client, session, _ = admin_client
        with patch(
            "src.api.routers.permissions.permission_service.update_role",
            new_callable=AsyncMock,
            side_effect=ValueError("bad role data"),
        ):
            from uuid import uuid4
            response = await client.put(f"/permissions/roles/{uuid4()}", json={
                "name": "Updated",
            })
        assert response.status_code == 400
        assert "bad role data" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_value_error(self, admin_client):
        """ValueError during role delete returns 400."""
        client, session, _ = admin_client
        with patch(
            "src.api.routers.permissions.permission_service.delete_role",
            new_callable=AsyncMock,
            side_effect=ValueError("cannot delete role"),
        ):
            from uuid import uuid4
            response = await client.delete(f"/permissions/roles/{uuid4()}")
        assert response.status_code == 400
