from collections import deque
import time

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from visual.force_image_view import ForceImageView
from visual.force_point_detail_strip import ForcePointDetailStrip
from visual.vertical_time_axis import VerticalTimeAxis


class ForceImagePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_seconds = 60.0
        self._frames = deque()
        self._follow_live = True
        self._view_end_ts = None

        self.image_view = ForceImageView()
        self.time_axis = VerticalTimeAxis()
        self.detail_strip = ForcePointDetailStrip()

        self.image_view.pointSelected.connect(self.detail_strip.update_point)
        self.time_axis.valueChanged.connect(self._on_time_axis_changed)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        top_row.addWidget(self.image_view, 1)
        top_row.addWidget(self.time_axis, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(top_row, 1)
        layout.addWidget(self.detail_strip, 0)

    def add_frame(self, frame):
        timestamp = float(frame.get("timestamp", time.time()))
        self._frames.append(frame)
        self._prune_frames(timestamp)
        if self._follow_live:
            self._view_end_ts = timestamp
        self._sync_display()

    def clear(self):
        self._frames.clear()
        self._follow_live = True
        self._view_end_ts = None
        self.time_axis.blockSignals(True)
        self.time_axis.setValue(self.time_axis.maximum())
        self.time_axis.blockSignals(False)
        self.image_view.set_force_frame(None)
        self.detail_strip.clear()

    def set_history_position(self, value, maximum):
        maximum = max(1, int(maximum))
        value = max(0, min(int(value), maximum))
        self._follow_live = value >= maximum
        latest_ts = self._latest_timestamp()
        if latest_ts is None:
            self._view_end_ts = None
            self._sync_display()
            return
        offset_ratio = 1.0 - (float(value) / float(maximum))
        offset_seconds = offset_ratio * self.history_seconds
        self._view_end_ts = latest_ts - offset_seconds
        self._sync_display()

    def is_following_live(self):
        return self._follow_live

    def _on_time_axis_changed(self, value):
        self.set_history_position(value, self.time_axis.maximum())

    def _latest_timestamp(self):
        if not self._frames:
            return None
        return float(self._frames[-1].get("timestamp", time.time()))

    def _selected_frame(self):
        if not self._frames:
            return None
        view_end_ts = self._view_end_ts
        if view_end_ts is None:
            return self._frames[-1]
        selected = None
        for frame in self._frames:
            timestamp = float(frame.get("timestamp", 0.0))
            if timestamp <= view_end_ts:
                selected = frame
            else:
                break
        return selected or self._frames[0]

    def _prune_frames(self, latest_timestamp):
        cutoff = float(latest_timestamp) - self.history_seconds
        while self._frames and float(self._frames[0].get("timestamp", 0.0)) < cutoff:
            self._frames.popleft()

    def _sync_display(self):
        selected_frame = self._selected_frame()
        self.detail_strip.clear()
        self.image_view.set_force_frame(selected_frame)
        if self._follow_live:
            self.time_axis.blockSignals(True)
            self.time_axis.setValue(self.time_axis.maximum())
            self.time_axis.blockSignals(False)
