"""replace Full RULA fields with camera-derived neck score

Revision ID: d71a9e4b2f63
Revises: c82f1a3d4e60
Create Date: 2026-10-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d71a9e4b2f63"
down_revision: Union[str, Sequence[str], None] = "c82f1a3d4e60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_summary_rula_action_level", "session_summaries", type_="check"
    )
    op.drop_constraint(
        "ck_summary_rula_score", "session_summaries", type_="check"
    )
    op.drop_column("session_summaries", "rula_action_level")
    op.drop_column("session_summaries", "rula_final_score")
    op.add_column(
        "session_summaries",
        sa.Column("rula_neck_score", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_summary_rula_neck_score",
        "session_summaries",
        "rula_neck_score IS NULL OR rula_neck_score BETWEEN 1 AND 6",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_summary_rula_neck_score", "session_summaries", type_="check"
    )
    op.drop_column("session_summaries", "rula_neck_score")
    op.add_column(
        "session_summaries",
        sa.Column("rula_final_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "session_summaries",
        sa.Column("rula_action_level", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_summary_rula_score",
        "session_summaries",
        "rula_final_score IS NULL OR rula_final_score BETWEEN 1 AND 7",
    )
    op.create_check_constraint(
        "ck_summary_rula_action_level",
        "session_summaries",
        "rula_action_level IS NULL OR rula_action_level BETWEEN 1 AND 4",
    )
