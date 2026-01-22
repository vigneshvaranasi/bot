"""seed RBAC permissions, permission sets, and roles

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-01-19

This migration seeds the RBAC system with:
- 27 permissions across 10 categories
- 14 predefined permission sets
- 8 predefined system roles
- Migrates existing admin/user roles to new RBAC structure
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'e5f6g7h8i9j0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6g7h8i9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Define all permissions
PERMISSIONS = [
    # AI/ML Settings
    {'code': 'aiml.view', 'name': 'View AI/ML Settings', 'description': 'Can view model, temperature, deny words, langfuse settings', 'category': 'aiml'},
    {'code': 'aiml.edit', 'name': 'Edit AI/ML Settings', 'description': 'Can modify all AI/ML settings', 'category': 'aiml'},

    # Authentication
    {'code': 'auth.view', 'name': 'View Auth Settings', 'description': 'Can view authentication provider settings', 'category': 'auth'},
    {'code': 'auth.edit', 'name': 'Edit Auth Settings', 'description': 'Can enable/disable auth providers', 'category': 'auth'},

    # LLM Providers
    {'code': 'llm_provider.view', 'name': 'View LLM Providers', 'description': 'Can view configured LLM providers', 'category': 'llm_provider'},
    {'code': 'llm_provider.create', 'name': 'Create LLM Provider', 'description': 'Can add new LLM providers', 'category': 'llm_provider'},
    {'code': 'llm_provider.edit', 'name': 'Edit LLM Provider', 'description': 'Can modify existing providers', 'category': 'llm_provider'},
    {'code': 'llm_provider.delete', 'name': 'Delete LLM Provider', 'description': 'Can remove providers', 'category': 'llm_provider'},
    {'code': 'llm_provider.test', 'name': 'Test LLM Provider', 'description': 'Can test provider connections', 'category': 'llm_provider'},

    # Integrations
    {'code': 'integration.view', 'name': 'View Integrations', 'description': 'Can view integration configs', 'category': 'integration'},
    {'code': 'integration.create', 'name': 'Create Integration', 'description': 'Can add new integrations', 'category': 'integration'},
    {'code': 'integration.edit', 'name': 'Edit Integration', 'description': 'Can modify integrations', 'category': 'integration'},
    {'code': 'integration.delete', 'name': 'Delete Integration', 'description': 'Can remove integrations', 'category': 'integration'},
    {'code': 'integration.sync', 'name': 'Sync Integration', 'description': 'Can trigger data sync', 'category': 'integration'},

    # User Management
    {'code': 'user.view', 'name': 'View Users', 'description': 'Can view user list', 'category': 'user'},
    {'code': 'user.edit', 'name': 'Edit User', 'description': 'Can modify user status/roles', 'category': 'user'},
    {'code': 'user.delete', 'name': 'Delete User', 'description': 'Can soft-delete users', 'category': 'user'},

    # Role Management
    {'code': 'role.view', 'name': 'View Roles', 'description': 'Can view roles and permissions', 'category': 'role'},
    {'code': 'role.create', 'name': 'Create Role', 'description': 'Can create custom roles', 'category': 'role'},
    {'code': 'role.edit', 'name': 'Edit Role', 'description': 'Can modify role permission sets', 'category': 'role'},
    {'code': 'role.delete', 'name': 'Delete Role', 'description': 'Can delete custom roles', 'category': 'role'},

    # Permission Set Management
    {'code': 'permission_set.view', 'name': 'View Permission Sets', 'description': 'Can view permission sets', 'category': 'permission_set'},
    {'code': 'permission_set.create', 'name': 'Create Permission Set', 'description': 'Can create custom permission sets', 'category': 'permission_set'},
    {'code': 'permission_set.edit', 'name': 'Edit Permission Set', 'description': 'Can modify permission sets', 'category': 'permission_set'},
    {'code': 'permission_set.delete', 'name': 'Delete Permission Set', 'description': 'Can delete custom permission sets', 'category': 'permission_set'},

    # History/Audit
    {'code': 'history.view', 'name': 'View Config History', 'description': 'Can view configuration history', 'category': 'history'},
    {'code': 'history.rollback', 'name': 'Rollback Configuration', 'description': 'Can rollback to previous versions', 'category': 'history'},

    # Chat
    {'code': 'chat.use', 'name': 'Use Chat', 'description': 'Can interact with the chatbot', 'category': 'chat'},

    # System
    {'code': 'system.view', 'name': 'View System Config', 'description': 'Can view system-wide settings', 'category': 'system'},
    {'code': 'system.edit', 'name': 'Edit System Config', 'description': 'Can modify system settings', 'category': 'system'},
]

# Define permission sets with their permissions
PERMISSION_SETS = {
    'aiml_viewer': {
        'name': 'AI/ML Viewer',
        'description': 'View-only access to AI/ML settings',
        'permissions': ['aiml.view'],
    },
    'aiml_manager': {
        'name': 'AI/ML Manager',
        'description': 'Full access to AI/ML settings',
        'permissions': ['aiml.view', 'aiml.edit'],
    },
    'auth_viewer': {
        'name': 'Auth Viewer',
        'description': 'View-only access to authentication settings',
        'permissions': ['auth.view'],
    },
    'auth_manager': {
        'name': 'Auth Manager',
        'description': 'Full access to authentication settings',
        'permissions': ['auth.view', 'auth.edit'],
    },
    'llm_viewer': {
        'name': 'LLM Viewer',
        'description': 'View-only access to LLM providers',
        'permissions': ['llm_provider.view'],
    },
    'llm_manager': {
        'name': 'LLM Manager',
        'description': 'Full access to LLM providers',
        'permissions': ['llm_provider.view', 'llm_provider.create', 'llm_provider.edit', 'llm_provider.delete', 'llm_provider.test'],
    },
    'integration_viewer': {
        'name': 'Integration Viewer',
        'description': 'View-only access to integrations',
        'permissions': ['integration.view'],
    },
    'integration_manager': {
        'name': 'Integration Manager',
        'description': 'Full access to integrations',
        'permissions': ['integration.view', 'integration.create', 'integration.edit', 'integration.delete', 'integration.sync'],
    },
    'user_viewer': {
        'name': 'User Viewer',
        'description': 'View-only access to user management',
        'permissions': ['user.view'],
    },
    'user_manager': {
        'name': 'User Manager',
        'description': 'Full access to user management',
        'permissions': ['user.view', 'user.edit', 'user.delete', 'role.view'],
    },
    'role_manager': {
        'name': 'Role Manager',
        'description': 'Full access to role and permission set management',
        'permissions': ['role.view', 'role.create', 'role.edit', 'role.delete', 'permission_set.view', 'permission_set.create', 'permission_set.edit', 'permission_set.delete'],
    },
    'auditor': {
        'name': 'Auditor',
        'description': 'View-only access to all settings and history',
        'permissions': ['history.view', 'aiml.view', 'auth.view', 'llm_provider.view', 'integration.view', 'user.view', 'role.view', 'permission_set.view'],
    },
    'chat_user': {
        'name': 'Chat User',
        'description': 'Basic access to use the chatbot',
        'permissions': ['chat.use'],
    },
    'full_admin': {
        'name': 'Full Admin',
        'description': 'Full administrative access to all features',
        'permissions': [p['code'] for p in PERMISSIONS],  # All permissions
    },
}

# Define roles with their permission sets
ROLES = {
    'Super Admin': {
        'description': 'Full administrative access to all system features',
        'permission_sets': ['full_admin'],
    },
    'Configuration Manager': {
        'description': 'Manages AI/ML and authentication configuration',
        'permission_sets': ['aiml_manager', 'auth_manager', 'auditor'],
    },
    'LLM Administrator': {
        'description': 'Manages LLM providers and views AI/ML settings',
        'permission_sets': ['llm_manager', 'aiml_viewer'],
    },
    'Integration Administrator': {
        'description': 'Manages external integrations',
        'permission_sets': ['integration_manager'],
    },
    'Security Administrator': {
        'description': 'Manages authentication and user access',
        'permission_sets': ['auth_manager', 'user_manager'],
    },
    'Auditor': {
        'description': 'Read-only access for compliance and auditing',
        'permission_sets': ['auditor'],
    },
    'Advanced User': {
        'description': 'Chat access with view permissions for settings',
        'permission_sets': ['chat_user', 'aiml_viewer', 'llm_viewer'],
    },
    'Basic User': {
        'description': 'Basic chat access only',
        'permission_sets': ['chat_user'],
    },
}


def upgrade() -> None:
    """Seed RBAC data."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Clear existing simple permissions (from init migration) if they exist
    if 'role_permission' in tables:
        conn.execute(sa.text("DELETE FROM role_permission"))
    if 'user_permission' in tables:
        conn.execute(sa.text("DELETE FROM user_permission"))
    # Clear permissions table if it has any data
    conn.execute(sa.text("DELETE FROM permissions"))

    # 2. Insert all permissions
    permission_ids = {}
    for perm in PERMISSIONS:
        perm_id = str(uuid.uuid4())
        permission_ids[perm['code']] = perm_id
        conn.execute(sa.text("""
            INSERT INTO permissions (id, code, name, description, category)
            VALUES (:id, :code, :name, :description, :category)
        """), {
            'id': perm_id,
            'code': perm['code'],
            'name': perm['name'],
            'description': perm['description'],
            'category': perm['category'],
        })

    # 3. Insert all permission sets and their permissions
    permission_set_ids = {}
    for ps_code, ps_data in PERMISSION_SETS.items():
        ps_id = str(uuid.uuid4())
        permission_set_ids[ps_code] = ps_id
        conn.execute(sa.text("""
            INSERT INTO permission_sets (id, code, name, description)
            VALUES (:id, :code, :name, :description)
        """), {
            'id': ps_id,
            'code': ps_code,
            'name': ps_data['name'],
            'description': ps_data['description'],
        })

        # Link permissions to this set
        for perm_code in ps_data['permissions']:
            conn.execute(sa.text("""
                INSERT INTO permission_set_permissions (permission_set_id, permission_id)
                VALUES (:ps_id, :perm_id)
            """), {
                'ps_id': ps_id,
                'perm_id': permission_ids[perm_code],
            })

    # 4. Update existing roles or create new ones
    role_ids = {}

    # Get existing roles
    existing_roles = conn.execute(sa.text("SELECT id, name FROM roles")).fetchall()
    existing_role_map = {r[1]: r[0] for r in existing_roles}

    for role_name, role_data in ROLES.items():
        if role_name == 'Super Admin' and 'admin' in existing_role_map:
            # Update existing 'admin' role to 'Super Admin'
            role_id = str(existing_role_map['admin'])
            conn.execute(sa.text("""
                UPDATE roles
                SET name = :name, description = :description
                WHERE id = :id
            """), {
                'id': role_id,
                'name': role_name,
                'description': role_data['description'],
            })
        elif role_name == 'Basic User' and 'user' in existing_role_map:
            # Update existing 'user' role to 'Basic User'
            role_id = str(existing_role_map['user'])
            conn.execute(sa.text("""
                UPDATE roles
                SET name = :name, description = :description
                WHERE id = :id
            """), {
                'id': role_id,
                'name': role_name,
                'description': role_data['description'],
            })
        elif role_name in existing_role_map:
            # Role already exists, just update
            role_id = str(existing_role_map[role_name])
            conn.execute(sa.text("""
                UPDATE roles
                SET description = :description
                WHERE id = :id
            """), {
                'id': role_id,
                'description': role_data['description'],
            })
        else:
            # Create new role
            role_id = str(uuid.uuid4())
            conn.execute(sa.text("""
                INSERT INTO roles (id, name, description)
                VALUES (:id, :name, :description)
            """), {
                'id': role_id,
                'name': role_name,
                'description': role_data['description'],
            })

        role_ids[role_name] = role_id

        # Link permission sets to this role
        for ps_code in role_data['permission_sets']:
            conn.execute(sa.text("""
                INSERT INTO role_permission_sets (role_id, permission_set_id)
                VALUES (:role_id, :ps_id)
                ON CONFLICT DO NOTHING
            """), {
                'role_id': role_id,
                'ps_id': permission_set_ids[ps_code],
            })

    # 5. Update user_roles for users that had 'admin' or 'user' role
    # This ensures existing users get the proper new role assignments
    if 'admin' in existing_role_map:
        old_admin_id = str(existing_role_map['admin'])
        new_super_admin_id = role_ids.get('Super Admin')
        if new_super_admin_id and old_admin_id != new_super_admin_id:
            conn.execute(sa.text("""
                UPDATE user_roles SET role_id = :new_id WHERE role_id = :old_id
            """), {'new_id': new_super_admin_id, 'old_id': old_admin_id})

    if 'user' in existing_role_map:
        old_user_id = str(existing_role_map['user'])
        new_basic_user_id = role_ids.get('Basic User')
        if new_basic_user_id and old_user_id != new_basic_user_id:
            conn.execute(sa.text("""
                UPDATE user_roles SET role_id = :new_id WHERE role_id = :old_id
            """), {'new_id': new_basic_user_id, 'old_id': old_user_id})


def downgrade() -> None:
    """Remove seeded RBAC data and restore original roles."""
    conn = op.get_bind()

    # Clear RBAC junction tables
    conn.execute(sa.text("DELETE FROM role_permission_sets"))
    conn.execute(sa.text("DELETE FROM permission_set_permissions"))

    # Clear permission sets
    conn.execute(sa.text("DELETE FROM permission_sets"))

    # Clear new permissions
    conn.execute(sa.text("DELETE FROM permissions"))

    # Restore original role names
    conn.execute(sa.text("""
        UPDATE roles SET name = 'admin', description = NULL
        WHERE name = 'Super Admin'
    """))
    conn.execute(sa.text("""
        UPDATE roles SET name = 'user', description = NULL
        WHERE name = 'Basic User'
    """))

    # Delete new roles
    conn.execute(sa.text("""
        DELETE FROM roles WHERE name NOT IN ('admin', 'user')
    """))
