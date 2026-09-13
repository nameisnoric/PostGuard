import os
import glob
import numpy as np
import cv2 as cv

# =========================
# 1. Configuration
# =========================

# Chessboard inner corners
PATTERN_SIZE = (11, 7)

# Chessboard square size (mm)
SQUARE_SIZE = 30.0

# Termination criteria for corner refinement
criteria = (
    cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER,
    30,
    0.001
)

# =========================
# 2. Find calibration images
# =========================

base_dir = os.path.dirname(os.path.abspath(__file__))
image_folder = os.path.join(base_dir, "calibration_images")

images = glob.glob(
    os.path.join(image_folder, "**", "*.png"),
    recursive=True
)

print("Found", len(images), "images")

# =========================
# 3. Prepare object points
# =========================

objp = np.zeros(
    (PATTERN_SIZE[0] * PATTERN_SIZE[1], 3),
    np.float32
)

objp[:, :2] = np.mgrid[
    0:PATTERN_SIZE[0],
    0:PATTERN_SIZE[1]
].T.reshape(-1, 2)

# Convert square units to millimeters
objp *= SQUARE_SIZE

# =========================
# 4. Storage
# =========================

objpoints = []
imgpoints = []

# =========================
# 5. Detect chessboard
# =========================

for fname in images:

    img = cv.imread(fname)

    if img is None:
        print("[ERROR] Cannot read:", fname)
        continue

    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

    ret, corners = cv.findChessboardCorners(
        gray,
        PATTERN_SIZE,
        None
    )

    if ret:

        # Improve corner accuracy
        corners2 = cv.cornerSubPix(
            gray,
            corners,
            (11, 11),
            (-1, -1),
            criteria
        )

        objpoints.append(objp)
        imgpoints.append(corners2)

        print("[OK]", os.path.basename(fname))

        # Show detected corners
        cv.drawChessboardCorners(
            img,
            PATTERN_SIZE,
            corners2,
            ret
        )

        cv.imshow("Chessboard Detection", img)
        cv.waitKey(200)

    else:
        print("[NOT FOUND]", os.path.basename(fname))

cv.destroyAllWindows()

# =========================
# 6. Check detected images
# =========================

print()
print("Successfully detected:", len(objpoints), "/", len(images))

if len(objpoints) == 0:
    print("No chessboard detected.")
    exit()

# =========================
# 7. Camera Calibration
# =========================

image_size = gray.shape[::-1]

ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv.calibrateCamera(
    objpoints,
    imgpoints,
    image_size,
    None,
    None
)

print()
print("===== Calibration Result =====")

print("Camera Matrix:")
print(camera_matrix)

print()
print("Distortion Coefficients:")
print(dist_coeffs)

print()
print("Reprojection Error:")
print(ret)

# =========================
# 8. Save Calibration Result
# =========================

import json

calibration_result = {
    "image_width": int(image_size[0]),
    "image_height": int(image_size[1]),
    "camera_matrix": camera_matrix.tolist(),
    "distortion_coefficients": dist_coeffs.tolist(),
    "reprojection_error": float(ret)
}

output_file = os.path.join(
    base_dir,
    "calibration_result.json"
)

with open(output_file, "w") as f:
    json.dump(calibration_result, f, indent=4)

print()
print("Calibration result saved to:")
print(output_file)