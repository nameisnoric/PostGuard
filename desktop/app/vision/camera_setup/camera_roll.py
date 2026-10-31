import cv2
import numpy as np


def level_frame(frame, roll_deg, remove_black_border=True):
    """
    α╕½α╕íα╕╕α╕Öα╕áα╕▓α╕₧α╣Çα╕₧α╕╖α╣êα╕¡α╣üα╕üα╣ë Camera Roll

    remove_black_border=True
    α╕êα╕░ Zoom α╕áα╕▓α╕₧α╣Çα╕Ñα╣çα╕üα╕Öα╣ëα╕¡α╕óα╣Çα╕₧α╕╖α╣êα╕¡α╣äα╕íα╣êα╣âα╕½α╣ëα╣Çα╕üα╕┤α╕öα╕éα╕¡α╕Üα╕öα╕│
    """
    h, w = frame.shape[:2]

    if remove_black_border:
        angle_rad = np.radians(abs(roll_deg))

        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)

        scale_x = cos_a + (h / w) * sin_a
        scale_y = cos_a + (w / h) * sin_a

        scale = max(scale_x, scale_y)
    else:
        scale = 1.0

    matrix = cv2.getRotationMatrix2D(
        (w / 2, h / 2),
        roll_deg,
        scale
    )

    corrected = cv2.warpAffine(
        frame,
        matrix,
        (w, h)
    )

    return corrected


def draw_level_grid(img, step=160):
    """α╕ºα╕▓α╕öα╣Çα╕¬α╣ëα╕Öα╕òα╕▓α╕úα╕▓α╕çα╕òα╕▒α╣ëα╕ç/α╕Öα╕¡α╕Ö α╣âα╕½α╣ëα╕£α╕╣α╣ëα╣âα╕èα╣ëα╣Çα╕ùα╕╡α╕óα╕Üα╕üα╕▒α╕Üα╕éα╕¡α╕Üα╕¢α╕úα╕░α╕òα╕╣α╕½α╕úα╕╖α╕¡α╕£α╕Öα╕▒α╕ç"""
    h, w = img.shape[:2]

    for x in range(step, w, step):
        cv2.line(img, (x, 0), (x, h), (255, 255, 255), 1)

    for y in range(step, h, step):
        cv2.line(img, (0, y), (w, y), (255, 255, 255), 1)

    cv2.line(img, (w // 2, 0), (w // 2, h), (0, 255, 255), 2)
    cv2.line(img, (0, h // 2), (w, h // 2), (0, 255, 255), 2)


def _normalize_axis_angle(angle_deg):
    """
    α╣üα╕¢α╕Ñα╕çα╕íα╕╕α╕íα╕éα╕¡α╕çα╣Çα╕¬α╣ëα╕Öα╣âα╕½α╣ëα╣Çα╕¢α╣çα╕Öα╕äα╕ºα╕▓α╕íα╣Çα╕¡α╕╡α╕óα╕çα╣Çα╕ùα╕╡α╕óα╕Üα╕üα╕▒α╕Üα╣üα╕üα╕Öα╣üα╕Öα╕ºα╕Öα╕¡α╕Ö/α╣üα╕Öα╕ºα╕òα╕▒α╣ëα╕çα╕ùα╕╡α╣êα╣âα╕üα╕Ñα╣ëα╕ùα╕╡α╣êα╕¬α╕╕α╕ö
    α╕£α╕Ñα╕Ñα╕▒α╕₧α╕ÿα╣îα╕¡α╕óα╕╣α╣êα╣âα╕Öα╕èα╣êα╕ºα╕ç -45 α╕ûα╕╢α╕ç +45 α╕¡α╕çα╕¿α╕▓
    """
    return (float(angle_deg) + 45.0) % 90.0 - 45.0


def _weighted_median(values, weights):
    """α╕½α╕▓ Median α╣üα╕Üα╕Üα╣âα╕½α╣ëα╕Öα╣ëα╕│α╕½α╕Öα╕▒α╕üα╕öα╣ëα╕ºα╕óα╕äα╕ºα╕▓α╕íα╕óα╕▓α╕ºα╕éα╕¡α╕çα╣Çα╕¬α╣ëα╕Ö"""
    values = np.asarray(values, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)

    if values.size == 0 or weights.size != values.size:
        return None

    total_weight = float(np.sum(weights))

    if total_weight <= 0:
        return None

    order = np.argsort(values)
    values = values[order]
    weights = weights[order]

    cumulative = np.cumsum(weights)
    cutoff = total_weight * 0.5

    index = int(np.searchsorted(cumulative, cutoff, side="left"))
    index = min(index, len(values) - 1)

    return float(values[index])


def estimate_scene_tilt(frame):
    """
    α╕¢α╕úα╕░α╕íα╕▓α╕ô Camera Roll α╕êα╕▓α╕üα╣Çα╕¬α╣ëα╕Öα╣éα╕äα╕úα╕çα╕¬α╕úα╣ëα╕▓α╕çα╣âα╕Öα╕ëα╕▓α╕ü

    α╕éα╕▒α╣ëα╕Öα╕òα╕¡α╕Ö:
    1. α╣âα╕èα╣ë ROI α╕üα╕ºα╣ëα╕▓α╕çα╕üα╕ºα╣êα╕▓α╣Çα╕ºα╕¡α╕úα╣îα╕èα╕▒α╕Öα╣Çα╕öα╕┤α╕í
    2. α╣Çα╕₧α╕┤α╣êα╕í local contrast α╣Çα╕₧α╕╖α╣êα╕¡α╕èα╣êα╕ºα╕óα╕ëα╕▓α╕üα╕ùα╕╡α╣ê contrast α╕òα╣êα╕│
    3. α╕òα╕úα╕ºα╕êα╣Çα╕¬α╣ëα╕Öα╕öα╣ëα╕ºα╕ó HoughLinesP
    4. α╕úα╕ºα╕íα╣üα╕Öα╕ºα╕òα╕▒α╣ëα╕ç/α╣üα╕Öα╕ºα╕Öα╕¡α╕Öα╣âα╕½α╣ëα╕¡α╕óα╕╣α╣êα╣âα╕Ö axis-relative angle α╣Çα╕öα╕╡α╕óα╕ºα╕üα╕▒α╕Ö
    5. α╣âα╕½α╣ëα╕Öα╣ëα╕│α╕½α╕Öα╕▒α╕üα╕òα╕▓α╕íα╕äα╕ºα╕▓α╕íα╕óα╕▓α╕ºα╕éα╕¡α╕çα╣Çα╕¬α╣ëα╕Ö
    6. α╕½α╕▓ dominant angle cluster α╕üα╣êα╕¡α╕Ö
    7. α╣âα╕èα╣ë weighted median α╕éα╕¡α╕ç cluster α╕½α╕Ñα╕▒α╕ü

    α╕äα╕╖α╕Öα╕äα╣êα╕▓:
        float -> α╕íα╕╕α╕íα╕ëα╕▓α╕üα╣éα╕öα╕óα╕¢α╕úα╕░α╕íα╕▓α╕ô
        None  -> α╕éα╣ëα╕¡α╕íα╕╣α╕Ñα╣Çα╕¬α╣ëα╕Öα╣äα╕íα╣êα╕₧α╕¡α╕½α╕úα╕╖α╕¡α╣äα╕íα╣êα╕Öα╣êα╕▓α╣Çα╕èα╕╖α╣êα╕¡α╕ûα╕╖α╕¡
    """

    if frame is None:
        return None

    h, w = frame.shape[:2]

    if h < 40 or w < 40:
        return None

    # α╣âα╕èα╣ëα╕₧α╕╖α╣ëα╕Öα╕ùα╕╡α╣êα╕áα╕▓α╕₧α╕íα╕▓α╕üα╕éα╕╢α╣ëα╕Öα╣Çα╕₧α╕╖α╣êα╕¡α╣äα╕íα╣êα╕òα╕▒α╕öα╕éα╕¡α╕Üα╕¢α╕úα╕░α╕òα╕╣/α╕£α╕Öα╕▒α╕çα╕¡α╕¡α╕üα╕íα╕▓α╕üα╣Çα╕üα╕┤α╕Öα╣äα╕¢
    crop = frame[
        int(h * 0.08):int(h * 0.92),
        int(w * 0.08):int(w * 0.92)
    ]

    if crop.size == 0:
        return None

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    # α╕èα╣êα╕ºα╕óα╣Çα╕₧α╕┤α╣êα╕í contrast α╕éα╕¡α╕çα╣Çα╕¬α╣ëα╕Öα╣âα╕Öα╕ëα╕▓α╕ü
    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    )

    gray = clahe.apply(gray)

    blurred = cv2.GaussianBlur(
        gray,
        (5, 5),
        0
    )

    edges = cv2.Canny(
        blurred,
        40,
        120
    )

    min_dimension = min(crop.shape[:2])

    min_line_length = max(
        40,
        int(min_dimension * 0.12)
    )

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 360.0,
        threshold=35,
        minLineLength=min_line_length,
        maxLineGap=25
    )

    if lines is None:
        return None

    lines = lines.reshape(-1, 4)

    angles = []
    weights = []

    for x1, y1, x2, y2 in lines:
        dx = float(x2 - x1)
        dy = float(y2 - y1)

        length = float(np.hypot(dx, dy))

        if length < min_line_length:
            continue

        raw_angle = float(
            np.degrees(
                np.arctan2(dy, dx)
            )
        )

        axis_angle = _normalize_axis_angle(
            raw_angle
        )

        # α╣Çα╕¢α╕┤α╕öα╕èα╣êα╕ºα╕çα╣Çα╕£α╕╖α╣êα╕¡ noise α╕íα╕▓α╕üα╕üα╕ºα╣êα╕▓α╣Çα╕ºα╕¡α╕úα╣îα╕èα╕▒α╕Öα╣Çα╕öα╕┤α╕í
        if abs(axis_angle) > 20.0:
            continue

        angles.append(axis_angle)
        weights.append(length)

    if len(angles) < 3:
        return None

    angles = np.asarray(
        angles,
        dtype=np.float64
    )

    weights = np.asarray(
        weights,
        dtype=np.float64
    )

    # α╕½α╕▓ dominant orientation α╕öα╣ëα╕ºα╕ó histogram α╣üα╕Üα╕Üα╕ûα╣êα╕ºα╕çα╕Öα╣ëα╕│α╕½α╕Öα╕▒α╕ü
    bin_edges = np.arange(
        -20.5,
        21.5,
        1.0
    )

    histogram, histogram_edges = np.histogram(
        angles,
        bins=bin_edges,
        weights=weights
    )

    if histogram.size == 0:
        return None

    peak_index = int(
        np.argmax(histogram)
    )

    peak_center = (
        histogram_edges[peak_index]
        +
        histogram_edges[peak_index + 1]
    ) / 2.0

    # α╣âα╕èα╣ëα╣Çα╕ëα╕₧α╕▓α╕░α╣Çα╕¬α╣ëα╕Öα╕ùα╕╡α╣êα╕¡α╕óα╕╣α╣êα╣âα╕üα╕Ñα╣ë dominant orientation
    cluster_mask = (
        np.abs(
            angles - peak_center
        )
        <= 3.0
    )

    cluster_angles = angles[cluster_mask]
    cluster_weights = weights[cluster_mask]

    if len(cluster_angles) < 2:
        return None

    total_weight = float(
        np.sum(weights)
    )

    cluster_weight = float(
        np.sum(cluster_weights)
    )

    if total_weight <= 0:
        return None

    confidence = (
        cluster_weight
        /
        total_weight
    )

    # α╕ûα╣ëα╕▓ dominant cluster α╕¡α╣êα╕¡α╕Öα╣Çα╕üα╕┤α╕Öα╣äα╕¢ α╣äα╕íα╣êα╣Çα╕öα╕▓α╕íα╕╕α╕íα╕íα╕▒α╣êα╕º
    if confidence < 0.20:
        return None

    result = _weighted_median(
        cluster_angles,
        cluster_weights
    )

    if result is None:
        return None

    return float(result)


def shoulder_tilt_report(
    left_shoulder,
    right_shoulder,
    threshold=3.0
):
    """
    α╣âα╕èα╣ëα╕üα╕▒α╕Üα╕áα╕▓α╕₧α╕ùα╕╡α╣êα╕£α╣êα╕▓α╕Ö level_frame α╣üα╕Ñα╣ëα╕º
    α╕½α╣ëα╕▓α╕íα╕Ñα╕Üα╕äα╣êα╕▓α╕üα╕Ñα╣ëα╕¡α╕çα╣Çα╕¡α╕╡α╕óα╕çα╕ïα╣ëα╕│
    """

    if left_shoulder[0] > right_shoulder[0]:
        left_shoulder, right_shoulder = (
            right_shoulder,
            left_shoulder
        )

    tilt = float(
        np.degrees(
            np.arctan2(
                right_shoulder[1] - left_shoulder[1],
                right_shoulder[0] - left_shoulder[0]
            )
        )
    )

    return {
        "tilt_deg": tilt,
        "needs_user_confirm": abs(tilt) > threshold
    }
