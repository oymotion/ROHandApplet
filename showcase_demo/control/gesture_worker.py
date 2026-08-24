import os
import time
from pathlib import Path

import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from control.force_reader import ForceReader
from control.gesture_mapper import (
    DEFAULT_MIN_SEND_DELTA,
    DEFAULT_POSITION_SMOOTHING,
    DEFAULT_SEND_INTERVAL_MS,
    MOTION_PROFILE_FIXED,
    hand_to_sdk_positions,
    limit_position_step_for_profile,
    should_send_positions,
    smooth_sdk_positions,
)
from control.joint_reader import (
    DEFAULT_FINGER_PID_P,
    read_actual_positions,
    write_position_pid_p,
    write_speed_control_params,
    write_target_positions,
    write_uniform_speed,
)
from control.rs485_client import Rs485Client, Rs485Config
from control.sensor_capability import read_sensor_capability
from control.vendor_paths import install_vendor_paths

ROOT = Path(__file__).resolve().parents[1]
MPL_CACHE_DIR = ROOT / "cache" / "matplotlib"
MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

install_vendor_paths()

from HandTrackingModule import HandDetector  # noqa: E402


LOOP_MS = 2


class GestureShowcaseWorker(QThread):
    frame_signal = Signal(dict)
    camera_signal = Signal(QImage)
    status_signal = Signal(str)

    def __init__(self, port=None, baudrate=115200, hand_id=2, motion_profile=MOTION_PROFILE_FIXED, parent=None):
        super().__init__(parent)
        self.port = port
        self.baudrate = baudrate
        self.hand_id = hand_id
        self.motion_profile = motion_profile
        self._stopped = False
        self._gesture_enabled = True
        self._prev_gesture = [0, 0, 0, 0, 0, 0]
        self._smoothed_gesture = [0, 0, 0, 0, 0, 0]
        self._last_send_time = 0.0

    def stop(self):
        self._stopped = True

    def set_gesture_enabled(self, enabled):
        self._gesture_enabled = bool(enabled)

    def run(self):
        rs485 = None
        video = None
        try:
            rs485 = Rs485Client(Rs485Config(port=self.port, baudrate=self.baudrate, hand_id=self.hand_id)).connect()
            self.status_signal.emit(f"RS485已连接: {rs485.port}")
            capability = read_sensor_capability(rs485)
            force_reader = ForceReader(rs485, capability.sub_model)
            force_reader.reset_force()
            write_position_pid_p(rs485, p_value=DEFAULT_FINGER_PID_P)
            write_speed_control_params(rs485)
            write_uniform_speed(rs485)

            video = self._open_camera()
            camera_status = "摄像头已连接" if video else "未找到摄像头"
            detector = HandDetector(maxHands=1, detectionCon=0.8) if video else None
            self.status_signal.emit(
                f"传感器 sub_model={capability.sub_model}, sensor_type={capability.sensor_type}, direction={capability.supports_direction}"
            )

            while not self._stopped:
                raw_positions = self._read_gesture(video, detector)
                if self._gesture_enabled:
                    target_positions = smooth_sdk_positions(
                        self._smoothed_gesture,
                        raw_positions,
                        smoothing=DEFAULT_POSITION_SMOOTHING,
                    )
                    target_positions = limit_position_step_for_profile(
                        self._prev_gesture,
                        target_positions,
                        profile=self.motion_profile,
                    )
                    now = time.monotonic()
                    send_interval_elapsed = now - self._last_send_time >= DEFAULT_SEND_INTERVAL_MS / 1000.0
                    if send_interval_elapsed and should_send_positions(
                        self._prev_gesture, target_positions, min_delta=DEFAULT_MIN_SEND_DELTA
                    ):
                        write_target_positions(rs485, target_positions)
                        self._prev_gesture = list(target_positions)
                        self._last_send_time = now
                    self._smoothed_gesture = list(target_positions)
                else:
                    target_positions = list(self._prev_gesture)
                    self._smoothed_gesture = list(target_positions)

                actual_positions = self._safe_read_actual(rs485)
                force_summary = self._safe_read_force(force_reader)
                mode_suffix = "手势识别关闭" if not self._gesture_enabled else "实时控制运行中"
                frame = {
                    "timestamp": time.time(),
                    "target_positions": list(target_positions),
                    "actual_positions": actual_positions,
                    "force_summary": force_summary,
                    "status": f"{camera_status} | {mode_suffix}",
                }
                self.frame_signal.emit(frame)
                self.msleep(LOOP_MS)
        except Exception as exc:
            self.status_signal.emit(f"演示线程已停止: {exc}")
        finally:
            if video is not None:
                video.release()
            if rs485 is not None:
                rs485.close()

    def _open_camera(self):
        for index in range(4):
            video = cv2.VideoCapture(index)
            if video.isOpened():
                ok, _ = video.read()
                if ok:
                    self.status_signal.emit(f"摄像头已打开: index={index}")
                    return video
            video.release()
        self.status_signal.emit("未找到摄像头，实体手控制仍会保持打开")
        return None

    def _read_gesture(self, video, detector):
        if video is None:
            return list(self._prev_gesture)
        ok, img = video.read()
        if not ok:
            return list(self._prev_gesture)
        img = cv2.flip(img, 1)
        if self._gesture_enabled and detector is not None:
            hands, img = detector.findHands(img, draw=True)
            gesture = hand_to_sdk_positions(hands[0]) if hands else [0, 0, 0, 0, 0, 0]
        else:
            gesture = list(self._prev_gesture)
        self._emit_camera(img)
        return gesture

    def _emit_camera(self, img):
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        height, width, channel = rgb.shape
        image = QImage(rgb.data, width, height, channel * width, QImage.Format_RGB888).copy()
        self.camera_signal.emit(image)

    def _safe_read_actual(self, rs485):
        try:
            return read_actual_positions(rs485)
        except Exception:
            return []

    def _safe_read_force(self, force_reader):
        try:
            return force_reader.read_summary()
        except Exception:
            return {}
