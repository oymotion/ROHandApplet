from __future__ import annotations


ROH_LIGHT_QSS = """
QWidget {
  background-color: #FAFAFA;
  color: #19232D;
  font-family: "Microsoft YaHei UI", "Segoe UI", Arial;
  font-size: 9pt;
  selection-background-color: #9FCBFF;
  selection-color: #19232D;
}

QMainWindow::separator {
  background-color: #C0C4C8;
}

QFrame#CanvasFrame,
QFrame#LegendFrame,
QFrame#StatusFrame,
QFrame#TimelineFrame,
QFrame#ValueStripFrame {
  border: 1px solid #C0C4C8;
  border-radius: 4px;
  background-color: #FAFAFA;
}

QLabel#HeaderTitle {
  color: #19232D;
  font-weight: 600;
}

QLabel#HeaderHint,
QLabel#StatusText {
  color: #60798B;
}

QLabel#ForceValueLabel {
  background-color: #FFFFFF;
  border: 1px solid #C0C4C8;
  border-radius: 4px;
  padding: 4px 8px;
  color: #19232D;
}

QPushButton {
  background-color: #C0C4C8;
  color: #19232D;
  border: 1px solid #C0C4C8;
  border-radius: 4px;
  padding: 4px 10px;
}

QPushButton:hover {
  border: 1px solid #73C7FF;
}

QPushButton:pressed {
  background-color: #ACB1B6;
}

QPushButton:disabled {
  color: #9DA9B5;
  background-color: #FAFAFA;
  border: 1px solid #C0C4C8;
}

QStatusBar {
  border-top: 1px solid #C0C4C8;
  background-color: #C0C4C8;
  color: #19232D;
}

QSplitter::handle {
  background-color: #C0C4C8;
}
"""

ROH_DARK_QSS = ROH_LIGHT_QSS


def build_window_title(title: str) -> str:
    return f"{title} - AP002"
