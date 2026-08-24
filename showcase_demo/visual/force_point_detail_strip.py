from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QWidget


class ForcePointDetailStrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(72)

        self._value_labels = {}
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(4)

        fields = ("finger", "point", "normal", "tangential", "direction")
        for column, field in enumerate(fields):
            title = QLabel(field)
            title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            value = QLabel("-")
            value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._value_labels[field] = value
            layout.addWidget(title, 0, column)
            layout.addWidget(value, 1, column)

    def update_point(self, payload):
        payload = payload or {}
        self._value_labels["finger"].setText(str(payload.get("finger", "-")))
        point_index = payload.get("point_index", "-")
        zone = payload.get("zone", "")
        if zone:
            self._value_labels["point"].setText(f"{zone}:{point_index}")
        else:
            self._value_labels["point"].setText(str(point_index))
        self._value_labels["normal"].setText(self._format_number(payload.get("normal")))
        self._value_labels["tangential"].setText(self._format_number(payload.get("tangential")))
        self._value_labels["direction"].setText(self._format_number(payload.get("direction_display_deg")))

    def clear(self):
        for label in self._value_labels.values():
            label.setText("-")

    def _format_number(self, value):
        if value is None:
            return "-"
        number = float(value)
        if abs(number - round(number)) < 1e-6:
            return str(int(round(number)))
        return f"{number:.1f}"
