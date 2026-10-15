"""add account deletion state

Revision ID: d2c54f7819ab
Revises: c4f9d2a7b105
Create Date: 2026-10-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2c54f7819ab"
down_revision: Union[str, Sequence[str], None] = "c4f9d2a7b105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "account_status",
            sa.String(length=32),
            server_default="ACTIVE",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("deletion_scheduled_for", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_account_status", "users", ["account_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_account_status", table_name="users")
    op.drop_column("users", "deletion_scheduled_for")
    op.drop_column("users", "deletion_requested_at")
    op.drop_column("users", "account_status")
