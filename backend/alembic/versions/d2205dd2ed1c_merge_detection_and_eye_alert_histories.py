"""merge detection and eye alert histories

Revision ID: d2205dd2ed1c
Revises: b84d2a6e1f40, c1e5a7b9d204
Create Date: 2026-11-02 00:21:46.748876

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2205dd2ed1c'
down_revision: Union[str, Sequence[str], None] = ('b84d2a6e1f40', 'c1e5a7b9d204')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
