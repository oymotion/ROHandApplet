import math
import os
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSize, QEvent, QPoint
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from control.joint_mapper import sdk_positions_to_urdf_commands


ROOT = Path(__file__).resolve().parents[1]
URDF_DIR = ROOT / "assets" / "urdf"
URDF_PATH = URDF_DIR / "rohand_left.urdf"
RESOLVED_URDF_PATH = URDF_DIR / "rohand_left_pybullet.urdf"
ASCII_URDF_CACHE_DIRNAME = "ROHandShowcaseCache"
RENDER_TIMER_MS = 50
RENDER_SCALE = 0.70
MIN_RENDER_WIDTH = 260
MIN_RENDER_HEIGHT = 190
WHEEL_PAN_STEP = 0.008
CTRL_WHEEL_ZOOM_STEP = 0.020
URDF_RENDER_DEFAULT_ENABLED = True


class UrdfView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._label = _RenderLabel("URDF view initializing")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setMinimumHeight(260)
        self._label.setStyleSheet(
            "background:#ffffff;border:1px solid #cfd8dc;color:#37474f;"
        )
        self._label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self._pybullet = None
        self._body_id = None
        self._joint_name_to_id = {}
        self._positions = [0, 0, 0, 0, 0, 0]

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.render)
        self._timer.start(RENDER_TIMER_MS)

        self._dragging = False
        self._last_mouse_pos = QPoint()
        self._camera_yaw = -85.0
        self._camera_pitch = -20.0
        self._camera_distance = 0.30
        self._camera_target = (-0.02, 0.0, 0.02)
        self._render_enabled = URDF_RENDER_DEFAULT_ENABLED

        self._label.setMouseTracking(True)
        self._label.installEventFilter(self)

        self._init_pybullet()

    def update_positions(self, positions):
        self._positions = list(positions)
        if self._pybullet is None or self._body_id is None or not self._render_enabled:
            return
        commands = sdk_positions_to_urdf_commands(self._positions)
        for joint_name, value in commands.items():
            joint_id = self._joint_name_to_id.get(joint_name)
            if joint_id is not None:
                self._pybullet.resetJointState(self._body_id, joint_id, value)

    def set_render_enabled(self, enabled):
        enabled = bool(enabled)
        self._render_enabled = enabled
        if enabled:
            self._timer.start(RENDER_TIMER_MS)
        else:
            self._timer.stop()
            self._label.setText("URDF rendering disabled")
        self.render()

    def _init_pybullet(self):
        try:
            import pybullet as p
        except Exception as exc:
            self._label.setText(f"PyBullet unavailable\n{exc}")
            return
        try:
            import pybullet_data
        except Exception:
            pybullet_data = None

        self._pybullet = p
        runtime_urdf_dir, runtime_urdf_path = self._prepare_runtime_urdf()
        client_id = p.connect(p.DIRECT)
        p.setAdditionalSearchPath(str(runtime_urdf_dir), physicsClientId=client_id)
        if pybullet_data is not None:
            p.setAdditionalSearchPath(
                pybullet_data.getDataPath(), physicsClientId=client_id
            )
        self._body_id = p.loadURDF(
            str(runtime_urdf_path), useFixedBase=True, physicsClientId=client_id
        )
        for joint_id in range(p.getNumJoints(self._body_id, physicsClientId=client_id)):
            info = p.getJointInfo(self._body_id, joint_id, physicsClientId=client_id)
            self._joint_name_to_id[info[1].decode("utf-8")] = joint_id
        self._client_id = client_id

    def _prepare_runtime_urdf(self):
        runtime_urdf_dir = self._copy_urdf_to_ascii_cache()
        source_urdf_path = runtime_urdf_dir / "rohand_left.urdf"
        resolved_urdf_path = runtime_urdf_dir / "rohand_left_pybullet.urdf"
        text = source_urdf_path.read_text(encoding="utf-8")
        text = text.replace("package://ap002/meshes_l/", "meshes_l/")
        resolved_urdf_path.write_text(text, encoding="utf-8")
        return runtime_urdf_dir, resolved_urdf_path

    def _copy_urdf_to_ascii_cache(self):
        for cache_dir in self._candidate_urdf_cache_dirs():
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                for item in URDF_DIR.iterdir():
                    target = cache_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, target, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, target)
                return cache_dir
            except Exception:
                continue
        return URDF_DIR

    def _candidate_urdf_cache_dirs(self):
        configured = os.getenv("ROHAND_URDF_CACHE", "").strip()
        if configured:
            yield Path(configured)
        if os.name == "nt":
            system_drive = os.getenv("SystemDrive", "C:")
            yield Path(system_drive + "\\") / ASCII_URDF_CACHE_DIRNAME / "urdf"
            public_dir = os.getenv("PUBLIC", "")
            if public_dir:
                yield Path(public_dir) / ASCII_URDF_CACHE_DIRNAME / "urdf"
            program_data = os.getenv("ProgramData", "")
            if program_data:
                yield Path(program_data) / ASCII_URDF_CACHE_DIRNAME / "urdf"
        yield Path.cwd() / ASCII_URDF_CACHE_DIRNAME / "urdf"

    def render(self):
        if not self._render_enabled:
            self._label.setText("URDF rendering disabled")
            return
        if self._pybullet is None or self._body_id is None:
            return
        p = self._pybullet
        width = max(int(self._label.width() * RENDER_SCALE), MIN_RENDER_WIDTH)
        height = max(int(self._label.height() * RENDER_SCALE), MIN_RENDER_HEIGHT)
        target_x, target_y, target_z = self._camera_target
        yaw_rad = self._camera_yaw * 3.141592653589793 / 180.0
        pitch_rad = self._camera_pitch * 3.141592653589793 / 180.0
        eye_x = target_x + self._camera_distance * math.cos(pitch_rad) * math.cos(
            yaw_rad
        )
        eye_y = target_y + self._camera_distance * math.cos(pitch_rad) * math.sin(
            yaw_rad
        )
        eye_z = target_z + self._camera_distance * math.sin(pitch_rad)
        view = p.computeViewMatrix(
            cameraEyePosition=[eye_x, eye_y, eye_z],
            cameraTargetPosition=[target_x, target_y, target_z],
            cameraUpVector=[0, 0, 1],
            physicsClientId=self._client_id,
        )
        proj = p.computeProjectionMatrixFOV(
            35, width / height, 0.01, 2.0, physicsClientId=self._client_id
        )
        _, _, rgba, _, _ = p.getCameraImage(
            width,
            height,
            viewMatrix=view,
            projectionMatrix=proj,
            renderer=p.ER_TINY_RENDERER,
            physicsClientId=self._client_id,
        )
        image = QImage(bytes(rgba), width, height, QImage.Format_RGBA8888)
        self._label.setPixmap(
            QPixmap.fromImage(image).scaled(
                self._label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )

    def eventFilter(self, watched, event):
        if watched is self._label:
            if (
                event.type() == QEvent.MouseButtonPress
                and event.button() == Qt.LeftButton
            ):
                self._dragging = True
                self._last_mouse_pos = event.pos()
                return True
            if event.type() == QEvent.MouseMove and self._dragging:
                delta = event.pos() - self._last_mouse_pos
                self._last_mouse_pos = event.pos()
                self._camera_yaw += delta.x() * 0.4
                self._camera_pitch = max(
                    -85.0, min(35.0, self._camera_pitch - delta.y() * 0.4)
                )
                self.render()
                return True
            if (
                event.type() == QEvent.MouseButtonRelease
                and event.button() == Qt.LeftButton
            ):
                self._dragging = False
                return True
            if event.type() == QEvent.Wheel:
                wheel_steps = event.angleDelta().y() / 120.0
                if event.modifiers() & Qt.ControlModifier:
                    self._camera_distance = max(
                        0.10,
                        min(
                            0.80,
                            self._camera_distance - wheel_steps * CTRL_WHEEL_ZOOM_STEP,
                        ),
                    )
                else:
                    target_x, target_y, target_z = self._camera_target
                    self._camera_target = (
                        target_x + wheel_steps * WHEEL_PAN_STEP,
                        target_y,
                        target_z,
                    )
                self.render()
                return True
        return super().eventFilter(watched, event)


class _RenderLabel(QLabel):
    def sizeHint(self):
        return QSize(320, 260)

    def minimumSizeHint(self):
        return QSize(320, 260)
