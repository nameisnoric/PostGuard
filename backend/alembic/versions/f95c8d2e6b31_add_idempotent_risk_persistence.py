"""add idempotent risk-event and notification persistence

Revision ID: f95c8d2e6b31
Revises: e84b7c1d5a20
Create Date: 2026-10-25

The integration branch used revision 689804df2e36 to create these tables,
while the deployed database already reported that revision. This migration
therefore inspects the schema and creates only missing objects. It works for a
fresh feature/detection database and for a database that already received the
integration-branch tables.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f95c8d2e6b31"
down_revision: Union[str, Sequence[str], None] = "e84b7c1d5a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _table_names()
    if "risk_events" not in tables:
        op.create_table(
            "risk_events",
            sa.Column("risk_event_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("runtime_event_id", sa.String(length=128), nullable=False),
            sa.Column("initial_risk_level", sa.String(length=32), nullable=False),
            sa.Column("current_risk_level", sa.String(length=32), nullable=False),
            sa.Column("max_risk_level", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_seconds", sa.Float(), nullable=False),
            sa.Column("resolved_reason", sa.String(length=128), nullable=True),
            sa.Column("active_factors", sa.JSON(), nullable=False),
            sa.Column("evidence_groups", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("risk_event_id"),
            sa.UniqueConstraint(
                "session_id",
                "runtime_event_id",
                name="uq_risk_events_session_runtime_event",
            ),
        )
        op.create_index("ix_risk_events_risk_event_id", "risk_events", ["risk_event_id"])
        op.create_index("ix_risk_events_session_id", "risk_events", ["session_id"])
        op.create_index("ix_risk_events_status", "risk_events", ["status"])

    tables = _table_names()
    if "alert_notifications" not in tables:
        op.create_table(
            "alert_notifications",
            sa.Column("notification_id", sa.Integer(), nullable=False),
            sa.Column("risk_event_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("runtime_notification_id", sa.String(length=128), nullable=True),
            sa.Column("alert_type", sa.String(length=32), nullable=False),
            sa.Column("risk_level", sa.String(length=32), nullable=True),
            sa.Column("decision", sa.String(length=32), nullable=False),
            sa.Column("reason", sa.String(length=128), nullable=True),
            sa.Column("emitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["risk_event_id"], ["risk_events.risk_event_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("notification_id"),
            sa.UniqueConstraint(
                "session_id",
                "runtime_notification_id",
                name="uq_alert_notifications_session_runtime_notification",
            ),
        )
        op.create_index("ix_alert_notifications_notification_id", "alert_notifications", ["notification_id"])
        op.create_index("ix_alert_notifications_risk_event_id", "alert_notifications", ["risk_event_id"])
        op.create_index("ix_alert_notifications_session_id", "alert_notifications", ["session_id"])
        op.create_index("ix_alert_notifications_emitted_at", "alert_notifications", ["emitted_at"])
        return

    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("alert_notifications")}
    if "runtime_notification_id" not in columns:
        op.add_column(
            "alert_notifications",
            sa.Column("runtime_notification_id", sa.String(length=128), nullable=True),
        )

    constraints = {
        constraint.get("name")
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints("alert_notifications")
    }
    if "uq_alert_notifications_session_runtime_notification" not in constraints:
        op.create_unique_constraint(
            "uq_alert_notifications_session_runtime_notification",
            "alert_notifications",
            ["session_id", "runtime_notification_id"],
        )


def downgrade() -> None:
    # The two tables may have been created by the already-deployed integration
    # revision. Keep them intact and remove only the idempotency addition.
    if "alert_notifications" not in _table_names():
        return
    inspector = sa.inspect(op.get_bind())
    constraints = {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints("alert_notifications")
    }
    if "uq_alert_notifications_session_runtime_notification" in constraints:
        op.drop_constraint(
            "uq_alert_notifications_session_runtime_notification",
            "alert_notifications",
            type_="unique",
        )
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("alert_notifications")}
    if "runtime_notification_id" in columns:
        op.drop_column("alert_notifications", "runtime_notification_id")
