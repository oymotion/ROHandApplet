from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QWidget


FINGER_VALUE_ORDER = ("thumb", "index", "middle", "ring", "little", "palm")


class ForceValueStrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(92)

        layout = QGridLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(2)

        self._name_labels = {}
        self._value_labels = {}
        for column, name in enumerate(FINGER_VALUE_ORDER):
            name_label = QLabel(name)
            name_label.setAlignment(Qt.AlignCenter)
            value_label = QLabel("0")
            value_label.setAlignment(Qt.AlignCenter)
            value_label.setStyleSheet("font-size:18px;font-weight:600;")
            self._name_labels[name] = name_label
            self._value_labels[name] = value_label
            layout.addWidget(name_label, 0, column)
            layout.addWidget(value_label, 1, column)

    def update_summary(self, summary):
        totals = (summary or {}).get("totals", {})
        for name in FINGER_VALUE_ORDER:
            value = totals.get(name, {}).get("normal", 0.0)
            self._value_labels[name].setText(str(int(round(float(value)))))

    def clear(self):
        self.update_summary({})
