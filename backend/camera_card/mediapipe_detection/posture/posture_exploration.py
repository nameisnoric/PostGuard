def calculate_head_shoulder_world_values(points):

    nose = points["nose"]

    left_ear = points["left_ear"]
    right_ear = points["right_ear"]

    left_shoulder = points["left_shoulder"]
    right_shoulder = points["right_shoulder"]


    ear_mid_y = (
        left_ear["world_y"]
        + right_ear["world_y"]
    ) / 2

    ear_mid_z = (
        left_ear["world_z"]
        + right_ear["world_z"]
    ) / 2


    shoulder_mid_y = (
        left_shoulder["world_y"]
        + right_shoulder["world_y"]
    ) / 2

    shoulder_mid_z = (
        left_shoulder["world_z"]
        + right_shoulder["world_z"]
    ) / 2


    return {
        "head_shoulder_y": (
            ear_mid_y
            - shoulder_mid_y
        ),

        "head_shoulder_z": (
            ear_mid_z
            - shoulder_mid_z
        ),

        "nose_shoulder_y": (
            nose["world_y"]
            - shoulder_mid_y
        ),

        "nose_shoulder_z": (
            nose["world_z"]
            - shoulder_mid_z
        ),
    }