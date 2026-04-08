"""add LLM Routing

Revision ID: a8f1e2b3c4d5
Revises: 4c77b0713086
Create Date: 2026-04-08 10:48:44.190500

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a8f1e2b3c4d5'
down_revision: Union[str, Sequence[str], None] = '4c77b0713086'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create model_routing_configs table and add routing fields to settings."""
    # Create model_routing_configs table
    op.create_table(
        'model_routing_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('llm_providers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('model_id', sa.String(200), nullable=False),
        sa.Column('task_types', postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('prompt_sizes', postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('cost_tier', sa.String(20), nullable=False, server_default=sa.text("'medium'")),
        sa.Column('latency_tier', sa.String(20), nullable=False, server_default=sa.text("'medium'")),
        sa.Column('quality_tier', sa.String(20), nullable=False, server_default=sa.text("'medium'")),
        sa.Column('is_enabled', sa.Boolean, nullable=False, server_default=sa.text('true')),
        sa.Column('is_fallback', sa.Boolean, nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index('idx_model_routing_provider', 'model_routing_configs', ['provider_id'])
    op.create_index('idx_model_routing_enabled', 'model_routing_configs', ['is_enabled'])
    op.create_index(
        'idx_model_routing_fallback', 'model_routing_configs', ['is_fallback'],
        postgresql_where=sa.text('is_fallback = true'),
    )

    # Add auto-routing fields to settings
    op.add_column('settings', sa.Column('auto_routing_enabled', sa.Boolean, nullable=False, server_default=sa.text('false')))
    op.add_column('settings', sa.Column('router_provider_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('settings', sa.Column('router_model_id', sa.String, nullable=True))

    op.create_foreign_key(
        'fk_settings_router_provider',
        'settings', 'llm_providers',
        ['router_provider_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Remove auto-routing tables and columns."""
    op.drop_constraint('fk_settings_router_provider', 'settings', type_='foreignkey')
    op.drop_column('settings', 'router_model_id')
    op.drop_column('settings', 'router_provider_id')
    op.drop_column('settings', 'auto_routing_enabled')

    op.drop_index('idx_model_routing_fallback', 'model_routing_configs')
    op.drop_index('idx_model_routing_enabled', 'model_routing_configs')
    op.drop_index('idx_model_routing_provider', 'model_routing_configs')
    op.drop_table('model_routing_configs')
