import os
import json
import cv2 as cv
import numpy as np

base_dir = os.path.dirname(os.path.abspath(__file__))

calibration_file = os.path.join( 
    base_dir, "calibration_result.json"
)

with open(calibration_file, "r") as f:
    calibration = json.load(f)

camera_matrix = np.array(
    calibration["camera_matrix"],
    dtype=np.float64
)

dist_coeff = np.array(
    calibration["distortion_coefficients"],
    dtype=np.float64
)

image_width = calibration["image_width"]
image_height = calibration["image_height"]

print("Camera Matrix: \n", camera_matrix)
print("Distortion_coefficients: \n", dist_coeff)

cap = cv.VideoCapture(0)

# ใช้ resolution เดียวกับตอน Calibration
cap.set(cv.CAP_PROP_FRAME_WIDTH, image_width)
cap.set(cv.CAP_PROP_FRAME_HEIGHT, image_height)

new_camera_matrix, roi = cv.getOptimalNewCameraMatrix(
    camera_matrix,
    dist_coeffs,
    (1024, 576),
    1,
    (1024, 576)
)

while True:

    ret, frame = cap.read()

    if not ret:
        print("Cannot read frame")
        break

    # Undistort frame
    undistorted = cv.undistort(
        frame,
        camera_matrix,
        dist_coeffs,
        None,
        new_camera_matrix
    )

    # Show original
    cv.imshow("Original", frame)

    # Show undistorted
    cv.imshow("Undistorted", undistorted)

    # Press Q to exit
    if cv.waitKey(1) & 0xFF == ord("q"):
        break


# =========================
# 5. Release
# =========================

cap.release()
cv.destroyAllWindows()