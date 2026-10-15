"""Desktop access to the Personal Baseline collector from camera_card."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    # Keep the Desktop package named ``app`` ahead of Backend's package with
    # the same name; camera_card itself has a unique top-level package name.
    sys.path.append(str(BACKEND_DIR))

from camera_card.baseline.personal_baseline import (  # noqa: E402
    BASELINE_COLLECTING,
    BASELINE_FAILED,
    BASELINE_NEED_CONFIRMATION,
    BASELINE_SUCCESS,
    CONFIRMATION_CONFIRMED,
    PersonalBaselineCollector,
    PersonalBaselineConfig,
)

__all__ = [
    "BASELINE_COLLECTING",
    "BASELINE_FAILED",
    "BASELINE_NEED_CONFIRMATION",
    "BASELINE_SUCCESS",
    "CONFIRMATION_CONFIRMED",
    "PersonalBaselineCollector",
    "PersonalBaselineConfig",
]
