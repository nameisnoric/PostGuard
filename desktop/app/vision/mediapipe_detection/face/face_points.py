# ==========================================================
# Face Landmark IDs ที่ PostGuard สนใจ
#
# left / right หมายถึง Anatomical Left / Right ของผู้ใช้
# ไม่ใช่ด้านซ้าย/ขวาของภาพ Mirror
#
# ตอนนี้เตรียม:
# - Head / Face landmarks
# - Eye / Eyelid landmarks
#
# Eyelid points ยังไม่ได้ใช้คำนวณ Blink ในขั้นนี้
# ==========================================================

FACE_POINTS = {

    # ======================================================
    # Center Face
    # ======================================================

    "nose_tip": 1,
    "chin": 152,


    # ======================================================
    # Anatomical RIGHT EYE
    # ======================================================

    "right_eye_outer": 33,
    "right_eye_inner": 133,

    # Eyelid
    "right_eye_upper": 159,
    "right_eye_lower": 145,


    # ======================================================
    # Anatomical LEFT EYE
    # ======================================================

    "left_eye_outer": 263,
    "left_eye_inner": 362,

    # Eyelid
    "left_eye_upper": 386,
    "left_eye_lower": 374,


    # ======================================================
    # Face Sides
    # ======================================================

    "right_face": 234,
    "left_face": 454,
}


# ==========================================================
# Extract Selected Face Points
# ==========================================================

def extract_face_points(
    result,
    frame_width,
    frame_height
):

    # ======================================================
    # 1. ไม่มี Result
    # ======================================================

    if result is None:
        return None


    # ======================================================
    # 2. ไม่พบ Face Landmark
    # ======================================================

    if not result.face_landmarks:
        return None


    # ======================================================
    # 3. ใช้ Face แรก
    #
    # PostGuard ใช้ num_faces=1
    # ======================================================

    face_landmarks = (
        result.face_landmarks[0]
    )


    # ======================================================
    # 4. Dictionary สำหรับ Selected Points
    # ======================================================

    points = {}


    # ======================================================
    # 5. Extract Selected Landmark
    # ======================================================

    for name, landmark_id in FACE_POINTS.items():

        # --------------------------------------------------
        # ป้องกัน Index เกินจำนวน Landmark
        # --------------------------------------------------

        if landmark_id >= len(face_landmarks):
            return None


        landmark = (
            face_landmarks[
                landmark_id
            ]
        )


        # --------------------------------------------------
        # Normalized Coordinate
        #
        # x / y = normalized coordinate
        # z     = relative depth
        #
        # z ของ Face Landmarker ไม่ใช่เมตร
        # --------------------------------------------------

        x_norm = float(
            landmark.x
        )

        y_norm = float(
            landmark.y
        )

        z = float(
            landmark.z
        )


        # --------------------------------------------------
        # Normalized -> Pixel
        # --------------------------------------------------

        x_pixel = int(
            x_norm
            * frame_width
        )

        y_pixel = int(
            y_norm
            * frame_height
        )


        # --------------------------------------------------
        # Save
        # --------------------------------------------------

        points[name] = {

            "id": landmark_id,

            # Normalized
            "x_norm": x_norm,
            "y_norm": y_norm,
            "z": z,

            # Pixel
            "x": x_pixel,
            "y": y_pixel,
        }


    # ======================================================
    # 6. Return Selected Points
    # ======================================================

    return points