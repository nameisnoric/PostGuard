# ==========================================================
# Face Landmark IDs ที่ PostGuard สนใจ
#
# left / right หมายถึง Anatomical Left / Right ของผู้ใช้
# ไม่ใช่ด้านซ้าย/ขวาของภาพ Mirror
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

    "right_eye_upper": 159,
    "right_eye_lower": 145,


    # ======================================================
    # Anatomical LEFT EYE
    # ======================================================

    "left_eye_outer": 263,
    "left_eye_inner": 362,

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
        # Normalized -> Sub-pixel Coordinate
        #
        # สำคัญ:
        #
        # ตรงนี้ยังเป็น float
        #
        # ใช้กับ geometric measurement เช่น
        # Eye Openness Ratio
        #
        # เพื่อไม่ให้เสีย precision จากการ int()
        # --------------------------------------------------

        x_pixel_float = (
            x_norm
            *
            frame_width
        )

        y_pixel_float = (
            y_norm
            *
            frame_height
        )


        # --------------------------------------------------
        # Sub-pixel -> Integer Pixel
        #
        # ใช้สำหรับ:
        #
        # - OpenCV drawing
        # - Debug
        # - Compatibility กับ code เดิม
        #
        # ตรงนี้คือส่วนที่หายไป
        # จึงเกิด NameError
        # --------------------------------------------------

        x_pixel = int(
            x_pixel_float
        )

        y_pixel = int(
            y_pixel_float
        )


        # --------------------------------------------------
        # Save
        # --------------------------------------------------

        points[name] = {

            "id": landmark_id,


            # ==============================================
            # Normalized Coordinate
            # ==============================================

            "x_norm": x_norm,
            "y_norm": y_norm,
            "z": z,


            # ==============================================
            # Sub-pixel Coordinate
            #
            # สำหรับ measurement ที่ต้องการ precision
            # เช่น Eye Openness
            # ==============================================

            "x_float": float(
                x_pixel_float
            ),

            "y_float": float(
                y_pixel_float
            ),


            # ==============================================
            # Integer Pixel
            #
            # สำหรับ Drawing / Debug / Code เดิม
            # ==============================================

            "x": x_pixel,
            "y": y_pixel,
        }


    # ======================================================
    # 6. Return Selected Points
    # ======================================================

    return points