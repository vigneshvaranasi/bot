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
