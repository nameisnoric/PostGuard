"""Keep camera preview containers aligned with the actual frame aspect ratio."""


def fitted_preview_size(frame_width, frame_height, max_width, max_height):
    """Return the largest frame-sized rectangle inside the given bounds."""
    values = (frame_width, frame_height, max_width, max_height)
    if any(type(value) not in (int, float) or value <= 0 for value in values):
        raise ValueError("Preview dimensions must be positive numbers")
    scale = min(max_width / frame_width, max_height / frame_height)
    return (
        max(1, round(frame_width * scale)),
        max(1, round(frame_height * scale)),
    )


def fit_preview_label(label, frame_width, frame_height, max_width, max_height):
    """Resize a QLabel so its background has the same ratio as the frame."""
    width, height = fitted_preview_size(
        frame_width,
        frame_height,
        max_width,
        max_height,
    )
    if label.width() != width or label.height() != height:
        label.setFixedSize(width, height)
    return width, height
