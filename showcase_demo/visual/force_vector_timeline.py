import math
import time
from collections import deque

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from visual.force_display_mapping import FINGER_PAD_ROWS, finger_zone_names, force_zone_pressure
from visual.force_colors import force_color_for_pressure, pressure_level


FINGER_ROWS = ("thumb", "index", "middle", "ring", "little", "palm")
CURVE_NORMAL_MAX = 900.0
CURVE_TANGENTIAL_MAX = 750.0
NO_DIRECTION_LANE_OFFSET_RATIO = 0.58
ARROW_PEN_STYLE = Qt.SolidLine
ARROW_ALPHA_RATIO = 0.5
ARROW_MIN_NORMAL = 25.0
RIGHT_REFRESH_TIMER_MS = 20
CURVE_MARKER_SHAPE = "circle"
PAD_LAYER_DRAW_CURVES = False
PAD_LAYER_DRAW_POINTS = False
VISIBLE_DIRECTION_POINT_INDICES = (0, 1)


def arrow_head_points(tip_x, tip_y, angle_rad, head_len=7.0, head_angle=0.55):
    left = (
        tip_x - math.cos(angle_rad - head_angle) * head_len,
        tip_y - math.sin(angle_rad - head_angle) * head_len,
    )
    right = (
        tip_x - math.cos(angle_rad + head_angle) * head_len,
        tip_y - math.sin(angle_rad + head_angle) * head_len,
    )
    return left, right


def curve_y_for_pressure(base_y, band_height, normal):
    level = pressure_level(normal, CURVE_NORMAL_MAX)
    return base_y + band_height * (1.0 - level)


def arrow_length_for_tangential(tangential):
    return 2.5 + pressure_level(tangential, CURVE_TANGENTIAL_MAX) * 22.5


def marker_radius_for_pressure(normal):
    return 0.7 + pressure_level(normal, CURVE_NORMAL_MAX) * 0.7


def should_draw_arrow(normal):
    return float(normal) >= ARROW_MIN_NORMAL


def is_arrow_point(point_index, has_direction):
    return int(point_index) == 0 and bool(has_direction)


def timeline_lanes_for_indices(finger_name, _directional_indices, _pad_indices):
    lanes = []
    for zone_name in finger_zone_names(finger_name):
        if zone_name == "tip":
            lanes.append((zone_name, True))
        elif zone_name == "pad" and finger_name in FINGER_PAD_ROWS:
            lanes.append((zone_name, False))
        elif zone_name == "palm":
            lanes.append((zone_name, False))
    return lanes


def arrow_segment_for_point(origin_x, origin_y, angle_rad, marker_radius, tangential):
    start_offset = marker_radius + 1.5
    length = arrow_length_for_tangential(tangential)
    start = QPointF(
        origin_x + math.cos(angle_rad) * start_offset,
        origin_y + math.sin(angle_rad) * start_offset,
    )
    end = QPointF(
        start.x() + math.cos(angle_rad) * length,
        start.y() + math.sin(angle_rad) * length,
    )
    return start, end


def _point_matches_direction(point, require_direction):
    has_direction = "direction_display_deg" in point
    if require_direction is True:
        return has_direction
    if require_direction is False:
        return not has_direction
    return True


def _sample_from_point(frame, point):
    return {
        "timestamp": float(frame.get("timestamp", 0.0)),
        "normal": float(point.get("normal", 0.0)),
        "tangential": float(point.get("tangential", 0.0)),
        "direction_display_deg": float(point.get("direction_display_deg", 0.0)),
        "has_direction": "direction_display_deg" in point,
        "point_index": int(point.get("point_index", 0)),
    }


def extract_finger_series(frames, finger_name, require_direction=None):
    ordered_frames = sorted(frames, key=lambda frame: float(frame.get("timestamp", 0.0)))
    series = []
    for frame in ordered_frames:
        summary = frame.get("force_summary", {})
        points = summary.get("fingers", {}).get(finger_name, [])
        points = [point for point in points if _point_matches_direction(point, require_direction)]
        best_point = None
        if points:
            best_point = max(
                points,
                key=lambda point: (
                    float(point.get("normal", 0.0)),
                    float(point.get("tangential", 0.0)),
                ),
            )
        normal_value = float((best_point or {}).get("normal", 0.0))
        tangential_value = float((best_point or {}).get("tangential", 0.0))
        direction_value = float((best_point or {}).get("direction_display_deg", 0.0))
        series.append(
            {
                "timestamp": float(frame.get("timestamp", 0.0)),
                "normal": normal_value,
                "tangential": tangential_value,
                "direction_display_deg": direction_value,
                "has_direction": bool(best_point and "direction_display_deg" in best_point),
            }
        )
    return series


def extract_finger_point_indices(frames, finger_name, require_direction=None):
    indices = set()
    for frame in frames:
        points = frame.get("force_summary", {}).get("fingers", {}).get(finger_name, [])
        for point in points:
            if _point_matches_direction(point, require_direction):
                indices.add(int(point.get("point_index", 0)))
    return sorted(indices)


def extract_finger_point_series(frames, finger_name, point_index, require_direction=None):
    ordered_frames = sorted(frames, key=lambda frame: float(frame.get("timestamp", 0.0)))
    series = []
    for frame in ordered_frames:
        points = frame.get("force_summary", {}).get("fingers", {}).get(finger_name, [])
        matching_points = [
            point
            for point in points
            if int(point.get("point_index", -1)) == point_index and _point_matches_direction(point, require_direction)
        ]
        if not matching_points:
            continue
        point = max(
            matching_points,
            key=lambda item: (
                float(item.get("normal", 0.0)),
                float(item.get("tangential", 0.0)),
            ),
        )
        series.append(_sample_from_point(frame, point))
    return series


def extract_finger_zone_series(frames, finger_name, zone_name):
    ordered_frames = sorted(frames, key=lambda frame: float(frame.get("timestamp", 0.0)))
    series = []
    for frame in ordered_frames:
        summary = frame.get("force_summary", {})
        normal = force_zone_pressure(summary, finger_name, zone_name)
        point = {}
        points = summary.get("fingers", {}).get(finger_name, [])
        if zone_name == "tip":
            point = next((item for item in points if int(item.get("point_index", -1)) == 0), {})
        elif zone_name == "pad":
            point = next((item for item in points if int(item.get("point_index", -1)) == 1), {})
        series.append(
            {
                "timestamp": float(frame.get("timestamp", 0.0)),
                "normal": normal,
                "tangential": float(point.get("tangential", 0.0)),
                "direction_display_deg": float(point.get("direction_display_deg", 0.0)),
                "has_direction": "direction_display_deg" in point,
                "point_index": int(point.get("point_index", 0)),
            }
        )
    return series


class ForceVectorTimeline(QWidget):
    sampleSelected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(430)
        self.setMinimumHeight(520)
        self.window_seconds = 10.0
        self._min_window_seconds = 2.5
        self._max_window_seconds = 60.0
        self.history_seconds = 60.0
        self._frames = deque()
        self._start_time = None
        self._follow_live = True
        self._view_end_ts = None
        self._selected_frame_ts = None
        self._visible_samples = []
        self._dragging_pan = False
        self._pan_anchor_pos = None
        self._pan_anchor_view_end_ts = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.update)
        self._refresh_timer.start(RIGHT_REFRESH_TIMER_MS)

    def add_frame(self, frame):
        timestamp = float(frame.get("timestamp", time.time()))
        if self._start_time is None:
            self._start_time = timestamp
        self._frames.append(frame)
        self._prune_frames(timestamp)
        if self._follow_live:
            self._view_end_ts = timestamp
        if self._follow_live or self._selected_frame_ts is None:
            self._selected_frame_ts = timestamp

    def clear(self):
        self._frames.clear()
        self._start_time = None
        self._follow_live = True
        self._view_end_ts = None
        self._selected_frame_ts = None
        self._visible_samples = []
        self._dragging_pan = False
        self.update()

    def set_history_position(self, value, maximum):
        maximum = max(1, int(maximum))
        value = max(0, min(int(value), maximum))
        self._follow_live = value >= maximum
        latest_ts = self._latest_timestamp()
        if latest_ts is None:
            self._view_end_ts = None
            self.update()
            return
        offset_ratio = 1.0 - (float(value) / float(maximum))
        offset_seconds = offset_ratio * self.history_seconds
        self._view_end_ts = latest_ts - offset_seconds
        self._selected_frame_ts = self._view_end_ts
        self.update()

    def is_following_live(self):
        return self._follow_live

    def set_window_seconds(self, window_seconds):
        self.window_seconds = max(self._min_window_seconds, min(self._max_window_seconds, float(window_seconds)))
        self.update()

    def selected_frame(self):
        if not self._frames:
            return None
        selected_ts = self._selected_frame_ts
        if selected_ts is None:
            return self._frames[-1]
        selected = None
        for frame in self._frames:
            timestamp = float(frame.get("timestamp", 0.0))
            if timestamp <= selected_ts:
                selected = frame
            else:
                break
        return selected or self._frames[0]

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("white"))
        painter.setRenderHint(QPainter.Antialiasing)
        margin_left = 90
        margin_top = 34
        margin_bottom = 28
        plot_w = max(10, self.width() - margin_left - 20)
        row_h = (self.height() - margin_top - margin_bottom) / len(FINGER_ROWS)

        painter.setPen(QColor(55, 65, 70))
        painter.drawText(12, 22, "力向量时间轴")
        painter.setPen(QColor(210, 218, 224))
        for i, name in enumerate(FINGER_ROWS):
            y = margin_top + row_h * (i + 0.5)
            painter.drawLine(margin_left, int(y), margin_left + plot_w, int(y))
            painter.setPen(QColor(55, 65, 70))
            painter.drawText(10, int(y + 5), name)
            painter.setPen(QColor(210, 218, 224))

        if not self._frames:
            painter.setPen(QColor(120, 130, 135))
            painter.drawText(self.rect(), Qt.AlignCenter, "等待压力数据")
            return

        view_end_ts = self._view_end_ts if self._view_end_ts is not None else self._latest_timestamp()
        if view_end_ts is None:
            return
        start_ts = view_end_ts - self.window_seconds
        self._visible_samples = self._visible_points(start_ts, view_end_ts, margin_left, plot_w, margin_top, row_h)
        for row_idx, name in enumerate(FINGER_ROWS):
            band_top = margin_top + row_h * row_idx + 6
            band_height = max(18.0, row_h * 0.62)
            band_bottom = band_top + band_height
            painter.setPen(QColor(210, 218, 224))
            painter.drawLine(margin_left, int(band_bottom), margin_left + plot_w, int(band_bottom))
            directional_indices = extract_finger_point_indices(self._frames, name, require_direction=True)
            pad_indices = extract_finger_point_indices(self._frames, name, require_direction=False)
            lanes = timeline_lanes_for_indices(name, directional_indices, pad_indices)
            if not lanes:
                continue
            lane_height = max(8.0, band_height / len(lanes))
            for lane_idx, (zone_name, with_arrow) in enumerate(lanes):
                series = [
                    sample
                    for sample in extract_finger_zone_series(self._frames, name, zone_name)
                    if start_ts <= sample["timestamp"] <= view_end_ts
                ]
                lane_top = band_top + lane_height * lane_idx
                self._draw_curve_layer(
                    painter,
                    name,
                    series,
                    start_ts,
                    margin_left,
                    plot_w,
                    lane_top,
                    max(6.0, lane_height * 0.72),
                    with_arrow,
                )
        self._draw_selected_sample(painter)

    def _latest_timestamp(self):
        if not self._frames:
            return None
        return float(self._frames[-1].get("timestamp", time.time()))

    def _prune_frames(self, latest_timestamp):
        cutoff = float(latest_timestamp) - self.history_seconds
        while self._frames and float(self._frames[0].get("timestamp", 0.0)) < cutoff:
            self._frames.popleft()

    def _draw_curve_layer(self, painter, finger_name, series, start_ts, margin_left, plot_w, band_top, band_height, with_arrow):
        if not series:
            return
        curve_points = []
        for sample in series:
            x = margin_left + ((sample["timestamp"] - start_ts) / self.window_seconds) * plot_w
            y = curve_y_for_pressure(band_top, band_height, sample["normal"])
            curve_points.append(QPointF(x, y))

        curve_color = force_color_for_pressure(finger_name, max(sample["normal"] for sample in series)).darker(155)
        curve_color.setAlpha(235)
        painter.setPen(QPen(curve_color, 2.2))
        painter.setBrush(Qt.NoBrush)
        if len(curve_points) >= 2:
            for idx in range(1, len(curve_points)):
                painter.drawLine(curve_points[idx - 1], curve_points[idx])

        arrow_stride = max(1, len(series) // 120)
        for idx, (sample, point) in enumerate(zip(series, curve_points)):
            if idx % arrow_stride != 0 and idx != len(series) - 1:
                continue
            pressure = pressure_level(sample["normal"], CURVE_NORMAL_MAX)
            marker = force_color_for_pressure(finger_name, sample["normal"])
            marker.setAlpha(max(90, int(marker.alpha() * 0.72)))
            if with_arrow:
                arrow_color = marker.lighter(140)
                arrow_color.setAlpha(max(40, int(255 * ARROW_ALPHA_RATIO)))
                point_color = marker.darker(140)
                point_color.setAlpha(220)
                painter.setPen(QPen(arrow_color, 1.0 + pressure * 2.0, ARROW_PEN_STYLE))
                angle = math.radians(sample["direction_display_deg"])
                marker_radius = marker_radius_for_pressure(sample["normal"])
                if should_draw_arrow(sample["normal"]):
                    arrow_start, end = arrow_segment_for_point(point.x(), point.y(), angle, marker_radius, sample["tangential"])
                    painter.drawLine(arrow_start, end)
                    left_head, right_head = arrow_head_points(end.x(), end.y(), angle)
                    painter.drawLine(end, QPointF(*left_head))
                    painter.drawLine(end, QPointF(*right_head))
                painter.setPen(QPen(point_color, 1))
                painter.setBrush(point_color)
                painter.drawEllipse(point, marker_radius, marker_radius)
            else:
                if PAD_LAYER_DRAW_POINTS:
                    painter.setPen(QPen(marker, 1.0 + pressure * 1.8))
                    painter.setBrush(marker)
                    painter.drawEllipse(point, 2.2 + pressure * 1.4, 2.2 + pressure * 1.4)

    def _visible_points(self, start_ts, view_end_ts, margin_left, plot_w, margin_top, row_h):
        points = []
        for row_idx, name in enumerate(FINGER_ROWS):
            band_top = margin_top + row_h * row_idx + 6
            band_height = max(18.0, row_h * 0.62)
            directional_indices = extract_finger_point_indices(self._frames, name, require_direction=True)
            pad_indices = extract_finger_point_indices(self._frames, name, require_direction=False)
            lanes = timeline_lanes_for_indices(name, directional_indices, pad_indices)
            if not lanes:
                continue
            lane_height = max(8.0, band_height / len(lanes))
            for lane_idx, (zone_name, with_arrow) in enumerate(lanes):
                series = [
                    sample
                    for sample in extract_finger_zone_series(self._frames, name, zone_name)
                    if start_ts <= sample["timestamp"] <= view_end_ts
                ]
                lane_top = band_top + lane_height * lane_idx
                lane_band_height = max(6.0, lane_height * 0.72)
                for sample in series:
                    x = margin_left + ((sample["timestamp"] - start_ts) / self.window_seconds) * plot_w
                    y = curve_y_for_pressure(lane_top, lane_band_height, sample["normal"])
                    frame = self._frame_for_timestamp(sample["timestamp"])
                    points.append(
                        {
                            "frame_ts": sample["timestamp"],
                            "frame": frame,
                            "finger": name,
                            "zone": zone_name,
                            "point_index": sample["point_index"],
                            "normal": sample["normal"],
                            "tangential": sample["tangential"],
                            "direction_display_deg": sample["direction_display_deg"],
                            "x": x,
                            "y": y,
                            "with_arrow": with_arrow,
                        }
                    )
        return points

    def _frame_for_timestamp(self, timestamp):
        selected = None
        for frame in self._frames:
            frame_ts = float(frame.get("timestamp", 0.0))
            if frame_ts <= timestamp:
                selected = frame
            else:
                break
        return selected or (self._frames[-1] if self._frames else None)

    def _draw_selected_sample(self, painter):
        if not self._visible_samples or self._selected_frame_ts is None:
            return
        selected = min(
            self._visible_samples,
            key=lambda sample: abs(sample["frame_ts"] - self._selected_frame_ts),
            default=None,
        )
        if selected is None:
            return
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(38, 122, 140), 2))
        painter.drawEllipse(QPointF(selected["x"], selected["y"]), 7.5, 7.5)

    def _nearest_visible_sample(self, x, y):
        if not self._visible_samples:
            return None
        best = None
        for sample in self._visible_samples:
            distance = math.hypot(float(x) - sample["x"], float(y) - sample["y"])
            if best is None or distance < best["distance"]:
                best = {"distance": distance, "sample": sample}
        if best is None or best["distance"] > 18.0:
            return None
        return best["sample"]

    def _timestamp_for_screen_x(self, x):
        if self._view_end_ts is None:
            return None
        margin_left = 90
        plot_w = max(10, self.width() - margin_left - 20)
        start_ts = self._view_end_ts - self.window_seconds
        ratio = (float(x) - margin_left) / float(plot_w)
        ratio = max(0.0, min(1.0, ratio))
        return start_ts + ratio * self.window_seconds

    def wheelEvent(self, event):
        if not self._frames:
            return
        cursor_ts = self._timestamp_for_screen_x(event.position().x())
        if cursor_ts is None:
            return
        zoom_factor = 0.88 if event.angleDelta().y() > 0 else 1.12
        self.window_seconds = max(
            self._min_window_seconds,
            min(self._max_window_seconds, self.window_seconds * zoom_factor),
        )
        latest_ts = self._latest_timestamp()
        if latest_ts is None:
            return
        start_ts = (self._view_end_ts or latest_ts) - self.window_seconds
        relative = (cursor_ts - start_ts) / max(0.001, self.window_seconds)
        relative = max(0.0, min(1.0, relative))
        self._view_end_ts = cursor_ts + (1.0 - relative) * self.window_seconds
        if self._view_end_ts > latest_ts:
            self._view_end_ts = latest_ts
        self._follow_live = False
        self.update()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._dragging_pan = True
            self._pan_anchor_pos = event.position()
            self._pan_anchor_view_end_ts = self._view_end_ts
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            sample = self._nearest_visible_sample(event.position().x(), event.position().y())
            if sample is not None:
                self._selected_frame_ts = float(sample["frame_ts"])
                self._follow_live = False
                if sample["frame"] is not None:
                    self.sampleSelected.emit(sample["frame"])
                self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging_pan and self._pan_anchor_pos is not None and self._pan_anchor_view_end_ts is not None:
            delta_x = event.position().x() - self._pan_anchor_pos.x()
            margin_left = 90
            plot_w = max(10, self.width() - margin_left - 20)
            seconds_per_pixel = self.window_seconds / float(plot_w)
            shift_seconds = -delta_x * seconds_per_pixel
            self._view_end_ts = self._pan_anchor_view_end_ts + shift_seconds
            latest_ts = self._latest_timestamp()
            if latest_ts is not None and self._view_end_ts > latest_ts:
                self._view_end_ts = latest_ts
            self._follow_live = False
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton and self._dragging_pan:
            self._dragging_pan = False
            self._pan_anchor_pos = None
            self._pan_anchor_view_end_ts = None
            event.accept()
            return
        super().mouseReleaseEvent(event)
