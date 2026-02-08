"""add direct user permissions and RBAC audit log tables

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-01-22

This migration adds:
1. user_permissions - Junction table for direct user -> permission assignment (bypassing roles)
2. user_permission_sets - Junction table for direct user -> permission_set assignment (bypassing roles)
3. rbac_audit_logs - Audit trail for all RBAC changes

The effective permissions for a user become the UNION of:
- Permissions from roles (Role -> PermissionSet -> Permission)
- Permissions from direct permission set assignments (User -> PermissionSet -> Permission)
- Permissions from direct permission assignments (User -> Permission)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, Sequence[str], None] = 'f6g7h8i9j0k1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add direct user permission tables and RBAC audit log."""

    # 1. Create user_permissions junction table
    op.create_table(
        'user_permissions',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_id', UUID(as_uuid=True), sa.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('assigned_at', sa.DateTime, server_default=sa.text('now()')),
        sa.Column('assigned_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    )

    # 2. Create user_permission_sets junction table
    op.create_table(
        'user_permission_sets',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_set_id', UUID(as_uuid=True), sa.ForeignKey('permission_sets.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('assigned_at', sa.DateTime, server_default=sa.text('now()')),
        sa.Column('assigned_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    )

    # 3. Create rbac_audit_logs table
    op.create_table(
        'rbac_audit_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('entity_type', sa.String(50), nullable=False, comment='Type: role, permission_set, user_role, user_permission, user_permission_set'),
        sa.Column('entity_id', UUID(as_uuid=True), nullable=False, comment='Primary entity ID'),
        sa.Column('secondary_entity_id', UUID(as_uuid=True), nullable=True, comment='Secondary ID for junction tables'),
        sa.Column('action', sa.String(20), nullable=False, comment='Action: create, update, delete, assign, unassign'),
        sa.Column('old_value', JSONB, nullable=True, comment='Previous state'),
        sa.Column('new_value', JSONB, nullable=True, comment='New state'),
        sa.Column('changed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('changed_at', sa.DateTime, server_default=sa.text('now()'), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True)
    )

    # 4. Create indexes for efficient queries
    # user_permissions indexes
    op.create_index('idx_user_permissions_user_id', 'user_permissions', ['user_id'])
    op.create_index('idx_user_permissions_permission_id', 'user_permissions', ['permission_id'])

    # user_permission_sets indexes
    op.create_index('idx_user_permission_sets_user_id', 'user_permission_sets', ['user_id'])
    op.create_index('idx_user_permission_sets_permission_set_id', 'user_permission_sets', ['permission_set_id'])

    # rbac_audit_logs indexes
    op.create_index('idx_rbac_audit_entity_type', 'rbac_audit_logs', ['entity_type'])
    op.create_index('idx_rbac_audit_entity_id', 'rbac_audit_logs', ['entity_id'])
    op.create_index('idx_rbac_audit_changed_by', 'rbac_audit_logs', ['changed_by'])
    op.create_index('idx_rbac_audit_changed_at', 'rbac_audit_logs', ['changed_at'])
    op.create_index('idx_rbac_audit_action', 'rbac_audit_logs', ['action'])
    # Composite index for filtering by entity type and time
    op.create_index('idx_rbac_audit_type_time', 'rbac_audit_logs', ['entity_type', 'changed_at'])


def downgrade() -> None:
    """Remove direct user permission tables and RBAC audit log."""

    # Drop indexes
    op.drop_index('idx_rbac_audit_type_time', table_name='rbac_audit_logs')
    op.drop_index('idx_rbac_audit_action', table_name='rbac_audit_logs')
    op.drop_index('idx_rbac_audit_changed_at', table_name='rbac_audit_logs')
    op.drop_index('idx_rbac_audit_changed_by', table_name='rbac_audit_logs')
    op.drop_index('idx_rbac_audit_entity_id', table_name='rbac_audit_logs')
    op.drop_index('idx_rbac_audit_entity_type', table_name='rbac_audit_logs')

    op.drop_index('idx_user_permission_sets_permission_set_id', table_name='user_permission_sets')
    op.drop_index('idx_user_permission_sets_user_id', table_name='user_permission_sets')

    op.drop_index('idx_user_permissions_permission_id', table_name='user_permissions')
    op.drop_index('idx_user_permissions_user_id', table_name='user_permissions')

    # Drop tables
    op.drop_table('rbac_audit_logs')
    op.drop_table('user_permission_sets')
    op.drop_table('user_permissions')
