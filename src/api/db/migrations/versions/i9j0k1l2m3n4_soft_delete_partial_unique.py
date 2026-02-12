"""replace unconditional unique constraints with partial unique indexes for soft delete

Revision ID: i9j0k1l2m3n4
Revises: b2c3d4e5f6h8
Create Date: 2026-02-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'i9j0k1l2m3n4'
down_revision: Union[str, None] = 'b2c3d4e5f6h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing unconditional unique constraints
    op.drop_constraint('roles_name_key', 'roles', type_='unique')
    op.drop_constraint('permission_sets_code_key', 'permission_sets', type_='unique')
    op.drop_constraint('permissions_code_key', 'permissions', type_='unique')
    op.drop_constraint('uq_permissions_name', 'permissions', type_='unique')

    # Drop redundant btree indexes if they exist
    op.drop_index('idx_permissions_code', table_name='permissions', if_exists=True)
    op.drop_index('idx_permission_sets_code', table_name='permission_sets', if_exists=True)

    # Create partial unique indexes (only enforce uniqueness for non-deleted rows)
    op.execute(
        "CREATE UNIQUE INDEX uq_roles_name_active ON roles (name) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_permission_sets_code_active ON permission_sets (code) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_permissions_code_active ON permissions (code) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_permissions_name_active ON permissions (name) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    # Drop partial unique indexes
    op.drop_index('uq_roles_name_active', table_name='roles')
    op.drop_index('uq_permission_sets_code_active', table_name='permission_sets')
    op.drop_index('uq_permissions_code_active', table_name='permissions')
    op.drop_index('uq_permissions_name_active', table_name='permissions')

    # Recreate unconditional unique constraints
    op.create_unique_constraint('roles_name_key', 'roles', ['name'])
    op.create_unique_constraint('permission_sets_code_key', 'permission_sets', ['code'])
    op.create_unique_constraint('permissions_code_key', 'permissions', ['code'])
    op.create_unique_constraint('uq_permissions_name', 'permissions', ['name'])

    # Recreate btree indexes
    op.create_index('idx_permissions_code', 'permissions', ['code'])
    op.create_index('idx_permission_sets_code', 'permission_sets', ['code'])
