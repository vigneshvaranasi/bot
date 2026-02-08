"""add audit trail columns to settings table

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-01-18

This migration adds audit trail columns to the settings table:
- change_type: 'create', 'update', or 'rollback'
- source_version_id: the version being replaced (for updates/rollbacks)
- target_version_id: the version being restored (for rollbacks only)
- change_reason: optional user-provided reason for the change
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add audit trail columns to settings table."""
    # Add change_type column with default 'update' for existing records
    op.add_column(
        'settings',
        sa.Column(
            'change_type',
            sa.String(20),
            nullable=False,
            server_default='update'
        )
    )

    # Add source_version_id (the version being replaced)
    op.add_column(
        'settings',
        sa.Column(
            'source_version_id',
            UUID(as_uuid=True),
            sa.ForeignKey('settings.id', ondelete='SET NULL'),
            nullable=True
        )
    )

    # Add target_version_id (the version being restored, for rollbacks)
    op.add_column(
        'settings',
        sa.Column(
            'target_version_id',
            UUID(as_uuid=True),
            sa.ForeignKey('settings.id', ondelete='SET NULL'),
            nullable=True
        )
    )

    # Add change_reason for optional audit notes
    op.add_column(
        'settings',
        sa.Column(
            'change_reason',
            sa.Text,
            nullable=True
        )
    )

    # Create indexes for efficient history queries
    op.create_index(
        'idx_settings_change_type',
        'settings',
        ['change_type']
    )

    op.create_index(
        'idx_settings_source_version_id',
        'settings',
        ['source_version_id']
    )


def downgrade() -> None:
    """Remove audit trail columns from settings table."""
    op.drop_index('idx_settings_source_version_id', table_name='settings')
    op.drop_index('idx_settings_change_type', table_name='settings')
    op.drop_column('settings', 'change_reason')
    op.drop_column('settings', 'target_version_id')
    op.drop_column('settings', 'source_version_id')
    op.drop_column('settings', 'change_type')
