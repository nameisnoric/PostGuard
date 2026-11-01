"""add eye alert persistence

Revision ID: c1e5a7b9d204
Revises: baf0193449bc
Create Date: 2026-11-01

This migration is intentionally idempotent because the detection branch may
already have created eye_alert_notifications and the eye summary counters.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1e5a7b9d204"
down_revision: Union[str, Sequence[str], None] = "baf0193449bc"
branch_labels = None
depends_on = None


EYE_COUNTERS = (
    "eye_alert_count",
    "eye_first_alert_count",
    "eye_repeat_alert_count",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    tables = set(inspector.get_table_names())

    if "eye_alert_notifications" not in tables:
        op.create_table(
            "eye_alert_notifications",
            sa.Column(
                "eye_notification_id",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "session_id",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "alert_type",
                sa.String(length=32),
                nullable=False,
            ),
            sa.Column(
                "blink_rate",
                sa.Float(),
                nullable=False,
            ),
            sa.Column(
                "window_blink_count",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "decision",
                sa.String(length=32),
                nullable=False,
            ),
            sa.Column(
                "reason",
                sa.String(length=128),
                nullable=True,
            ),
            sa.Column(
                "emitted_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["session_id"],
                ["sessions.session_id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint(
                "eye_notification_id"
            ),
        )

        op.create_index(
            "ix_eye_alert_notifications_eye_notification_id",
            "eye_alert_notifications",
            ["eye_notification_id"],
        )

        op.create_index(
            "ix_eye_alert_notifications_session_id",
            "eye_alert_notifications",
            ["session_id"],
        )

        op.create_index(
            "ix_eye_alert_notifications_emitted_at",
            "eye_alert_notifications",
            ["emitted_at"],
        )

    summary_columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns(
            "session_summaries"
        )
    }

    for column_name in EYE_COUNTERS:
        if column_name not in summary_columns:
            op.add_column(
                "session_summaries",
                sa.Column(
                    column_name,
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                ),
            )


def downgrade() -> None:
    # Do not remove shared objects here.
    #
    # These columns/table may belong to the detection branch
    # and can already contain real production/session data.
    pass