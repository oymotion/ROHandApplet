import json
import math
import socket
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from model import PARTS, PressureFrame


def parse_host_port(value: str) -> Tuple[str, int]:
    if ":" not in value:
        raise ValueError("Address must look like host:port")
    host, port_text = value.rsplit(":", 1)
    return host, int(port_text)


class DemoSource:
    def __init__(self):
        self._start = time.monotonic()
        self._phases = [
            ("idle", 1.5),
            ("thumb", 1.8),
            ("index", 1.8),
            ("middle", 1.8),
            ("ring", 1.8),
            ("little", 1.8),
            ("palm", 2.0),
            ("thumb+index", 1.8),
            ("middle+ring", 1.8),
            ("little+palm", 1.8),
            ("all", 2.0),
            ("idle", 1.8),
        ]
        self._phase_total = sum(duration for _name, duration in self._phases)

    def _phase_for_time(self, t: float) -> tuple[str, float]:
        cycle = t % self._phase_total
        cursor = 0.0
        for name, duration in self._phases:
            if cycle <= cursor + duration:
                return name, (cycle - cursor) / max(duration, 1e-6)
            cursor += duration
        return "idle", 0.0

    def _pulse(self, base: float, peak: float, phase: float, width: float = 0.42) -> float:
        envelope = max(0.0, 1.0 - abs(phase - 0.5) / max(width, 1e-6))
        envelope = max(0.0, min(1.0, envelope))
        smooth = 0.5 - 0.5 * math.cos(envelope * math.pi)
        return base + (peak - base) * smooth

    def read(self) -> PressureFrame:
        t = time.monotonic() - self._start
        phase_name, phase_pos = self._phase_for_time(t)

        scores = {
            "thumb": 10.0,
            "index": 10.0,
            "middle": 10.0,
            "ring": 10.0,
            "little": 10.0,
            "palm": 10.0,
        }

        idle_wobble = 12.0 * (0.5 + 0.5 * math.sin(t * 2.2))
        scores["middle"] += idle_wobble * 0.5
        scores["ring"] += idle_wobble * 0.35
        scores["little"] += idle_wobble * 0.25

        if phase_name == "thumb":
            scores["thumb"] = self._pulse(20.0, 1200.0, phase_pos)
        elif phase_name == "index":
            scores["index"] = self._pulse(30.0, 1550.0, phase_pos)
            scores["middle"] += 120.0 * (0.5 + 0.5 * math.sin(t * 2.0))
        elif phase_name == "middle":
            scores["middle"] = self._pulse(40.0, 2200.0, phase_pos)
            scores["index"] += 220.0 * (0.5 + 0.5 * math.sin(t * 1.8))
        elif phase_name == "ring":
            scores["ring"] = self._pulse(30.0, 1750.0, phase_pos)
        elif phase_name == "little":
            scores["little"] = self._pulse(25.0, 1450.0, phase_pos)
        elif phase_name == "palm":
            scores["palm"] = self._pulse(50.0, 2500.0, phase_pos)
            scores["thumb"] += 100.0 * (0.5 + 0.5 * math.sin(t * 2.4))
        elif phase_name == "thumb+index":
            scores["thumb"] = self._pulse(20.0, 1150.0, phase_pos)
            scores["index"] = self._pulse(25.0, 1450.0, phase_pos)
        elif phase_name == "middle+ring":
            scores["middle"] = self._pulse(35.0, 2100.0, phase_pos)
            scores["ring"] = self._pulse(25.0, 1650.0, phase_pos)
        elif phase_name == "little+palm":
            scores["little"] = self._pulse(20.0, 1350.0, phase_pos)
            scores["palm"] = self._pulse(50.0, 2400.0, phase_pos)
        elif phase_name == "all":
            scores["thumb"] = self._pulse(20.0, 1100.0, phase_pos)
            scores["index"] = self._pulse(25.0, 1500.0, phase_pos)
            scores["middle"] = self._pulse(35.0, 2200.0, phase_pos)
            scores["ring"] = self._pulse(25.0, 1750.0, phase_pos)
            scores["little"] = self._pulse(20.0, 1450.0, phase_pos)
            scores["palm"] = self._pulse(40.0, 2600.0, phase_pos)
        else:
            scores["thumb"] += 20.0 * (0.5 + 0.5 * math.sin(t * 1.3))
            scores["index"] += 20.0 * (0.5 + 0.5 * math.sin(t * 1.7 + 0.8))
            scores["middle"] += 20.0 * (0.5 + 0.5 * math.sin(t * 1.1 + 1.6))
            scores["ring"] += 20.0 * (0.5 + 0.5 * math.sin(t * 1.5 + 2.1))
            scores["little"] += 20.0 * (0.5 + 0.5 * math.sin(t * 1.4 + 3.2))
            scores["palm"] += 12.0 * (0.5 + 0.5 * math.sin(t * 1.0))

        return PressureFrame(timestamp=time.time(), scores=scores)


class UdpJsonSource:
    def __init__(self, host: str, port: int):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((host, port))
        self._socket.settimeout(0.01)
        self._last = PressureFrame()

    def read(self) -> PressureFrame:
        try:
            payload, _addr = self._socket.recvfrom(65535)
        except TimeoutError:
            return self._last
        except socket.timeout:
            return self._last

        try:
            data = json.loads(payload.decode("utf-8"))
        except Exception:
            return self._last

        scores = {name: float(data.get("scores", {}).get(name, 0.0)) for name in PARTS}
        self._last = PressureFrame(timestamp=float(data.get("timestamp", time.time())), scores=scores)
        return self._last


@dataclass
class SourceConfig:
    mode: str = "demo"
    udp_host: str = "127.0.0.1"
    udp_port: int = 27182
