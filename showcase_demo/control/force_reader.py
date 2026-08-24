from control.force_vectors import FORCE_NAMES, TACS_3D_FORCE, summarize_force_frame
from control.vendor_paths import install_vendor_paths

install_vendor_paths()

from heat_map_dot import HeatMapDot  # noqa: E402
import roh_registers_v2 as registers  # noqa: E402


PALM_INDEX = 5


class ForceReader:
    def __init__(self, rs485, sub_model):
        self.rs485 = rs485
        self.heatmap_dot = HeatMapDot(sub_model)
        self.heatmap_dot.init_dot_info()

    @property
    def sensor_type(self):
        return self.heatmap_dot.SENSOR_TYPE

    @property
    def max_force(self):
        return self.heatmap_dot.MAX_FORCE

    @property
    def force_points_left(self):
        return self.heatmap_dot.LEFT_FORCE_POINT

    def reset_force(self):
        self.rs485.write_registers(registers.ROH_RESET_FORCE, 1)

    def read_raw_by_name(self):
        raw_by_name = {}
        for sensor_id, name in enumerate(FORCE_NAMES):
            reg_cnt = self.heatmap_dot.FORCE_VALUE_LENGTH[sensor_id]
            values = self.rs485.read_registers(
                registers.ROH_FINGER_FORCE_EX0 + sensor_id * registers.FORCE_GROUP_SIZE,
                reg_cnt,
            )
            if self.sensor_type == TACS_3D_FORCE and sensor_id != PALM_INDEX:
                raw_by_name[name] = [self._swap_u16(value) for value in values]
            else:
                expanded = []
                for value in values:
                    expanded.append((value >> 8) & 0xFF)
                    expanded.append(value & 0xFF)
                raw_by_name[name] = expanded
        return raw_by_name

    def read_summary(self):
        return summarize_force_frame(self.read_raw_by_name(), self.sensor_type)

    @staticmethod
    def _swap_u16(value):
        swapped = ((value & 0xFF) << 8) | ((value >> 8) & 0xFF)
        return 0 if swapped >= 65535 else swapped
