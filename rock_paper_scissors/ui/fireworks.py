from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget


class FireworksOverlay(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setVisible(False)
        self._particles: list[dict[str, float | QColor]] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

    def start(self, duration_ms: int = 2400) -> None:
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.setVisible(True)
        self._particles = self._spawn_particles()
        self._timer.start(33)
        QTimer.singleShot(duration_ms, self.stop)

    def stop(self) -> None:
        self._timer.stop()
        self._particles.clear()
        self.setVisible(False)
        self.update()

    def _spawn_particles(self) -> list[dict[str, float | QColor]]:
        width = max(self.width(), 1)
        height = max(self.height(), 1)
        center_x = width * 0.5
        center_y = height * 0.35
        colors = [
            QColor("#ff4d4d"),
            QColor("#ffd24d"),
            QColor("#4dff88"),
            QColor("#4dd2ff"),
            QColor("#ff4df2"),
        ]
        particles: list[dict[str, float | QColor]] = []
        for _ in range(100):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(2.0, 8.0)
            particles.append(
                {
                    "x": center_x,
                    "y": center_y,
                    "vx": math.cos(angle) * speed,
                    "vy": math.sin(angle) * speed - 2,
                    "life": random.uniform(35, 70),
                    "color": random.choice(colors),
                    "size": random.uniform(3, 7),
                }
            )
        return particles

    def _advance(self) -> None:
        alive: list[dict[str, float | QColor]] = []
        for particle in self._particles:
            particle["x"] = float(particle["x"]) + float(particle["vx"])
            particle["y"] = float(particle["y"]) + float(particle["vy"])
            particle["vy"] = float(particle["vy"]) + 0.12
            particle["life"] = float(particle["life"]) - 1
            if float(particle["life"]) > 0:
                alive.append(particle)
        self._particles = alive
        self.update()
        if not self._particles:
            self.stop()

    def paintEvent(self, event) -> None:
        if not self._particles:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for particle in self._particles:
            life = max(float(particle["life"]) / 70.0, 0.0)
            color = QColor(particle["color"])
            color.setAlphaF(life)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            size = float(particle["size"])
            painter.drawEllipse(QPointF(float(particle["x"]), float(particle["y"])), size, size)
