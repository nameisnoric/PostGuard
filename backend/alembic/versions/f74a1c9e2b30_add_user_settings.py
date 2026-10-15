"""add user settings

Revision ID: f74a1c9e2b30
Revises: b71c2e9a4f10
Create Date: 2026-10-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f74a1c9e2b30"
down_revision: Union[str, Sequence[str], None] = "b71c2e9a4f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "notifications_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "sound_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "sound_volume",
            sa.Integer(),
            server_default="70",
            nullable=False,
        ),
        sa.Column(
            "reminder_interval_minutes",
            sa.Integer(),
            server_default="5",
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.CheckConstraint("sound_volume BETWEEN 0 AND 100", name="ck_settings_volume"),
        sa.CheckConstraint(
            "reminder_interval_minutes BETWEEN 1 AND 60",
            name="ck_settings_reminder_interval",
        ),
    )


def downgrade() -> None:
    op.drop_table("user_settings")
