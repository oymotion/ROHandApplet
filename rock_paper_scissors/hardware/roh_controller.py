from __future__ import annotations

from pathlib import Path

from pymodbus import FramerType
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
from serial.tools import list_ports

from roh_registers_v2 import ROH_FINGER_POS_TARGET0


GESTURE_POSITIONS = {
    "Neutral": [0, 0, 0, 0, 0, 0],
    "Paper": [0, 0, 0, 0, 0, 0],
    "Rock": [45000, 65535, 65535, 65535, 65535, 0],
    "Scissors": [45000, 0, 0, 65535, 65535, 0],
}


def find_comport(port_name: str) -> str | None:
    for port in list_ports.comports():
        if port_name in port.description:
            return port.device
    return None


class RohController:
    def __init__(self, node_id: int = 2) -> None:
        self.node_id = node_id
        self.client: ModbusSerialClient | None = None
        self.is_connected = False

    def open_port(self, port_keyword: str | None = None) -> bool:
        if port_keyword is None:
            port = find_comport("CH340") or find_comport("USB")
        else:
            port = find_comport(port_keyword)

        if port is None:
            self.client = None
            self.is_connected = False
            return False

        try:
            self.client = ModbusSerialClient(port=port, framer=FramerType.RTU, baudrate=115200, timeout=1)
            if not self.client.connect():
                self.client = None
                self.is_connected = False
                return False
            self.is_connected = True
            return True
        except Exception:
            self.client = None
            self.is_connected = False
            return False

    def close_port(self) -> None:
        if self.client and self.is_connected:
            self.client.close()
        self.is_connected = False

    def _write(self, gesture: str) -> bool:
        if not self.client or gesture not in GESTURE_POSITIONS:
            return False

        try:
            resp = self.client.write_registers(
                ROH_FINGER_POS_TARGET0, GESTURE_POSITIONS[gesture], slave=self.node_id
            )
            return not resp.isError()
        except ModbusException:
            return False

    def set_gesture(self, gesture: str) -> bool:
        return self._write(gesture)

    def set_neutral(self) -> bool:
        return self._write("Neutral")

    def show(self, gesture: str) -> bool:
        return self.set_gesture(gesture)
