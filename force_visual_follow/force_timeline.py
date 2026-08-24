from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List, Sequence

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget

from model import PARTS, PressureFrame


PART_COLORS = {
    "thumb": QColor("#8C3D3D"),
    "index": QColor("#2A7F62"),
    "middle": QColor("#3765A8"),
    "ring": QColor("#A26A2B"),
    "little": QColor("#6550A4"),
    "palm": QColor("#4C4C4C"),
}

PART_TITLES = {
    "thumb": "thumb",
    "index": "index",
    "middle": "middle",
    "ring": "ring",
    "little": "little",
    "palm": "palm",
}


@dataclass(frozen=True)
class ForceSample:
    timestamp: float
    value: float


class ForceTimelineModel:
    def __init__(self, history_limit: int = 240):
        self.history_limit = max(1, history_limit)
        self._series: Dict[str, Deque[ForceSample]] = {
            name: deque(maxlen=self.history_limit) for name in PARTS
        }

    def append_frame(self, frame: PressureFrame):
        for name in PARTS:
            self._series[name].append(
                ForceSample(timestamp=frame.timestamp, value=float(frame.scores.get(name, 0.0)))
            )

    def series(self, name: str) -> Sequence[ForceSample]:
        return tuple(self._series[name])

    def latest_values(self) -> Dict[str, float]:
        latest = {}
        for name in PARTS:
            latest[name] = self._series[name][-1].value if self._series[name] else 0.0
        return latest

    def history_length(self) -> int:
        return max((len(series) for series in self._series.values()), default=0)

    def max_value(self) -> float:
        peak = 0.0
        for name in PARTS:
            for sample in self._series[name]:
                peak = max(peak, sample.value)
        return peak


def set_source_gesture_enabled(source, enabled: bool):
    hook = getattr(source, "set_gesture_enabled", None)
    if callable(hook):
        hook(bool(enabled))


class ForceCurvePlot(QWidget):
    def __init__(self, model: ForceTimelineModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setMinimumHeight(220)
        self.setObjectName("TimelinePlot")

    def set_frame(self, frame: PressureFrame):
        self.model.append_frame(frame)
        self.update()

    def _plot_rect(self) -> QRectF:
        return QRectF(58, 28, max(1.0, self.width() - 82), max(1.0, self.height() - 58))

    def _series_points(self, series: Sequence[ForceSample], rect: QRectF, peak: float) -> List[QPointF]:
        if not series:
            return []
        if len(series) == 1:
            sample = series[0]
            y = rect.bottom() - (sample.value / peak) * rect.height()
            return [QPointF(rect.left(), y)]

        span = max(1, len(series) - 1)
        points: List[QPointF] = []
        for idx, sample in enumerate(series):
            x = rect.left() + (idx / span) * rect.width()
            y = rect.bottom() - (sample.value / peak) * rect.height()
            points.append(QPointF(x, y))
        return points

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FAFAFA"))

        painter.setPen(QPen(QColor("#19232D"), 1))
        painter.setFont(QFont("Microsoft YaHei UI", 9))
        painter.drawText(12, 18, "力量-时间轴")

        rect = self._plot_rect()
        painter.setPen(QPen(QColor("#C0C4C8"), 1))
        painter.drawRect(rect)

        peak = max(100.0, self.model.max_value() * 1.12)
        painter.setPen(QPen(QColor("#E2E6EA"), 1))
        for step in range(1, 5):
            y = rect.top() + (step / 5.0) * rect.height()
            painter.drawLine(rect.left(), y, rect.right(), y)
        for step in range(1, 7):
            x = rect.left() + (step / 7.0) * rect.width()
            painter.drawLine(x, rect.top(), x, rect.bottom())

        painter.setFont(QFont("Microsoft YaHei UI", 8))
        painter.setPen(QPen(QColor("#60798B"), 1))
        painter.drawText(10, rect.top() + 4, f"{int(peak):d}")
        painter.drawText(10, rect.bottom(), "0")

        for name in PARTS:
            series = self.model.series(name)
            if not series:
                continue

            points = self._series_points(series, rect, peak)
            if len(points) < 2:
                continue

            color = QColor(PART_COLORS[name])
            color.setAlpha(210)
            painter.setPen(QPen(color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            painter.drawPath(path)

            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(points[-1], 2.6, 2.6)

            label = PART_TITLES[name]
            painter.setPen(QPen(color, 1))
            painter.drawText(rect.right() - 62, rect.top() + 16 + 16 * list(PARTS).index(name), label)


class ForceValueStrip(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ValueStripFrame")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self._labels: Dict[str, QLabel] = {}
        for name in PARTS:
            label = QLabel(f"{PART_TITLES[name]}: 0")
            label.setAlignment(Qt.AlignCenter)
            label.setObjectName("ForceValueLabel")
            label.setMinimumHeight(30)
            layout.addWidget(label, 1)
            self._labels[name] = label

    def set_frame(self, frame: PressureFrame):
        for name in PARTS:
            self._labels[name].setText(f"{PART_TITLES[name]}: {frame.scores.get(name, 0.0):.0f}")


class ForceTimelinePanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TimelineFrame")
        self.model = ForceTimelineModel()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setObjectName("TimelineSplitter")
        self.splitter.setHandleWidth(8)

        self.plot = ForceCurvePlot(self.model)
        self.values = ForceValueStrip()
        self.splitter.addWidget(self.plot)
        self.splitter.addWidget(self.values)
        self.splitter.setSizes([520, 90])
        layout.addWidget(self.splitter)

    def set_frame(self, frame: PressureFrame):
        self.plot.set_frame(frame)
        self.values.set_frame(frame)
