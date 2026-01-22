"""
Verify RBAC Setup

Checks and fixes the RBAC data chain:
- permissions
- permission_sets
- permission_set_permissions
- roles
- role_permission_sets
- user_roles

Usage:
    python scripts/verify_rbac.py
"""

import asyncio
import sys
import os

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.api.db.session import async_session


async def verify_rbac():
    """Verify RBAC data chain is complete."""
    async with async_session() as session:
        print("\n" + "=" * 60)
        print("RBAC Data Verification")
        print("=" * 60)

        # 1. Check permissions table
        result = await session.execute(text("SELECT COUNT(*) FROM permissions"))
        perm_count = result.scalar()
        print(f"\n1. Permissions: {perm_count} records")

        if perm_count == 0:
            print("   ❌ No permissions found! Run migrations: alembic upgrade head")
            return False

        # 2. Check permission_sets table
        result = await session.execute(text("SELECT id, code, name FROM permission_sets"))
        ps_rows = result.fetchall()
        print(f"\n2. Permission Sets: {len(ps_rows)} records")
        for row in ps_rows:
            print(f"   - {row[1]}: {row[2]}")

        if len(ps_rows) == 0:
            print("   ❌ No permission sets found! Run migrations: alembic upgrade head")
            return False

        # Check for full_admin permission set
        full_admin = next((r for r in ps_rows if r[1] == 'full_admin'), None)
        if not full_admin:
            print("   ❌ 'full_admin' permission set not found!")
            return False
        else:
            print(f"   ✓ full_admin found (ID: {full_admin[0]})")

        # 3. Check permission_set_permissions
        result = await session.execute(text("""
            SELECT ps.code, COUNT(psp.permission_id) as perm_count
            FROM permission_sets ps
            LEFT JOIN permission_set_permissions psp ON ps.id = psp.permission_set_id
            GROUP BY ps.id, ps.code
        """))
        psp_rows = result.fetchall()
        print(f"\n3. Permission Set -> Permissions mapping:")
        for row in psp_rows:
            status = "✓" if row[1] > 0 else "❌"
            print(f"   {status} {row[0]}: {row[1]} permissions")

        # Check full_admin has permissions
        full_admin_perms = next((r for r in psp_rows if r[0] == 'full_admin'), None)
        if full_admin_perms and full_admin_perms[1] == 0:
            print("\n   ⚠️  full_admin has 0 permissions! Fixing...")
            # Fix: add all permissions to full_admin
            await session.execute(text("""
                INSERT INTO permission_set_permissions (permission_set_id, permission_id)
                SELECT ps.id, p.id
                FROM permission_sets ps, permissions p
                WHERE ps.code = 'full_admin' AND p.deleted_at IS NULL
                ON CONFLICT DO NOTHING
            """))
            await session.commit()
            print("   ✓ Fixed full_admin permissions")

        # 4. Check roles table
        result = await session.execute(text("SELECT id, name, is_system FROM roles WHERE deleted_at IS NULL"))
        role_rows = result.fetchall()
        print(f"\n4. Roles: {len(role_rows)} records")
        for row in role_rows:
            system_tag = " (system)" if row[2] else ""
            print(f"   - {row[1]}{system_tag}")

        # Check for Super Admin role
        super_admin = next((r for r in role_rows if r[1] == 'Super Admin'), None)
        if not super_admin:
            print("   ❌ 'Super Admin' role not found!")
            return False
        else:
            print(f"   ✓ Super Admin found (ID: {super_admin[0]})")

        # 5. Check role_permission_sets
        result = await session.execute(text("""
            SELECT r.name as role_name, ps.code as ps_code, ps.name as ps_name
            FROM roles r
            LEFT JOIN role_permission_sets rps ON r.id = rps.role_id
            LEFT JOIN permission_sets ps ON rps.permission_set_id = ps.id
            WHERE r.deleted_at IS NULL
            ORDER BY r.name
        """))
        rps_rows = result.fetchall()
        print(f"\n5. Role -> Permission Set mapping:")

        current_role = None
        for row in rps_rows:
            if row[0] != current_role:
                current_role = row[0]
                print(f"   {current_role}:")
            if row[1]:
                print(f"      - {row[1]} ({row[2]})")
            else:
                print(f"      ❌ No permission sets assigned!")

        # Check Super Admin has full_admin
        super_admin_ps = [r for r in rps_rows if r[0] == 'Super Admin']
        has_full_admin = any(r[1] == 'full_admin' for r in super_admin_ps)

        if not has_full_admin:
            print("\n   ⚠️  Super Admin doesn't have full_admin permission set! Fixing...")
            # Fix: assign full_admin to Super Admin
            await session.execute(text("""
                INSERT INTO role_permission_sets (role_id, permission_set_id)
                SELECT r.id, ps.id
                FROM roles r, permission_sets ps
                WHERE r.name = 'Super Admin' AND ps.code = 'full_admin'
                ON CONFLICT DO NOTHING
            """))
            await session.commit()
            print("   ✓ Fixed Super Admin role permissions")

        # 6. Check user_roles
        result = await session.execute(text("""
            SELECT u.email, r.name as role_name
            FROM users u
            LEFT JOIN user_roles ur ON u.id = ur.user_id
            LEFT JOIN roles r ON ur.role_id = r.id
            ORDER BY u.email
        """))
        ur_rows = result.fetchall()
        print(f"\n6. User -> Role assignments:")
        for row in ur_rows:
            role = row[1] if row[1] else "❌ No roles"
            print(f"   - {row[0]}: {role}")

        # 7. Test end-to-end: get permissions for admin user
        print(f"\n7. End-to-end permission check for admin@gmail.com:")
        result = await session.execute(text("""
            SELECT DISTINCT p.code
            FROM permissions p
            JOIN permission_set_permissions psp ON p.id = psp.permission_id
            JOIN role_permission_sets rps ON psp.permission_set_id = rps.permission_set_id
            JOIN user_roles ur ON rps.role_id = ur.role_id
            JOIN users u ON ur.user_id = u.id
            WHERE u.email = 'admin@gmail.com'
            AND p.deleted_at IS NULL
            LIMIT 10
        """))
        perm_rows = result.fetchall()
        if perm_rows:
            print(f"   ✓ Found {len(perm_rows)}+ permissions:")
            for row in perm_rows[:5]:
                print(f"      - {row[0]}")
            if len(perm_rows) > 5:
                print(f"      ... and more")
        else:
            print("   ❌ No permissions found for admin user!")
            print("      This means the permission chain is broken somewhere.")

        print("\n" + "=" * 60)
        print("Verification complete!")
        print("=" * 60 + "\n")

        return True


if __name__ == "__main__":
    asyncio.run(verify_rbac())
