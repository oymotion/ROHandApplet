PORT_KEYWORDS = ("CH340", "USB-SERIAL", "USB Serial", "Serial", "UART", "USB")


def pick_serial_port(ports, forced_port=None):
    if forced_port:
        return forced_port

    ports = list(ports)
    for keyword in PORT_KEYWORDS:
        for port in ports:
            text = f"{getattr(port, 'description', '')} {getattr(port, 'manufacturer', '')} {getattr(port, 'hwid', '')}"
            if keyword.lower() in text.lower():
                return port.device

    return ports[0].device if ports else None
