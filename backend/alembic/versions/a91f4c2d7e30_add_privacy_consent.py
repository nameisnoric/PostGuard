"""add privacy consent state

Revision ID: a91f4c2d7e30
Revises: b8e7c4d2a190
Create Date: 2026-10-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a91f4c2d7e30"
down_revision: Union[str, Sequence[str], None] = "b8e7c4d2a190"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("privacy_consent_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "privacy_consent_accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "privacy_consent_withdrawn_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "privacy_consent_withdrawn_at")
    op.drop_column("users", "privacy_consent_accepted_at")
    op.drop_column("users", "privacy_consent_version")
