FINGER_PAD_ROWS = ("index", "middle", "ring")

FORCE_ZONE_MARKERS = {
    "thumb": {"tip": (310, 210)},
    "index": {"tip": (303, 65), "pad": (295, 99)},
    "middle": {"tip": (354, 45), "pad": (349, 79)},
    "ring": {"tip": (408, 65), "pad": (406, 99)},
    "little": {"tip": (452, 114)},
    "palm": {"palm": (397, 315)},
}

PALM_DOT_MARKERS = (
    (350, 295), (350, 305), (350, 315),
    (360, 295), (360, 305), (360, 315),
    (370, 295), (370, 305), (370, 315), (370, 325),
    (380, 295), (380, 305), (380, 315), (380, 325), (380, 335),
    (390, 295), (390, 305), (390, 315), (390, 325), (390, 335),
    (400, 295), (400, 305), (400, 315), (400, 325), (400, 335),
    (410, 295), (410, 305), (410, 315), (410, 325), (410, 335),
    (420, 295), (420, 305), (420, 315), (420, 325), (420, 335),
    (430, 295), (430, 305), (430, 315), (430, 325), (430, 335),
    (440, 295), (440, 305), (440, 315), (440, 325), (440, 335),
    (450, 295), (450, 305), (450, 315), (450, 325), (450, 335),
)


def finger_zone_names(finger_name):
    if finger_name in FINGER_PAD_ROWS:
        return ("tip", "pad")
    if finger_name == "palm":
        return ("palm",)
    return ("tip",)


def _point_normal(points, point_index):
    for point in points:
        if int(point.get("point_index", -1)) == int(point_index):
            return float(point.get("normal", 0.0))
    return 0.0


def _max_normal(points, excluded_indices=()):
    excluded = {int(index) for index in excluded_indices}
    values = [
        float(point.get("normal", 0.0))
        for point in points
        if int(point.get("point_index", -1)) not in excluded
    ]
    return max(values, default=0.0)


def force_zone_pressure(summary, finger_name, zone_name):
    fingers = summary.get("fingers", {}) if summary else {}
    totals = summary.get("totals", {}) if summary else {}
    points = fingers.get(finger_name, [])
    sensor_type = int(summary.get("sensor_type", 0)) if summary else 0

    if finger_name == "palm" or zone_name == "palm":
        return float(totals.get("palm", {}).get("normal", 0.0))

    if zone_name == "tip":
        point0 = _point_normal(points, 0)
        if sensor_type == 1 or point0 > 0.0:
            return point0
        return _max_normal(points)

    if zone_name == "pad" and finger_name in FINGER_PAD_ROWS:
        point1 = _point_normal(points, 1)
        if sensor_type == 1 or point1 > 0.0:
            return point1
        return _max_normal(points, excluded_indices=(0,))

    return 0.0
