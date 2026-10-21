# mediapipe_detection/pose/pose_points.py


# ==========================================================
# Landmark ที่ PostGuard ใช้
# ==========================================================

POSE_POINTS = {
    "nose": 0,
    "left_ear": 7,
    "right_ear": 8,
    "left_shoulder": 11,
    "right_shoulder": 12,
}


# ==========================================================
# Extract Landmark
# ==========================================================

def extract_pose_points(
    result,
    frame_width,
    frame_height
):
    """
    รับผลลัพธ์จาก MediaPipe Pose
    แล้วเลือกเฉพาะ Landmark ที่ PostGuard ใช้

    Parameters
    ----------
    result:
        ผลลัพธ์ที่ได้จาก MediaPipe Pose Landmarker

    frame_width:
        ความกว้างของภาพ Webcam

    frame_height:
        ความสูงของภาพ Webcam

    Returns
    -------
    dict | None

    ถ้าพบ Pose:
        คืน dictionary ของ Landmark

    ถ้าไม่พบ Pose:
        คืน None
    """

    # ------------------------------------------------------
    # 1. ตรวจว่าพบ Pose หรือไม่
    # ------------------------------------------------------

    if not result.pose_landmarks:
        return None


    # ------------------------------------------------------
    # 2. ใช้ Pose ของคนแรก
    # ------------------------------------------------------

    landmarks = result.pose_landmarks[0]


    # ------------------------------------------------------
    # 3. ดึง World Landmarks
    # ถ้ามี
    # ------------------------------------------------------

    world_landmarks = None

    if result.pose_world_landmarks:
        world_landmarks = (
            result.pose_world_landmarks[0]
        )


    # ------------------------------------------------------
    # 4. เตรียม dictionary สำหรับเก็บผล
    # ------------------------------------------------------

    points = {}


    # ------------------------------------------------------
    # 5. ดึงเฉพาะ Landmark ที่ PostGuard ต้องใช้
    # ------------------------------------------------------

    for name, index in POSE_POINTS.items():

        landmark = landmarks[index]


        # --------------------------------------------------
        # MediaPipe ให้ x / y เป็น normalized coordinate
        #
        # ตัวอย่าง:
        # x = 0.5
        #
        # หมายถึงอยู่ประมาณกลางภาพ
        #
        # เราจึงแปลงเป็น pixel เพื่อใช้กับ OpenCV
        # --------------------------------------------------

        x = int(
            landmark.x * frame_width
        )

        y = int(
            landmark.y * frame_height
        )


        # --------------------------------------------------
        # ค่า World Landmark เริ่มต้นเป็น None
        # --------------------------------------------------

        world_x = None
        world_y = None
        world_z = None


        # --------------------------------------------------
        # ถ้ามี World Landmark
        # ให้ดึง x / y / z ออกมา
        # --------------------------------------------------

        if world_landmarks is not None:

            world_landmark = (
                world_landmarks[index]
            )

            world_x = float(
                world_landmark.x
            )

            world_y = float(
                world_landmark.y
            )

            world_z = float(
                world_landmark.z
            )


        # --------------------------------------------------
        # เก็บข้อมูล Landmark
        # --------------------------------------------------

        points[name] = {

            # ----------------------------------------------
            # Image Coordinate
            # ----------------------------------------------

            "x": x,

            "y": y,

            "z": float(
                landmark.z
            ),


            # ----------------------------------------------
            # World Coordinate
            # ----------------------------------------------

            "world_x": world_x,

            "world_y": world_y,

            "world_z": world_z,


            # ----------------------------------------------
            # Landmark Quality
            # ----------------------------------------------

            "visibility": float(
                landmark.visibility
            ),

            "presence": float(
                landmark.presence
            ),
        }


    return points