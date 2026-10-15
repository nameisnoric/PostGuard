"""reconcile existing Supabase account-deletion head

Revision ID: b71c2e9a4f10
Revises: d2c54f7819ab
Create Date: 2026-10-15

The deployed Supabase database already records this revision after the account
deletion columns. Its original migration file was not present in the repository.
Schema inspection confirmed that no additional objects need to be created here.
"""

from typing import Sequence, Union


revision: str = "b71c2e9a4f10"
down_revision: Union[str, Sequence[str], None] = "d2c54f7819ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
