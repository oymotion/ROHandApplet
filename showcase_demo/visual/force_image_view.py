from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from control.force_vectors import FORCE_NAMES
from visual.force_display_mapping import FORCE_ZONE_MARKERS, PALM_DOT_MARKERS, finger_zone_names, force_zone_pressure
from visual.force_colors import force_color_for_pressure, pressure_level


ASSET_PATH = Path(__file__).resolve().parents[1] / "assets" / "force_left.png"
FORCE_IMAGE_MAX_PRESSURE = 3000.0


class ForceImageView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(260)
        self._pixmap = QPixmap(str(ASSET_PATH))
        self._summary = None

    def update_force(self, summary):
        self._summary = summary
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("white"))
        if self._pixmap.isNull():
            painter.drawText(self.rect(), Qt.AlignCenter, "force_left.png missing")
            return

        scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x0 = (self.width() - scaled.width()) / 2
        y0 = (self.height() - scaled.height()) / 2
        painter.drawPixmap(int(x0), int(y0), scaled)

        if not self._summary:
            return
        sx = scaled.width() / self._pixmap.width()
        sy = scaled.height() / self._pixmap.height()
        totals = self._summary.get("totals", {})
        for name in FORCE_NAMES:
            if name == "palm":
                self._draw_palm_points(painter, x0, y0, sx, sy)
            else:
                self._draw_force_zones(painter, x0, y0, sx, sy, name)
            markers = FORCE_ZONE_MARKERS.get(name, {})
            if not markers:
                continue
            total = totals.get(name, {}).get("normal", 0.0)
            cx = sum(point[0] for point in markers.values()) / len(markers)
            cy = sum(point[1] for point in markers.values()) / len(markers)
            label_color = force_color_for_pressure(name, total, max_pressure=FORCE_IMAGE_MAX_PRESSURE * 4.0)
            painter.setPen(QPen(label_color, 2))
            painter.drawText(int(x0 + cx * sx + 14), int(y0 + cy * sy), f"{name}:{int(total)}")

    def _draw_palm_points(self, painter, x0, y0, sx, sy):
        points = self._summary.get("fingers", {}).get("palm", []) if self._summary else []
        values_by_index = {int(point.get("point_index", -1)): float(point.get("normal", 0.0)) for point in points}
        for point_index, (cx, cy) in enumerate(PALM_DOT_MARKERS):
            normal = values_by_index.get(point_index, 0.0)
            level = pressure_level(normal, FORCE_IMAGE_MAX_PRESSURE)
            radius = 2.2 + level * 5.8
            color = force_color_for_pressure("palm", normal, max_pressure=FORCE_IMAGE_MAX_PRESSURE)
            painter.setBrush(color)
            painter.setPen(QPen(color.darker(135), 1))
            painter.drawEllipse(x0 + cx * sx, y0 + cy * sy, radius, radius)

    def _draw_force_zones(self, painter, x0, y0, sx, sy, finger_name):
        markers = FORCE_ZONE_MARKERS.get(finger_name, {})
        for zone_name in finger_zone_names(finger_name):
            if zone_name not in markers:
                continue
            normal = force_zone_pressure(self._summary, finger_name, zone_name)
            level = pressure_level(normal, FORCE_IMAGE_MAX_PRESSURE)
            radius = 3.0 + level * 9.0
            color = force_color_for_pressure(finger_name, normal, max_pressure=FORCE_IMAGE_MAX_PRESSURE)
            cx, cy = markers[zone_name]
            painter.setBrush(color)
            painter.setPen(QPen(color.darker(135), 1))
            painter.drawEllipse(x0 + cx * sx, y0 + cy * sy, radius, radius)
