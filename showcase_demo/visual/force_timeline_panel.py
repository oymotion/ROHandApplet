from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from visual.force_value_strip import ForceValueStrip
from visual.force_vector_timeline import ForceVectorTimeline
from visual.vertical_time_axis import VerticalTimeAxis


class ForceTimelinePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.timeline = ForceVectorTimeline()
        self.time_axis = VerticalTimeAxis()
        self.detail_strip = ForceValueStrip()

        self.timeline.sampleSelected.connect(self._on_sample_selected)
        self.time_axis.valueChanged.connect(self._on_axis_changed)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        top_row.addWidget(self.timeline, 1)
        top_row.addWidget(self.time_axis, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(top_row, 1)
        layout.addWidget(self.detail_strip, 0)

    def add_frame(self, frame):
        self.timeline.add_frame(frame)
        selected = self.timeline.selected_frame()
        if selected and selected.get("force_summary"):
            self.detail_strip.update_summary(selected["force_summary"])
        else:
            self.detail_strip.clear()

    def clear(self):
        self.timeline.clear()
        self.detail_strip.clear()
        self.time_axis.blockSignals(True)
        self.time_axis.setValue(self.time_axis.maximum())
        self.time_axis.blockSignals(False)

    def set_history_position(self, value, maximum):
        self.time_axis.blockSignals(True)
        self.time_axis.setValue(value)
        self.time_axis.blockSignals(False)
        self.timeline.set_history_position(value, maximum)
        selected = self.timeline.selected_frame()
        if selected and selected.get("force_summary"):
            self.detail_strip.update_summary(selected["force_summary"])
        else:
            self.detail_strip.clear()

    def is_following_live(self):
        return self.timeline.is_following_live()

    def _on_axis_changed(self, value):
        self.timeline.set_history_position(value, self.time_axis.maximum())
        selected = self.timeline.selected_frame()
        if selected and selected.get("force_summary"):
            self.detail_strip.update_summary(selected["force_summary"])
        else:
            self.detail_strip.clear()

    def _on_sample_selected(self, frame):
        if frame and frame.get("force_summary"):
            self.detail_strip.update_summary(frame["force_summary"])
        else:
            self.detail_strip.clear()
