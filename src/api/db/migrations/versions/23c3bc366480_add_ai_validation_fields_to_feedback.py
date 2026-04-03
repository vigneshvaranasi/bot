"""add ai validation fields to feedback

Revision ID: 23c3bc366480
Revises: 4a41df53be8f
Create Date: 2026-04-03 19:45:57.850683

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "23c3bc366480"
down_revision: Union[str, Sequence[str], None] = "4a41df53be8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add AI validation fields to feedback tables."""
    # Add columns to settings table
    op.add_column(
        "settings",
        sa.Column(
            "feedback_auto_approve_by_ai",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Add columns to message_feedback table
    op.add_column(
        "message_feedback", sa.Column("ai_validated", sa.String(20), nullable=True)
    )
    op.add_column("message_feedback", sa.Column("ai_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove AI validation fields."""
    op.drop_column("message_feedback", "ai_reason")
    op.drop_column("message_feedback", "ai_validated")
    op.drop_column("settings", "feedback_auto_approve_by_ai")
