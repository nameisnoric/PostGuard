"""add personal baseline validation metadata

Revision ID: b8e7c4d2a190
Revises: 9d3a6b7c8e21
Create Date: 2026-10-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8e7c4d2a190"
down_revision: Union[str, Sequence[str], None] = "9d3a6b7c8e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = (
        sa.Column("baseline_status", sa.String(length=24), nullable=True),
        sa.Column("confirmation_status", sa.String(length=24), nullable=True),
        sa.Column("baseline_sample_count", sa.Integer(), nullable=True),
        sa.Column("baseline_duration_seconds", sa.Float(), nullable=True),
        sa.Column("baseline_valid_ratio", sa.Float(), nullable=True),
        sa.Column("shoulder_tilt_sd", sa.Float(), nullable=True),
        sa.Column("neck_lateral_tilt_sd", sa.Float(), nullable=True),
        sa.Column("neck_flexion_sd", sa.Float(), nullable=True),
        sa.Column("eye_distance_sd", sa.Float(), nullable=True),
    )
    for column in columns:
        op.add_column("personal_baselines", column)


def downgrade() -> None:
    for column in (
        "eye_distance_sd",
        "neck_flexion_sd",
        "neck_lateral_tilt_sd",
        "shoulder_tilt_sd",
        "baseline_valid_ratio",
        "baseline_duration_seconds",
        "baseline_sample_count",
        "confirmation_status",
        "baseline_status",
    ):
        op.drop_column("personal_baselines", column)
