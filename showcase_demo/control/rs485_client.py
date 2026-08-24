from dataclasses import dataclass

from pymodbus.client import ModbusSerialClient
from serial.tools import list_ports

from control.serial_port import pick_serial_port


@dataclass
class Rs485Config:
    port: str | None = None
    baudrate: int = 115200
    hand_id: int = 2
    timeout: float = 0.5


class Rs485Client:
    def __init__(self, config: Rs485Config):
        self.config = config
        self.port = pick_serial_port(list_ports.comports(), config.port)
        if not self.port:
            raise RuntimeError("No AP002 RS485 serial port found.")
        self.client = ModbusSerialClient(
            port=self.port,
            baudrate=config.baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=config.timeout,
        )

    def connect(self):
        if not self.client.connect():
            raise RuntimeError(f"Failed to open RS485 serial port: {self.port}")
        return self

    def close(self):
        self.client.close()

    def read_registers(self, address, count):
        response = self.client.read_holding_registers(address, count, slave=self.config.hand_id)
        if response.isError():
            raise RuntimeError(f"Read holding registers failed: address={address}, count={count}, response={response}")
        return list(response.registers)

    def write_registers(self, address, values):
        if isinstance(values, int):
            values = [values]
        response = self.client.write_registers(address, list(values), slave=self.config.hand_id)
        if response.isError():
            raise RuntimeError(f"Write registers failed: address={address}, values={values}, response={response}")
        return True
