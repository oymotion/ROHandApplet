from control.vendor_paths import install_vendor_paths

install_vendor_paths()

from FingerMathURDF import HAND_FingerPosToAngle  # noqa: E402


SDK_POS_MAX = 65535
FOUR_FINGER_SLIDER_MAX = 0.019
THUMB_SLIDER_MAX = 0.010
THUMB_ROOT_MAX = 1.57

JOINT_NAMES = [
    ["th_proximal_link", "th_slider_link", "th_connecting_link", "th_distal_link"],
    ["if_slider_link", "if_slider_abpart_link", "if_proximal_link", "if_distal_link", "if_connecting_link"],
    ["mf_slider_link", "mf_slider_abpart_link", "mf_proximal_link", "mf_distal_link", "mf_connecting_link"],
    ["rf_slider_link", "rf_slider_abpart_link", "rf_proximal_link", "rf_distal_link", "rf_connecting_link"],
    ["lf_slider_link", "lf_slider_abpart_link", "lf_proximal_link", "lf_distal_link", "lf_connecting_link"],
    ["th_root_link"],
]


def clamp(value, low, high):
    return max(low, min(high, value))


def sdk_pos_to_urdf_value(position, max_value):
    ratio = clamp(float(position), 0.0, float(SDK_POS_MAX)) / float(SDK_POS_MAX)
    return ratio * max_value


def sdk_positions_to_urdf_joint_state(positions):
    if len(positions) != 6:
        raise ValueError("AP002 target/actual positions must contain 6 values.")

    slider_values = [
        sdk_pos_to_urdf_value(positions[0], THUMB_SLIDER_MAX),
        sdk_pos_to_urdf_value(positions[1], FOUR_FINGER_SLIDER_MAX),
        sdk_pos_to_urdf_value(positions[2], FOUR_FINGER_SLIDER_MAX),
        sdk_pos_to_urdf_value(positions[3], FOUR_FINGER_SLIDER_MAX),
        sdk_pos_to_urdf_value(positions[4], FOUR_FINGER_SLIDER_MAX),
        sdk_pos_to_urdf_value(positions[5], THUMB_ROOT_MAX),
    ]

    names = []
    values = []
    for finger_id, slider_value in enumerate(slider_values):
        joint_angles = HAND_FingerPosToAngle(finger_id, slider_value)
        names.extend(JOINT_NAMES[finger_id])
        if finger_id == 0:
            values.extend([joint_angles[0], slider_value, joint_angles[1], joint_angles[2]])
        elif finger_id == 5:
            values.append(slider_value)
        else:
            values.append(slider_value)
            values.extend(joint_angles)

    return {"name": names, "position": values}


def sdk_positions_to_urdf_commands(positions):
    joint_state = sdk_positions_to_urdf_joint_state(positions)
    return dict(zip(joint_state["name"], joint_state["position"]))
