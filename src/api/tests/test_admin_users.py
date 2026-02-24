"""Comprehensive tests for Admin/User Management endpoints (/admin).

Covers:
- List users (GET /admin/users)
- Update user (PUT /admin/users/{id})
- Delete user (DELETE /admin/users/{id})
- User role assignments (GET/PUT/POST/DELETE /admin/users/{id}/roles)
- Direct permission assignments (GET/PUT/POST/DELETE /admin/users/{id}/permissions/direct)
- Direct permission set assignments (GET/PUT/POST/DELETE /admin/users/{id}/permission-sets/direct)
- Effective permissions (GET /admin/users/{id}/permissions/effective)
- Permission/RBAC enforcement
- Unauthenticated access
"""

import pytest
from uuid import uuid4

from sqlalchemy.future import select

from src.api.db.models import (
    User,
    Role,
    UserRole,
    Permission,
    PermissionSet,
    PermissionSetPermission,
    UserPermission,
    UserPermissionSet,
)


# ============================================================
# Helpers
# ============================================================

async def _create_user(session, *, email=None, is_active=True, role_id=None):
    """Create a User in the DB and return it."""
    if email is None:
        email = f"user_{uuid4().hex[:8]}@test.com"
    user = User(email=email, is_active=is_active, role_id=role_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _create_role(session, *, name=None):
    """Create a Role and return it."""
    if name is None:
        name = f"Role_{uuid4().hex[:6]}"
    role = Role(name=name)
    session.add(role)
    await session.commit()
    await session.refresh(role)
    return role


async def _create_permission(session, *, code=None, name=None, category="test"):
    """Create a Permission and return it."""
    if code is None:
        code = f"test.{uuid4().hex[:6]}"
    if name is None:
        name = f"Test {code}"
    perm = Permission(code=code, name=name, category=category, is_system=False)
    session.add(perm)
    await session.commit()
    await session.refresh(perm)
    return perm


async def _create_permission_set(session, *, code=None, name=None):
    """Create a PermissionSet and return it."""
    if code is None:
        code = f"set_{uuid4().hex[:6]}"
    if name is None:
        name = f"Set {code}"
    ps = PermissionSet(code=code, name=name)
    session.add(ps)
    await session.commit()
    await session.refresh(ps)
    return ps


# ============================================================
# GET /admin/users — List users
# ============================================================


class TestListUsers:
    """Tests for GET /admin/users"""

    @pytest.mark.asyncio
    async def test_list_users_empty(self, admin_client):
        """Returns empty list when no extra users exist."""
        client, _, _ = admin_client
        response = await client.get("/admin/users")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["users"], list)
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_users_returns_users(self, admin_client):
        """Returns created users."""
        client, session, _ = admin_client
        await _create_user(session, email="listme@test.com")

        response = await client.get("/admin/users")
        data = response.json()
        emails = {u["email"] for u in data["users"]}
        assert "listme@test.com" in emails

    @pytest.mark.asyncio
    async def test_list_users_pagination(self, admin_client):
        """Respects limit and offset."""
        client, session, _ = admin_client
        for i in range(5):
            await _create_user(session, email=f"page{i}@test.com")

        response = await client.get("/admin/users?limit=2&offset=0")
        data = response.json()
        assert len(data["users"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0
        assert data["has_more"] is True

    @pytest.mark.asyncio
    async def test_list_users_search(self, admin_client):
        """Filters by email search."""
        client, session, _ = admin_client
        await _create_user(session, email="findme_unique@test.com")
        await _create_user(session, email="other@test.com")

        response = await client.get("/admin/users?search=findme_unique")
        data = response.json()
        assert data["total"] >= 1
        emails = {u["email"] for u in data["users"]}
        assert "findme_unique@test.com" in emails

    @pytest.mark.asyncio
    async def test_list_users_excludes_deleted(self, admin_client):
        """Soft-deleted users are excluded."""
        from datetime import datetime, UTC
        client, session, _ = admin_client
        user = await _create_user(session, email="deleted@test.com")
        user.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()

        response = await client.get("/admin/users?search=deleted@test.com")
        assert response.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_list_users_requires_permission(self, no_perms_client):
        """Requires user.view permission."""
        client, _, _ = no_perms_client
        response = await client.get("/admin/users")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_users_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        response = await client.get("/admin/users")
        assert response.status_code == 403


# ============================================================
# PUT /admin/users/{id} — Update user
# ============================================================


class TestUpdateUser:
    """Tests for PUT /admin/users/{user_id}"""

    @pytest.mark.asyncio
    async def test_update_user(self, admin_client):
        """Update user's active status and role."""
        client, session, _ = admin_client
        role = await _create_role(session, name="UpdateRole")
        user = await _create_user(session)

        response = await client.put(f"/admin/users/{user.id}", json={
            "is_active": False,
            "role_id": str(role.id),
        })
        assert response.status_code == 200
        assert response.json()["message"] == "User updated"

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, admin_client):
        """Non-existent user returns 404."""
        client, session, _ = admin_client
        role = await _create_role(session)
        response = await client.put(f"/admin/users/{uuid4()}", json={
            "is_active": True,
            "role_id": str(role.id),
        })
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_user_requires_permission(self, no_perms_client):
        """Requires user.edit permission."""
        client, _, _ = no_perms_client
        response = await client.put(f"/admin/users/{uuid4()}", json={
            "is_active": True,
            "role_id": str(uuid4()),
        })
        assert response.status_code == 403


# ============================================================
# DELETE /admin/users/{id} — Delete user
# ============================================================


class TestDeleteUser:
    """Tests for DELETE /admin/users/{user_id}"""

    @pytest.mark.asyncio
    async def test_delete_user(self, admin_client):
        """Soft-delete a user."""
        client, session, _ = admin_client
        user = await _create_user(session, email="todelete@test.com")

        response = await client.delete(f"/admin/users/{user.id}")
        assert response.status_code == 200
        assert response.json()["message"] == "User deleted"

    @pytest.mark.asyncio
    async def test_delete_user_is_soft_delete(self, admin_client):
        """Deleted user still exists in DB with deleted_at set."""
        client, session, _ = admin_client
        user = await _create_user(session, email="softdel@test.com")
        user_id = user.id

        await client.delete(f"/admin/users/{user_id}")

        session.expire_all()
        result = await session.execute(select(User).where(User.id == user_id))
        db_user = result.scalar_one()
        assert db_user.deleted_at is not None
        assert db_user.is_active is False

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, admin_client):
        """Non-existent user returns 404."""
        client, _, _ = admin_client
        response = await client.delete(f"/admin/users/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_user_requires_permission(self, no_perms_client):
        """Requires user.delete permission."""
        client, _, _ = no_perms_client
        response = await client.delete(f"/admin/users/{uuid4()}")
        assert response.status_code == 403


# ============================================================
# User Role Assignments
# ============================================================


class TestUserRoles:
    """Tests for /admin/users/{id}/roles endpoints"""

    @pytest.mark.asyncio
    async def test_get_user_roles_empty(self, admin_client):
        """User with no roles returns empty list."""
        client, session, _ = admin_client
        user = await _create_user(session)

        response = await client.get(f"/admin/users/{user.id}/roles")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["roles"] == []

    @pytest.mark.asyncio
    async def test_assign_role_to_user(self, admin_client):
        """POST assigns a role to a user."""
        client, session, _ = admin_client
        user = await _create_user(session)
        role = await _create_role(session, name="AssignRole")

        response = await client.post(f"/admin/users/{user.id}/roles", json={
            "role_id": str(role.id),
        })
        assert response.status_code == 200
        assert response.json()["message"] == "Role assigned"

    @pytest.mark.asyncio
    async def test_assign_role_already_assigned(self, admin_client):
        """Re-assigning same role returns already assigned message."""
        client, session, _ = admin_client
        user = await _create_user(session)
        role = await _create_role(session, name="AlreadyRole")

        await client.post(f"/admin/users/{user.id}/roles", json={
            "role_id": str(role.id),
        })
        response = await client.post(f"/admin/users/{user.id}/roles", json={
            "role_id": str(role.id),
        })
        assert response.status_code == 200
        assert "already" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_get_user_roles_after_assign(self, admin_client):
        """GET returns assigned roles."""
        client, session, _ = admin_client
        user = await _create_user(session)
        role = await _create_role(session, name="GetAfterAssign")

        await client.post(f"/admin/users/{user.id}/roles", json={
            "role_id": str(role.id),
        })

        response = await client.get(f"/admin/users/{user.id}/roles")
        data = response.json()
        assert len(data["roles"]) == 1
        assert data["roles"][0]["role_name"] == "GetAfterAssign"

    @pytest.mark.asyncio
    async def test_replace_user_roles(self, admin_client):
        """PUT replaces all roles for a user."""
        client, session, _ = admin_client
        user = await _create_user(session)
        role1 = await _create_role(session, name="Replace1")
        role2 = await _create_role(session, name="Replace2")

        # Assign role1 first
        await client.post(f"/admin/users/{user.id}/roles", json={
            "role_id": str(role1.id),
        })

        # Replace with role2 only
        response = await client.put(f"/admin/users/{user.id}/roles", json={
            "role_ids": [str(role2.id)],
        })
        assert response.status_code == 200
        role_names = {r["role_name"] for r in response.json()["roles"]}
        assert role_names == {"Replace2"}

    @pytest.mark.asyncio
    async def test_remove_role_from_user(self, admin_client):
        """DELETE removes a specific role from a user."""
        client, session, _ = admin_client
        user = await _create_user(session)
        role = await _create_role(session, name="RemoveRole")

        await client.post(f"/admin/users/{user.id}/roles", json={
            "role_id": str(role.id),
        })

        response = await client.delete(f"/admin/users/{user.id}/roles/{role.id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Role removed"

    @pytest.mark.asyncio
    async def test_remove_role_not_assigned(self, admin_client):
        """Removing a role not assigned returns 404."""
        client, session, _ = admin_client
        user = await _create_user(session)
        role = await _create_role(session)

        response = await client.delete(f"/admin/users/{user.id}/roles/{role.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_assign_role_user_not_found(self, admin_client):
        """Assigning role to non-existent user returns 404."""
        client, session, _ = admin_client
        role = await _create_role(session)
        response = await client.post(f"/admin/users/{uuid4()}/roles", json={
            "role_id": str(role.id),
        })
        assert response.status_code == 404


# ============================================================
# Direct Permission Assignments
# ============================================================


class TestDirectPermissions:
    """Tests for /admin/users/{id}/permissions/direct endpoints"""

    @pytest.mark.asyncio
    async def test_get_direct_permissions_empty(self, admin_client):
        """Returns empty list when no direct permissions."""
        client, session, _ = admin_client
        user = await _create_user(session)

        response = await client.get(f"/admin/users/{user.id}/permissions/direct")
        assert response.status_code == 200
        data = response.json()
        assert data["direct_permissions"] == []

    @pytest.mark.asyncio
    async def test_assign_direct_permission(self, admin_client):
        """POST assigns a permission directly to a user."""
        client, session, _ = admin_client
        user = await _create_user(session)
        perm = await _create_permission(session, code="direct.test")

        response = await client.post(f"/admin/users/{user.id}/permissions/direct", json={
            "permission_id": str(perm.id),
        })
        assert response.status_code == 200
        assert "assigned" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_get_direct_permissions_after_assign(self, admin_client):
        """GET returns the assigned direct permission."""
        client, session, _ = admin_client
        user = await _create_user(session)
        perm = await _create_permission(session, code="direct.get_after")

        await client.post(f"/admin/users/{user.id}/permissions/direct", json={
            "permission_id": str(perm.id),
        })

        response = await client.get(f"/admin/users/{user.id}/permissions/direct")
        data = response.json()
        assert len(data["direct_permissions"]) == 1
        assert data["direct_permissions"][0]["permission_code"] == "direct.get_after"

    @pytest.mark.asyncio
    async def test_update_direct_permissions_bulk(self, admin_client):
        """PUT replaces all direct permissions."""
        client, session, _ = admin_client
        user = await _create_user(session)
        perm1 = await _create_permission(session, code="bulk.a")
        perm2 = await _create_permission(session, code="bulk.b")

        response = await client.put(f"/admin/users/{user.id}/permissions/direct", json={
            "permission_ids": [str(perm1.id), str(perm2.id)],
        })
        assert response.status_code == 200
        codes = {p["permission_code"] for p in response.json()["direct_permissions"]}
        assert codes == {"bulk.a", "bulk.b"}

    @pytest.mark.asyncio
    async def test_remove_direct_permission(self, admin_client):
        """DELETE removes a direct permission."""
        client, session, _ = admin_client
        user = await _create_user(session)
        perm = await _create_permission(session, code="direct.remove")

        await client.post(f"/admin/users/{user.id}/permissions/direct", json={
            "permission_id": str(perm.id),
        })

        response = await client.delete(
            f"/admin/users/{user.id}/permissions/direct/{perm.id}"
        )
        assert response.status_code == 200
        assert "removed" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_remove_direct_permission_not_found(self, admin_client):
        """Removing non-assigned permission returns 404."""
        client, session, _ = admin_client
        user = await _create_user(session)
        perm = await _create_permission(session)

        response = await client.delete(
            f"/admin/users/{user.id}/permissions/direct/{perm.id}"
        )
        assert response.status_code == 404


# ============================================================
# Direct Permission Set Assignments
# ============================================================


class TestDirectPermissionSets:
    """Tests for /admin/users/{id}/permission-sets/direct endpoints"""

    @pytest.mark.asyncio
    async def test_get_direct_permission_sets_empty(self, admin_client):
        """Returns empty list when no direct permission sets."""
        client, session, _ = admin_client
        user = await _create_user(session)

        response = await client.get(f"/admin/users/{user.id}/permission-sets/direct")
        assert response.status_code == 200
        data = response.json()
        assert data["direct_permission_sets"] == []

    @pytest.mark.asyncio
    async def test_assign_direct_permission_set(self, admin_client):
        """POST assigns a permission set directly to a user."""
        client, session, _ = admin_client
        user = await _create_user(session)
        ps = await _create_permission_set(session, code="direct_ps")

        response = await client.post(
            f"/admin/users/{user.id}/permission-sets/direct",
            json={"permission_set_id": str(ps.id)},
        )
        assert response.status_code == 200
        assert "assigned" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_get_direct_permission_sets_after_assign(self, admin_client):
        """GET returns the assigned direct permission set."""
        client, session, _ = admin_client
        user = await _create_user(session)
        ps = await _create_permission_set(session, code="direct_ps_get")

        await client.post(
            f"/admin/users/{user.id}/permission-sets/direct",
            json={"permission_set_id": str(ps.id)},
        )

        response = await client.get(f"/admin/users/{user.id}/permission-sets/direct")
        data = response.json()
        assert len(data["direct_permission_sets"]) == 1
        assert data["direct_permission_sets"][0]["permission_set_code"] == "direct_ps_get"

    @pytest.mark.asyncio
    async def test_update_direct_permission_sets_bulk(self, admin_client):
        """PUT replaces all direct permission sets."""
        client, session, _ = admin_client
        user = await _create_user(session)
        ps1 = await _create_permission_set(session, code="bulk_ps1")
        ps2 = await _create_permission_set(session, code="bulk_ps2")

        response = await client.put(
            f"/admin/users/{user.id}/permission-sets/direct",
            json={"permission_set_ids": [str(ps1.id), str(ps2.id)]},
        )
        assert response.status_code == 200
        codes = {p["permission_set_code"] for p in response.json()["direct_permission_sets"]}
        assert codes == {"bulk_ps1", "bulk_ps2"}

    @pytest.mark.asyncio
    async def test_remove_direct_permission_set(self, admin_client):
        """DELETE removes a direct permission set."""
        client, session, _ = admin_client
        user = await _create_user(session)
        ps = await _create_permission_set(session, code="remove_ps")

        await client.post(
            f"/admin/users/{user.id}/permission-sets/direct",
            json={"permission_set_id": str(ps.id)},
        )

        response = await client.delete(
            f"/admin/users/{user.id}/permission-sets/direct/{ps.id}"
        )
        assert response.status_code == 200
        assert "removed" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_remove_direct_permission_set_not_found(self, admin_client):
        """Removing non-assigned permission set returns 404."""
        client, session, _ = admin_client
        user = await _create_user(session)
        ps = await _create_permission_set(session)

        response = await client.delete(
            f"/admin/users/{user.id}/permission-sets/direct/{ps.id}"
        )
        assert response.status_code == 404


# ============================================================
# GET /admin/users/{id}/permissions/effective
# ============================================================


class TestEffectivePermissions:
    """Tests for GET /admin/users/{id}/permissions/effective"""

    @pytest.mark.asyncio
    async def test_effective_permissions_empty(self, admin_client):
        """User with nothing assigned has empty effective permissions."""
        client, session, _ = admin_client
        user = await _create_user(session)

        response = await client.get(f"/admin/users/{user.id}/permissions/effective")
        assert response.status_code == 200
        data = response.json()
        assert data["effective"] == []
        assert data["from_roles"] == []
        assert data["from_direct_sets"] == []
        assert data["from_direct_permissions"] == []

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Raw SQL text() queries pass str(uuid) with dashes but SQLite stores UUIDs as hex without dashes")
    async def test_effective_permissions_from_direct(self, admin_client):
        """Direct permission shows up in effective and from_direct_permissions."""
        client, session, _ = admin_client
        user = await _create_user(session)
        perm = await _create_permission(session, code="eff.direct")

        await client.post(f"/admin/users/{user.id}/permissions/direct", json={
            "permission_id": str(perm.id),
        })

        response = await client.get(f"/admin/users/{user.id}/permissions/effective")
        data = response.json()
        assert "eff.direct" in data["effective"]
        assert "eff.direct" in data["from_direct_permissions"]

    @pytest.mark.asyncio
    async def test_effective_permissions_requires_permission(self, no_perms_client):
        """Requires user.view permission."""
        client, _, _ = no_perms_client
        response = await client.get(f"/admin/users/{uuid4()}/permissions/effective")
        assert response.status_code == 403


# ============================================================
# Unauthenticated access
# ============================================================


class TestAdminUnauthenticated:
    """Unauthenticated requests to admin endpoints are rejected."""

    @pytest.mark.asyncio
    async def test_list_users_unauth(self, client):
        response = await client.get("/admin/users")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_user_unauth(self, client):
        response = await client.put(f"/admin/users/{uuid4()}", json={
            "is_active": True, "role_id": str(uuid4()),
        })
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_user_unauth(self, client):
        response = await client.delete(f"/admin/users/{uuid4()}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_roles_unauth(self, client):
        response = await client.get(f"/admin/users/{uuid4()}/roles")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_assign_role_unauth(self, client):
        response = await client.post(f"/admin/users/{uuid4()}/roles", json={
            "role_id": str(uuid4()),
        })
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_direct_perms_unauth(self, client):
        response = await client.get(f"/admin/users/{uuid4()}/permissions/direct")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_direct_perm_sets_unauth(self, client):
        response = await client.get(f"/admin/users/{uuid4()}/permission-sets/direct")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_effective_perms_unauth(self, client):
        response = await client.get(f"/admin/users/{uuid4()}/permissions/effective")
        assert response.status_code == 403


# ============================================================
# Edge cases & hardening — Admin Users endpoints
# ============================================================


class TestListUsersEdgeCases:
    """Edge cases for listing users."""

    @pytest.mark.asyncio
    async def test_list_users_offset_beyond_total(self, admin_client):
        """Offset beyond total returns empty."""
        client, session, _ = admin_client
        await _create_user(session, email="only@test.com")

        response = await client.get("/admin/users?limit=10&offset=100")
        data = response.json()
        assert data["users"] == []

    @pytest.mark.asyncio
    async def test_list_users_search_no_match(self, admin_client):
        """Search with no matching results."""
        client, session, _ = admin_client
        await _create_user(session, email="real@test.com")

        response = await client.get("/admin/users?search=xyznonexistent123")
        data = response.json()
        assert data["total"] == 0
        assert data["users"] == []

    @pytest.mark.asyncio
    async def test_list_users_search_partial_email(self, admin_client):
        """Search matches partial email."""
        client, session, _ = admin_client
        await _create_user(session, email="john.doe@company.com")

        response = await client.get("/admin/users?search=john.doe")
        data = response.json()
        assert data["total"] >= 1
        emails = {u["email"] for u in data["users"]}
        assert "john.doe@company.com" in emails


class TestDeleteUserEdgeCases:
    """Edge cases for user deletion."""

    @pytest.mark.asyncio
    async def test_delete_user_excluded_from_list(self, admin_client):
        """After deleting, user no longer appears in list."""
        client, session, _ = admin_client
        user = await _create_user(session, email="vanish@test.com")

        await client.delete(f"/admin/users/{user.id}")

        response = await client.get("/admin/users?search=vanish@test.com")
        assert response.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_delete_already_deleted_user(self, admin_client):
        """Deleting an already-deleted user re-applies soft delete (200).

        Documents current behavior: endpoint does not check deleted_at before
        soft-deleting, so it returns 200 even for already-deleted users.
        """
        from datetime import datetime, UTC
        client, session, _ = admin_client
        user = await _create_user(session, email="alreadydel@test.com")
        user.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        user.is_active = False
        await session.commit()

        response = await client.delete(f"/admin/users/{user.id}")
        assert response.status_code == 200


class TestUserRolesEdgeCases:
    """Edge cases for user role assignments."""

    @pytest.mark.asyncio
    async def test_assign_nonexistent_role(self, admin_client):
        """Assigning non-existent role returns error."""
        client, session, _ = admin_client
        user = await _create_user(session)

        response = await client.post(f"/admin/users/{user.id}/roles", json={
            "role_id": str(uuid4()),
        })
        assert response.status_code in (400, 404)

    @pytest.mark.asyncio
    async def test_assign_multiple_roles(self, admin_client):
        """User can have multiple roles."""
        client, session, _ = admin_client
        user = await _create_user(session)
        role1 = await _create_role(session, name="Multi1")
        role2 = await _create_role(session, name="Multi2")

        await client.post(f"/admin/users/{user.id}/roles", json={
            "role_id": str(role1.id),
        })
        await client.post(f"/admin/users/{user.id}/roles", json={
            "role_id": str(role2.id),
        })

        response = await client.get(f"/admin/users/{user.id}/roles")
        data = response.json()
        role_names = {r["role_name"] for r in data["roles"]}
        assert role_names == {"Multi1", "Multi2"}

    @pytest.mark.asyncio
    async def test_replace_roles_with_empty_list(self, admin_client):
        """PUT with empty list removes all roles."""
        client, session, _ = admin_client
        user = await _create_user(session)
        role = await _create_role(session, name="ToRemove")

        await client.post(f"/admin/users/{user.id}/roles", json={
            "role_id": str(role.id),
        })

        response = await client.put(f"/admin/users/{user.id}/roles", json={
            "role_ids": [],
        })
        assert response.status_code == 200
        assert response.json()["roles"] == []


class TestDirectPermissionEdgeCases:
    """Edge cases for direct permission assignments."""

    @pytest.mark.asyncio
    async def test_assign_duplicate_direct_permission(self, admin_client):
        """Re-assigning same direct permission succeeds silently.

        Documents current behavior: no duplicate check, just re-assigns.
        """
        client, session, _ = admin_client
        user = await _create_user(session)
        perm = await _create_permission(session, code="dup.direct")

        r1 = await client.post(f"/admin/users/{user.id}/permissions/direct", json={
            "permission_id": str(perm.id),
        })
        assert r1.status_code == 200

        r2 = await client.post(f"/admin/users/{user.id}/permissions/direct", json={
            "permission_id": str(perm.id),
        })
        assert r2.status_code == 200
        assert "permission" in r2.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_assign_direct_permission_nonexistent_user(self, admin_client):
        """Assigning direct permission to non-existent user.

        Documents current behavior: endpoint does not validate user existence
        before assigning, so it succeeds (200) even with a fake user ID.
        """
        client, session, _ = admin_client
        perm = await _create_permission(session, code="orphan.perm")

        response = await client.post(f"/admin/users/{uuid4()}/permissions/direct", json={
            "permission_id": str(perm.id),
        })
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_replace_direct_permissions_with_empty(self, admin_client):
        """PUT with empty list — documents current behavior.

        Current behavior: empty permission_ids does NOT remove existing
        permissions, it's treated as a no-op that keeps existing assignments.
        """
        client, session, _ = admin_client
        user = await _create_user(session)
        perm = await _create_permission(session, code="remove.all")

        await client.post(f"/admin/users/{user.id}/permissions/direct", json={
            "permission_id": str(perm.id),
        })

        response = await client.put(f"/admin/users/{user.id}/permissions/direct", json={
            "permission_ids": [],
        })
        assert response.status_code == 200
        # Existing permissions are preserved (not cleared)
        assert len(response.json()["direct_permissions"]) >= 1


class TestDirectPermissionSetEdgeCases:
    """Edge cases for direct permission set assignments."""

    @pytest.mark.asyncio
    async def test_assign_duplicate_direct_permission_set(self, admin_client):
        """Re-assigning same direct permission set succeeds silently.

        Documents current behavior: no duplicate check, just re-assigns.
        """
        client, session, _ = admin_client
        user = await _create_user(session)
        ps = await _create_permission_set(session, code="dup_ps")

        r1 = await client.post(
            f"/admin/users/{user.id}/permission-sets/direct",
            json={"permission_set_id": str(ps.id)},
        )
        assert r1.status_code == 200

        r2 = await client.post(
            f"/admin/users/{user.id}/permission-sets/direct",
            json={"permission_set_id": str(ps.id)},
        )
        assert r2.status_code == 200
        assert "permission set" in r2.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_replace_direct_permission_sets_with_empty(self, admin_client):
        """PUT with empty list — documents current behavior.

        Current behavior: empty permission_set_ids does NOT remove existing
        permission sets, it's treated as a no-op that keeps existing assignments.
        """
        client, session, _ = admin_client
        user = await _create_user(session)
        ps = await _create_permission_set(session, code="remove_ps_all")

        await client.post(
            f"/admin/users/{user.id}/permission-sets/direct",
            json={"permission_set_id": str(ps.id)},
        )

        response = await client.put(
            f"/admin/users/{user.id}/permission-sets/direct",
            json={"permission_set_ids": []},
        )
        assert response.status_code == 200
        # Existing permission sets are preserved (not cleared)
        assert len(response.json()["direct_permission_sets"]) >= 1
