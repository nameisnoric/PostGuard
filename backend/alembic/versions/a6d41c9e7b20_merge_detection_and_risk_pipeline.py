"""merge detection and desktop risk-pipeline migration histories

Revision ID: a6d41c9e7b20
Revises: f95c8d2e6b31, baf0193449bc
Create Date: 2026-10-28
"""

from typing import Sequence, Union


revision: str = "a6d41c9e7b20"
down_revision: Union[str, Sequence[str], None] = (
    "f95c8d2e6b31",
    "baf0193449bc",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
