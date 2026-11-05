"""
PostGuard - Real Camera Resolution Compatibility Validation

Purpose
-------
Validate the Resolution Compatibility Gate with a real webcam while reusing
the same production logic used by MonitoringPage.

This is a MANUAL hardware validation script. It is intentionally kept outside
the normal unit-test workflow because it opens a physical camera.

Examples
--------
From C:\project\PostGuard\desktop:

    $env:PYTHONPATH = "C:\project\PostGuard\desktop"

    ..\backend\.venv\Scripts\python.exe `
        tests\vision_manual\test_resolution_compatibility_camera.py

Optional arguments:

    ..\backend\.venv\Scripts\python.exe `
        tests\vision_manual\test_resolution_compatibility_camera.py `
        --device 0 `
        --width 1280 `
        --height 720

The script runs two validation cases against the SAME real frame:

1. MATCH case
   Baseline resolution = actual camera frame resolution
   Expected result: COMPATIBLE

2. MISMATCH case
   Baseline resolution is intentionally changed
   Expected result: MISMATCH

A CSV report is saved under:
    tests/vision_manual/results/
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from app.vision.camera_setup.resolution_compatibility import (
    RESOLUTION_COMPATIBLE,
    RESOLUTION_MISMATCH,
    evaluate_resolution_compatibility,
)


DEFAULT_DEVICE_INDEX = 0
DEFAULT_REQUESTED_WIDTH = 1280
DEFAULT_REQUESTED_HEIGHT = 720

RESULTS_DIRECTORY = Path(__file__).resolve().parent / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate PostGuard resolution compatibility "
            "with a real webcam."
        )
    )

    parser.add_argument(
        "--device",
        type=int,
        default=DEFAULT_DEVICE_INDEX,
        help=(
            "OpenCV camera device index. "
            f"Default: {DEFAULT_DEVICE_INDEX}"
        ),
    )

    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_REQUESTED_WIDTH,
        help=(
            "Requested camera width. "
            f"Default: {DEFAULT_REQUESTED_WIDTH}"
        ),
    )

    parser.add_argument(
        "--height",
        type=int,
        default=DEFAULT_REQUESTED_HEIGHT,
        help=(
            "Requested camera height. "
            f"Default: {DEFAULT_REQUESTED_HEIGHT}"
        ),
    )

    return parser.parse_args()


def positive_dimension(value: int, name: str) -> int:
    if value <= 0:
        raise ValueError(
            f"{name} must be greater than zero."
        )

    return value


def open_camera(
    device_index: int,
    requested_width: int,
    requested_height: int,
) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(device_index)

    if not capture.isOpened():
        capture.release()
        raise RuntimeError(
            f"Unable to open camera device {device_index}."
        )

    # OpenCV's set() is a request to the camera/driver.
    # The actual frame shape remains the source of truth.
    capture.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        requested_width,
    )
    capture.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        requested_height,
    )

    return capture


def read_real_frame(
    capture: cv2.VideoCapture,
    warmup_frames: int = 10,
):
    """
    Read several frames before validation.

    Some webcams need a few frames after opening/changing resolution before
    the stream stabilizes. Only the final successfully read frame is used.
    """
    frame = None

    for _ in range(max(1, warmup_frames)):
        success, candidate = capture.read()

        if success and candidate is not None:
            frame = candidate

    if frame is None:
        raise RuntimeError(
            "Unable to read a valid frame from the camera."
        )

    return frame


def create_baseline(
    width: int,
    height: int,
) -> dict[str, Any]:
    """
    Build only the resolution fields required by the production gate.

    This is not a replacement for a real Personal Baseline. It is a small
    validation fixture used to prove the compatibility decision against a
    real camera frame.
    """
    return {
        "camera_frame_width": int(width),
        "camera_frame_height": int(height),
    }


def create_intentional_mismatch_baseline(
    actual_width: int,
    actual_height: int,
) -> dict[str, Any]:
    """
    Produce a baseline guaranteed to differ from the real frame.

    Prefer changing width while keeping height unchanged. This avoids making
    assumptions about which alternate modes the webcam itself supports,
    because the mismatch case tests the compatibility logic against the
    already captured real frame.
    """
    mismatch_width = (
        actual_width + 1
        if actual_width > 0
        else 1
    )

    return create_baseline(
        mismatch_width,
        actual_height,
    )


def make_result_row(
    *,
    test_case: str,
    device_index: int,
    requested_width: int,
    requested_height: int,
    baseline: dict[str, Any],
    result: dict[str, Any],
    expected_status: str,
) -> dict[str, Any]:
    passed = (
        result.get("status")
        == expected_status
    )

    return {
        "tested_at": datetime.now().astimezone().isoformat(),
        "test_case": test_case,
        "device_index": device_index,
        "requested_width": requested_width,
        "requested_height": requested_height,
        "baseline_width": baseline.get(
            "camera_frame_width"
        ),
        "baseline_height": baseline.get(
            "camera_frame_height"
        ),
        "actual_width": result.get(
            "actual_width"
        ),
        "actual_height": result.get(
            "actual_height"
        ),
        "status": result.get("status"),
        "compatible": result.get(
            "compatible"
        ),
        "reason": result.get("reason"),
        "expected_status": expected_status,
        "passed": passed,
    }


def print_case(row: dict[str, Any]) -> None:
    print()
    print("-" * 60)
    print(f"TEST CASE       : {row['test_case']}")
    print("-" * 60)
    print(
        "Requested       : "
        f"{row['requested_width']}x"
        f"{row['requested_height']}"
    )
    print(
        "Baseline        : "
        f"{row['baseline_width']}x"
        f"{row['baseline_height']}"
    )
    print(
        "Actual          : "
        f"{row['actual_width']}x"
        f"{row['actual_height']}"
    )
    print(
        f"Status          : {row['status']}"
    )
    print(
        f"Compatible      : {row['compatible']}"
    )
    print(
        f"Reason          : {row['reason']}"
    )
    print(
        f"Expected status : {row['expected_status']}"
    )
    print(
        "RESULT          : "
        + (
            "PASS"
            if row["passed"]
            else "FAIL"
        )
    )


def save_csv(
    rows: list[dict[str, Any]],
) -> Path:
    RESULTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_path = (
        RESULTS_DIRECTORY
        / (
            "resolution_compatibility_camera_"
            f"{timestamp}.csv"
        )
    )

    fieldnames = [
        "tested_at",
        "test_case",
        "device_index",
        "requested_width",
        "requested_height",
        "baseline_width",
        "baseline_height",
        "actual_width",
        "actual_height",
        "status",
        "compatible",
        "reason",
        "expected_status",
        "passed",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def main() -> int:
    args = parse_args()

    try:
        requested_width = positive_dimension(
            args.width,
            "width",
        )
        requested_height = positive_dimension(
            args.height,
            "height",
        )
    except ValueError as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print("=" * 60)
    print(
        "PostGuard Resolution Compatibility "
        "Camera Test"
    )
    print("=" * 60)
    print(f"Camera device   : {args.device}")
    print(
        "Requested       : "
        f"{requested_width}x"
        f"{requested_height}"
    )

    capture = None

    try:
        capture = open_camera(
            args.device,
            requested_width,
            requested_height,
        )

        frame = read_real_frame(capture)

        actual_height, actual_width = (
            frame.shape[:2]
        )

        reported_width = int(
            round(
                capture.get(
                    cv2.CAP_PROP_FRAME_WIDTH
                )
            )
        )
        reported_height = int(
            round(
                capture.get(
                    cv2.CAP_PROP_FRAME_HEIGHT
                )
            )
        )
        reported_fps = capture.get(
            cv2.CAP_PROP_FPS
        )

        print(
            "Driver reported : "
            f"{reported_width}x"
            f"{reported_height}"
        )
        print(
            "Actual frame     : "
            f"{actual_width}x"
            f"{actual_height}"
        )
        print(
            "FPS reported     : "
            f"{reported_fps:.3f}"
        )

        # ------------------------------------------------------------
        # Case R1: matching baseline
        # ------------------------------------------------------------
        matching_baseline = create_baseline(
            actual_width,
            actual_height,
        )

        matching_result = (
            evaluate_resolution_compatibility(
                matching_baseline,
                frame,
            )
        )

        match_row = make_result_row(
            test_case="R1_MATCH_REAL_FRAME",
            device_index=args.device,
            requested_width=requested_width,
            requested_height=requested_height,
            baseline=matching_baseline,
            result=matching_result,
            expected_status=RESOLUTION_COMPATIBLE,
        )

        # ------------------------------------------------------------
        # Case R2: intentional mismatch
        # ------------------------------------------------------------
        mismatch_baseline = (
            create_intentional_mismatch_baseline(
                actual_width,
                actual_height,
            )
        )

        mismatch_result = (
            evaluate_resolution_compatibility(
                mismatch_baseline,
                frame,
            )
        )

        mismatch_row = make_result_row(
            test_case=(
                "R2_MISMATCH_REAL_FRAME"
            ),
            device_index=args.device,
            requested_width=requested_width,
            requested_height=requested_height,
            baseline=mismatch_baseline,
            result=mismatch_result,
            expected_status=RESOLUTION_MISMATCH,
        )

        rows = [
            match_row,
            mismatch_row,
        ]

        for row in rows:
            print_case(row)

        output_path = save_csv(rows)

        overall_pass = all(
            row["passed"]
            for row in rows
        )

        print()
        print("=" * 60)
        print(
            "OVERALL RESULT  : "
            + (
                "PASS"
                if overall_pass
                else "FAIL"
            )
        )
        print(
            "CSV RESULT      : "
            f"{output_path}"
        )
        print("=" * 60)

        return (
            0
            if overall_pass
            else 1
        )

    except Exception as exc:
        print()
        print("=" * 60)
        print("OVERALL RESULT  : ERROR")
        print(f"ERROR           : {exc}")
        print("=" * 60)
        return 2

    finally:
        if capture is not None:
            capture.release()


if __name__ == "__main__":
    raise SystemExit(main())
