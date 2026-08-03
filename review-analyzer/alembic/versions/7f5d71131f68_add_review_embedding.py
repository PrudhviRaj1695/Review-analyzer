"""add review embedding

Revision ID: 7f5d71131f68
Revises: 520463b5e478
Create Date: 2026-07-14 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f5d71131f68"
down_revision: Union[str, Sequence[str], None] = "520463b5e478"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("reviews", sa.Column("embedding", Vector(1536), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("reviews", "embedding")
