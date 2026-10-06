import cv2


class CameraService:

    @staticmethod
    def scan_cameras(
        max_index: int = 2
    ) -> list[dict]:

        cameras = []

        for index in range(max_index):

            print(
                f"Checking camera index {index}..."
            )

            # ไม่บังคับ DirectShow
            # ให้ OpenCV เลือก backend ที่เหมาะสมเอง
            capture = cv2.VideoCapture(index)

            if not capture.isOpened():

                print(
                    f"Camera {index}: not available"
                )

                capture.release()
                continue

            # ลองอ่านภาพจริงจากกล้อง
            success, frame = capture.read()

            if not success or frame is None:

                print(
                    f"Camera {index}: "
                    "opened but cannot read frame"
                )

                capture.release()
                continue

            # อ่านขนาดภาพจริงที่ได้รับ
            height, width = frame.shape[:2]

            camera_data = {
                "device_index": index,
                "camera_name": f"Camera {index}",
                "resolution_width": width,
                "resolution_height": height
            }

            cameras.append(
                camera_data
            )

            print(
                f"Camera {index}: detected "
                f"({width}x{height})"
            )

            # คืนกล้องให้ระบบ
            capture.release()

        return cameras