import cv2


POINT_COLOR = (
    0,
    255,
    0
)

LINE_COLOR = (
    0,
    255,
    255
)

TEXT_COLOR = (
    255,
    255,
    255
)


def draw_pose(
    frame,
    points,
    mirrored=False
):

    if points is None:
        return frame


    def pt(name):

        x = points[name]["x"]
        y = points[name]["y"]


        if mirrored:

            width = frame.shape[1]

            x = (
                width
                - 1
                - x
            )


        return (
            x,
            y
        )


    # ==============================================
    # วาดเส้นหู
    # ==============================================

    cv2.line(
        frame,
        pt("left_ear"),
        pt("right_ear"),
        LINE_COLOR,
        2
    )


    # ==============================================
    # วาดเส้นไหล่
    # ==============================================

    cv2.line(
        frame,
        pt("left_shoulder"),
        pt("right_shoulder"),
        LINE_COLOR,
        2
    )


    # ==============================================
    # วาด Landmark
    # ==============================================

    for name in points:

        x, y = pt(name)


        cv2.circle(
            frame,
            (x, y),
            7,
            POINT_COLOR,
            -1
        )


        cv2.putText(
            frame,
            name,
            (x + 8, y - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            TEXT_COLOR,
            1
        )


    return frame