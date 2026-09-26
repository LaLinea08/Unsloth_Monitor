"""Platform boundary: Windows telemetry is deliberately not implemented yet."""

import platform
import socket

from ..metrics import Availability, HardwareSnapshot, Metric


HARDWARE_UNITS = {
    "cpu_name": "", "cpu_utilization": "%", "cpu_temperature": "°C",
    "ram_used": "B", "ram_total": "B", "uptime": "s", "gpu_name": "",
    "gpu_utilization": "%", "vram_used": "B", "vram_total": "B",
    "gpu_temperature": "°C", "gpu_power": "W",
}


class UnsupportedCollector:
    def __init__(self, system: str):
        self.system = system

    def collect(self) -> HardwareSnapshot:
        return HardwareSnapshot(metrics={
            key: Metric(unit=unit, source=f"platform:{self.system}",
                        availability=Availability.UNSUPPORTED,
                        detail="Hardware collection currently requires Linux.")
            for key, unit in HARDWARE_UNITS.items()
        }, hostname=socket.gethostname())

    def close(self):
        pass


def create_collector():
    system = platform.system()
    if system == "Linux":
        from .linux import LinuxCollector
        return LinuxCollector()
    return UnsupportedCollector(system)
