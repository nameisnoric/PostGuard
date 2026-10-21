import sys
import time
from pathlib import Path

import cv2


# ==========================================================
# Path Setup
# ==========================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

if str(BASE_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BASE_DIR)
    )


# ==========================================================
# Pipeline
# ==========================================================

from mediapipe_detection.detection_pipeline import (
    DetectionPipeline,
)


# ==========================================================
# Main
# ==========================================================

def main():

    camera_index = 0

    capture = cv2.VideoCapture(
        camera_index,
        cv2.CAP_DSHOW,
    )

    if not capture.isOpened():

        capture.release()

        capture = cv2.VideoCapture(
            camera_index
        )


    if not capture.isOpened():

        raise RuntimeError(
            "Cannot open camera."
        )


    pipeline = (
        DetectionPipeline()
    )


    window_name = (
        "PostGuard - Context Filter Test"
    )


    try:

        print()
        print("=" * 70)
        print("PostGuard Context Filter Live Test")
        print("=" * 70)

        print()
        print("Expected:")
        print()
        print("Sit still")
        print("TRANSITION -> VALID")
        print()
        print("Move / change posture")
        print("VALID -> TRANSITION")
        print()
        print("Hold new posture still")
        print("TRANSITION -> VALID")
        print()
        print("Leave camera / hide shoulders")
        print("-> UNKNOWN")
        print()
        print("ESC = exit")
        print()


        while True:

            success, frame = (
                capture.read()
            )


            if (
                not success
                or
                frame is None
            ):

                continue


            timestamp = (
                time.perf_counter()
            )


            result = (
                pipeline.process_frame(
                    frame,
                    timestamp,
                )
            )


            context = (
                result.get(
                    "context",
                    {}
                )
            )


            state = (
                context.get(
                    "state",
                    "UNKNOWN"
                )
            )


            reason = (
                context.get(
                    "reason",
                    "-"
                )
            )


            allow = (
                context.get(
                    "allow_posture_evaluation",
                    False
                )
            )


            median_motion = (
                context.get(
                    "median_motion"
                )
            )


            max_motion = (
                context.get(
                    "max_motion"
                )
            )


            stable_seconds = (
                context.get(
                    "stable_seconds",
                    0.0
                )
            )


            display = cv2.flip(
                frame,
                1,
            )


            # ==================================================
            # Context State
            # ==================================================

            cv2.putText(
                display,
                f"Context: {state}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )


            cv2.putText(
                display,
                f"Reason: {reason}",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )


            cv2.putText(
                display,
                f"Allow posture: {allow}",
                (20, 115),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )


            cv2.putText(
                display,
                (
                    "Stable: "
                    f"{stable_seconds:.2f}s"
                ),
                (20, 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )


            if median_motion is not None:

                cv2.putText(
                    display,
                    (
                        "Median motion: "
                        f"{median_motion:.4f}"
                    ),
                    (20, 185),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.60,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )


            if max_motion is not None:

                cv2.putText(
                    display,
                    (
                        "Max motion: "
                        f"{max_motion:.4f}"
                    ),
                    (20, 220),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.60,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )


            cv2.putText(
                display,
                "ESC = exit",
                (20, 260),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )


            cv2.imshow(
                window_name,
                display,
            )


            key = (
                cv2.waitKey(
                    1
                )
                &
                0xFF
            )


            if key == 27:
                break


    finally:

        pipeline.close()

        capture.release()

        cv2.destroyAllWindows()


if __name__ == "__main__":

    main()