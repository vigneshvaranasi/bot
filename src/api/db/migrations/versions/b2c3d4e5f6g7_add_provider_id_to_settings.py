"""add provider_id to settings table

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-17

This migration adds the provider_id column to the settings table,
allowing users to select their preferred LLM provider.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add provider_id column to settings table."""
    op.add_column(
        'settings',
        sa.Column(
            'provider_id',
            UUID(as_uuid=True),
            sa.ForeignKey('llm_providers.id', ondelete='SET NULL'),
            nullable=True
        )
    )

    # Create index for efficient lookups
    op.create_index(
        'idx_settings_provider_id',
        'settings',
        ['provider_id']
    )


def downgrade() -> None:
    """Remove provider_id column from settings table."""
    op.drop_index('idx_settings_provider_id', table_name='settings')
    op.drop_column('settings', 'provider_id')
