import cv2
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class FaceDetector:

    def __init__(
        self,
        model_path,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5
    ):

        # ==================================================
        # 1. Base Options
        # ==================================================

        base_options = python.BaseOptions(
            model_asset_path=str(model_path)
        )


        # ==================================================
        # 2. Face Landmarker Options
        #
        # IMAGE mode:
        # ตอนนี้ยังใช้สำหรับ prototype/test เหมือนเดิม
        #
        # จุดที่เพิ่ม:
        # output_facial_transformation_matrixes=True
        # ==================================================

        options = vision.FaceLandmarkerOptions(

            base_options=base_options,

            running_mode=vision.RunningMode.IMAGE,

            num_faces=num_faces,

            min_face_detection_confidence=(
                min_face_detection_confidence
            ),

            min_face_presence_confidence=(
                min_face_presence_confidence
            ),

            # ตอนนี้ยังไม่ใช้ Blendshape
            output_face_blendshapes=False,

            # ==================================================
            # เปิด Transformation Matrix
            #
            # ใช้สำหรับทดลอง Head Orientation
            # Pitch / Yaw / Roll
            # ==================================================

            output_facial_transformation_matrixes=True
        )


        # ==================================================
        # 3. Create Face Landmarker
        # ==================================================

        self.landmarker = (
            vision.FaceLandmarker.create_from_options(
                options
            )
        )


    # ======================================================
    # Detect
    # ======================================================

    def detect(
        self,
        frame
    ):

        # --------------------------------------------------
        # ป้องกัน frame ไม่มีข้อมูล
        # --------------------------------------------------

        if frame is None:
            return None


        # ==================================================
        # OpenCV ใช้ BGR
        # MediaPipe ใช้ RGB
        # ==================================================

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )


        # ==================================================
        # numpy frame -> MediaPipe Image
        # ==================================================

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame
        )


        # ==================================================
        # Face Detection
        #
        # Result ตอนนี้จะมี:
        #
        # result.face_landmarks
        #
        # result.facial_transformation_matrixes
        # ==================================================

        result = self.landmarker.detect(
            mp_image
        )


        return result


    # ======================================================
    # Close
    # ======================================================

    def close(
        self
    ):

        self.landmarker.close()