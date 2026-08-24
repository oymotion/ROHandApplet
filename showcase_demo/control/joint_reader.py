from control.vendor_paths import install_vendor_paths

install_vendor_paths()

import roh_registers_v2 as registers  # noqa: E402


DEFAULT_FINGER_SPEED = 22000
DEFAULT_FINGER_PID_P = 120
DEFAULT_BRAKE_DISTANCE = 512
DEFAULT_ACCEL_DISTANCE = 512
DEFAULT_PID_SPEED_RATIO = 1.0
PID_REGISTER_SCALE = 100
PID_SPEED_RATIO_REGISTER_SCALE = 100
NUM_MOTORS = 6


def read_actual_positions(rs485):
    return rs485.read_registers(registers.ROH_FINGER_POS0, 6)


def write_target_positions(rs485, positions):
    if len(positions) != 6:
        raise ValueError("AP002 target positions must contain 6 values.")
    return rs485.write_registers(registers.ROH_FINGER_POS_TARGET0, positions)


def write_uniform_speed(rs485, speed=DEFAULT_FINGER_SPEED):
    speed = int(max(0, min(65535, int(speed))))
    return rs485.write_registers(registers.ROH_FINGER_SPEED0, [speed] * NUM_MOTORS)


def write_full_speed(rs485):
    return write_uniform_speed(rs485, 65535)


def speed_control_values(
    brake_distance=DEFAULT_BRAKE_DISTANCE,
    accel_distance=DEFAULT_ACCEL_DISTANCE,
    pid_speed_ratio=DEFAULT_PID_SPEED_RATIO,
):
    return [
        int(max(0, min(65535, int(brake_distance)))),
        int(max(0, min(65535, int(accel_distance)))),
        int(
            max(
                0,
                min(
                    65535,
                    round(float(pid_speed_ratio) * PID_SPEED_RATIO_REGISTER_SCALE),
                ),
            )
        ),
    ]


def write_speed_control_params(
    rs485,
    brake_distance=DEFAULT_BRAKE_DISTANCE,
    accel_distance=DEFAULT_ACCEL_DISTANCE,
    pid_speed_ratio=DEFAULT_PID_SPEED_RATIO,
):
    return rs485.write_registers(
        registers.ROH_SPEED_CTRL_BRAKE_DISTANCE,
        speed_control_values(brake_distance, accel_distance, pid_speed_ratio),
    )


def pid_p_values(p_value=DEFAULT_FINGER_PID_P):
    raw_value = int(round(float(p_value) * PID_REGISTER_SCALE))
    return [raw_value] * NUM_MOTORS


def write_position_pid_p(rs485, p_value=DEFAULT_FINGER_PID_P):
    return rs485.write_registers(registers.ROH_FINGER_P0, pid_p_values(p_value))
