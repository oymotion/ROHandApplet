import math


SDK_POSITIONS_MAX = [45000, 65535, 65535, 65535, 65535, 65535]
DEFAULT_POSITION_SMOOTHING = 0.35
DEFAULT_MIN_SEND_DELTA = 10
DEFAULT_SEND_INTERVAL_MS = 2
DEFAULT_MAX_POSITION_STEP = 900
MOTION_PROFILE_FIXED = "fixed"
MOTION_PROFILE_ADAPTIVE = "adaptive"
ADAPTIVE_STEP_NEAR = 2000
ADAPTIVE_STEP_FAR = 22000
ADAPTIVE_ERROR_SPLIT = 3000
THUMB_ROOT_OPEN_ANGLE = 97.0
THUMB_ROOT_CLOSED_ANGLE = 125.0
FINGER_JOINTS = {
    "thumb": (2, 3, 4),
    "index": (5, 6, 8),
    "middle": (9, 10, 12),
    "ring": (13, 14, 16),
    "little": (17, 18, 20),
}
FINGER_ORDER = ("thumb", "index", "middle", "ring", "little", "thumb_root")


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, float(value)))


def angle_degrees(point_a, point_b, point_c):
    ax, ay = float(point_a[0]), float(point_a[1])
    bx, by = float(point_b[0]), float(point_b[1])
    cx, cy = float(point_c[0]), float(point_c[1])
    vector_a = (ax - bx, ay - by)
    vector_c = (cx - bx, cy - by)
    length_a = math.hypot(*vector_a)
    length_c = math.hypot(*vector_c)
    if length_a <= 0.0 or length_c <= 0.0:
        return 180.0
    cosine = (vector_a[0] * vector_c[0] + vector_a[1] * vector_c[1]) / (
        length_a * length_c
    )
    return math.degrees(math.acos(clamp(cosine, -1.0, 1.0)))


def curl_ratio_from_angle(angle, straight_angle=170.0, bent_angle=80.0):
    if straight_angle == bent_angle:
        return 0.0
    return clamp((straight_angle - float(angle)) / (straight_angle - bent_angle))


def point_distance(point_a, point_b):
    return math.hypot(
        float(point_a[0]) - float(point_b[0]), float(point_a[1]) - float(point_b[1])
    )


def thumb_curl_ratio_from_landmarks(landmarks):
    angle = angle_degrees(landmarks[2], landmarks[3], landmarks[4])
    angle_ratio = curl_ratio_from_angle(angle, straight_angle=175.0, bent_angle=105.0)
    hand_width = max(point_distance(landmarks[5], landmarks[17]), 1e-6)
    tip_to_index_mcp = point_distance(landmarks[4], landmarks[5])
    close_distance = hand_width * 0.12
    open_distance = hand_width * 0.45
    distance_ratio = 1.0 - clamp(
        (tip_to_index_mcp - close_distance) / (open_distance - close_distance)
    )
    return clamp(max(angle_ratio, distance_ratio))


def thumb_root_ratio_from_angle(angle):
    return clamp(
        1.0
        - (
            (float(angle) - THUMB_ROOT_OPEN_ANGLE)
            / (THUMB_ROOT_CLOSED_ANGLE - THUMB_ROOT_OPEN_ANGLE)
        )
    )


def landmarks_to_curl_ratios(hand):
    landmarks = hand.get("lmList", [])
    if len(landmarks) < 21:
        return {name: 0.0 for name in FINGER_ORDER}

    ratios = {}
    for name, (base_id, middle_id, tip_id) in FINGER_JOINTS.items():
        if name == "thumb":
            ratios[name] = thumb_curl_ratio_from_landmarks(landmarks)
            continue
        angle = angle_degrees(
            landmarks[base_id], landmarks[middle_id], landmarks[tip_id]
        )
        ratios[name] = curl_ratio_from_angle(angle)

    thumb_root_angle = angle_degrees(landmarks[2], landmarks[5], landmarks[9])
    ratios["thumb_root"] = thumb_root_ratio_from_angle(thumb_root_angle)
    return ratios


def curl_ratios_to_sdk_positions(ratios):
    return [
        int(round(clamp(ratios.get(name, 0.0)) * SDK_POSITIONS_MAX[index]))
        for index, name in enumerate(FINGER_ORDER)
    ]


def hand_to_sdk_positions(hand):
    return curl_ratios_to_sdk_positions(landmarks_to_curl_ratios(hand))


def smooth_sdk_positions(previous, target, smoothing=DEFAULT_POSITION_SMOOTHING):
    smoothing = clamp(smoothing)
    return [
        int(
            round(
                float(previous[index]) * (1.0 - smoothing)
                + float(target[index]) * smoothing
            )
        )
        for index in range(len(target))
    ]


def should_send_positions(previous, target, min_delta=DEFAULT_MIN_SEND_DELTA):
    return any(
        abs(int(target[index]) - int(previous[index])) >= int(min_delta)
        for index in range(len(target))
    )


def limit_position_step(previous, target, max_step=DEFAULT_MAX_POSITION_STEP):
    limited = []
    for index, target_value in enumerate(target):
        previous_value = int(previous[index])
        delta = int(target_value) - previous_value
        if delta > max_step:
            limited.append(previous_value + int(max_step))
        elif delta < -max_step:
            limited.append(previous_value - int(max_step))
        else:
            limited.append(int(target_value))
    return limited


def adaptive_max_step_for_error(error):
    error = abs(int(error))
    if error <= ADAPTIVE_ERROR_SPLIT:
        return ADAPTIVE_STEP_NEAR
    return ADAPTIVE_STEP_FAR


def limit_position_step_adaptive(previous, target):
    limited = []
    for index, target_value in enumerate(target):
        previous_value = int(previous[index])
        delta = int(target_value) - previous_value
        max_step = adaptive_max_step_for_error(delta)
        if delta > max_step:
            limited.append(previous_value + max_step)
        elif delta < -max_step:
            limited.append(previous_value - max_step)
        else:
            limited.append(int(target_value))
    return limited


def limit_position_step_for_profile(previous, target, profile=MOTION_PROFILE_FIXED):
    if profile == MOTION_PROFILE_ADAPTIVE:
        return limit_position_step_adaptive(previous, target)
    return limit_position_step(previous, target, max_step=DEFAULT_MAX_POSITION_STEP)
