"""reconcile deployed Supabase head before RULA-adapted reports

Revision ID: 689804df2e36
Revises: a91f4c2d7e30
Create Date: 2026-10-22

The deployed Supabase database records this revision. Schema inspection
confirmed that it already contains the local history through privacy consent
and personal-baseline validation. No additional DDL is required here.
"""

from typing import Sequence, Union


revision: str = "689804df2e36"
down_revision: Union[str, Sequence[str], None] = "a91f4c2d7e30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
