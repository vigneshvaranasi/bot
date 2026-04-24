"""add guardrail (scope check) config to settings

Revision ID: d9e0f1a2b3c4
Revises: c9f4a2b1d3e0
Create Date: 2026-04-23 12:36:41.479292

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd9e0f1a2b3c4'
down_revision: Union[str, Sequence[str], None] = 'c9f4a2b1d3e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add guardrail configuration columns to settings."""
    op.add_column(
        'settings',
        sa.Column('guardrail_enabled', sa.Boolean, nullable=False, server_default=sa.text('false')),
    )
    op.add_column(
        'settings',
        sa.Column('guardrail_provider_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        'settings',
        sa.Column('guardrail_model_id', sa.String, nullable=True),
    )
    op.add_column(
        'settings',
        sa.Column(
            'guardrail_history_turns',
            sa.Integer,
            nullable=False,
            server_default=sa.text('3'),
        ),
    )

    op.create_foreign_key(
        'fk_settings_guardrail_provider',
        'settings', 'llm_providers',
        ['guardrail_provider_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Remove guardrail configuration columns from settings."""
    op.drop_constraint('fk_settings_guardrail_provider', 'settings', type_='foreignkey')
    op.drop_column('settings', 'guardrail_history_turns')
    op.drop_column('settings', 'guardrail_model_id')
    op.drop_column('settings', 'guardrail_provider_id')
    op.drop_column('settings', 'guardrail_enabled')