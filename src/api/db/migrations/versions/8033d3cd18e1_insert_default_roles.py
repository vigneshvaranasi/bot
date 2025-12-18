"""insert default roles

Revision ID: 8033d3cd18e1
Revises: 67e467be33ff
Create Date: 2025-10-19 23:57:18.590478

"""

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8033d3cd18e1"
down_revision: Union[str, Sequence[str], None] = "67e467be33ff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        f"""
        INSERT INTO roles (id, name)
        VALUES (gen_random_uuid(), 'admin'),
               (gen_random_uuid(), 'user')
        ON CONFLICT (name) DO NOTHING;
    """
    )
    pass


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        f"""
        DELETE FROM roles WHERE name IN ('admin', 'user');
    """
    )

    pass
