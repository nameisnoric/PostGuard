"""use RULA-adapted front-camera risk score

Revision ID: e84b7c1d5a20
Revises: d71a9e4b2f63
Create Date: 2026-10-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e84b7c1d5a20"
down_revision: Union[str, Sequence[str], None] = "d71a9e4b2f63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_summary_rula_neck_score", "session_summaries", type_="check"
    )
    op.drop_column("session_summaries", "rula_neck_score")
    # The integration/desktop-risk-pipeline deployment added this column while
    # retaining a different Alembic head. Reconciliation must therefore accept
    # both that deployed schema and a fresh database.
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("session_summaries")
    }
    if "risk_score_method" not in columns:
        op.add_column(
            "session_summaries",
            sa.Column("risk_score_method", sa.String(length=40), nullable=True),
        )


def downgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("session_summaries")
    }
    if "risk_score_method" in columns:
        op.drop_column("session_summaries", "risk_score_method")
    op.add_column(
        "session_summaries",
        sa.Column("rula_neck_score", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_summary_rula_neck_score",
        "session_summaries",
        "rula_neck_score IS NULL OR rula_neck_score BETWEEN 1 AND 6",
    )
