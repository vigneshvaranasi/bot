"""add llm_providers table with default ollama seed

Revision ID: a1b2c3d4e5f6
Revises: fe08ca05f885
Create Date: 2026-01-17

This migration creates the llm_providers table for managing LLM provider configurations
(Anthropic, OpenAI, Google, Custom/Ollama) with encrypted API key storage.

It also seeds a default Ollama provider using the OLLAMA_API_URL and DEFAULT_OLLAMA_MODEL
environment variables.
"""
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'fe08ca05f885'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create llm_providers table and seed default Ollama provider."""

    # Create llm_providers table
    op.create_table(
        'llm_providers',
        sa.Column('id', UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('provider_type', sa.String(50), nullable=False),
        sa.Column('base_url', sa.String(500), nullable=True),
        sa.Column('api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('config', JSONB(), server_default='{}', nullable=False),
        sa.Column('models', JSONB(), server_default='[]', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('last_health_check_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_health_check_status', sa.String(20), nullable=True),
        sa.Column('last_health_check_error', sa.Text(), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for efficient queries
    op.create_index(
        'idx_llm_providers_active_type',
        'llm_providers',
        ['is_active', 'provider_type']
    )
    op.create_index(
        'idx_llm_providers_default',
        'llm_providers',
        ['is_default'],
        postgresql_where=sa.text('is_default = true')
    )

    # Seed default Ollama provider from environment variables
    ollama_url = os.getenv('OLLAMA_API_URL', 'http://localhost:11434')
    default_model = os.getenv('DEFAULT_OLLAMA_MODEL', 'gpt-oss:20b')

    # Escape single quotes in URL if any
    ollama_url_escaped = ollama_url.replace("'", "''")
    default_model_escaped = default_model.replace("'", "''")

    op.execute(f"""
        INSERT INTO llm_providers (name, provider_type, base_url, config, models, is_active, is_default)
        VALUES (
            'Default',
            'custom',
            '{ollama_url_escaped}',
            '{{"auth_type": "none", "auto_discover_models": true}}'::jsonb,
            '["{default_model_escaped}"]'::jsonb,
            true,
            true
        )
    """)


def downgrade() -> None:
    """Drop llm_providers table and indexes."""
    op.drop_index('idx_llm_providers_default', table_name='llm_providers')
    op.drop_index('idx_llm_providers_active_type', table_name='llm_providers')
    op.drop_table('llm_providers')
