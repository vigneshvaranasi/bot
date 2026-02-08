"""add RBAC tables for 3-level permission system

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-01-19

This migration implements a Salesforce-like 3-level RBAC system:
- Permissions (atomic) -> Permission Sets (groups) -> Roles -> Users
- Supports multiple roles per user
- Preserves backward compatibility with existing role_id
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add RBAC tables and update existing tables."""

    # Check if permissions table exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Handle permissions table - create if doesn't exist, or update if it does
    if 'permissions' not in tables:
        # Create permissions table from scratch with all new columns
        op.create_table(
            'permissions',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('code', sa.String(100), unique=True, nullable=False),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('category', sa.String(50), nullable=False),
            sa.Column('is_system', sa.Boolean, server_default='true', nullable=False),
            sa.Column('created_at', sa.DateTime, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()')),
            sa.Column('deleted_at', sa.DateTime, nullable=True),
            sa.UniqueConstraint('name', name='uq_permissions_name')
        )
    else:
        # Update existing permissions table with new columns
        existing_columns = [col['name'] for col in inspector.get_columns('permissions')]

        if 'code' not in existing_columns:
            op.add_column('permissions', sa.Column('code', sa.String(100), nullable=True))

        if 'description' not in existing_columns:
            op.add_column('permissions', sa.Column('description', sa.Text, nullable=True))

        if 'category' not in existing_columns:
            op.add_column('permissions', sa.Column('category', sa.String(50), nullable=True))

        if 'is_system' not in existing_columns:
            op.add_column('permissions', sa.Column('is_system', sa.Boolean, server_default='true', nullable=False))

        if 'created_at' not in existing_columns:
            op.add_column('permissions', sa.Column('created_at', sa.DateTime, server_default=sa.text('now()')))

        if 'updated_at' not in existing_columns:
            op.add_column('permissions', sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()')))

        # Update existing permissions: set code from name
        op.execute("UPDATE permissions SET code = LOWER(REPLACE(name, ' ', '_')) WHERE code IS NULL")

        # Make code not nullable and unique
        if 'code' not in existing_columns:
            op.alter_column('permissions', 'code', nullable=False)
            op.create_unique_constraint('uq_permissions_code', 'permissions', ['code'])

    # 2. Update roles table with new columns (check if they exist first)
    roles_columns = [col['name'] for col in inspector.get_columns('roles')]

    if 'description' not in roles_columns:
        op.add_column('roles', sa.Column('description', sa.Text, nullable=True))

    if 'is_system' not in roles_columns:
        op.add_column('roles', sa.Column('is_system', sa.Boolean, server_default='false', nullable=False))

    if 'created_at' not in roles_columns:
        op.add_column('roles', sa.Column('created_at', sa.DateTime, server_default=sa.text('now()')))

    if 'updated_at' not in roles_columns:
        op.add_column('roles', sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()')))

    # Mark existing roles as system roles
    op.execute("UPDATE roles SET is_system = true WHERE name IN ('admin', 'user')")

    # 3. Create permission_sets table
    op.create_table(
        'permission_sets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('code', sa.String(100), unique=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('is_system', sa.Boolean, server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()')),
        sa.Column('deleted_at', sa.DateTime, nullable=True)
    )

    # 4. Create permission_set_permissions junction table
    op.create_table(
        'permission_set_permissions',
        sa.Column('permission_set_id', UUID(as_uuid=True), sa.ForeignKey('permission_sets.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_id', UUID(as_uuid=True), sa.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True)
    )

    # 5. Create role_permission_sets junction table
    op.create_table(
        'role_permission_sets',
        sa.Column('role_id', UUID(as_uuid=True), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_set_id', UUID(as_uuid=True), sa.ForeignKey('permission_sets.id', ondelete='CASCADE'), primary_key=True)
    )

    # 6. Create user_roles junction table
    op.create_table(
        'user_roles',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('role_id', UUID(as_uuid=True), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('assigned_at', sa.DateTime, server_default=sa.text('now()')),
        sa.Column('assigned_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    )

    # 7. Make users.role_id nullable for backward compatibility transition
    op.alter_column('users', 'role_id', nullable=True)

    # 8. Migrate existing user roles to user_roles table
    op.execute("""
        INSERT INTO user_roles (user_id, role_id, assigned_at)
        SELECT id, role_id, created_at
        FROM users
        WHERE role_id IS NOT NULL
        AND deleted_at IS NULL
    """)

    # 9. Create indexes for efficient queries
    op.create_index('idx_permissions_code', 'permissions', ['code'])
    op.create_index('idx_permissions_category', 'permissions', ['category'])
    op.create_index('idx_permission_sets_code', 'permission_sets', ['code'])
    op.create_index('idx_user_roles_user_id', 'user_roles', ['user_id'])
    op.create_index('idx_user_roles_role_id', 'user_roles', ['role_id'])


def downgrade() -> None:
    """Remove RBAC tables and restore original structure."""

    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Drop indexes (check if they exist first)
    indexes = {idx['name'] for idx in inspector.get_indexes('user_roles')} if 'user_roles' in inspector.get_table_names() else set()
    if 'idx_user_roles_role_id' in indexes:
        op.drop_index('idx_user_roles_role_id', table_name='user_roles')
    if 'idx_user_roles_user_id' in indexes:
        op.drop_index('idx_user_roles_user_id', table_name='user_roles')

    permission_sets_indexes = {idx['name'] for idx in inspector.get_indexes('permission_sets')} if 'permission_sets' in inspector.get_table_names() else set()
    if 'idx_permission_sets_code' in permission_sets_indexes:
        op.drop_index('idx_permission_sets_code', table_name='permission_sets')

    permissions_indexes = {idx['name'] for idx in inspector.get_indexes('permissions')} if 'permissions' in inspector.get_table_names() else set()
    if 'idx_permissions_category' in permissions_indexes:
        op.drop_index('idx_permissions_category', table_name='permissions')
    if 'idx_permissions_code' in permissions_indexes:
        op.drop_index('idx_permissions_code', table_name='permissions')

    # Make users.role_id not nullable again (restore from user_roles)
    op.execute("""
        UPDATE users u
        SET role_id = ur.role_id
        FROM user_roles ur
        WHERE u.id = ur.user_id
        AND u.role_id IS NULL
    """)
    op.alter_column('users', 'role_id', nullable=False)

    # Drop new junction tables
    op.drop_table('user_roles')
    op.drop_table('role_permission_sets')
    op.drop_table('permission_set_permissions')
    op.drop_table('permission_sets')

    # Remove new columns from roles
    roles_columns = [col['name'] for col in inspector.get_columns('roles')]
    if 'updated_at' in roles_columns:
        op.drop_column('roles', 'updated_at')
    if 'created_at' in roles_columns:
        op.drop_column('roles', 'created_at')
    if 'is_system' in roles_columns:
        op.drop_column('roles', 'is_system')
    if 'description' in roles_columns:
        op.drop_column('roles', 'description')

    # Check if permissions table existed before this migration
    # If role_permission table exists, it means permissions was an existing table
    # Otherwise, we created the permissions table and should drop it
    tables = inspector.get_table_names()
    if 'role_permission' in tables:
        # permissions existed before - just remove added columns
        try:
            op.drop_constraint('uq_permissions_code', 'permissions', type_='unique')
        except Exception:
            pass  # Constraint might not exist
        permissions_columns = [col['name'] for col in inspector.get_columns('permissions')]
        for col in ['updated_at', 'created_at', 'is_system', 'category', 'description', 'code']:
            if col in permissions_columns:
                op.drop_column('permissions', col)
    else:
        # permissions was created by this migration - drop the whole table
        op.drop_table('permissions')
