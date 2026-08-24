from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from data.export_csv import export_jsonl_to_csv
from data.recorder import JsonlRecorder
from data.replayer import ReplayController
from visual.camera_view import CameraView
from visual.force_image_view import ForceImageView
from visual.force_timeline_panel import ForceTimelinePanel
from visual.urdf_view import UrdfView


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
ICON_PATH = ROOT / "assets" / "icon.ico"


class ShowcaseMainWindow(QMainWindow):
    def __init__(self, port=None, baudrate=115200, hand_id=2, motion_profile="fixed"):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.hand_id = hand_id
        self.motion_profile = motion_profile
        self.worker = None
        self.recorder = None
        self.sensor_status = "未连接"
        self.replayer = ReplayController(self)
        self.replayer.frame_signal.connect(self.update_frame)
        self.replayer.finished_signal.connect(lambda: self.status_label.setText("回放结束"))

        self.setWindowTitle("AP002 Showcase Demo")
        self.resize(1400, 820)
        self.setWindowIcon(QIcon(str(ICON_PATH)))

        self.camera_label = CameraView()

        self.urdf_view = UrdfView()
        self.force_image_view = ForceImageView()
        self.force_timeline_panel = ForceTimelinePanel()
        self.status_label = QLabel("待机")
        self.timeline_scrubber = QSlider(Qt.Horizontal)
        self.timeline_scrubber.setRange(0, 1000)
        self.timeline_scrubber.setValue(1000)
        self.timeline_scrubber.setSingleStep(1)
        self.timeline_scrubber.valueChanged.connect(self._scrub_timeline_history)

        self.start_button = QPushButton("开始实时演示")
        self.stop_button = QPushButton("停止")
        self.record_button = QPushButton("开始记录")
        self.replay_button = QPushButton("打开回放")
        self.export_button = QPushButton("导出CSV")
        self.clear_button = QPushButton("清空")
        self.urdf_toggle_button = QPushButton("关闭3D")
        self.urdf_toggle_button.setCheckable(True)
        self.urdf_toggle_button.setChecked(True)
        self.gesture_toggle_button = QPushButton("关闭手势识别")
        self.gesture_toggle_button.setCheckable(True)
        self.gesture_toggle_button.setChecked(True)
        self.motion_profile_label = QLabel(f"模式: {motion_profile}")
        self.motion_profile_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.status_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.status_label.setMinimumWidth(0)
        self.start_button.clicked.connect(self.start_live)
        self.stop_button.clicked.connect(self.stop_live)
        self.record_button.clicked.connect(self.toggle_recording)
        self.replay_button.clicked.connect(self.open_replay)
        self.export_button.clicked.connect(self.export_csv)
        self.clear_button.clicked.connect(self._clear_history_views)
        self.urdf_toggle_button.toggled.connect(self._toggle_urdf_display)
        self.gesture_toggle_button.toggled.connect(self._toggle_gesture_recognition)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.record_button)
        button_row.addWidget(self.replay_button)
        button_row.addWidget(self.export_button)
        button_row.addWidget(self.clear_button)
        button_row.addStretch(1)
        toggle_row = QHBoxLayout()
        toggle_row.addWidget(self.urdf_toggle_button)
        toggle_row.addWidget(self.gesture_toggle_button)
        toggle_row.addWidget(self.motion_profile_label)
        toggle_row.addStretch(1)
        right_layout.addLayout(button_row)
        right_layout.addLayout(toggle_row)
        right_layout.addWidget(self.force_timeline_panel, 1)
        scrubber_row = QHBoxLayout()
        scrubber_row.addWidget(QLabel("回看"))
        scrubber_row.addWidget(self.timeline_scrubber, 1)
        right_layout.addLayout(scrubber_row)
        right_layout.addWidget(self.status_label)

        self.left_bottom_splitter = QSplitter(Qt.Horizontal)
        self.left_bottom_splitter.addWidget(self.camera_label)
        self.left_bottom_splitter.addWidget(self.force_image_view)
        self.left_bottom_splitter.setStretchFactor(0, 1)
        self.left_bottom_splitter.setStretchFactor(1, 1)
        self.left_bottom_splitter.setSizes([330, 330])

        left_top_bottom = QSplitter(Qt.Vertical)
        left_top_bottom.addWidget(self.urdf_view)
        left_top_bottom.addWidget(self.left_bottom_splitter)
        left_top_bottom.setStretchFactor(0, 1)
        left_top_bottom.setStretchFactor(1, 1)
        left_top_bottom.setSizes([360, 360])

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.addWidget(left_top_bottom)
        self.main_splitter.addWidget(right_panel)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([700, 700])
        self.urdf_view.set_render_enabled(True)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.main_splitter)
        self.setCentralWidget(container)
        QTimer.singleShot(0, self._balance_splitter_sizes)

    def set_camera_image(self, image):
        self.camera_label.set_frame(image)

    def update_frame(self, frame):
        positions = frame.get("target_positions") or frame.get("actual_positions")
        if positions:
            self.urdf_view.update_positions(positions)
        if frame.get("force_summary"):
            self.force_image_view.update_force(frame["force_summary"])
        else:
            self.force_image_view.update_force(None)
        self.force_timeline_panel.add_frame(frame)
        if self.recorder is not None:
            self.recorder.write_frame(frame)
        status_text = frame.get("status", "运行中")
        self.status_label.setText(f"{self.sensor_status} | {status_text}")

    def start_live(self):
        if self.worker is not None and self.worker.isRunning():
            return
        from control.gesture_worker import GestureShowcaseWorker

        self._clear_history_views()
        self.worker = GestureShowcaseWorker(
            port=self.port,
            baudrate=self.baudrate,
            hand_id=self.hand_id,
            motion_profile=self.motion_profile,
            parent=self,
        )
        self.worker.set_gesture_enabled(self.gesture_toggle_button.isChecked())
        self.worker.frame_signal.connect(self.update_frame)
        self.worker.camera_signal.connect(self.set_camera_image)
        self.worker.status_signal.connect(self._update_sensor_status)
        self.worker.start()
        self.status_label.setText("正在启动实时演示")

    def stop_live(self):
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(1500)
            self.worker = None
        self.status_label.setText("实时演示已停止")

    def toggle_recording(self):
        if self.recorder is None:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            filename = datetime.now().strftime("ap002_showcase_%Y%m%d_%H%M%S.jsonl")
            self.recorder = JsonlRecorder(LOG_DIR / filename)
            self.record_button.setText("停止记录")
            self.status_label.setText(f"Recording: {filename}")
        else:
            self.recorder.close()
            self.recorder = None
            self.record_button.setText("开始记录")
            self.status_label.setText("记录已停止")

    def open_replay(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open JSONL replay", str(LOG_DIR), "JSONL Files (*.jsonl)")
        if not path:
            return
        self.stop_live()
        self._clear_history_views()
        self.replayer.load(path)
        self.replayer.start(50)
        self.status_label.setText(f"正在回放: {Path(path).name}")

    def export_csv(self):
        src, _ = QFileDialog.getOpenFileName(self, "Open JSONL to export", str(LOG_DIR), "JSONL Files (*.jsonl)")
        if not src:
            return
        dst = str(Path(src).with_suffix(".csv"))
        export_jsonl_to_csv(src, dst)
        self.status_label.setText(f"CSV 已导出: {Path(dst).name}")

    def closeEvent(self, event):
        self.stop_live()
        if self.recorder is not None:
            self.recorder.close()
            self.recorder = None
        event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._balance_splitter_sizes)

    def _toggle_urdf_display(self, checked):
        self.urdf_view.set_render_enabled(checked)
        self.urdf_toggle_button.setText("关闭3D" if checked else "打开3D")

    def _toggle_gesture_recognition(self, checked):
        if self.worker is not None:
            self.worker.set_gesture_enabled(checked)
        self.gesture_toggle_button.setText("关闭手势识别" if checked else "开启手势识别")

    def _update_sensor_status(self, text):
        self.sensor_status = text
        self.status_label.setText(text)

    def _balance_splitter_sizes(self):
        total_width = max(2, self.main_splitter.width())
        half = total_width // 2
        self.main_splitter.setSizes([half, total_width - half])

    def _scrub_timeline_history(self, value):
        self.force_timeline_panel.set_history_position(value, self.timeline_scrubber.maximum())

    def _reset_timeline_scrubber(self):
        self.timeline_scrubber.blockSignals(True)
        self.timeline_scrubber.setValue(self.timeline_scrubber.maximum())
        self.timeline_scrubber.blockSignals(False)
        self.force_timeline_panel.set_history_position(self.timeline_scrubber.value(), self.timeline_scrubber.maximum())

    def _clear_history_views(self):
        self.force_image_view.update_force(None)
        self.force_timeline_panel.clear()
        self._reset_timeline_scrubber()
