"""add connector_type to integrations

Revision ID: c9f4a2b1d3e0
Revises: a8f1e2b3c4d5
Create Date: 2026-04-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9f4a2b1d3e0"
down_revision: Union[str, Sequence[str], None] = "a8f1e2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "integrations",
        sa.Column("connector_type", sa.String(), nullable=True),
    )

    op.execute(
        """
        UPDATE integrations
        SET connector_type = CASE
            WHEN LOWER(service_name) LIKE 'servicenow%' THEN 'servicenow'
            WHEN LOWER(service_name) LIKE 'jira%'        THEN 'jira'
            ELSE LOWER(service_name)
        END
        WHERE connector_type IS NULL
        """
    )

    op.alter_column("integrations", "connector_type", nullable=False)


def downgrade() -> None:
    op.drop_column("integrations", "connector_type")
