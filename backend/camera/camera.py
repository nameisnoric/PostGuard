import cv2
import os
import json
import numpy as np


def load_calibration():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    calibration_file = os.path.join(
        base_dir,
        "calibration_result.json"
    )

    with open(calibration_file, "r") as f:
        data = json.load(f)

    camera_matrix = np.array(
        data["camera_matrix"],
        dtype=np.float64
    )

    dist_coeffs = np.array(
        data["distortion_coefficients"],
        dtype=np.float64
    )

    return camera_matrix, dist_coeffs


def start_camera():

    # =========================
    # Load calibration
    # =========================

    camera_matrix, dist_coeffs = load_calibration()

    cam = cv2.VideoCapture(0)

    if not cam.isOpened():
        print("Error: Cannot open camera")
        return

    # =========================
    # Camera loop
    # =========================

    while True:

        ret, frame = cam.read()

        if not ret:
            print("Error: Cannot read frame")
            break

        # กลับด้านซ้าย-ขวา
        frame = cv2.flip(frame, 1)

        # =========================
        # Undistort
        # =========================

        h, w = frame.shape[:2]

        new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
            camera_matrix,
            dist_coeffs,
            (w, h),
            1,
            (w, h)
        )

        undistorted = cv2.undistort(
            frame,
            camera_matrix,
            dist_coeffs,
            None,
            new_camera_matrix
        )

        # =========================
        # Display
        # =========================

        cv2.imshow("PostGuard Camera - Original", frame)
        cv2.imshow("PostGuard Camera - Undistorted", undistorted)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    start_camera()