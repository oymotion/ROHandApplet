import argparse
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QSplitter, QVBoxLayout, QWidget

from hand_scene import HandScene
from force_timeline import ForceTimelinePanel, set_source_gesture_enabled
from model import PARTS, PressureFrame
from sources import DemoSource, UdpJsonSource, parse_host_port
from style import ROH_LIGHT_QSS


ICON_PATH = Path(__file__).resolve().parent / "assets" / "icon.ico"


def parse_args():
    parser = argparse.ArgumentParser(description="AP002 left-hand force visualizer.")
    parser.add_argument("--demo", action="store_true", help="Use built-in animated demo source.")
    parser.add_argument("--udp", default=None, help="Listen for JSON frames on host:port.")
    parser.add_argument(
        "--display-baseline-seconds",
        type=float,
        default=2.0,
        help="Seconds to collect unpressed display noise after the first real frame. Use 0 to disable.",
    )
    parser.add_argument(
        "--display-deadband",
        type=float,
        default=40.0,
        help="Extra display-only pressure deadband after baseline subtraction.",
    )
    return parser.parse_args()


class MainWindow(QMainWindow):
    def __init__(self, source, baseline_seconds: float, deadband: float):
        super().__init__()
        self.source = source
        self.baseline_seconds = max(0.0, baseline_seconds)
        self.deadband = max(0.0, deadband)
        self.baseline_started_at = None
        self.baseline_max = {name: 0.0 for name in PARTS}
        self.baseline_sample_count = 0
        self.baseline_ready = self.baseline_seconds <= 0.0
        self.gesture_enabled = True
        self.setWindowTitle("Force Visualizer")
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QFrame()
        header.setObjectName("StatusFrame")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(10)

        title = QLabel("AP002 Force Visualizer")
        title.setObjectName("HeaderTitle")
        hint = QLabel("ROHandSetting-style force display")
        hint.setObjectName("HeaderHint")
        header_layout.addWidget(title)
        header_layout.addWidget(hint, 1)

        self.gesture_button = QPushButton("关闭手势识别")
        self.gesture_button.setCheckable(True)
        self.gesture_button.setChecked(True)
        self.gesture_button.toggled.connect(self._on_gesture_toggled)
        header_layout.addWidget(self.gesture_button)
        layout.addWidget(header)

        body = QFrame()
        body.setObjectName("CanvasFrame")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(8, 8, 8, 8)
        body_layout.setSpacing(8)

        self.scene = HandScene("AP002 Left Force View")
        self.timeline = ForceTimelinePanel()
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setObjectName("MainSplitter")
        self.main_splitter.setHandleWidth(8)
        self.main_splitter.addWidget(self.scene)
        self.main_splitter.addWidget(self.timeline)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([760, 760])
        body_layout.addWidget(self.main_splitter, 1)
        layout.addWidget(body, 1)

        status_frame = QFrame()
        status_frame.setObjectName("StatusFrame")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 6, 10, 6)
        status_layout.setSpacing(8)

        self.status = QLabel("Waiting for pressure frames...")
        self.status.setObjectName("StatusText")
        status_layout.addWidget(self.status, 1)
        layout.addWidget(status_frame)

        self.setCentralWidget(root)

        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

        self._on_gesture_toggled(True)

    def _has_real_frame(self, frame: PressureFrame) -> bool:
        return frame.timestamp > 0.0 or any(frame.scores.get(name, 0.0) > 0.0 for name in PARTS)

    def _update_display_baseline(self, frame: PressureFrame) -> bool:
        if self.baseline_ready:
            return True
        if not self._has_real_frame(frame):
            self.status.setText("Waiting for first pressure frame...")
            return False

        now = time.monotonic()
        if self.baseline_started_at is None:
            self.baseline_started_at = now

        for name in PARTS:
            self.baseline_max[name] = max(self.baseline_max[name], frame.scores.get(name, 0.0))
        self.baseline_sample_count += 1

        elapsed = now - self.baseline_started_at
        remaining = max(0.0, self.baseline_seconds - elapsed)
        self.status.setText(
            "Collecting display baseline, keep hand unpressed... "
            f"{remaining:.1f}s  samples={self.baseline_sample_count}"
        )

        if elapsed >= self.baseline_seconds:
            self.baseline_ready = True
            return True
        return False

    def _adjust_frame_for_display(self, frame: PressureFrame) -> PressureFrame:
        adjusted = {}
        for name in PARTS:
            raw = frame.scores.get(name, 0.0)
            adjusted[name] = max(0.0, raw - self.baseline_max[name] - self.deadband)
        return PressureFrame(timestamp=frame.timestamp, scores=adjusted)

    def _on_gesture_toggled(self, enabled: bool):
        self.gesture_enabled = bool(enabled)
        self.gesture_button.setText("关闭手势识别" if enabled else "开启手势识别")
        set_source_gesture_enabled(self.source, enabled)
        if hasattr(self, "status"):
            state = "开启" if enabled else "关闭"
            self.status.setText(f"手势识别: {state}，压力显示持续运行")

    def tick(self):
        frame = self.source.read()
        if not isinstance(frame, PressureFrame):
            return

        if not self._update_display_baseline(frame):
            self.scene.set_frame(PressureFrame(timestamp=frame.timestamp))
            return

        display_frame = self._adjust_frame_for_display(frame)
        self.scene.set_frame(display_frame)
        self.timeline.set_frame(display_frame)
        self.status.setText(
            f"display t={display_frame.timestamp:.3f}  thumb={display_frame.scores['thumb']:.0f}  "
            f"index={display_frame.scores['index']:.0f}  middle={display_frame.scores['middle']:.0f}  "
            f"ring={display_frame.scores['ring']:.0f}  little={display_frame.scores['little']:.0f}  "
            f"palm={display_frame.scores['palm']:.0f}  "
            f"baseline={self.baseline_sample_count} samples  deadband={self.deadband:.0f}"
        )


def build_source(args):
    if args.udp:
        host, port = parse_host_port(args.udp)
        return UdpJsonSource(host, port)
    return DemoSource()


def main():
    args = parse_args()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 9))
    app.setStyleSheet(ROH_LIGHT_QSS)
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))
    window = MainWindow(
        build_source(args),
        baseline_seconds=args.display_baseline_seconds,
        deadband=args.display_deadband,
    )
    window.resize(1180, 820)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
