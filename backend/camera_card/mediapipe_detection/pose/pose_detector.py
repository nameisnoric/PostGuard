import time

import cv2
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .pose_points import extract_pose_points


class PoseDetector:

    def __init__(
        self,
        model_path,
        num_poses=1,
        min_detection_confidence=0.5,
        min_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    ):
        """
        สร้าง MediaPipe Pose Landmarker

        Parameters
        ----------
        model_path:
            path ของไฟล์ pose_landmarker_lite.task

        num_poses:
            จำนวนคนสูงสุดที่ต้องการตรวจ
            ตอนนี้ PostGuard ใช้ 1 คน

        min_detection_confidence:
            confidence ขั้นต่ำตอน detect pose

        min_presence_confidence:
            confidence ขั้นต่ำว่ามี landmark อยู่จริง

        min_tracking_confidence:
            confidence ขั้นต่ำของการ tracking ระหว่าง frame
        """

        # ==================================================
        # 1. กำหนด Model
        # ==================================================

        base_options = python.BaseOptions(
            model_asset_path=str(
                model_path
            )
        )


        # ==================================================
        # 2. ตั้งค่า Pose Landmarker
        # ==================================================

        options = vision.PoseLandmarkerOptions(

            base_options=base_options,

            running_mode=(
                vision.RunningMode.VIDEO
            ),

            num_poses=num_poses,

            min_pose_detection_confidence=(
                min_detection_confidence
            ),

            min_pose_presence_confidence=(
                min_presence_confidence
            ),

            min_tracking_confidence=(
                min_tracking_confidence
            ),

            output_segmentation_masks=False,
        )


        # ==================================================
        # 3. สร้าง Pose Landmarker
        # ==================================================

        self.landmarker = (
            vision.PoseLandmarker
            .create_from_options(
                options
            )
        )


        # ==================================================
        # 4. ใช้สร้าง timestamp สำหรับ VIDEO mode
        # ==================================================

        self.start_time = (
            time.perf_counter()
        )


    def detect(
        self,
        frame
    ):
        """
        รับ OpenCV frame
        แล้วคืนเฉพาะ Landmark ที่ PostGuard ใช้

        Return
        ------
        dict | None

        ถ้าพบ Pose:
            คืน points จาก pose_points.py

        ถ้าไม่พบ:
            คืน None
        """

        # ==================================================
        # 1. อ่านขนาดภาพ
        # ==================================================

        height, width = (
            frame.shape[:2]
        )


        # ==================================================
        # 2. OpenCV BGR -> RGB
        # ==================================================

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )


        # ==================================================
        # 3. NumPy Image -> MediaPipe Image
        # ==================================================

        mp_image = mp.Image(

            image_format=(
                mp.ImageFormat.SRGB
            ),

            data=rgb_frame
        )


        # ==================================================
        # 4. สร้าง timestamp
        # ==================================================

        timestamp_ms = int(
            (
                time.perf_counter()
                - self.start_time
            )
            * 1000
        )


        # ==================================================
        # 5. ส่งภาพเข้า MediaPipe Pose
        # ==================================================

        result = (
            self.landmarker
            .detect_for_video(
                mp_image,
                timestamp_ms
            )
        )


        # ==================================================
        # 6. เลือก Landmark ที่ PostGuard ใช้
        # ==================================================

        return extract_pose_points(
            result,
            width,
            height
        )


    def close(
        self
    ):
        """
        ปิด MediaPipe resource
        """

        self.landmarker.close()