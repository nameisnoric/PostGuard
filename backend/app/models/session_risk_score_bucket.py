from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.database.database import Base


class SessionRiskScoreBucket(Base):
    """
    One aggregated PostGuard Risk Score time bucket.

    Example:
        bucket_index = 0
        start_second = 0
        end_second = 10
        average_risk_score = 17

    This table stores graph-ready data.

    It intentionally does NOT store every camera frame.
    """

    __tablename__ = (
        "session_risk_score_buckets"
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "bucket_index",
            name=(
                "uq_session_risk_score_bucket_"
                "session_index"
            ),
        ),

        CheckConstraint(
            "bucket_index >= 0",
            name=(
                "ck_session_risk_score_bucket_"
                "index_nonnegative"
            ),
        ),

        CheckConstraint(
            "start_second >= 0",
            name=(
                "ck_session_risk_score_bucket_"
                "start_nonnegative"
            ),
        ),

        CheckConstraint(
            "end_second > start_second",
            name=(
                "ck_session_risk_score_bucket_"
                "time_range"
            ),
        ),

        CheckConstraint(
            "sample_count > 0",
            name=(
                "ck_session_risk_score_bucket_"
                "sample_count_positive"
            ),
        ),

        CheckConstraint(
            (
                "minimum_risk_score >= 0 "
                "AND minimum_risk_score <= 100"
            ),
            name=(
                "ck_session_risk_score_bucket_"
                "minimum_score_range"
            ),
        ),

        CheckConstraint(
            (
                "average_risk_score >= 0 "
                "AND average_risk_score <= 100"
            ),
            name=(
                "ck_session_risk_score_bucket_"
                "average_score_range"
            ),
        ),

        CheckConstraint(
            (
                "maximum_risk_score >= 0 "
                "AND maximum_risk_score <= 100"
            ),
            name=(
                "ck_session_risk_score_bucket_"
                "maximum_score_range"
            ),
        ),

        CheckConstraint(
            (
                "minimum_risk_score "
                "<= average_risk_score "
                "AND average_risk_score "
                "<= maximum_risk_score"
            ),
            name=(
                "ck_session_risk_score_bucket_"
                "score_order"
            ),
        ),

        CheckConstraint(
            (
                "minimum_modified_rula_score "
                "BETWEEN 1 AND 7"
            ),
            name=(
                "ck_session_risk_score_bucket_"
                "minimum_rula_range"
            ),
        ),

        CheckConstraint(
            (
                "maximum_modified_rula_score "
                "BETWEEN 1 AND 7"
            ),
            name=(
                "ck_session_risk_score_bucket_"
                "maximum_rula_range"
            ),
        ),

        CheckConstraint(
            (
                "minimum_modified_rula_score "
                "<= maximum_modified_rula_score"
            ),
            name=(
                "ck_session_risk_score_bucket_"
                "rula_order"
            ),
        ),
    )

    bucket_id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    session_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sessions.session_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    bucket_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    start_second: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    end_second: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    sample_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    average_risk_score: Mapped[
        float
    ] = mapped_column(
        Float,
        nullable=False,
    )

    minimum_risk_score: Mapped[
        float
    ] = mapped_column(
        Float,
        nullable=False,
    )

    maximum_risk_score: Mapped[
        float
    ] = mapped_column(
        Float,
        nullable=False,
    )

    minimum_modified_rula_score: Mapped[
        int
    ] = mapped_column(
        Integer,
        nullable=False,
    )

    maximum_modified_rula_score: Mapped[
        int
    ] = mapped_column(
        Integer,
        nullable=False,
    )