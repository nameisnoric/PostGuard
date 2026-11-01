"""add idempotent eye alert notifications

Revision ID: e31b6a9c4d20
Revises: 7c9e2a4b1d60
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e31b6a9c4d20"
down_revision: Union[str, Sequence[str], None] = "7c9e2a4b1d60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "eye_alert_notifications" in inspector.get_table_names():
        columns = {
            column["name"]
            for column in inspector.get_columns("eye_alert_notifications")
        }
        if "runtime_notification_id" not in columns:
            op.add_column(
                "eye_alert_notifications",
                sa.Column("runtime_notification_id", sa.String(length=128), nullable=True),
            )
            op.execute(sa.text(
                "UPDATE eye_alert_notifications "
                "SET runtime_notification_id = "
                "'legacy-eye-' || CAST(eye_notification_id AS VARCHAR) "
                "WHERE runtime_notification_id IS NULL"
            ))
            op.alter_column(
                "eye_alert_notifications",
                "runtime_notification_id",
                existing_type=sa.String(length=128),
                nullable=False,
            )
        unique_names = {
            constraint.get("name")
            for constraint in inspector.get_unique_constraints("eye_alert_notifications")
        }
        if "uq_eye_alert_session_runtime_notification" not in unique_names:
            op.create_unique_constraint(
                "uq_eye_alert_session_runtime_notification",
                "eye_alert_notifications",
                ["session_id", "runtime_notification_id"],
            )
        return

    op.create_table(
        "eye_alert_notifications",
        sa.Column("eye_notification_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("runtime_notification_id", sa.String(length=128), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("blink_rate", sa.Float(), nullable=False),
        sa.Column("window_blink_count", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=128), nullable=True),
        sa.Column("emitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("eye_notification_id"),
        sa.UniqueConstraint(
            "session_id", "runtime_notification_id",
            name="uq_eye_alert_session_runtime_notification",
        ),
    )
    op.create_index("ix_eye_alert_notifications_eye_notification_id", "eye_alert_notifications", ["eye_notification_id"])
    op.create_index("ix_eye_alert_notifications_session_id", "eye_alert_notifications", ["session_id"])
    op.create_index("ix_eye_alert_notifications_emitted_at", "eye_alert_notifications", ["emitted_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    summary_columns = {
        column["name"] for column in inspector.get_columns("session_summaries")
    }
    # A database previously initialized by the pipeline branch already owns
    # this table and its eye_* summary columns. Revert only our idempotency
    # extension so a downgrade never removes its existing alert history.
    if "eye_alert_count" in summary_columns:
        unique_names = {
            constraint.get("name")
            for constraint in inspector.get_unique_constraints("eye_alert_notifications")
        }
        if "uq_eye_alert_session_runtime_notification" in unique_names:
            op.drop_constraint(
                "uq_eye_alert_session_runtime_notification",
                "eye_alert_notifications",
                type_="unique",
            )
        columns = {
            column["name"]
            for column in inspector.get_columns("eye_alert_notifications")
        }
        if "runtime_notification_id" in columns:
            op.drop_column("eye_alert_notifications", "runtime_notification_id")
        return

    op.drop_index("ix_eye_alert_notifications_emitted_at", table_name="eye_alert_notifications")
    op.drop_index("ix_eye_alert_notifications_session_id", table_name="eye_alert_notifications")
    op.drop_index("ix_eye_alert_notifications_eye_notification_id", table_name="eye_alert_notifications")
    op.drop_table("eye_alert_notifications")
