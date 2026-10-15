"""add private user avatar path

Revision ID: c4f9d2a7b105
Revises: 3f50ad4657ae
Create Date: 2026-10-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f9d2a7b105"
down_revision: Union[str, Sequence[str], None] = "3f50ad4657ae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_path", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_path")
