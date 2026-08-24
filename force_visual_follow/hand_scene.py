from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from model import PARTS, PressureFrame


IMAGE_SIZE = 520.0
ASSET_PATH = Path(__file__).resolve().parent / "assets" / "force_left.png"

# Points are in the 520x520 asset coordinate system.
FORCE_MARKERS = {
    "little": {"point": (452, 114), "label": "little"},
    "ring": {"point": (408, 65), "label": "ring"},
    "middle": {"point": (354, 45), "label": "middle"},
    "index": {"point": (303, 65), "label": "index"},
    "thumb": {"point": (310, 210), "label": "thumb"},
    "palm": {"point": (397, 315), "label": "palm"},
}


def pressure_color(value: float) -> QColor:
    value = max(0.0, min(1.0, value))
    hue = int((1.0 - value) * 180)
    color = QColor()
    color.setHsv(hue, 255, 255)
    return color


class HandScene(QWidget):
    def __init__(self, label: str = "AP002 Left Force View", parent=None):
        super().__init__(parent)
        self.label = label
        self.frame = PressureFrame()
        self.pixmap = QPixmap(str(ASSET_PATH))
        self.setMinimumSize(760, 680)
        self.setObjectName("CanvasFrame")

    def set_frame(self, frame: PressureFrame):
        self.frame = frame
        self.update()

    def _image_rect(self) -> QRectF:
        margin = 18.0
        available_w = max(1.0, self.width() - margin * 2)
        available_h = max(1.0, self.height() - margin * 2)
        side = min(available_w, available_h)
        x = (self.width() - side) / 2
        y = (self.height() - side) / 2
        return QRectF(x, y, side, side)

    def _to_widget_point(
        self, rect: QRectF, image_point: tuple[float, float]
    ) -> QPointF:
        return QPointF(
            rect.left() + image_point[0] / IMAGE_SIZE * rect.width(),
            rect.top() + image_point[1] / IMAGE_SIZE * rect.height(),
        )

    def _draw_pressure_circle(
        self,
        painter: QPainter,
        start: QPointF,
        normalized_value: float,
    ):
        value = max(0.0, min(1.0, normalized_value))
        color = pressure_color(value)
        outer = max(4.0, 4.0 + 9.0 * value)
        inner = max(1.8, outer * 0.45)
        stroke = max(1, round(1.1 + 1.6 * value))
        painter.setPen(QPen(QColor(25, 35, 45, 120), stroke, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(color)
        painter.drawEllipse(start, outer, outer)
        if value > 0.05:
            glow = QColor(color)
            glow.setAlpha(70)
            painter.setPen(Qt.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(start, outer * 1.4, outer * 1.4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 90 if value > 0.3 else 120))
        painter.drawEllipse(start, inner, inner)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FAFAFA"))

        image_rect = self._image_rect()
        if self.pixmap.isNull():
            painter.setPen(QPen(QColor("#1A72BB"), 2))
            painter.drawText(
                self.rect(), Qt.AlignCenter, f"Image not found:\n{ASSET_PATH}"
            )
            return

        painter.drawPixmap(image_rect, self.pixmap, QRectF(self.pixmap.rect()))

        scale_px = image_rect.width() / IMAGE_SIZE
        normalized = self.frame.normalized(900.0)

        painter.setFont(QFont("Microsoft YaHei UI", max(8, round(9 * scale_px))))
        for name in PARTS:
            marker = FORCE_MARKERS[name]
            score = self.frame.scores.get(name, 0.0)
            value = normalized.get(name, 0.0)
            self._current_part = name
            start = self._to_widget_point(image_rect, marker["point"])
            self._draw_pressure_circle(painter, start, value)

            color = pressure_color(value)
            label_pos = QPointF(start.x() + 10 * scale_px, start.y() - 8 * scale_px)
            text = f"{score:.0f}"
            metrics = painter.fontMetrics()
            text_rect = QRectF(
                label_pos.x() - 4,
                label_pos.y() - metrics.height() + 2,
                metrics.horizontalAdvance(text) + 8,
                metrics.height() + 4,
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(250, 250, 250, 230))
            painter.drawRoundedRect(text_rect, 4, 4)
            painter.setPen(QPen(color, 1))
            painter.drawText(label_pos, text)

        painter.setPen(QPen(QColor("#C0C4C8"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(image_rect.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
