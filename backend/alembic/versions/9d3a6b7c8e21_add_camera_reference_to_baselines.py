"""add camera reference snapshot to personal baselines

Revision ID: 9d3a6b7c8e21
Revises: f74a1c9e2b30
Create Date: 2026-10-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d3a6b7c8e21"
down_revision: Union[str, Sequence[str], None] = "f74a1c9e2b30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "personal_baselines", sa.Column("camera_frame_width", sa.Integer(), nullable=True)
    )
    op.add_column(
        "personal_baselines", sa.Column("camera_frame_height", sa.Integer(), nullable=True)
    )
    op.add_column(
        "personal_baselines", sa.Column("camera_scale_x", sa.Float(), nullable=True)
    )
    op.add_column(
        "personal_baselines", sa.Column("camera_scale_y", sa.Float(), nullable=True)
    )
    op.add_column(
        "personal_baselines", sa.Column("camera_scale_avg", sa.Float(), nullable=True)
    )
    op.add_column(
        "personal_baselines", sa.Column("camera_card_roll", sa.Float(), nullable=True)
    )
    op.add_column(
        "personal_baselines",
        sa.Column("camera_horizontal_perspective", sa.Float(), nullable=True),
    )
    op.add_column(
        "personal_baselines",
        sa.Column("camera_vertical_perspective", sa.Float(), nullable=True),
    )
    op.add_column(
        "personal_baselines",
        sa.Column("camera_calibrated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    for column in (
        "camera_calibrated_at",
        "camera_vertical_perspective",
        "camera_horizontal_perspective",
        "camera_card_roll",
        "camera_scale_avg",
        "camera_scale_y",
        "camera_scale_x",
        "camera_frame_height",
        "camera_frame_width",
    ):
        op.drop_column("personal_baselines", column)
