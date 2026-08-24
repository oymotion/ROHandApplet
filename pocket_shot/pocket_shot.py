import os
import sys
import math
import time
import logging
from typing import List, Tuple, Optional

import cv2
import numpy as np
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from pymodbus import FramerType
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from serial.tools import list_ports

# 导入您的模块
from roh_registers_v2 import *
from heat_map_dot import *

# 手常量定义
NUM_FINGERS = 5
PALM_INDEX = NUM_FINGERS
LEFT_HAND = 0
RIGHT_HAND = 1
NODE_ID = 2
TACS_3D_FORCE = 1
TACS_DOT_MATRIX = 0

# 球常量定义
MAX_POWER = 100.0
BALL_RADIUS = 14
HOLE_RADIUS = 25
FRICTION = 0.97
MIN_SPEED = 0.15
WALL_BOUNCE = 0.78
BALL_MOVE_FORCE_THRESHOLD = 500

# 手指名称
FINGER_NAMES = ["拇指", "食指", "中指", "无名指", "小指", "手掌"]

# 游戏尺寸
GAME_WIDTH = 800
GAME_HEIGHT = 600

def resource_path(relative_path):
    """获取资源文件的绝对路径，支持PyInstaller打包"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class Ball:
    """台球类"""
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.radius = BALL_RADIUS
        self.is_moving = False
        self.is_resetting = False
        self.reset_timer = 0

    def reset(self, x: Optional[float] = None, y: Optional[float] = None):
        self.x = x if x is not None else GAME_WIDTH // 2
        self.y = y if y is not None else GAME_HEIGHT // 2
        self.vx = 0.0
        self.vy = 0.0
        self.is_moving = False
        self.is_resetting = False
        self.reset_timer = 0

    def update(self) -> bool:
        if not self.is_moving:
            return False

        self.vx *= FRICTION
        self.vy *= FRICTION

        speed = math.hypot(self.vx, self.vy)
        if speed < MIN_SPEED:
            self.vx = 0.0
            self.vy = 0.0
            self.is_moving = False
            return False

        self.x += self.vx
        self.y += self.vy
        self._wall_collision()

        if self._check_hole():
            self.is_moving = False
            self.is_resetting = True
            self.reset_timer = time.time()
            return False

        return True

    def _wall_collision(self):
        if self.x - self.radius < 0:
            self.x = self.radius
            self.vx = -self.vx * WALL_BOUNCE
        elif self.x + self.radius > GAME_WIDTH:
            self.x = GAME_WIDTH - self.radius
            self.vx = -self.vx * WALL_BOUNCE

        if self.y - self.radius < 0:
            self.y = self.radius
            self.vy = -self.vy * WALL_BOUNCE
        elif self.y + self.radius > GAME_HEIGHT:
            self.y = GAME_HEIGHT - self.radius
            self.vy = -self.vy * WALL_BOUNCE

        self.x = max(self.radius, min(GAME_WIDTH - self.radius, self.x))
        self.y = max(self.radius, min(GAME_HEIGHT - self.radius, self.y))

    def _check_hole(self) -> bool:
        holes = [
            (30, 30), 
            (GAME_WIDTH // 2, 20), 
            (GAME_WIDTH - 30, 30), 
            (30, GAME_HEIGHT - 30), 
            (GAME_WIDTH // 2, GAME_HEIGHT - 20), 
            (GAME_WIDTH - 30, GAME_HEIGHT - 30)
        ]
        for hx, hy in holes:
            if math.hypot(self.x - hx, self.y - hy) < HOLE_RADIUS - 4:
                return True
        return False

    def shoot_with_angle(self, angle_deg: float, power: float = 1.0) -> bool:
        if self.is_resetting:
            return False

        angle_rad = math.radians(angle_deg)
        speed = min(power, 1.0) * MAX_POWER
        self.vx = speed * math.cos(angle_rad)
        self.vy = speed * math.sin(angle_rad)

        if math.hypot(self.vx, self.vy) < 0.3:
            return False

        self.is_moving = True
        return True

class GameWidget(QWidget):
    """台球游戏显示组件"""
    def __init__(self):
        super().__init__()
        self.ball = Ball(GAME_WIDTH // 2, GAME_HEIGHT // 2)
        self.holes = [
            (30, 30), 
            (GAME_WIDTH // 2, 20), 
            (GAME_WIDTH - 30, 30), 
            (30, GAME_HEIGHT - 30), 
            (GAME_WIDTH // 2, GAME_HEIGHT - 20), 
            (GAME_WIDTH - 30, GAME_HEIGHT - 30)
        ]
        self.setMinimumSize(400, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.reset_delay = 1.0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        widget_width = self.width()
        widget_height = self.height()
        
        scale_x = widget_width / GAME_WIDTH
        scale_y = widget_height / GAME_HEIGHT
        scale = min(scale_x, scale_y)
        
        game_width = GAME_WIDTH * scale
        game_height = GAME_HEIGHT * scale
        offset_x = (widget_width - game_width) // 2
        offset_y = (widget_height - game_height) // 2

        painter.fillRect(self.rect(), QColor(30, 120, 60))
        painter.fillRect(offset_x, offset_y, game_width, game_height, QColor(30, 120, 60))

        border_width = max(3, int(6 * scale))
        painter.setPen(QPen(QColor(80, 60, 30), border_width))
        painter.drawRect(offset_x, offset_y, game_width, game_height)

        for hx, hy in self.holes:
            hole_radius = max(5, int(HOLE_RADIUS * scale))
            painter.setBrush(QColor(10, 10, 10))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(
                QPointF(offset_x + hx * scale, offset_y + hy * scale), 
                hole_radius, hole_radius
            )

        if self.ball:
            ball_x = offset_x + self.ball.x * scale
            ball_y = offset_y + self.ball.y * scale
            ball_radius = max(3, int(self.ball.radius * scale))
            
            if self.ball.is_resetting:
                alpha = int(128 + 127 * math.sin(time.time() * 10))
                painter.setBrush(QColor(255, 255, 255, alpha))
                painter.drawEllipse(
                    QPointF(ball_x, ball_y), 
                    ball_radius + 5, ball_radius + 5
                )
            
            shadow_offset = max(2, int(3 * scale))
            painter.setBrush(QColor(0, 0, 0, 60))
            painter.drawEllipse(
                QPointF(ball_x + shadow_offset, ball_y + shadow_offset), 
                ball_radius, ball_radius
            )

            gradient = QRadialGradient(
                ball_x - max(2, int(4 * scale)), 
                ball_y - max(2, int(4 * scale)),
                ball_radius + max(1, int(2 * scale))
            )
            gradient.setColorAt(0, QColor(255, 255, 255))
            gradient.setColorAt(0.3, QColor(220, 230, 220))
            gradient.setColorAt(0.7, QColor(180, 200, 180))
            gradient.setColorAt(1, QColor(100, 130, 100))

            painter.setBrush(gradient)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(ball_x, ball_y), ball_radius, ball_radius)

            highlight_radius = max(2, int(4 * scale))
            painter.setBrush(QColor(255, 255, 255, 180))
            painter.drawEllipse(
                QPointF(ball_x - max(2, int(3 * scale)), ball_y - max(3, int(6 * scale))), 
                highlight_radius, highlight_radius
            )

        painter.end()

    def update_ball(self):
        if self.ball.is_resetting:
            if time.time() - self.ball.reset_timer > self.reset_delay:
                self.ball.reset()
                self.update()
            return
        
        self.ball.update()
        self.update()

    def reset_ball(self):
        self.ball.reset()
        self.update()

class ForceDisplayWidget(QWidget):
    """力传感器数据显示组件"""
    def __init__(self):
        super().__init__()
        self.hm_cfg = None
        self.force_all = []
        self.force_point_loc = []
        self.force_img = None
        self.is_initialized = False
        self.setMinimumSize(400, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 缓存每个手指的角度数据，供外部使用
        self.finger_angles = [0.0] * (NUM_FINGERS + 1)
        self.finger_forces_cache = [0.0] * (NUM_FINGERS + 1)

    def initialize(self, hm_cfg, force_point_loc, force_img):
        self.hm_cfg = hm_cfg
        self.force_point_loc = force_point_loc
        self.force_img = force_img
        self.is_initialized = True
        self.update()

    def update_force_data(self, force_all):
        self.force_all = force_all
        self.update()

    def get_finger_angle(self, finger_index):
        """获取指定手指的角度（从缓存中读取）"""
        if finger_index < len(self.finger_angles):
            return self.finger_angles[finger_index]
        return 0.0

    def get_finger_force(self, finger_index):
        """获取指定手指的力度（从缓存中读取）"""
        if finger_index < len(self.finger_forces_cache):
            return self.finger_forces_cache[finger_index]
        return 0.0

    def paintEvent(self, event):
        if not self.is_initialized or self.force_img is None:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(40, 40, 40))
            painter.setPen(QColor(200, 200, 200))
            painter.drawText(self.rect(), Qt.AlignCenter, "等待传感器连接...")
            painter.end()
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        img_h, img_w = self.force_img.shape[:2]
        scale_w = self.width() / img_w
        scale_h = self.height() / img_h
        scale = min(scale_w, scale_h, 1.0)

        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        x_offset = (self.width() - new_w) // 2
        y_offset = (self.height() - new_h) // 2

        if new_w < 10 or new_h < 10:
            painter.end()
            return

        heatmap = np.zeros((img_h, img_w), dtype=np.uint8)

        try:
            # 重置角度缓存
            self.finger_angles = [0.0] * (NUM_FINGERS + 1)
            self.finger_forces_cache = [0.0] * (NUM_FINGERS + 1)

            for finger_id, force_points in enumerate(self.force_point_loc):
                force = self.force_all[finger_id] if finger_id < len(self.force_all) else []
                
                # 计算该手指的总力度
                if self.hm_cfg.SENSOR_TYPE == TACS_3D_FORCE:
                    total_force = 0
                    for i in range(0, len(force), 3):
                        if i + 1 < len(force):
                            total_force += math.sqrt(force[i]**2 + force[i+1]**2)
                    self.finger_forces_cache[finger_id] = total_force
                else:
                    self.finger_forces_cache[finger_id] = sum(force)

                # 用于计算平均角度
                angle_sum = 0.0
                angle_count = 0

                for dot_index in range(len(force_points)):
                    x, y = force_points[dot_index]

                    if self.hm_cfg.SENSOR_TYPE == TACS_3D_FORCE:
                        if 0 <= x < img_w and 0 <= y < img_h and finger_id != PALM_INDEX:
                            if dot_index * 3 < len(force):
                                value = force[dot_index * 3] * self.hm_cfg.COLOR_SCALE
                                radius = self.hm_cfg.POINT_RADIUS + int(self._interpolate(
                                    value, 0, self.hm_cfg.MAX_FORCE, 0, 10))
                                color = self._map_value_to_color(value, 0, self.hm_cfg.MAX_FORCE, 120, 1)
                                cv2.circle(heatmap, (x, y), radius, color, -1)

                                if dot_index * 3 + 2 < len(force):
                                    # 计算角度（与热力图绘制保持一致）
                                    angle_deg = force[dot_index * 3 + 2] - 90
                                    if angle_deg < 0:
                                        angle_deg += 360
                                    if angle_deg >= 360:
                                        angle_deg -= 360
                                    
                                    # 累加角度用于计算平均值
                                    angle_sum += angle_deg
                                    angle_count += 1
                                    
                                    value_tf = force[dot_index * 3 + 1] * self.hm_cfg.COLOR_SCALE
                                    length = int(self._interpolate(value_tf, 0, self.hm_cfg.MAX_FORCE, 0, 100))
                                    angle_rad = math.radians(angle_deg)
                                    arrow_end = (
                                        x + int(length * math.cos(angle_rad) * self.hm_cfg.ARROW_SCALE),
                                        y + int(length * math.sin(angle_rad) * self.hm_cfg.ARROW_SCALE)
                                    )
                                    color_arrow = self._map_value_to_color(value_tf, 0, self.hm_cfg.MAX_FORCE, 120, 1)
                                    cv2.arrowedLine(heatmap, (x, y), arrow_end, color_arrow, 3, tipLength=0.3)
                    else:
                        if 0 <= x < img_w and 0 <= y < img_h:
                            value = force[dot_index] * self.hm_cfg.COLOR_SCALE if dot_index < len(force) else 0
                            color = self._map_value_to_color(value, 0, self.hm_cfg.MAX_FORCE, 120, 1)
                            radius = self.hm_cfg.PALM_POINT_RADIUS if finger_id == PALM_INDEX else self.hm_cfg.POINT_RADIUS
                            cv2.circle(heatmap, (x, y), radius, color, -1)

                # 计算该手指的平均角度
                if angle_count > 0:
                    self.finger_angles[finger_id] = angle_sum / angle_count
                elif self.hm_cfg.SENSOR_TYPE == TACS_DOT_MATRIX:
                    # 点阵传感器：从力的中心计算角度
                    total_force = sum(force) if force else 0
                    if total_force > 0 and len(force_points) > 0:
                        center_x, center_y = 0.0, 0.0
                        for i, f in enumerate(force):
                            if i < len(force_points) and f > 0:
                                x, y = force_points[i]
                                center_x += x * f
                                center_y += y * f
                        center_x /= total_force
                        center_y /= total_force
                        
                        palm_center_x = img_w // 2
                        palm_center_y = img_h // 2
                        dx = palm_center_x - center_x
                        dy = palm_center_y - center_y
                        
                        angle_rad = math.atan2(dy, dx)
                        angle_deg = math.degrees(angle_rad)
                        if angle_deg < 0:
                            angle_deg += 360
                        self.finger_angles[finger_id] = angle_deg

            heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_HSV)
            heatmap_colored = cv2.resize(heatmap_colored, (img_w, img_h))
            mask = np.uint8(heatmap > 0) * 255

            result = self.force_img.copy()
            if mask.any():
                result[mask > 0] = cv2.addWeighted(
                    self.force_img[mask > 0], 0.2,
                    heatmap_colored[mask > 0], 0.8, 0
                )

            result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
            h, w, ch = result_rgb.shape
            bytes_per_line = ch * w
            qt_image = QImage(result_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)

            scaled_image = qt_image.scaled(new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawImage(x_offset, y_offset, scaled_image)

        except Exception as e:
            logging.error(f"绘制热力图时出错: {e}")
            painter.setPen(QColor(255, 0, 0))
            painter.drawText(self.rect(), Qt.AlignCenter, f"绘制错误: {str(e)}")

        painter.end()

    def _interpolate(self, n, from_min, from_max, to_min, to_max):
        if from_max == from_min:
            return to_min
        return (n - from_min) / (from_max - from_min) * (to_max - to_min) + to_min

    def _map_value_to_color(self, n, from_min, from_max, to_min, to_max):
        if from_max == from_min:
            return int(to_min)
        n = max(from_min, min(n, from_max))
        result = (n - from_min) / (from_max - from_min) * (to_max - to_min) + to_min
        return int(result)

class FingerInfoWidget(QWidget):
    """手指力信息显示组件"""
    def __init__(self):
        super().__init__()
        self.finger_forces = [0] * (NUM_FINGERS + 1)
        self.finger_thresholds = [BALL_MOVE_FORCE_THRESHOLD] * (NUM_FINGERS + 1)
        
        self.finger_colors = [
            QColor(255, 100, 100),
            QColor(100, 255, 100),
            QColor(100, 100, 255),
            QColor(255, 255, 100),
            QColor(255, 100, 255),
            QColor(100, 255, 255)
        ]
        
        self.setMinimumWidth(150)
        self.setMaximumWidth(250)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

    def update_forces(self, force_all):
        for i in range(min(len(force_all), NUM_FINGERS + 1)):
            self.finger_forces[i] = sum(force_all[i]) if force_all[i] else 0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.fillRect(self.rect(), QColor(50, 50, 50, 200))
        
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(10, 25, "手指力信息")
        
        y_pos = 40
        bar_height = 20
        bar_width = self.width() - 70
        max_force = 0xFFFF
        
        for i in range(NUM_FINGERS):
            painter.setPen(QColor(200, 200, 200))
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(10, y_pos + 15, FINGER_NAMES[i])
            
            bar_x = 60
            bar_y = y_pos + 2
            bar_width_current = min(int((self.finger_forces[i] / max_force) * (self.width() - 80)), self.width() - 80)
            
            painter.setBrush(QColor(80, 80, 80))
            painter.setPen(Qt.NoPen)
            painter.drawRect(bar_x, bar_y, self.width() - 80, bar_height)
            
            if self.finger_forces[i] > self.finger_thresholds[i]:
                color = self.finger_colors[i].lighter(150)
            else:
                color = self.finger_colors[i]
            
            painter.setBrush(color)
            painter.drawRect(bar_x, bar_y, bar_width_current, bar_height)
            
            threshold_x = bar_x + int((self.finger_thresholds[i] / max(1, max_force)) * (self.width() - 80))
            if threshold_x < bar_x + self.width() - 80:
                painter.setPen(QColor(255, 255, 255, 150))
                painter.setBrush(Qt.NoBrush)
                painter.drawLine(threshold_x, bar_y, threshold_x, bar_y + bar_height)
            
            if self.finger_forces[i] > self.finger_thresholds[i]:
                painter.setBrush(QColor(0, 255, 0))
            else:
                painter.setBrush(QColor(100, 100, 100))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(bar_x + self.width() - 90, bar_y + 4, 12, 12)
            
            y_pos += 30
        
        y_pos += 10
        active_fingers = []
        for i in range(NUM_FINGERS):
            if self.finger_forces[i] > self.finger_thresholds[i]:
                active_fingers.append(FINGER_NAMES[i])
        
        painter.setPen(QColor(255, 255, 255))
        font.setPointSize(9)
        painter.setFont(font)
        if active_fingers:
            painter.setPen(QColor(0, 255, 0))
            painter.drawText(10, y_pos + 15, f"激活: {' '.join(active_fingers)}")
        else:
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(10, y_pos + 15, "等待输入...")
        
        painter.end()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("力反馈台球游戏 - Pocket Shot")
        self.setGeometry(100, 100, 1400, 800)

        self.itf_inst = None
        self.hm_cfg = None
        self.force_img = None
        self.force_point_loc = None
        self.is_connected = False
        self.connection_attempted = False

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.force_widget = ForceDisplayWidget()
        main_layout.addWidget(self.force_widget, 3)

        self.game_widget = GameWidget()
        main_layout.addWidget(self.game_widget, 3)

        right_panel = QWidget()
        right_panel.setFixedWidth(200)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(5)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("正在连接传感器...")
        self.status_label.setStyleSheet("QLabel { color: yellow; }")
        right_layout.addWidget(self.status_label)

        #self.force_label = QLabel("力度: 0%")
        #right_layout.addWidget(self.force_label)

        #self.angle_label = QLabel("角度: 0°")
        #right_layout.addWidget(self.angle_label)

        self.ball_status_label = QLabel("球状态: 就绪")
        right_layout.addWidget(self.ball_status_label)

        self.finger_info = FingerInfoWidget()
        right_layout.addWidget(self.finger_info)

        right_layout.addStretch()
        main_layout.addWidget(right_panel)

        self.game_timer = QTimer()
        self.game_timer.timeout.connect(self.update_game)
        self.game_timer.start(33)

        self.sensor_timer = QTimer()
        self.sensor_timer.timeout.connect(self.update_sensor_data)
        self.sensor_timer.start(100)

        self.last_shoot_time = 0
        self.shoot_cooldown = 0.3

        QTimer.singleShot(500, self.auto_connect)

    def auto_connect(self):
        if self.connection_attempted:
            return
        
        self.connection_attempted = True
        self.status_label.setText("正在连接传感器...")
        self.status_label.setStyleSheet("QLabel { color: yellow; }")
        
        self.connect_sensor()

    def connect_sensor(self):
        try:
            port = self.find_comport("CH340") or self.find_comport("USB")
            if not port:
                self.status_label.setText("未找到传感器")
                self.status_label.setStyleSheet("QLabel { color: orange; }")
                return

            self.itf_inst = ModbusSerialClient(port, FramerType.RTU, 115200)
            if not self.itf_inst.connect():
                self.status_label.setText("连接失败")
                self.status_label.setStyleSheet("QLabel { color: orange; }")
                return

            self.hm_cfg = self.load_force_config()
            if not self.hm_cfg:
                self.status_label.setText("配置加载失败")
                self.status_label.setStyleSheet("QLabel { color: orange; }")
                return

            hand_type = 1
            self.force_img, self.force_point_loc = self.img_init(hand_type, self.hm_cfg)

            self.is_connected = True
            self.status_label.setText("已连接 ✓")
            self.status_label.setStyleSheet("QLabel { color: green; }")

            self.force_widget.initialize(self.hm_cfg, self.force_point_loc, self.force_img)

        except Exception as e:
            self.status_label.setText("连接错误")
            self.status_label.setStyleSheet("QLabel { color: red; }")
            logging.error(f"连接传感器失败: {e}")

    def find_comport(self, port_name):
        ports = list_ports.comports()
        for port in ports:
            if port_name in port.description:
                return port.device
        return None

    def load_force_config(self):
        try:
            resp = self.read_registers(self.itf_inst, ROH_MANU_DATA0, 1)
            if resp is not None:
                sub_model = (resp[0] >> 8) & 0xFF
                hm_cfg = HeatMapDot(sub_model)
                hm_cfg.init_dot_info()
                return hm_cfg
        except Exception as e:
            logging.error(f"加载配置失败: {e}")
        return None       

    def read_registers(self, client, address, count):
        try:
            resp = client.read_holding_registers(address, count, NODE_ID)
            if not resp.isError():
                return resp.registers
        except Exception as e:
            logging.error(f"读取寄存器失败: {e}")
        return None

    def write_registers(self, client, address, values):
        try:
            resp = client.write_registers(address, values, NODE_ID)
            return not resp.isError()
        except Exception as e:
            logging.error(f"写入寄存器失败: {e}")
            return False

    def img_init(self, hand_type, hm_cfg):
        """初始化热力图图片"""
        try:
            if hand_type == 0:
                pic_path = "pic/force_left.png"
                force_point_loc = hm_cfg.LEFT_FORCE_POINT
            else:
                pic_path = "pic/force_right.png"
                force_point_loc = hm_cfg.RIGHT_FORCE_POINT

            image_path = resource_path(pic_path)
            
            if not os.path.exists(image_path):
                logging.error(f"图片文件不存在: {image_path}")
                alt_path = os.path.join(os.path.abspath("."), pic_path)
                if os.path.exists(alt_path):
                    image_path = alt_path
                    logging.info(f"在备用路径找到图片: {image_path}")
                else:
                    raise FileNotFoundError(f"找不到图片文件: {pic_path}")
            
            force_img = cv2.imread(image_path)
            if force_img is None:
                raise ValueError(f"无法读取图片: {image_path}")
            
            logging.info(f"成功加载图片: {image_path}")
            return force_img, force_point_loc
            
        except Exception as e:
            logging.error(f"加载图片失败: {e}")
            raise

    def update_sensor_data(self):
        if not self.is_connected:
            return

        try:
            force_all = []
            for finger_index in range(NUM_FINGERS + 1):
                reg_cnt = self.hm_cfg.FORCE_VALUE_LENGTH[finger_index]
                force = self.get_force_single_finger(finger_index, reg_cnt)
                force_all.append(force)

            self.force_widget.update_force_data(force_all)
            self.finger_info.update_forces(force_all)

            self.check_fingers_and_shoot(force_all)

        except Exception as e:
            logging.error(f"更新传感器数据失败: {e}")

    def get_force_single_finger(self, finger_index, reg_cnt):
        resp = self.read_registers(
            self.itf_inst,
            ROH_FINGER_FORCE_EX0 + finger_index * FORCE_GROUP_SIZE,
            reg_cnt
        )

        if resp is None or len(resp) != reg_cnt:
            return []

        if self.hm_cfg.SENSOR_TYPE == TACS_3D_FORCE:
            force = []
            for j in range(reg_cnt):
                val = ((resp[j] & 0xFF) << 8) | ((resp[j] >> 8) & 0xFF)
                force.append(val if val < 0xFFFF else 0)
            return force
        else:
            force = []
            for x in resp:
                force.append((x >> 8) & 0xFF)
                force.append(x & 0xFF)
            return force

    def calculate_finger_force(self, force, finger_index):
        """计算单个手指的总力"""
        if not force:
            return 0
            
        if self.hm_cfg.SENSOR_TYPE == TACS_3D_FORCE:
            total = 0
            for i in range(0, len(force), 3):
                if i + 1 < len(force):
                    total += math.sqrt(force[i]**2 + force[i+1]**2)
            return total
        else:
            return sum(force)

    def check_fingers_and_shoot(self, force_all):
        if self.game_widget.ball.is_moving or self.game_widget.ball.is_resetting:
            return

        current_time = time.time()
        if current_time - self.last_shoot_time < self.shoot_cooldown:
            return

        active_fingers = []
        for finger_idx in range(NUM_FINGERS):
            finger_force = force_all[finger_idx] if finger_idx < len(force_all) else []
            force_value = self.calculate_finger_force(finger_force, finger_idx)
            
            finger_threshold = self.finger_info.finger_thresholds[finger_idx]
            if force_value > finger_threshold:
                active_fingers.append((finger_idx, force_value))

        if active_fingers:
            active_fingers.sort(key=lambda x: x[1], reverse=True)
            selected_finger = active_fingers[0][0]
            self.shoot_with_finger(force_all, selected_finger)

    def shoot_with_finger(self, force_all, finger_idx):
        """使用指定手指击球，角度直接从ForceDisplayWidget的缓存中获取"""
        finger_force = force_all[finger_idx] if finger_idx < len(force_all) else []
        
        # 从ForceDisplayWidget获取缓存的角度（与热力图一致）
        angle_deg = self.force_widget.get_finger_angle(finger_idx)
        force_value = self.calculate_finger_force(finger_force, finger_idx)
        
        max_power = 2000
        power = min(force_value / max_power, 1.0)

        if power > 0.1:
            if self.game_widget.ball.shoot_with_angle(angle_deg, power):
                self.last_shoot_time = time.time()
                    
                #self.angle_label.setText(f"角度: {int(angle_deg)}°")
                #self.force_label.setText(f"力度: {int(power * 100)}%")
                self.ball_status_label.setText("球状态: 运动中")
                
                logging.info(f"手指 {FINGER_NAMES[finger_idx]} 击球: 角度={int(angle_deg)}°, 力度={int(power*100)}%")

    def update_game(self):
        self.game_widget.update_ball()
        
        if self.game_widget.ball.is_moving:
            self.ball_status_label.setText("球状态: 运动中")
        elif self.game_widget.ball.is_resetting:
            self.ball_status_label.setText("球状态: 重置中...")
        else:
            self.ball_status_label.setText("球状态: 就绪")

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()