"""add idempotent screen distance notifications

Revision ID: b84d2a6e1f40
Revises: f12c7b4d9e30
"""

from alembic import op
import sqlalchemy as sa


revision = "b84d2a6e1f40"
down_revision = "f12c7b4d9e30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "screen_distance_notifications",
        sa.Column("screen_notification_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("runtime_notification_id", sa.String(length=128), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("distance_ratio", sa.Float(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False, server_default="ALERT"),
        sa.Column("reason", sa.String(length=128), nullable=True),
        sa.Column("emitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("screen_notification_id"),
        sa.UniqueConstraint(
            "session_id",
            "runtime_notification_id",
            name="uq_screen_distance_session_runtime_notification",
        ),
    )
    op.create_index(
        "ix_screen_distance_notifications_screen_notification_id",
        "screen_distance_notifications",
        ["screen_notification_id"],
    )
    op.create_index(
        "ix_screen_distance_notifications_session_id",
        "screen_distance_notifications",
        ["session_id"],
    )
    op.create_index(
        "ix_screen_distance_notifications_emitted_at",
        "screen_distance_notifications",
        ["emitted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_screen_distance_notifications_emitted_at",
        table_name="screen_distance_notifications",
    )
    op.drop_index(
        "ix_screen_distance_notifications_session_id",
        table_name="screen_distance_notifications",
    )
    op.drop_index(
        "ix_screen_distance_notifications_screen_notification_id",
        table_name="screen_distance_notifications",
    )
    op.drop_table("screen_distance_notifications")
