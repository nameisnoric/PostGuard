import math

from app.vision.mediapipe_detection.posture.relative_neck_rotation import (
    RELATIVE_NECK_ROTATION_VERSION,
    TORSO_MAPPING_K,
    calculate_relative_neck_rotation,
)


def test_neutral_returns_zero_with_stable_contract():
    result = calculate_relative_neck_rotation(
        head_yaw=0.0,
        torso_angle=0.0,
        head_baseline=0.0,
        torso_baseline=0.0,
    )
    assert result["valid"] is True
    assert result["reason"] == "OK"
    assert result["value"] == 0.0
    assert result["relative_neck_rotation"] == 0.0
    assert result["version"] == RELATIVE_NECK_ROTATION_VERSION


def test_head_only_rotation_is_preserved():
    result = calculate_relative_neck_rotation(30.0, 0.0, 5.0, 0.0)
    assert result["valid"] is True
    assert result["head_delta"] == 25.0
    assert result["torso_delta"] == 0.0
    assert result["relative_neck_rotation"] == 25.0


def test_whole_body_rotation_is_suppressed():
    torso_angle = 30.0 / TORSO_MAPPING_K
    result = calculate_relative_neck_rotation(30.0, torso_angle, 0.0, 0.0)
    assert result["valid"] is True
    assert math.isclose(result["torso_equivalent"], 30.0)
    assert math.isclose(result["relative_neck_rotation"], 0.0, abs_tol=1e-9)


def test_baselines_are_subtracted_before_compensation():
    result = calculate_relative_neck_rotation(
        head_yaw=15.0,
        torso_angle=10.0,
        head_baseline=5.0,
        torso_baseline=5.0,
    )
    assert result["head_delta"] == 10.0
    assert result["torso_delta"] == 5.0
    assert result["relative_neck_rotation"] == 10.0 - (TORSO_MAPPING_K * 5.0)


def test_invalid_input_keeps_the_same_result_shape():
    result = calculate_relative_neck_rotation(None, 0.0, 0.0, 0.0)
    assert result["valid"] is False
    assert result["reason"] == "INVALID_INPUT"
    assert result["value"] is None
    assert result["relative_neck_rotation"] is None
    assert result["version"] == RELATIVE_NECK_ROTATION_VERSION


def test_non_finite_values_are_rejected():
    for invalid in (math.nan, math.inf, -math.inf):
        result = calculate_relative_neck_rotation(invalid, 0.0, 0.0, 0.0)
        assert result["valid"] is False
        assert result["reason"] == "INVALID_INPUT"
