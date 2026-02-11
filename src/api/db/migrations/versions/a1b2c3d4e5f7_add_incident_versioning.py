"""add incident versioning tables

Revision ID: a1b2c3d4e5f7
Revises: d65a3386d429
Create Date: 2026-02-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = 'd65a3386d429'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create incident_upload_sessions and incident_dataset_versions tables."""
    # Create incident_upload_sessions first (referenced by FK)
    op.create_table(
        'incident_upload_sessions',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('uploaded_by', UUID(as_uuid=True), nullable=True),
        sa.Column('source', sa.String(20), nullable=False, server_default='upload'),
        sa.Column('file_metadata', sa.JSON(), nullable=True),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('validation_report', sa.JSON(), nullable=True),
        sa.Column('field_mapping', sa.JSON(), nullable=True),
        sa.Column('normalized_data', sa.JSON(), nullable=True),
        sa.Column('incident_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create incident_dataset_versions
    op.create_table(
        'incident_dataset_versions',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('collection_name', sa.String(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='uploaded'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('incident_count', sa.Integer(), nullable=True),
        sa.Column('file_metadata', sa.JSON(), nullable=True),
        sa.Column('source', sa.String(20), nullable=False, server_default='upload'),
        sa.Column('snapshot_name', sa.String(), nullable=True),
        sa.Column('upload_session_id', UUID(as_uuid=True), nullable=True),
        sa.Column('uploaded_by', UUID(as_uuid=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['upload_session_id'], ['incident_upload_sessions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('collection_name'),
    )

    # Partial unique index: only one active version at a time
    op.execute(
        "CREATE UNIQUE INDEX ix_incident_dataset_versions_is_active "
        "ON incident_dataset_versions (is_active) WHERE is_active = true"
    )


def downgrade() -> None:
    """Drop incident versioning tables."""
    op.execute("DROP INDEX IF EXISTS ix_incident_dataset_versions_is_active")
    op.drop_table('incident_dataset_versions')
    op.drop_table('incident_upload_sessions')
