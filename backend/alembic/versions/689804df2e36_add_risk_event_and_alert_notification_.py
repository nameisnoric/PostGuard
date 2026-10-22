"""add risk event and alert notification persistence

Revision ID: 689804df2e36
Revises: a91f4c2d7e30
Create Date: 2026-10-22 05:19:51.950232
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "689804df2e36"
down_revision: Union[str, Sequence[str], None] = "a91f4c2d7e30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "risk_events",
        sa.Column(
            "risk_event_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "runtime_event_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "initial_risk_level",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "current_risk_level",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "max_risk_level",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "ended_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "duration_seconds",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "resolved_reason",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column(
            "active_factors",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "evidence_groups",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.session_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "risk_event_id"
        ),
        sa.UniqueConstraint(
            "session_id",
            "runtime_event_id",
            name="uq_risk_events_session_runtime_event",
        ),
    )

    op.create_index(
        op.f(
            "ix_risk_events_risk_event_id"
        ),
        "risk_events",
        ["risk_event_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_risk_events_session_id"
        ),
        "risk_events",
        ["session_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_risk_events_status"
        ),
        "risk_events",
        ["status"],
        unique=False,
    )

    op.create_table(
        "alert_notifications",
        sa.Column(
            "notification_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "risk_event_id",
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
            "risk_level",
            sa.String(length=32),
            nullable=True,
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
            ["risk_event_id"],
            ["risk_events.risk_event_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.session_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "notification_id"
        ),
    )

    op.create_index(
        op.f(
            "ix_alert_notifications_notification_id"
        ),
        "alert_notifications",
        ["notification_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_alert_notifications_risk_event_id"
        ),
        "alert_notifications",
        ["risk_event_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_alert_notifications_session_id"
        ),
        "alert_notifications",
        ["session_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_alert_notifications_emitted_at"
        ),
        "alert_notifications",
        ["emitted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(
            "ix_alert_notifications_emitted_at"
        ),
        table_name="alert_notifications",
    )

    op.drop_index(
        op.f(
            "ix_alert_notifications_session_id"
        ),
        table_name="alert_notifications",
    )

    op.drop_index(
        op.f(
            "ix_alert_notifications_risk_event_id"
        ),
        table_name="alert_notifications",
    )

    op.drop_index(
        op.f(
            "ix_alert_notifications_notification_id"
        ),
        table_name="alert_notifications",
    )

    op.drop_table(
        "alert_notifications"
    )

    op.drop_index(
        op.f(
            "ix_risk_events_status"
        ),
        table_name="risk_events",
    )

    op.drop_index(
        op.f(
            "ix_risk_events_session_id"
        ),
        table_name="risk_events",
    )

    op.drop_index(
        op.f(
            "ix_risk_events_risk_event_id"
        ),
        table_name="risk_events",
    )

    op.drop_table(
        "risk_events"
    )