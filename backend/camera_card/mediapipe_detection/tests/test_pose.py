from pathlib import Path
import sys

import cv2


# ==========================================================
# เพิ่ม camera_card ลง Python path
# เพื่อให้รันไฟล์นี้โดยตรงได้
# ==========================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

sys.path.insert(
    0,
    str(BASE_DIR)
)


# ==========================================================
# Pose Modules
# ==========================================================

from mediapipe_detection.pose.pose_detector import (
    PoseDetector
)

from mediapipe_detection.pose.pose_draw import (
    draw_pose
)

from mediapipe_detection.pose.pose_validator import (
    validate_pose_points
)

from mediapipe_detection.pose.pose_stability import (
    PoseStability
)


# ==========================================================
# Posture Features
# ==========================================================

from mediapipe_detection.posture.posture_features import (
    calculate_shoulder_tilt,
    calculate_shoulder_elevation,
    calculate_neck_lateral_tilt
)


# ==========================================================
# Experimental Posture Features
# ==========================================================

from mediapipe_detection.posture.posture_exploration import (
    calculate_head_shoulder_world_values
)


# ==========================================================
# Model Path
# ==========================================================

MODEL_PATH = (
    BASE_DIR
    / "models"
    / "pose_landmarker_lite.task"
)


def main():

    # ======================================================
    # 1. Pose Detector
    # ======================================================

    pose_detector = PoseDetector(
        MODEL_PATH
    )


    # ======================================================
    # 2. Stability
    # ======================================================

    stability = PoseStability(
        window_size=90,
        min_samples=30
    )


    # ======================================================
    # 3. Webcam
    # ======================================================

    cap = cv2.VideoCapture(0)


    if not cap.isOpened():

        print(
            "Error: Can't open camera"
        )

        pose_detector.close()

        return


    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720
    )


    # ======================================================
    # 4. Main Loop
    # ======================================================

    while True:

        # --------------------------------------------------
        # อ่านภาพดิบจาก Webcam
        # --------------------------------------------------

        ret, raw_frame = cap.read()


        if not ret:

            print(
                "Error: Can't read frame"
            )

            break


        # ==================================================
        # 5. MediaPipe วิเคราะห์ภาพจริง
        # ไม่ Mirror
        # ==================================================

        points = pose_detector.detect(
            raw_frame
        )


        # ==================================================
        # 6. ภาพสำหรับแสดงผลให้ผู้ใช้
        # Mirror เหมือนกระจก
        # ==================================================

        display_frame = cv2.flip(
            raw_frame,
            1
        )


        # ==================================================
        # 7. ไม่พบ Pose
        # ==================================================

        if points is None:

            cv2.putText(
                display_frame,
                "Pose: NOT FOUND",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )


            cv2.putText(
                display_frame,
                "Landmarks: INVALID",
                (20, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )


            stability.reset()


        # ==================================================
        # 8. พบ Pose
        # ==================================================

        else:

            cv2.putText(
                display_frame,
                "Pose: OK",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )


            # ==================================================
            # 9. วาด Landmark บนภาพ Mirror
            # ==================================================

            draw_pose(
                display_frame,
                points,
                mirrored=True
            )


            # ==================================================
            # 10. Landmark Validator
            # ==================================================

            validation = (
                validate_pose_points(
                    points
                )
            )


            # ==================================================
            # 11. Landmark VALID
            # ==================================================

            if validation["valid"]:

                cv2.putText(
                    display_frame,
                    "Landmarks: VALID",
                    (20, 75),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )


                # ==========================================
                # 12. Stability
                # ==========================================

                stability.add(
                    points
                )


                # ==========================================
                # 13. Experimental
                # Neck Flexion / Extension Raw Values
                # ==========================================

                world_values = (
                    calculate_head_shoulder_world_values(
                        points
                    )
                )


                if world_values is not None:

                    cv2.putText(
                        display_frame,
                        (
                            "Head-Shoulder Y: "
                            f"{world_values['head_shoulder_y']:+.3f} m"
                        ),
                        (600, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 255),
                        2
                    )


                    cv2.putText(
                        display_frame,
                        (
                            "Head-Shoulder Z: "
                            f"{world_values['head_shoulder_z']:+.3f} m"
                        ),
                        (600, 75),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 255),
                        2
                    )


                    cv2.putText(
                        display_frame,
                        (
                            "Nose-Shoulder Y: "
                            f"{world_values['nose_shoulder_y']:+.3f} m"
                        ),
                        (600, 110),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 0),
                        2
                    )


                    cv2.putText(
                        display_frame,
                        (
                            "Nose-Shoulder Z: "
                            f"{world_values['nose_shoulder_z']:+.3f} m"
                        ),
                        (600, 145),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 0),
                        2
                    )


                else:

                    cv2.putText(
                        display_frame,
                        "World Landmark: NOT AVAILABLE",
                        (600, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 0, 255),
                        2
                    )


                # ==========================================
                # 14. Shoulder Tilt
                # ==========================================

                shoulder_angle = (
                    calculate_shoulder_tilt(
                        points["left_shoulder"],
                        points["right_shoulder"]
                    )
                )


                # ==========================================
                # 15. Shoulder Elevation
                # ==========================================

                shoulder_elevation = (
                    calculate_shoulder_elevation(
                        points["nose"],
                        points["left_shoulder"],
                        points["right_shoulder"]
                    )
                )


                # ==========================================
                # 16. Neck Lateral Tilt
                # ==========================================

                neck_lateral = (
                    calculate_neck_lateral_tilt(
                        points["left_ear"],
                        points["right_ear"],
                        points["left_shoulder"],
                        points["right_shoulder"]
                    )
                )


                # ==========================================
                # 17. แสดง Shoulder Tilt
                # ==========================================

                if shoulder_angle is not None:

                    cv2.putText(
                        display_frame,
                        (
                            "Shoulder Tilt: "
                            f"{shoulder_angle:+.2f} deg"
                        ),
                        (20, 210),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 255),
                        2
                    )


                # ==========================================
                # 18. แสดง Shoulder Elevation
                # ==========================================

                if shoulder_elevation is not None:

                    cv2.putText(
                        display_frame,
                        (
                            "L Elevation: "
                            f"{shoulder_elevation['left']:.3f}"
                        ),
                        (20, 245),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        (255, 255, 0),
                        2
                    )


                    cv2.putText(
                        display_frame,
                        (
                            "R Elevation: "
                            f"{shoulder_elevation['right']:.3f}"
                        ),
                        (20, 280),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        (255, 255, 0),
                        2
                    )


                # ==========================================
                # 19. แสดง Neck Lateral Tilt
                # ==========================================

                if neck_lateral is not None:

                    cv2.putText(
                        display_frame,
                        (
                            "Ear Angle: "
                            f"{neck_lateral['ear_angle']:+.2f} deg"
                        ),
                        (20, 320),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 200, 0),
                        2
                    )


                    cv2.putText(
                        display_frame,
                        (
                            "Shoulder Angle: "
                            f"{neck_lateral['shoulder_angle']:+.2f} deg"
                        ),
                        (20, 350),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 200, 0),
                        2
                    )


                    cv2.putText(
                        display_frame,
                        (
                            "Neck Tilt: "
                            f"{neck_lateral['neck_tilt']:+.2f} deg"
                        ),
                        (20, 380),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 0, 255),
                        2
                    )


            # ==================================================
            # 20. Landmark INVALID
            # ==================================================

            else:

                cv2.putText(
                    display_frame,
                    "Landmarks: INVALID",
                    (20, 75),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2
                )


                stability.reset()


        # ==================================================
        # 21. Stability Display
        # ==================================================

        if not stability.is_ready():

            cv2.putText(
                display_frame,
                (
                    "Stability samples: "
                    f"{stability.sample_count()}/"
                    f"{stability.min_samples}"
                ),
                (20, 115),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2
            )


        else:

            stats = (
                stability.get_stats()
            )


            cv2.putText(
                display_frame,
                (
                    "L shoulder std: "
                    f"x={stats['left']['std_x']:.2f} "
                    f"y={stats['left']['std_y']:.2f}"
                ),
                (20, 115),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )


            cv2.putText(
                display_frame,
                (
                    "R shoulder std: "
                    f"x={stats['right']['std_x']:.2f} "
                    f"y={stats['right']['std_y']:.2f}"
                ),
                (20, 145),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )


            cv2.putText(
                display_frame,
                (
                    "Samples: "
                    f"{stats['samples']}/"
                    f"{stability.window_size}"
                ),
                (20, 175),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )


        # ==================================================
        # 22. Display
        # ==================================================

        cv2.imshow(
            "PostGuard - Pose Test",
            display_frame
        )


        # ==================================================
        # 23. Keyboard
        # ==================================================

        key = (
            cv2.waitKey(1)
            & 0xFF
        )


        # q / ESC = ออก
        if key in (
            ord("q"),
            27
        ):

            break


        # R = Reset Stability
        if key in (
            ord("r"),
            ord("R")
        ):

            stability.reset()

            print(
                "Stability reset"
            )


    # ======================================================
    # 24. Cleanup
    # ======================================================

    cap.release()

    pose_detector.close()

    cv2.destroyAllWindows()


if __name__ == "__main__":

    main()