from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget


class CameraView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._latest_image = None
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_frame(self, image):
        self._latest_image = image.copy()
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("white"))
        painter.setPen(QColor(55, 65, 70))
        if self._latest_image is None:
            painter.drawText(self.rect(), Qt.AlignCenter, "等待摄像头画面")
            return

        scaled = self._latest_image.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawImage(x, y, scaled)
