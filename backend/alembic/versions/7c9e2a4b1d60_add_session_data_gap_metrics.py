"""add camera-loss and data-gap metrics to session summaries

Revision ID: 7c9e2a4b1d60
Revises: c31e7a4d9b52
Create Date: 2026-11-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c9e2a4b1d60"
down_revision: Union[str, Sequence[str], None] = "c31e7a4d9b52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "session_summaries",
        sa.Column(
            "data_gap_duration",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "session_summaries",
        sa.Column(
            "camera_loss_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_summary_data_gap_duration_nonnegative",
        "session_summaries",
        "data_gap_duration >= 0",
    )
    op.create_check_constraint(
        "ck_summary_camera_loss_count_nonnegative",
        "session_summaries",
        "camera_loss_count >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_summary_camera_loss_count_nonnegative",
        "session_summaries",
        type_="check",
    )
    op.drop_constraint(
        "ck_summary_data_gap_duration_nonnegative",
        "session_summaries",
        type_="check",
    )
    op.drop_column("session_summaries", "camera_loss_count")
    op.drop_column("session_summaries", "data_gap_duration")
