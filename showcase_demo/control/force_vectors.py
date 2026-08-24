from dataclasses import asdict, dataclass


FINGER_NAMES = ("thumb", "index", "middle", "ring", "little")
FORCE_NAMES = (*FINGER_NAMES, "palm")
TACS_DOT_MATRIX = 0
TACS_3D_FORCE = 1


@dataclass(frozen=True)
class ForceVectorPoint:
    finger: str
    point_index: int
    normal: float
    tangential: float
    direction_raw_deg: float
    direction_display_deg: float

    def to_dict(self):
        return asdict(self)


def decode_3d_force_points(values, finger_name):
    points = []
    triplet_count = len(values) // 3
    for point_index in range(triplet_count):
        base = point_index * 3
        normal = float(values[base])
        tangential = float(values[base + 1])
        direction_raw = float(values[base + 2])
        points.append(
            ForceVectorPoint(
                finger=finger_name,
                point_index=point_index,
                normal=normal,
                tangential=tangential,
                direction_raw_deg=direction_raw,
                direction_display_deg=direction_raw - 90.0,
            )
        )
    return points


def summarize_force_frame(raw_by_name, sensor_type):
    fingers = {}
    totals = {}
    for name in FORCE_NAMES:
        values = list(raw_by_name.get(name, []))
        if sensor_type == TACS_3D_FORCE and name != "palm":
            points = decode_3d_force_points(values, name)
            fingers[name] = [point.to_dict() for point in points]
            totals[name] = {
                "normal": sum(point.normal for point in points),
                "tangential": sum(point.tangential for point in points),
            }
        else:
            fingers[name] = [{"point_index": idx, "normal": float(value)} for idx, value in enumerate(values)]
            totals[name] = {"normal": sum(float(value) for value in values), "tangential": 0.0}

    return {"sensor_type": sensor_type, "fingers": fingers, "totals": totals}
