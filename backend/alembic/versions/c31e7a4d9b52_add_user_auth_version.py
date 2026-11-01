"""add user authentication version

Revision ID: c31e7a4d9b52
Revises: a6d41c9e7b20
Create Date: 2026-10-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c31e7a4d9b52"
down_revision: Union[str, Sequence[str], None] = "a6d41c9e7b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "auth_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "auth_version")
