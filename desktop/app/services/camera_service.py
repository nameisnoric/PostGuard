import cv2


class CameraService:

    @staticmethod
    def scan_cameras(max_index: int = 2) -> list[dict]:
        """Scan physical webcams and report the actual captured resolution."""
        cameras = []

        for index in range(max_index):
            print(f"Checking camera index {index}...")

            # Windows: DirectShow + MJPEG often allows 1280x720 at 30 FPS.
            # If DirectShow cannot read a frame, retry using OpenCV's default backend.
            frame = None
            for backend in (cv2.CAP_DSHOW, cv2.CAP_ANY):
                capture = cv2.VideoCapture(index, backend)

                try:
                    if not capture.isOpened():
                        continue

                    # Configure the camera BEFORE requesting the first frame.
                    capture.set(
                        cv2.CAP_PROP_FOURCC,
                        cv2.VideoWriter_fourcc(*"MJPG")
                    )
                    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    capture.set(cv2.CAP_PROP_FPS, 30)

                    success, candidate = capture.read()
                    if success and candidate is not None:
                        frame = candidate
                        break
                finally:
                    capture.release()

            if frame is None:
                print(f"Camera {index}: not available or cannot read frame")
                continue

            # Report the real frame size, not the requested size.
            height, width = frame.shape[:2]
            camera_data = {
                "device_index": index,
                "camera_name": f"Camera {index}",
                "resolution_width": width,
                "resolution_height": height,
            }
            cameras.append(camera_data)
            print(f"Camera {index}: detected ({width}x{height})")

        return cameras
