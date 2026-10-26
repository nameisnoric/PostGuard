from __future__ import annotations

import math
from typing import Any, Mapping


# ============================================================
# CONTRACT
# ============================================================

SESSION_RISK_SCORE_CONTRACT_VERSION = "1.0"


# ============================================================
# DEFAULT CONFIG
# ============================================================

DEFAULT_BUCKET_SECONDS = 10.0


# ============================================================
# STATUS
# ============================================================

STATUS_AVAILABLE = "AVAILABLE"
STATUS_NO_VALID_SCORES = "NO_VALID_SCORES"


# ============================================================
# ERROR
# ============================================================

class SessionRiskScoreCollectorError(
    ValueError
):
    pass


# ============================================================
# NUMERIC HELPERS
# ============================================================

def _finite_number(
    value: Any,
) -> float | None:

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    if not isinstance(
        value,
        (int, float),
    ):
        return None

    number = float(
        value
    )

    if not math.isfinite(
        number
    ):
        return None

    return number


def _finite_non_negative_number(
    value: Any,
) -> float | None:

    number = _finite_number(
        value
    )

    if number is None:
        return None

    if number < 0.0:
        return None

    return number


# ============================================================
# COLLECTOR
# ============================================================

class SessionRiskScoreCollector:
    """
    Collect PostGuard Risk Score values across one Session.

    Responsibilities
    ----------------
    - Accept COMPLETE posture-score results only.
    - Preserve scores across pipeline resets / Pause / Resume.
    - Calculate Session AVG / MIN / MAX.
    - Build 10-second time buckets for Dashboard graph.
    - Keep Modified RULA distribution for traceability.

    Does NOT
    --------
    - calculate posture
    - calculate Modified RULA
    - calculate Risk Level
    - create Risk Event
    - decide Alert
    - persist database records
    - draw Dashboard UI
    """

    def __init__(
        self,
        *,
        bucket_seconds: float = (
            DEFAULT_BUCKET_SECONDS
        ),
    ) -> None:

        bucket_value = (
            _finite_non_negative_number(
                bucket_seconds
            )
        )

        if (
            bucket_value is None
            or
            bucket_value <= 0.0
        ):
            raise SessionRiskScoreCollectorError(
                "bucket_seconds must be a finite "
                "number greater than zero"
            )

        self.bucket_seconds = float(
            bucket_value
        )

        self.reset()

    # ========================================================
    # RESET
    # ========================================================

    def reset(
        self,
        *,
        session_started_at_monotonic: (
            float
            | None
        ) = None,
    ) -> None:
        """
        Reset data for a NEW Session.

        Do not call this for normal Pause/Resume.
        """

        if (
            session_started_at_monotonic
            is not None
        ):

            start_value = (
                _finite_non_negative_number(
                    session_started_at_monotonic
                )
            )

            if start_value is None:
                raise (
                    SessionRiskScoreCollectorError(
                        "session_started_at_monotonic "
                        "must be finite and non-negative"
                    )
                )

            self._session_started_at = float(
                start_value
            )

        else:
            self._session_started_at = None

        self._last_timestamp: (
            float
            | None
        ) = None

        self._samples: (
            list[
                dict[str, Any]
            ]
        ) = []

        self._total_pipeline_results = 0

        self._accepted_score_samples = 0

        self._skipped_score_samples = 0

        self._modified_rula_counts = {
            score: 0
            for score
            in range(
                1,
                8,
            )
        }

    # ========================================================
    # SESSION START
    # ========================================================

    def start_session(
        self,
        *,
        now: float,
    ) -> None:
        """
        Explicitly set Session time origin.

        Normally call once when Monitoring starts.
        """

        value = (
            _finite_non_negative_number(
                now
            )
        )

        if value is None:
            raise SessionRiskScoreCollectorError(
                "now must be finite and non-negative"
            )

        if self._samples:
            raise SessionRiskScoreCollectorError(
                "Cannot change Session start after "
                "score samples have been collected"
            )

        self._session_started_at = float(
            value
        )

        self._last_timestamp = None

    # ========================================================
    # SCORE READER
    # ========================================================

    def _read_score(
        self,
        pipeline_result: Mapping[str, Any],
    ) -> tuple[
        int,
        float,
    ] | None:

        posture_score = (
            pipeline_result.get(
                "posture_score"
            )
        )

        if not isinstance(
            posture_score,
            Mapping,
        ):
            return None

        if (
            posture_score.get(
                "status"
            )
            !=
            "COMPLETE"
        ):
            return None

        modified_rula = (
            posture_score.get(
                "modified_rula_score"
            )
        )

        postguard_score = (
            _finite_number(
                posture_score.get(
                    "postguard_risk_score"
                )
            )
        )

        if (
            type(modified_rula)
            is not int
        ):
            return None

        if not (
            1
            <=
            modified_rula
            <=
            7
        ):
            return None

        if postguard_score is None:
            return None

        if not (
            0.0
            <=
            postguard_score
            <=
            100.0
        ):
            return None

        return (
            modified_rula,
            float(
                postguard_score
            ),
        )

    # ========================================================
    # ADD PIPELINE RESULT
    # ========================================================

    def add_pipeline_result(
        self,
        pipeline_result: Mapping[str, Any],
    ) -> bool:
        """
        Add one pipeline cycle.

        Returns:
            True  = valid score was accepted
            False = score unavailable / partial / invalid

        Invalid or unavailable score does NOT become zero.
        """

        if not isinstance(
            pipeline_result,
            Mapping,
        ):
            raise SessionRiskScoreCollectorError(
                "pipeline_result must be a mapping"
            )

        self._total_pipeline_results += 1

        timestamp = (
            _finite_non_negative_number(
                pipeline_result.get(
                    "timestamp_monotonic"
                )
            )
        )

        if timestamp is None:
            self._skipped_score_samples += 1

            return False

        if (
            self._last_timestamp
            is not None
            and
            timestamp
            <
            self._last_timestamp
        ):
            raise SessionRiskScoreCollectorError(
                "pipeline timestamp must not "
                "move backwards"
            )

        # ----------------------------------------------------
        # If caller did not explicitly start collector,
        # first valid pipeline timestamp becomes origin.
        # ----------------------------------------------------

        if self._session_started_at is None:
            self._session_started_at = (
                float(
                    timestamp
                )
            )

        if (
            timestamp
            <
            self._session_started_at
        ):
            raise SessionRiskScoreCollectorError(
                "pipeline timestamp cannot be before "
                "Session start"
            )

        self._last_timestamp = float(
            timestamp
        )

        score = self._read_score(
            pipeline_result
        )

        if score is None:

            self._skipped_score_samples += 1

            return False

        (
            modified_rula,
            postguard_score,
        ) = score

        elapsed_seconds = (
            float(
                timestamp
            )
            -
            self._session_started_at
        )

        bucket_index = int(
            math.floor(
                elapsed_seconds
                /
                self.bucket_seconds
            )
        )

        self._samples.append({
            "timestamp_monotonic": (
                float(
                    timestamp
                )
            ),

            "elapsed_seconds": (
                elapsed_seconds
            ),

            "bucket_index": (
                bucket_index
            ),

            "modified_rula_score": (
                modified_rula
            ),

            "postguard_risk_score": (
                postguard_score
            ),
        })

        self._accepted_score_samples += 1

        self._modified_rula_counts[
            modified_rula
        ] += 1

        return True

    # ========================================================
    # BUILD BUCKETS
    # ========================================================

    def _build_buckets(
        self,
    ) -> list[
        dict[str, Any]
    ]:

        grouped: dict[
            int,
            list[
                dict[str, Any]
            ],
        ] = {}

        for sample in self._samples:

            bucket_index = int(
                sample[
                    "bucket_index"
                ]
            )

            grouped.setdefault(
                bucket_index,
                [],
            ).append(
                sample
            )

        result = []

        for bucket_index in sorted(
            grouped
        ):

            samples = grouped[
                bucket_index
            ]

            scores = [
                float(
                    item[
                        "postguard_risk_score"
                    ]
                )
                for item
                in samples
            ]

            rula_scores = [
                int(
                    item[
                        "modified_rula_score"
                    ]
                )
                for item
                in samples
            ]

            start_second = (
                bucket_index
                *
                self.bucket_seconds
            )

            end_second = (
                start_second
                +
                self.bucket_seconds
            )

            result.append({
                "bucket_index": (
                    bucket_index
                ),

                "start_second": (
                    start_second
                ),

                "end_second": (
                    end_second
                ),

                "sample_count": (
                    len(
                        samples
                    )
                ),

                "average_risk_score": (
                    sum(
                        scores
                    )
                    /
                    len(
                        scores
                    )
                ),

                "minimum_risk_score": (
                    min(
                        scores
                    )
                ),

                "maximum_risk_score": (
                    max(
                        scores
                    )
                ),

                # --------------------------------------------
                # Raw Modified RULA is kept for traceability.
                #
                # We do not expose average Modified RULA here
                # because it is an ordinal score.
                # --------------------------------------------

                "minimum_modified_rula_score": (
                    min(
                        rula_scores
                    )
                ),

                "maximum_modified_rula_score": (
                    max(
                        rula_scores
                    )
                ),
            })

        return result

    # ========================================================
    # SNAPSHOT
    # ========================================================

    def get_summary(
        self,
    ) -> dict[str, Any]:
        """
        Return current Session score statistics.

        No valid score:
            AVG/MIN/MAX = None

        We never substitute missing score with zero.
        """

        if not self._samples:

            return {
                "session_risk_score_contract_version": (
                    SESSION_RISK_SCORE_CONTRACT_VERSION
                ),

                "status": (
                    STATUS_NO_VALID_SCORES
                ),

                "reason": (
                    "NO_COMPLETE_POSTURE_SCORE_SAMPLES"
                ),

                "bucket_seconds": (
                    self.bucket_seconds
                ),

                "total_pipeline_results": (
                    self._total_pipeline_results
                ),

                "accepted_score_samples": (
                    self._accepted_score_samples
                ),

                "skipped_score_samples": (
                    self._skipped_score_samples
                ),

                "average_risk_score": None,

                "minimum_risk_score": None,

                "maximum_risk_score": None,

                "modified_rula_distribution": {
                    str(score): (
                        self._modified_rula_counts[
                            score
                        ]
                    )
                    for score
                    in range(
                        1,
                        8,
                    )
                },

                "buckets": [],
            }

        scores = [
            float(
                sample[
                    "postguard_risk_score"
                ]
            )
            for sample
            in self._samples
        ]

        return {
            "session_risk_score_contract_version": (
                SESSION_RISK_SCORE_CONTRACT_VERSION
            ),

            "status": (
                STATUS_AVAILABLE
            ),

            "reason": (
                "SESSION_RISK_SCORE_AVAILABLE"
            ),

            "bucket_seconds": (
                self.bucket_seconds
            ),

            "total_pipeline_results": (
                self._total_pipeline_results
            ),

            "accepted_score_samples": (
                self._accepted_score_samples
            ),

            "skipped_score_samples": (
                self._skipped_score_samples
            ),

            "average_risk_score": (
                sum(
                    scores
                )
                /
                len(
                    scores
                )
            ),

            "minimum_risk_score": (
                min(
                    scores
                )
            ),

            "maximum_risk_score": (
                max(
                    scores
                )
            ),

            "modified_rula_distribution": {
                str(score): (
                    self._modified_rula_counts[
                        score
                    ]
                )
                for score
                in range(
                    1,
                    8,
                )
            },

            "buckets": (
                self._build_buckets()
            ),
        }

    # ========================================================
    # RAW SAMPLE COUNT
    # ========================================================

    def get_sample_count(
        self,
    ) -> int:

        return len(
            self._samples
        )