import os
import json
import cv2 as cv
import numpy as np

# =========================
# 1. Paths
# =========================

base_dir = os.path.dirname(os.path.abspath(__file__))

calibration_file = os.path.join(
    base_dir,
    "calibration_result.json"
)

# Test image
test_image = os.path.join(
    base_dir,
    "calibration_images",
    "leftcamera",
    "Im_L_1.png"
)

# =========================
# 2. Load calibration data
# =========================

with open(calibration_file, "r") as f:
    calibration_data = json.load(f)

camera_matrix = np.array(
    calibration_data["camera_matrix"],
    dtype=np.float64
)

dist_coeffs = np.array(
    calibration_data["distortion_coefficients"],
    dtype=np.float64
)

print("Calibration loaded successfully")

print()
print("Camera Matrix:")
print(camera_matrix)

print()
print("Distortion Coefficients:")
print(dist_coeffs)

# =========================
# 3. Load test image
# =========================

img = cv.imread(test_image)

if img is None:
    print("Cannot read test image:")
    print(test_image)
    exit()

# =========================
# 4. Undistort
# =========================

h, w = img.shape[:2]

new_camera_matrix, roi = cv.getOptimalNewCameraMatrix(
    camera_matrix,
    dist_coeffs,
    (w, h),
    1,
    (w, h)
)

undistorted = cv.undistort(
    img,
    camera_matrix,
    dist_coeffs,
    None,
    new_camera_matrix
)

# =========================
# 5. Display
# =========================

cv.imshow("Original Image", img)
cv.imshow("Undistorted Image", undistorted)

print()
print("Press any key to close.")

cv.waitKey(0)
cv.destroyAllWindows()