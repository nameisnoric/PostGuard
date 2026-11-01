"""reconcile eye alert summary counters

Revision ID: f12c7b4d9e30
Revises: e31b6a9c4d20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f12c7b4d9e30"
down_revision: Union[str, Sequence[str], None] = "e31b6a9c4d20"
branch_labels = None
depends_on = None


COUNTERS = (
    "eye_alert_count",
    "eye_first_alert_count",
    "eye_repeat_alert_count",
)


def upgrade() -> None:
    existing = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("session_summaries")
    }
    for name in COUNTERS:
        if name not in existing:
            op.add_column(
                "session_summaries",
                sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
            )


def downgrade() -> None:
    # These columns may predate this branch, so preserve them and their data.
    pass
