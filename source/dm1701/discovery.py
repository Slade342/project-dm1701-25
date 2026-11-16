"""Read native USB serial descriptors; firmware capture verifies the board itself."""
def native_lab_port():
    try:
        from serial.tools import list_ports
    except ImportError:
        return None
    ports = [port for port in list_ports.comports() if port.vid == 0x1FC9 and port.pid == 0x0094]
    if len(ports) != 1:
        return None
    return ports[0].device
