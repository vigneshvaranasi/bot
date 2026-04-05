"""add query_type to golden_examples

Revision ID: 4c77b0713086
Revises: 23c3bc366480
Create Date: 2026-04-04 22:06:25.365202

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c77b0713086'
down_revision: Union[str, Sequence[str], None] = '23c3bc366480'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'golden_examples',
        sa.Column(
            'query_type',
            sa.String(length=20),
            nullable=False,
            server_default='static',
            comment='static or temporal — temporal queries always require tool calls',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('golden_examples', 'query_type')
