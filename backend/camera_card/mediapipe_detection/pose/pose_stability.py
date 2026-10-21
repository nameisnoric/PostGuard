from collections import deque

import numpy as np


class PoseStability:

    def __init__(
        self,
        window_size=90,
        min_samples=30
    ):

        self.window_size = (
            window_size
        )

        self.min_samples = (
            min_samples
        )


        self.left_shoulder_history = deque(
            maxlen=window_size
        )

        self.right_shoulder_history = deque(
            maxlen=window_size
        )


    def add(
        self,
        pose_points
    ):
        """
        เพิ่มตำแหน่ง Shoulder ของ valid frame
        """

        self.left_shoulder_history.append(
            (
                pose_points[
                    "left_shoulder"
                ]["x"],

                pose_points[
                    "left_shoulder"
                ]["y"]
            )
        )


        self.right_shoulder_history.append(
            (
                pose_points[
                    "right_shoulder"
                ]["x"],

                pose_points[
                    "right_shoulder"
                ]["y"]
            )
        )


    def reset(
        self
    ):

        self.left_shoulder_history.clear()
        self.right_shoulder_history.clear()


    def sample_count(
        self
    ):

        return len(
            self.left_shoulder_history
        )


    def is_ready(
        self
    ):

        return (
            self.sample_count()
            >= self.min_samples
        )


    def get_stats(
        self
    ):
        """
        คืนค่า Standard Deviation
        ของ Left/Right Shoulder
        """

        if not self.is_ready():
            return None


        left_array = np.array(
            self.left_shoulder_history,
            dtype=np.float32
        )


        right_array = np.array(
            self.right_shoulder_history,
            dtype=np.float32
        )


        return {

            "left": {

                "std_x": float(
                    np.std(
                        left_array[:, 0]
                    )
                ),

                "std_y": float(
                    np.std(
                        left_array[:, 1]
                    )
                ),
            },


            "right": {

                "std_x": float(
                    np.std(
                        right_array[:, 0]
                    )
                ),

                "std_y": float(
                    np.std(
                        right_array[:, 1]
                    )
                ),
            },


            "samples": (
                self.sample_count()
            )
        }