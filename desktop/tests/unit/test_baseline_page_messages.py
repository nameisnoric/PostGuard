import unittest

from app.ui.pages.baseline_page import (
    build_baseline_failure_message,
)


class BaselinePageMessageTests(unittest.TestCase):

    def test_low_valid_ratio_has_user_friendly_message(self):
        result = {
            "status": "FAILED",
            "failure_reason": "VALIDATION_FAILED",
            "validation": {
                "passed": False,
                "issues": ["LOW_VALID_RATIO"],
            },
            "rejection_reasons": {},
        }

        message = build_baseline_failure_message(result)

        self.assertIn("ข้อมูลท่าทาง", message)
        self.assertIn("ใบหน้า", message)
        self.assertNotIn("LOW_VALID_RATIO", message)

    def test_unstable_posture_has_stability_guidance(self):
        result = {
            "status": "FAILED",
            "failure_reason": "VALIDATION_FAILED",
            "validation": {
                "passed": False,
                "issues": ["SHOULDER_TILT_UNSTABLE"],
            },
            "rejection_reasons": {},
        }

        message = build_baseline_failure_message(result)

        self.assertIn("อยู่นิ่ง", message)
        self.assertNotIn("SHOULDER_TILT_UNSTABLE", message)

    def test_timeout_with_missing_features_mentions_visibility(self):
        result = {
            "status": "FAILED",
            "failure_reason": "CALIBRATION_TIMEOUT",
            "validation": {
                "passed": False,
                "issues": ["CALIBRATION_TIMEOUT"],
            },
            "rejection_reasons": {
                "shoulder_tilt_missing": 20,
                "eye_distance_missing": 5,
            },
        }

        message = build_baseline_failure_message(result)

        self.assertIn("ใบหน้า", message)
        self.assertIn("หัวไหล่", message)

    def test_timeout_with_contract_problem_gives_system_guidance(self):
        result = {
            "status": "FAILED",
            "failure_reason": "CALIBRATION_TIMEOUT",
            "validation": {
                "passed": False,
                "issues": ["CALIBRATION_TIMEOUT"],
            },
            "rejection_reasons": {
                "unsupported_contract_version": 10,
            },
        }

        message = build_baseline_failure_message(result)

        self.assertIn("ระบบตรวจจับ", message)
        self.assertNotIn("unsupported_contract_version", message)

    def test_unknown_failure_has_safe_generic_message(self):
        result = {
            "status": "FAILED",
            "failure_reason": "UNKNOWN",
            "validation": {
                "passed": False,
                "issues": [],
            },
            "rejection_reasons": {},
        }

        message = build_baseline_failure_message(result)

        self.assertIn("ลอง", message)

    def test_does_not_claim_low_light_is_cause(self):
        result = {
            "status": "FAILED",
            "failure_reason": "CALIBRATION_TIMEOUT",
            "validation": {
                "passed": False,
                "issues": ["CALIBRATION_TIMEOUT"],
            },
            "rejection_reasons": {
                "pose_not_found": 20,
            },
        }

        message = build_baseline_failure_message(result)

        self.assertNotIn("แสง", message)


if __name__ == "__main__":
    unittest.main()
