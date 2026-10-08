MIN_VISIBILITY = 0.6
MIN_PRESENCE = 0.6


REQUIRED_POINTS = [
    "nose",
    "left_shoulder",
    "right_shoulder",
]


def validate_pose_points(
    pose_points
):

    if pose_points is None:

        return {
            "valid": False,
            "reason": "pose_not_found",
            "invalid_points": []
        }


    invalid_points = []


    for name in REQUIRED_POINTS:

        point = pose_points.get(
            name
        )

        if point is None:

            invalid_points.append(
                name
            )

            continue


        visibility = (
            point["visibility"]
        )

        presence = (
            point["presence"]
        )


        if (
            visibility < MIN_VISIBILITY
            or
            presence < MIN_PRESENCE
        ):

            invalid_points.append(
                name
            )


    if invalid_points:

        return {
            "valid": False,

            "reason": (
                "low_landmark_quality"
            ),

            "invalid_points": (
                invalid_points
            )
        }


    return {
        "valid": True,
        "reason": "ok",
        "invalid_points": []
    }