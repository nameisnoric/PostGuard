
import cv2

from app.services.detection_service import DetectionService

def main():
    capture = cv2.VideoCapture(0)
    detector = None

    try:
        if not capture.isOpened():
            raise RuntimeError("Cannot open webcam")

        detector = DetectionService()

        for frame_number in range(1, 31):
            success, frame = capture.read()

            if not success:
                print("Failed to read camera frame")
                break

            result = detector.process_frame(frame)

            if frame_number % 5 == 0:
                print(
                    f"Frame {frame_number}: "
                    f"Pose={result['pose_points'] is not None}, "
                    f"Face={result['face_detected']}"
                )

    finally:
        if detector is not None:
            detector.close()

        capture.release()
        print("Camera and Detection closed")


if __name__ == "__main__":
    main()
