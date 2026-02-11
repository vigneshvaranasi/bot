"""seed knowledge base permissions

Revision ID: b2c3d4e5f6h8
Revises: a1b2c3d4e5f7
Create Date: 2026-02-10 10:01:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6h8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


KB_PERMISSIONS = [
    {'code': 'kb.view', 'name': 'View Knowledge Base', 'description': 'Can view knowledge base versions and data', 'category': 'knowledge_base'},
    {'code': 'kb.upload', 'name': 'Upload Incident Data', 'description': 'Can upload incident files to the knowledge base', 'category': 'knowledge_base'},
    {'code': 'kb.validate', 'name': 'Validate KB Data', 'description': 'Can validate and map incident data schemas', 'category': 'knowledge_base'},
    {'code': 'kb.ingest', 'name': 'Ingest KB Data', 'description': 'Can ingest validated data into the vector database', 'category': 'knowledge_base'},
    {'code': 'kb.version_manage', 'name': 'Manage KB Versions', 'description': 'Can activate and delete knowledge base versions', 'category': 'knowledge_base'},
    {'code': 'kb.rollback', 'name': 'Rollback KB Version', 'description': 'Can rollback to a previous knowledge base version', 'category': 'knowledge_base'},
]


def upgrade() -> None:
    """Seed KB permissions and add them to existing roles."""
    conn = op.get_bind()

    # 1. Insert KB permissions
    kb_perm_ids = {}
    for perm in KB_PERMISSIONS:
        perm_id = str(uuid.uuid4())
        kb_perm_ids[perm['code']] = perm_id
        conn.execute(sa.text("""
            INSERT INTO permissions (id, code, name, description, category)
            VALUES (:id, :code, :name, :description, :category)
            ON CONFLICT (code) DO NOTHING
        """), {
            'id': perm_id,
            'code': perm['code'],
            'name': perm['name'],
            'description': perm['description'],
            'category': perm['category'],
        })

    # Re-read actual IDs in case ON CONFLICT hit
    for perm in KB_PERMISSIONS:
        row = conn.execute(
            sa.text("SELECT id FROM permissions WHERE code = :code"),
            {'code': perm['code']},
        ).fetchone()
        if row:
            kb_perm_ids[perm['code']] = str(row[0])

    # 2. Create kb_manager permission set (all KB permissions)
    kb_manager_id = str(uuid.uuid4())
    conn.execute(sa.text("""
        INSERT INTO permission_sets (id, code, name, description)
        VALUES (:id, 'kb_manager', 'KB Manager', 'Full access to knowledge base management')
        ON CONFLICT (code) DO NOTHING
    """), {'id': kb_manager_id})

    # Re-read actual ID
    row = conn.execute(
        sa.text("SELECT id FROM permission_sets WHERE code = 'kb_manager'")
    ).fetchone()
    if row:
        kb_manager_id = str(row[0])

    for perm_code, perm_id in kb_perm_ids.items():
        conn.execute(sa.text("""
            INSERT INTO permission_set_permissions (permission_set_id, permission_id)
            VALUES (:ps_id, :perm_id)
            ON CONFLICT DO NOTHING
        """), {'ps_id': kb_manager_id, 'perm_id': perm_id})

    # 3. Create kb_viewer permission set (kb.view only)
    kb_viewer_id = str(uuid.uuid4())
    conn.execute(sa.text("""
        INSERT INTO permission_sets (id, code, name, description)
        VALUES (:id, 'kb_viewer', 'KB Viewer', 'View-only access to knowledge base')
        ON CONFLICT (code) DO NOTHING
    """), {'id': kb_viewer_id})

    row = conn.execute(
        sa.text("SELECT id FROM permission_sets WHERE code = 'kb_viewer'")
    ).fetchone()
    if row:
        kb_viewer_id = str(row[0])

    conn.execute(sa.text("""
        INSERT INTO permission_set_permissions (permission_set_id, permission_id)
        VALUES (:ps_id, :perm_id)
        ON CONFLICT DO NOTHING
    """), {'ps_id': kb_viewer_id, 'perm_id': kb_perm_ids['kb.view']})

    # 4. Add kb_manager to Super Admin role
    super_admin = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'Super Admin'")
    ).fetchone()
    if super_admin:
        conn.execute(sa.text("""
            INSERT INTO role_permission_sets (role_id, permission_set_id)
            VALUES (:role_id, :ps_id)
            ON CONFLICT DO NOTHING
        """), {'role_id': str(super_admin[0]), 'ps_id': kb_manager_id})

    # 5. Also add all KB permissions to full_admin permission set
    full_admin_ps = conn.execute(
        sa.text("SELECT id FROM permission_sets WHERE code = 'full_admin'")
    ).fetchone()
    if full_admin_ps:
        for perm_code, perm_id in kb_perm_ids.items():
            conn.execute(sa.text("""
                INSERT INTO permission_set_permissions (permission_set_id, permission_id)
                VALUES (:ps_id, :perm_id)
                ON CONFLICT DO NOTHING
            """), {'ps_id': str(full_admin_ps[0]), 'perm_id': perm_id})

    # 6. Add kb_viewer to Auditor role
    auditor_role = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'Auditor'")
    ).fetchone()
    if auditor_role:
        conn.execute(sa.text("""
            INSERT INTO role_permission_sets (role_id, permission_set_id)
            VALUES (:role_id, :ps_id)
            ON CONFLICT DO NOTHING
        """), {'role_id': str(auditor_role[0]), 'ps_id': kb_viewer_id})

    # Also add kb.view to auditor permission set
    auditor_ps = conn.execute(
        sa.text("SELECT id FROM permission_sets WHERE code = 'auditor'")
    ).fetchone()
    if auditor_ps:
        conn.execute(sa.text("""
            INSERT INTO permission_set_permissions (permission_set_id, permission_id)
            VALUES (:ps_id, :perm_id)
            ON CONFLICT DO NOTHING
        """), {'ps_id': str(auditor_ps[0]), 'perm_id': kb_perm_ids['kb.view']})


def downgrade() -> None:
    """Remove KB permissions and permission sets."""
    conn = op.get_bind()

    kb_codes = [p['code'] for p in KB_PERMISSIONS]

    # Remove from permission_set_permissions
    for code in kb_codes:
        conn.execute(sa.text("""
            DELETE FROM permission_set_permissions
            WHERE permission_id IN (SELECT id FROM permissions WHERE code = :code)
        """), {'code': code})

    # Remove role_permission_sets for kb_manager and kb_viewer
    for ps_code in ('kb_manager', 'kb_viewer'):
        conn.execute(sa.text("""
            DELETE FROM role_permission_sets
            WHERE permission_set_id IN (SELECT id FROM permission_sets WHERE code = :code)
        """), {'code': ps_code})

    # Remove permission sets
    conn.execute(sa.text("DELETE FROM permission_sets WHERE code IN ('kb_manager', 'kb_viewer')"))

    # Remove permissions
    for code in kb_codes:
        conn.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {'code': code})
