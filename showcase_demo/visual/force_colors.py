from PySide6.QtGui import QColor


FINGER_BASE_COLORS = {
    "thumb": QColor(220, 72, 72),
    "index": QColor(36, 150, 135),
    "middle": QColor(50, 115, 220),
    "ring": QColor(230, 145, 32),
    "little": QColor(135, 86, 210),
    "palm": QColor(85, 105, 120),
}


def clamp01(value):
    return max(0.0, min(1.0, float(value)))


def pressure_level(value, max_pressure, gamma=0.55):
    if max_pressure <= 0:
        return 0.0
    return clamp01(float(value) / float(max_pressure)) ** gamma


def force_color_for_pressure(
    finger_name,
    pressure,
    max_pressure=12000.0,
    min_value=95,
    max_value=245,
    min_alpha=70,
    max_alpha=235,
):
    base = FINGER_BASE_COLORS.get(finger_name, QColor(80, 90, 100))
    level = pressure_level(pressure, max_pressure)
    hue, saturation, _value, _alpha = base.getHsv()
    value = int(min_value + level * (max_value - min_value))
    alpha = int(min_alpha + level * (max_alpha - min_alpha))
    return QColor.fromHsv(hue, max(90, saturation), value, alpha)
