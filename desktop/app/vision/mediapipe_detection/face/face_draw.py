import cv2


# ==========================================================
# Debug Colors
#
# OpenCV = BGR
#
# Green   = Center
# Magenta = Anatomical LEFT
# Orange  = Anatomical RIGHT
# ==========================================================

CENTER_COLOR = (
    0,
    255,
    0
)

LEFT_COLOR = (
    255,
    0,
    255
)

RIGHT_COLOR = (
    0,
    165,
    255
)


# ==========================================================
# Get Point Color
# ==========================================================

def get_point_color(
    name
):

    # Anatomical LEFT
    if name.startswith(
        "left_"
    ):

        return LEFT_COLOR


    # Anatomical RIGHT
    if name.startswith(
        "right_"
    ):

        return RIGHT_COLOR


    # Nose / Chin
    return CENTER_COLOR


# ==========================================================
# Draw Face Points
# ==========================================================

def draw_face_points(
    frame,
    points,
    mirrored=False
):

    """
    Debug Selected Face Landmarks

    Green   = Center
    Magenta = Anatomical Left
    Orange  = Anatomical Right
    """

    # ======================================================
    # 1. Validate Input
    # ======================================================

    if frame is None:
        return frame

    if points is None:
        return frame


    # ======================================================
    # 2. Frame Size
    # ======================================================

    frame_height, frame_width = (
        frame.shape[:2]
    )


    # ======================================================
    # 3. Draw Selected Points
    # ======================================================

    for name, point in points.items():

        x = point["x"]
        y = point["y"]


        # --------------------------------------------------
        # Coordinate มาจาก Raw Frame
        #
        # ถ้า Display Frame ถูก Mirror
        # ต้องกลับแกน X
        # --------------------------------------------------

        if mirrored:

            display_x = (
                frame_width
                - 1
                - x
            )

        else:

            display_x = x


        display_y = y


        # --------------------------------------------------
        # เลือกสีตาม Anatomical Side
        # --------------------------------------------------

        color = get_point_color(
            name
        )


        # --------------------------------------------------
        # Eyelid ใช้จุดเล็กกว่า
        # --------------------------------------------------

        if (
            "_upper" in name
            or "_lower" in name
        ):

            radius = 4

        else:

            radius = 6


        # --------------------------------------------------
        # Draw Landmark
        # --------------------------------------------------

        cv2.circle(
            frame,
            (
                display_x,
                display_y
            ),
            radius,
            color,
            -1
        )


        # --------------------------------------------------
        # Draw Landmark ID
        # --------------------------------------------------

        cv2.putText(
            frame,
            str(
                point["id"]
            ),
            (
                display_x + 6,
                display_y + 12
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            color,
            1,
            cv2.LINE_AA
        )


        # --------------------------------------------------
        # Draw Landmark Name
        # --------------------------------------------------

        cv2.putText(
            frame,
            name,
            (
                display_x + 6,
                display_y - 6
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            color,
            1,
            cv2.LINE_AA
        )


    return frame