import cv2
import apriltag
import numpy as np

TAG_ID = 0

# =========================
# 1. Load image
# =========================

image_path = "tag36h11_id00000.png"

image = cv2.imread(image_path)

if image is None:
    print("Cannot load image")
    exit()

# =========================
# 2. Convert to grayscale
# =========================

gray = cv2.cvtColor(
    image,
    cv2.COLOR_BGR2GRAY
)

# =========================
# 3. AprilTag Detector
# =========================

options = apriltag.DetectorOptions(
    families="tag36h11"
)

detector = apriltag.Detector(options)

# =========================
# 4. Detect AprilTag
# =========================

results = detector.detect(gray)

print(
    "[INFO] {} total AprilTags detected".format(
        len(results)
    )
)

# =========================
# 5. Process detections
# =========================

for r in results:

    print("[INFO] Tag ID: {}".format(r.tag_id))

    tagFamily = r.tag_family.decode("utf-8")

    print(
        "[INFO] tag family: {}".format(tagFamily)
    )

    # ถ้าต้องการใช้เฉพาะ ID 0
    if r.tag_id != TAG_ID:
        continue

    # Get corners
    (ptA, ptB, ptC, ptD) = r.corners

    ptA = (int(ptA[0]), int(ptA[1]))
    ptB = (int(ptB[0]), int(ptB[1]))
    ptC = (int(ptC[0]), int(ptC[1]))
    ptD = (int(ptD[0]), int(ptD[1]))

    # Draw bounding box
    cv2.line(image, ptA, ptB, (0, 255, 0), 2)
    cv2.line(image, ptB, ptC, (0, 255, 0), 2)
    cv2.line(image, ptC, ptD, (0, 255, 0), 2)
    cv2.line(image, ptD, ptA, (0, 255, 0), 2)

    # Draw center
    cX = int(r.center[0])
    cY = int(r.center[1])

    cv2.circle(
        image,
        (cX, cY),
        5,
        (0, 0, 255),
        -1
    )

    # Show family + ID
    cv2.putText(
        image,
        f"{tagFamily} | ID: {r.tag_id}",
        (ptA[0], ptA[1] - 15),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 255, 0),
        2
    )

# =========================
# 6. Show result
# =========================

cv2.imshow(
    "AprilTag Detection",
    image
)

cv2.waitKey(0)
cv2.destroyAllWindows()