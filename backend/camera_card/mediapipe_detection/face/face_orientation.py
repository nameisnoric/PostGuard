import math

import numpy as np


# ==========================================================
# Face Orientation
#
# Facial Transformation Matrix
#          ↓
# Rotation Component
#          ↓
# Pure Rotation Matrix
#          ↓
# Pitch / Yaw / Roll
#
# IMPORTANT:
# ตอนนี้เป็น Experimental Metric
#
# ยังไม่ใช่:
# - Neck Risk
# - RULA
# - Personal Baseline
# - Flexion Threshold
# - Extension Threshold
# ==========================================================


def extract_face_orientation(
    result
):

    # ======================================================
    # 1. ไม่มี FaceLandmarker Result
    # ======================================================

    if result is None:
        return None


    # ======================================================
    # 2. Result ไม่มี Transformation Matrix attribute
    # ======================================================

    if not hasattr(
        result,
        "facial_transformation_matrixes"
    ):

        return None


    # ======================================================
    # 3. ไม่มี Transformation Matrix
    #
    # เช่นกรณี:
    # Face NOT FOUND
    # ======================================================

    matrices = (
        result.facial_transformation_matrixes
    )


    if matrices is None:
        return None


    if len(matrices) == 0:
        return None


    # ======================================================
    # 4. ใช้ใบหน้าแรก
    #
    # PostGuard:
    # num_faces = 1
    # ======================================================

    matrix = np.asarray(
        matrices[0],
        dtype=np.float64
    )


    # ======================================================
    # 5. ตรวจ Matrix Shape
    #
    # MediaPipe ควรให้ 4x4
    # ======================================================

    if matrix.shape != (
        4,
        4
    ):

        return None


    # ======================================================
    # 6. ดึงส่วน 3x3
    #
    # Transformation Matrix:
    #
    # [ sR sR sR Tx ]
    # [ sR sR sR Ty ]
    # [ sR sR sR Tz ]
    # [  0  0  0  1 ]
    #
    # s = uniform scale
    # R = rotation
    # T = translation
    #
    # MediaPipe ระบุว่า matrix ประกอบด้วย
    # uniform scale + rotation + translation
    # ======================================================

    rotation_with_scale = (
        matrix[
            :3,
            :3
        ]
    )


    # ======================================================
    # 7. แยก Scale + Rotation ด้วย SVD
    #
    # rotation_with_scale ≈ scale * R
    #
    # เราต้องการเฉพาะ R
    # ======================================================

    try:

        u, singular_values, vt = (
            np.linalg.svd(
                rotation_with_scale
            )
        )


    except np.linalg.LinAlgError:

        return None


    # ------------------------------------------------------
    # ประมาณ Uniform Scale
    #
    # ใช้เพื่อ debug เท่านั้น
    # ------------------------------------------------------

    scale = float(
        np.mean(
            singular_values
        )
    )


    # ------------------------------------------------------
    # Pure Rotation
    # ------------------------------------------------------

    rotation = (
        u
        @ vt
    )


    # ======================================================
    # 8. ป้องกัน Reflection Matrix
    #
    # Rotation Matrix ที่ถูกต้อง:
    #
    # det(R) ≈ +1
    #
    # ถ้าได้ -1 แปลว่าเกิด reflection
    # ======================================================

    if np.linalg.det(
        rotation
    ) < 0:

        u[
            :,
            -1
        ] *= -1


        rotation = (
            u
            @ vt
        )


    # ======================================================
    # 9. Euler Angle Extraction
    #
    # Convention ที่เรากำลังทดลอง:
    #
    # X rotation = Pitch
    # Y rotation = Yaw
    # Z rotation = Roll
    #
    # สมมติ:
    #
    # R = Rz(roll) * Ry(yaw) * Rx(pitch)
    #
    # IMPORTANT:
    # เครื่องหมาย + / - ยังไม่ล็อก
    #
    # ต้องยืนยันจากการทดลองจริง:
    # Normal / Flexion / Extension
    # ======================================================

    r00 = rotation[0, 0]
    r10 = rotation[1, 0]
    r20 = rotation[2, 0]

    r21 = rotation[2, 1]
    r22 = rotation[2, 2]


    # ======================================================
    # 10. ตรวจ Singular / Gimbal Lock
    # ======================================================

    sy = math.sqrt(
        (
            r00
            * r00
        )
        +
        (
            r10
            * r10
        )
    )


    singular = (
        sy
        < 1e-6
    )


    # ======================================================
    # 11. Normal Case
    # ======================================================

    if not singular:

        pitch_rad = math.atan2(
            r21,
            r22
        )


        yaw_rad = math.atan2(
            -r20,
            sy
        )


        roll_rad = math.atan2(
            r10,
            r00
        )


    # ======================================================
    # 12. Singular Case
    # ======================================================

    else:

        pitch_rad = math.atan2(
            -rotation[1, 2],
            rotation[1, 1]
        )


        yaw_rad = math.atan2(
            -r20,
            sy
        )


        # ใน singular state
        # Roll แยกไม่ได้แน่นอน
        roll_rad = 0.0


    # ======================================================
    # 13. Radians -> Degrees
    # ======================================================

    pitch = math.degrees(
        pitch_rad
    )


    yaw = math.degrees(
        yaw_rad
    )


    roll = math.degrees(
        roll_rad
    )


    # ======================================================
    # 14. Determinant
    #
    # Pure Rotation ควรใกล้ +1
    # ใช้เป็น diagnostic
    # ======================================================

    rotation_det = float(
        np.linalg.det(
            rotation
        )
    )


    # ======================================================
    # 15. Return
    # ======================================================

    return {

        # Orientation
        "pitch": pitch,
        "yaw": yaw,
        "roll": roll,

        # Diagnostic
        "scale": scale,
        "rotation_det": rotation_det,
        "singular": singular,

        # Raw / Debug Matrix
        "matrix": matrix,

        # Pure Rotation Matrix
        "rotation_matrix": rotation,
    }