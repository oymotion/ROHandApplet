from dataclasses import dataclass

from control.vendor_paths import install_vendor_paths

install_vendor_paths()

from heat_map_dot import HeatMapDot  # noqa: E402
import roh_registers_v2 as registers  # noqa: E402


@dataclass(frozen=True)
class SensorCapability:
    sub_model: int
    sensor_type: int
    force_value_length: list[int]
    max_force: int

    @property
    def supports_direction(self):
        return self.sensor_type == 1


def read_sensor_capability(rs485):
    manu_data = rs485.read_registers(registers.ROH_MANU_DATA0, 1)[0]
    sub_model = (manu_data >> 8) & 0xFF
    heatmap = HeatMapDot(sub_model)
    heatmap.init_dot_info()
    return SensorCapability(
        sub_model=sub_model,
        sensor_type=heatmap.SENSOR_TYPE,
        force_value_length=list(heatmap.FORCE_VALUE_LENGTH),
        max_force=heatmap.MAX_FORCE,
    )
