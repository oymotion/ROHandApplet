from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class ForceLegend(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(110)
        self.setMinimumHeight(560)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(QFont("Microsoft YaHei UI", 8))
        painter.fillRect(self.rect(), QColor("#FAFAFA"))

        margin = 14
        top_gap = 32
        bottom_gap = 56
        bar_w = 18
        bar_h = max(1, self.height() - top_gap - bottom_gap)
        bar_x = self.width() - margin - bar_w - 34
        bar_y = top_gap

        painter.setPen(QPen(QColor("#C0C4C8"), 1))
        painter.drawRoundedRect(
            QRectF(bar_x - 6, bar_y - 8, bar_w + 12, bar_h + 16), 4, 4
        )

        for y in range(bar_h):
            hue = int((1.0 - y / max(1, bar_h - 1)) * 180)
            color = QColor()
            color.setHsv(hue, 255, 255)
            painter.setPen(QPen(color, bar_w))
            painter.drawLine(
                bar_x + bar_w // 2, bar_y + y, bar_x + bar_w // 2, bar_y + y
            )

        painter.setPen(QPen(QColor("#19232D"), 1))
        tick_count = 9
        for idx in range(tick_count + 1):
            t = idx / tick_count
            y = bar_y + int((1.0 - t) * bar_h)
            painter.setPen(QPen(QColor("#19232D"), 1))
            painter.drawLine(bar_x + bar_w + 4, y, bar_x + bar_w + 10, y)
            value = int(t * 25000)
            painter.drawText(bar_x + bar_w + 14, y + 4, f"{value}")

        painter.setPen(QPen(QColor("#19232D"), 1))
        painter.drawText(bar_x - 2, bar_y - 12, "Force")
        unit_rect = QRectF(bar_x - 2, bar_y + bar_h + 20, bar_w + 60, 20)
        painter.drawText(unit_rect, Qt.AlignLeft | Qt.AlignVCenter, "mN")
