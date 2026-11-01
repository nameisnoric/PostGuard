# add eye alert persistence
# Revision ID: c1e5a7b9d204
# Revises: baf0193449bc
# Create Date: 2026-11-01

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c1e5a7b9d204"
down_revision: Union[str, Sequence[str], None] = "baf0193449bc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eye_alert_notifications",
        sa.Column("eye_notification_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("blink_rate", sa.Float(), nullable=False),
        sa.Column("window_blink_count", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=128), nullable=True),
        sa.Column("emitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("eye_notification_id"),
    )
    op.create_index(op.f("ix_eye_alert_notifications_eye_notification_id"), "eye_alert_notifications", ["eye_notification_id"])
    op.create_index(op.f("ix_eye_alert_notifications_session_id"), "eye_alert_notifications", ["session_id"])
    op.create_index(op.f("ix_eye_alert_notifications_emitted_at"), "eye_alert_notifications", ["emitted_at"])

    op.add_column("session_summaries", sa.Column("eye_alert_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("session_summaries", sa.Column("eye_first_alert_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("session_summaries", sa.Column("eye_repeat_alert_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("session_summaries", "eye_repeat_alert_count")
    op.drop_column("session_summaries", "eye_first_alert_count")
    op.drop_column("session_summaries", "eye_alert_count")
    op.drop_index(op.f("ix_eye_alert_notifications_emitted_at"), table_name="eye_alert_notifications")
    op.drop_index(op.f("ix_eye_alert_notifications_session_id"), table_name="eye_alert_notifications")
    op.drop_index(op.f("ix_eye_alert_notifications_eye_notification_id"), table_name="eye_alert_notifications")
    op.drop_table("eye_alert_notifications")
