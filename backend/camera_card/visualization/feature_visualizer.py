import cv2

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
YELLOW = (0, 255, 255)
CYAN = (255, 255, 0)


def _xy(point):
    if not isinstance(point, dict):
        return None
    try:
        return int(round(float(point['x']))), int(round(float(point['y'])))
    except (KeyError, TypeError, ValueError):
        return None


def _midpoint(point_a, point_b):
    a = _xy(point_a)
    b = _xy(point_b)
    if a is None or b is None:
        return None
    return int(round((a[0] + b[0]) / 2.0)), int(round((a[1] + b[1]) / 2.0))


def _put(frame, text, position, color=WHITE, scale=0.55, thickness=1):
    cv2.putText(frame, str(text), position, cv2.FONT_HERSHEY_SIMPLEX,
                scale, color, thickness, cv2.LINE_AA)


def _point(frame, point, label=None, color=GREEN, radius=5):
    if point is None:
        return
    cv2.circle(frame, point, radius, color, -1, cv2.LINE_AA)
    cv2.circle(frame, point, radius + 2, BLACK, 1, cv2.LINE_AA)
    if label:
        _put(frame, label, (point[0] + 8, point[1] - 8), WHITE, 0.45, 1)


def _line(frame, point_a, point_b, color=GREEN, thickness=2):
    if point_a is None or point_b is None:
        return
    cv2.line(frame, point_a, point_b, color, thickness, cv2.LINE_AA)


def _feature_value(result, feature_name):
    features = result.get('features') or {}
    feature = features.get(feature_name)
    if not isinstance(feature, dict) or feature.get('valid') is not True:
        return None
    value = feature.get('value')
    if isinstance(value, (int, float)):
        return float(value)
    return None


def draw_shoulder_tilt(frame, result):
    output = frame.copy()
    pose = (result.get('landmarks', {}).get('pose') or {})
    left = _xy(pose.get('left_shoulder'))
    right = _xy(pose.get('right_shoulder'))
    value = _feature_value(result, 'shoulder_tilt')
    if left is None or right is None:
        return output
    _point(output, left, 'L Shoulder')
    _point(output, right, 'R Shoulder')
    _line(output, left, right, GREEN, 3)
    center = (int((left[0] + right[0]) / 2), int((left[1] + right[1]) / 2))
    _line(output, (center[0] - 120, center[1]), (center[0] + 120, center[1]), CYAN, 1)
    if value is not None:
        _put(output, f'Shoulder Tilt = {value:+.2f} deg', (20, 40), YELLOW, 0.7, 2)
    return output


def draw_neck_lateral_tilt(frame, result):
    output = frame.copy()
    pose = (result.get('landmarks', {}).get('pose') or {})
    left_ear = _xy(pose.get('left_ear'))
    right_ear = _xy(pose.get('right_ear'))
    left_shoulder = _xy(pose.get('left_shoulder'))
    right_shoulder = _xy(pose.get('right_shoulder'))
    value = _feature_value(result, 'neck_lateral_tilt')
    required = (left_ear, right_ear, left_shoulder, right_shoulder)
    if any(point is None for point in required):
        return output
    _point(output, left_ear, 'L Ear')
    _point(output, right_ear, 'R Ear')
    _point(output, left_shoulder, 'L Shoulder')
    _point(output, right_shoulder, 'R Shoulder')
    _line(output, left_ear, right_ear, GREEN, 3)
    _line(output, left_shoulder, right_shoulder, CYAN, 3)
    if value is not None:
        _put(output, f'Neck Lateral = {value:+.2f} deg', (20, 40), YELLOW, 0.7, 2)
    _put(output, 'Formula: Ear angle - Shoulder angle', (20, 72), WHITE, 0.5, 1)
    return output


def draw_neck_flexion(frame, result):
    output = frame.copy()
    face = (result.get('landmarks', {}).get('face') or {})
    nose = _xy(face.get('nose_tip'))
    chin = _xy(face.get('chin'))
    value = _feature_value(result, 'neck_flexion')
    if nose is not None:
        _point(output, nose, 'Nose')
    if chin is not None:
        _point(output, chin, 'Chin')
    if nose is not None and chin is not None:
        _line(output, nose, chin, GREEN, 3)
        center = (int((nose[0] + chin[0]) / 2), int((nose[1] + chin[1]) / 2))
        _line(output, (center[0], center[1] - 100), (center[0], center[1] + 100), CYAN, 1)
    if value is not None:
        _put(output, f'Head Pitch = {value:+.2f} deg', (20, 40), YELLOW, 0.7, 2)
    _put(output, 'Actual metric: Face Transformation Matrix -> Pitch', (20, 72), WHITE, 0.48, 1)
    return output


def draw_eye_distance(frame, result):
    output = frame.copy()
    face = (result.get('landmarks', {}).get('face') or {})
    left_outer = face.get('left_eye_outer')
    left_inner = face.get('left_eye_inner')
    right_inner = face.get('right_eye_inner')
    right_outer = face.get('right_eye_outer')
    left_outer_xy = _xy(left_outer)
    left_inner_xy = _xy(left_inner)
    right_inner_xy = _xy(right_inner)
    right_outer_xy = _xy(right_outer)
    left_center = _midpoint(left_outer, left_inner)
    right_center = _midpoint(right_inner, right_outer)
    value = _feature_value(result, 'eye_distance')
    for point, label in ((left_outer_xy, 'L outer'), (left_inner_xy, 'L inner'),
                         (right_inner_xy, 'R inner'), (right_outer_xy, 'R outer')):
        _point(output, point, label, GREEN, 4)
    _line(output, left_outer_xy, left_inner_xy, CYAN, 1)
    _line(output, right_inner_xy, right_outer_xy, CYAN, 1)
    _point(output, left_center, 'L Eye Center', YELLOW, 5)
    _point(output, right_center, 'R Eye Center', YELLOW, 5)
    _line(output, left_center, right_center, GREEN, 3)
    if value is not None:
        _put(output, f'Eye Distance = {value:.2f} px', (20, 40), YELLOW, 0.7, 2)
    return output


def draw_feature(frame, result, feature_name):
    if feature_name == 'shoulder_tilt':
        return draw_shoulder_tilt(frame, result)
    if feature_name == 'neck_lateral_tilt':
        return draw_neck_lateral_tilt(frame, result)
    if feature_name == 'neck_flexion':
        return draw_neck_flexion(frame, result)
    if feature_name == 'eye_distance':
        return draw_eye_distance(frame, result)
    return frame.copy()
