from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QSlider


class VerticalTimeAxis(QSlider):
    def __init__(self, parent=None):
        super().__init__(Qt.Vertical, parent)
        self.setRange(0, 1000)
        self.setValue(1000)
        self.setSingleStep(1)
        self.setPageStep(25)
        self.setTickPosition(QSlider.TicksRight)
        self.setTickInterval(100)
        self.setInvertedAppearance(True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setFixedWidth(28)
