from pathlib import Path
import csv
import sys

import cv2
import numpy as np


# ==========================================================
# Locate camera_card independently of working directory
# ==========================================================

BASE_DIR = Path(__file__).resolve().parents[2]

if str(BASE_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BASE_DIR)
    )


from camera_setup.camera_roll import (
    estimate_scene_tilt,
    level_frame,
)

ANGLES = [-10, -8, -6, -4, -2, 2, 4, 6, 8, 10]
REPEATS = 2
CAMERA_INDEX = 0
GRID_STEP = 80
OUTPUT_DIR = BASE_DIR / "tests" / "tilt_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def rotate_image(frame, angle):
    """Simulate a known OpenCV rotation (positive means counterclockwise)."""
    height, width = frame.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(
        frame, matrix, (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def capture_frame(cap, round_number):
    while True:
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError("Cannot read webcam")
        preview = frame.copy()
        cv2.putText(
            preview, f"ROUND {round_number}: SPACE = capture, Q = quit",
            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
            (0, 255, 255), 2, cv2.LINE_AA,
        )
        cv2.imshow("PostGuard - Tilt Test Capture", preview)
        key = cv2.waitKey(1) & 0xFF
        if key == 32:
            return frame.copy()
        if key in (ord("q"), ord("Q"), 27):
            return None


def draw_test_grid(image, step=80):
    """Display overlay ONLY, added after all measurements are finished."""
    result = image.copy()
    height, width = result.shape[:2]
    overlay = result.copy()
    for x in range(step, width, step):
        cv2.line(overlay, (x, 0), (x, height), (185, 185, 185), 1)
    for y in range(step, height, step):
        cv2.line(overlay, (0, y), (width, y), (185, 185, 185), 1)
    result = cv2.addWeighted(overlay, 0.4, result, 0.6, 0)
    cv2.line(result, (width // 2, 0), (width // 2, height), (0, 255, 255), 2)
    cv2.line(result, (0, height // 2), (width, height // 2), (0, 255, 255), 2)
    return result


def degree(value, signed=True):
    if value is None:
        return "N/A"
    return f"{value:+.3f} deg" if signed else f"{value:.3f} deg"


def draw_panel(image, title, lines, color):
    result = image.copy()
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.55
    line_height = 27
    padding = 14
    text_lines = [title] + lines
    widths = [cv2.getTextSize(s, font, scale, 2)[0][0] for s in text_lines]
    width = min(max(widths) + 2 * padding, result.shape[1] - 30)
    height = line_height * len(text_lines) + 2 * padding
    x, y = 15, 15
    overlay = result.copy()
    cv2.rectangle(overlay, (x, y), (x + width, y + height), (12, 18, 24), -1)
    result = cv2.addWeighted(overlay, 0.9, result, 0.1, 0)
    cv2.rectangle(result, (x, y), (x + width, y + height), color, 2)
    for index, line in enumerate(text_lines):
        cv2.putText(
            result, line, (x + padding, y + padding + 18 + index * line_height),
            font, scale, color if index == 0 else (255, 255, 255),
            2, cv2.LINE_AA,
        )
    return result


def verify_with_features(original, corrected):
    """Independent image-content check: ORB matches + RANSAC affine.

    Estimate orientation of corrected image relative to original image.
    Returns (absolute_roll_deg, inlier_count, inlier_ratio, state).
    No invented angle if the matches are unreliable.
    """
    h, w = original.shape[:2]
    # Central region avoids black corners after affine rotation.
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(mask, (int(w * .12), int(h * .12)),
                  (int(w * .88), int(h * .88)), 255, -1)
    orb = cv2.ORB_create(nfeatures=2500, fastThreshold=10)
    g0 = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
    g1 = cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY)
    kp0, des0 = orb.detectAndCompute(g0, mask)
    kp1, des1 = orb.detectAndCompute(g1, mask)
    if des0 is None or des1 is None or len(kp0) < 12 or len(kp1) < 12:
        return None, 0, 0.0, "INSUFFICIENT_FEATURES"

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    pairs = matcher.knnMatch(des0, des1, k=2)
    good = [a for pair in pairs if len(pair) == 2
            for a, b in [pair] if a.distance < .75 * b.distance]
    if len(good) < 12:
        return None, 0, 0.0, "INSUFFICIENT_MATCHES"

    src = np.float32([kp0[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kp1[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    matrix, inliers = cv2.estimateAffinePartial2D(
        src, dst, method=cv2.RANSAC,
        ransacReprojThreshold=2.5, maxIters=5000, confidence=.99,
    )
    if matrix is None or inliers is None:
        return None, 0, 0.0, "AFFINE_FAILED"
    count = int(inliers.sum())
    ratio = count / len(good)
    if count < 20 or ratio < .35:
        return None, count, ratio, "LOW_MATCH_CONFIDENCE"

    # Rotation magnitude in the original -> corrected affine mapping.
    angle = float(np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0])))
    # reject non-rigid/unreasonable transform scale
    scale = float(np.hypot(matrix[0, 0], matrix[1, 0]))
    if not (.90 <= scale <= 1.10) or abs(angle) > 30:
        return None, count, ratio, "UNEXPECTED_TRANSFORM"
    return abs(angle), count, ratio, "OK"


def make_comparison(original_rotated, corrected, row):
    before = draw_test_grid(original_rotated, GRID_STEP)
    after = draw_test_grid(corrected, GRID_STEP)

    before_lines = [
        f"Round: {row['round']}",
        f"Reference rotation: {degree(row['reference_angle'])}",
        f"Original scene: {degree(row['baseline_angle'])}",
        f"Detected scene: {degree(row['detected_angle'])}",
        f"Detected change: {degree(row['detected_change'])}",
        f"Detection error: {degree(row['detection_error'], False)}",
    ]
    after_lines = [
        f"Round: {row['round']}",
        f"Correction applied: {row['correction_applied']}",
        f"Applied correction: {degree(row['correction_angle'])}",
        f"Geometric residual: {degree(row['geometric_residual_error'], False)}",
        f"Feature residual: {degree(row['feature_residual_error'], False)}",
        f"Feature inliers: {row['feature_inliers']} ({row['feature_inlier_ratio']:.0%})",
        f"Feature status: {row['feature_status']}",
        f"Line residual: {degree(row['post_detection_error'], False)}",
        f"Status: {row['status']}",
    ]
    before = draw_panel(before, "BEFORE CORRECTION", before_lines, (0, 185, 255))
    after = draw_panel(after, "AFTER CORRECTION", after_lines, (0, 220, 0))
    return before, after, np.hstack((before, after))


def run_test():
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError("Cannot open webcam")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    rows = []

    try:
        for round_number in range(1, REPEATS + 1):
            print(f"\nROUND {round_number}/{REPEATS}")
            print("Keep camera still and press SPACE.")
            original = capture_frame(cap, round_number)
            if original is None:
                break
            baseline = estimate_scene_tilt(original)
            if baseline is None:
                print("Original scene has insufficient lines; round skipped.")
                continue
            print(f"Original scene roll: {baseline:+.3f}")

            for angle in ANGLES:
                rotated = rotate_image(original, angle)
                detected = estimate_scene_tilt(rotated)

                # If no detection, there is no correction (identity operation).
                correction = 0.0
                corrected = rotated.copy()
                delta = None
                detection_error = None
                applied = False
                post_detected = None
                post_error = None
                status = "FAILED_NO_DETECTION"

                if detected is not None:
                    delta = detected - baseline
                    expected_change = -angle
                    detection_error = abs(delta - expected_change)
                    correction = delta
                    corrected = level_frame(
                        rotated, correction, remove_black_border=False
                    )
                    applied = True
                    post_detected = estimate_scene_tilt(corrected)
                    if post_detected is not None:
                        post_error = abs(post_detected - baseline)
                        status = "CORRECTED_POST_MEASURED"
                    else:
                        status = "CORRECTED_POST_UNMEASURABLE"

                # Measure actual corrected pixels vs original via feature matching.
                # This does NOT reuse HoughLinesP or the theoretical correction angle.
                feature_error, feature_inliers, feature_ratio, feature_status = (
                    verify_with_features(original, corrected)
                )

                # Always available because angle and commanded correction are known.
                # Geometric prediction, NOT an independent pixel measurement.
                geometric_error = abs(angle + correction)
                row = {
                    "round": round_number,
                    "reference_angle": angle,
                    "baseline_angle": baseline,
                    "detected_angle": detected,
                    "detected_change": delta,
                    "detection_error": detection_error,
                    "correction_angle": correction,
                    "correction_applied": applied,
                    "geometric_residual_error": geometric_error,
                    "post_detected_angle": post_detected,
                    "post_detection_error": post_error,
                    "feature_residual_error": feature_error,
                    "feature_inliers": feature_inliers,
                    "feature_inlier_ratio": feature_ratio,
                    "feature_status": feature_status,
                    "status": status,
                }
                rows.append(row)
                before, after, comparison = make_comparison(rotated, corrected, row)
                name = f"round{round_number}_{angle:+03d}"
                cv2.imwrite(str(OUTPUT_DIR / f"{name}_before.png"), before)
                cv2.imwrite(str(OUTPUT_DIR / f"{name}_after.png"), after)
                cv2.imwrite(str(OUTPUT_DIR / f"{name}_comparison.png"), comparison)
                cv2.imwrite(str(OUTPUT_DIR / f"{name}_rotated_raw.png"), rotated)
                cv2.imwrite(str(OUTPUT_DIR / f"{name}_corrected_raw.png"), corrected)
                print(
                    f"{angle:+4} deg | Detected: {degree(delta)} | "
                    f"Detection error: {degree(detection_error, False)} | "
                    f"Geometric: {geometric_error:.3f} deg | "
                    f"Feature: {degree(feature_error, False)} "
                    f"({feature_status}) | {status}"
                )

        csv_path = OUTPUT_DIR / "tilt_accuracy.csv"
        fieldnames = [
            "round", "reference_angle", "baseline_angle", "detected_angle",
            "detected_change", "detection_error", "correction_angle",
            "correction_applied", "geometric_residual_error",
            "post_detected_angle", "post_detection_error",
            "feature_residual_error", "feature_inliers",
            "feature_inlier_ratio", "feature_status", "status",
        ]
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        valid_detection = [r["detection_error"] for r in rows if r["detection_error"] is not None]
        valid_post = [r["post_detection_error"] for r in rows if r["post_detection_error"] is not None]
        valid_feature = [r["feature_residual_error"] for r in rows
                         if r["feature_residual_error"] is not None]
        applied = sum(r["correction_applied"] for r in rows)
        print("\n========== POSTGUARD TILT TEST ==========")
        print(f"Total trials: {len(rows)}")
        print(f"Detection valid: {len(valid_detection)}/{len(rows)}")
        print(f"Correction applied: {applied}/{len(rows)}")
        print(f"Post-detection valid: {len(valid_post)}/{len(rows)}")
        print(f"Feature validation valid: {len(valid_feature)}/{len(rows)}")
        if valid_detection:
            print(f"Detection MAE: {np.mean(valid_detection):.3f} deg")
        if rows:
            print(f"Geometric residual MAE (all): {np.mean([r['geometric_residual_error'] for r in rows]):.3f} deg")
        if valid_post:
            print(f"Post-detection residual MAE (valid only): {np.mean(valid_post):.3f} deg")
        if valid_feature:
            print(f"Feature residual MAE (valid only): {np.mean(valid_feature):.3f} deg")
        print(f"Results saved: {OUTPUT_DIR}")
        print(f"CSV saved: {csv_path}")
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run_test()
