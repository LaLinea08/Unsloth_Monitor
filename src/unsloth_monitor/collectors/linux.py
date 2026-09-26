"""Bounded, read-only Linux procfs/sysfs collection; no compute libraries.

Discovery and static readings are cached for the collector's lifetime. Call from
one worker, never the GUI thread. Restart after hardware hotplug/driver changes.
"""

from dataclasses import dataclass
from itertools import islice
import math
from pathlib import Path
import re
import socket

from ..metrics import Availability, HardwareSnapshot, Metric
from . import HARDWARE_UNITS


def _read(path: Path, limit: int = 4096) -> str:
    # Procfs st_size is normally zero; bound the actual read instead.
    with path.open("rb") as stream:
        return stream.read(limit).decode("utf-8", errors="replace").strip()


def _children(path: Path, pattern: str, limit: int = 256) -> list[Path]:
    # Bound enumeration as well as retained paths, without recursive scans.
    return sorted((p for p in islice(path.iterdir(), limit)
                   if re.fullmatch(pattern, p.name)), key=lambda p: p.name)


def _missing(source: Path | str, unit: str, detail: str,
             state: Availability = Availability.UNAVAILABLE) -> Metric:
    return Metric(unit=unit, source=str(source), availability=state, detail=detail)


def _error(path: Path, unit: str, error: Exception) -> Metric:
    state = (Availability.PERMISSION_DENIED if isinstance(error, PermissionError)
             else Availability.UNAVAILABLE)
    detail = ("Permission denied; no privilege escalation attempted."
              if state == Availability.PERMISSION_DENIED
              else "Reading missing, invalid, or no longer accessible.")
    return _missing(path, unit, detail, state)


def _number(path: Path, unit: str, scale: float = 1,
            minimum: float = 0, maximum: float | None = None,
            detail: str = "") -> Metric:
    try:
        # sysfs inputs here are integers; reject fractional/malformed counters.
        raw = int(_read(path, 128))
        value = raw if scale == 1 else raw / scale
        if not math.isfinite(value) or value < minimum:
            raise ValueError("out of range")
        if maximum is not None and value > maximum:
            raise ValueError("out of range")
        return Metric.available(value, unit, str(path), detail)
    except (OSError, ValueError, OverflowError) as exc:
        return _error(path, unit, exc)


@dataclass(frozen=True)
class Sensor:
    path: Path
    label: str


class LinuxCollector:
    def __init__(self, proc_root: Path = Path("/proc"),
                 sys_root: Path = Path("/sys"),
                 pci_ids_paths: tuple[Path, ...] | None = None):
        self.proc = Path(proc_root)
        self.sys = Path(sys_root)
        self.pci_ids_paths = pci_ids_paths if pci_ids_paths is not None else (
            Path("/usr/share/hwdata/pci.ids"), Path("/usr/share/misc/pci.ids"))
        self._ready = False
        self._cpu_previous: tuple[int, ...] | None = None
        self._static: dict[str, Metric] = {}
        self._gpu: Path | None = None
        self._cpu_sensor: Sensor | None = None
        self._gpu_sensor: Sensor | None = None
        self._gpu_power: Path | None = None
        self._cpu_sensor_error: Metric | None = None
        self._gpu_sensor_error: Exception | None = None
        self._hostname = socket.gethostname()

    def _discover(self):
        cpuinfo = self.proc / "cpuinfo"
        try:
            for line in _read(cpuinfo, 65536).splitlines():
                key, _, value = line.partition(":")
                if key.strip() in ("model name", "Hardware") and value.strip():
                    self._static["cpu_name"] = Metric.available(
                        value.strip()[:256], source=str(cpuinfo))
                    break
            else:
                self._static["cpu_name"] = _missing(cpuinfo, "", "CPU name not exposed.")
        except OSError as exc:
            self._static["cpu_name"] = _error(cpuinfo, "", exc)
        self._discover_cpu_sensor()
        self._discover_gpu()
        self._ready = True

    def _discover_cpu_sensor(self):
        hwmon = self.sys / "class/hwmon"
        choices: list[tuple[int, Sensor]] = []
        try:
            for node in _children(hwmon, r"hwmon\d+"):
                try:
                    driver = _read(node / "name", 128)
                    if driver not in ("k10temp", "coretemp", "k8temp"):
                        continue
                    for path in _children(node, r"temp\d+_input"):
                        label_path = path.with_name(path.name.replace("_input", "_label"))
                        try:
                            label = _read(label_path, 128)
                        except OSError:
                            label = "Tctl" if driver == "k10temp" else path.stem
                        priority = (0 if label == "Tdie" else
                                    1 if label.startswith("Package id") else
                                    2 if label == "Tctl" else 3)
                        choices.append((priority, Sensor(path, f"{driver} · {label}")))
                except OSError as exc:
                    if isinstance(exc, PermissionError):
                        self._cpu_sensor_error = _error(node, "°C", exc)
            if choices:
                self._cpu_sensor = min(choices, key=lambda x: x[0])[1]
        except OSError as exc:
            self._cpu_sensor_error = _error(hwmon, "°C", exc)

    def _discover_gpu(self):
        drm = self.sys / "class/drm"
        candidates: list[tuple[int, Path, Metric]] = []
        discovery_error = None
        try:
            for card in _children(drm, r"card\d+"):
                device = card / "device"
                try:
                    if _read(device / "vendor", 32).lower() != "0x1002":
                        continue
                    # VRAM totals are driver memory accounting, not an SMU query.
                    total = _number(device / "mem_info_vram_total", "B")
                    size = total.value if total.availability == Availability.AVAILABLE else -1
                    candidates.append((int(size), device, total))
                except OSError as exc:
                    if isinstance(exc, PermissionError):
                        discovery_error = exc
        except OSError as exc:
            discovery_error = exc
        if not candidates:
            unavailable = (_error(drm, "", discovery_error) if discovery_error else
                           _missing(drm, "", "No supported AMD DRM device found.",
                                    Availability.UNSUPPORTED))
            for key in HARDWARE_UNITS:
                if key.startswith("gpu_") or key.startswith("vram_"):
                    self._static[key] = _missing(
                        unavailable.source, HARDWARE_UNITS[key], unavailable.detail,
                        unavailable.availability)
            return
        _, self._gpu, total = max(candidates, key=lambda x: x[0])
        self._static["vram_total"] = total
        self._static["gpu_name"] = self._gpu_name(self._gpu)
        try:
            nodes = _children(self._gpu / "hwmon", r"hwmon\d+")
            for node in nodes:
                if _read(node / "name", 128) != "amdgpu":
                    continue
                try:
                    label = _read(node / "temp1_label", 128)
                except OSError:
                    label = "temp1"
                self._gpu_sensor = Sensor(node / "temp1_input", f"amdgpu · {label}")
                # Stat checks do not invoke sensor inputs. Average is preferred.
                average = node / "power1_average"
                self._gpu_power = average if average.exists() else node / "power1_input"
                break
        except OSError as exc:
            self._gpu_sensor_error = exc

    def _gpu_name(self, device: Path) -> Metric:
        product = device / "product_name"
        try:
            name = _read(product, 256)
            if name:
                return Metric.available(name, source=str(product))
        except OSError:
            pass
        id_path = device / "device"
        try:
            device_id = _read(id_path, 32).lower().removeprefix("0x")
            if not re.fullmatch(r"[0-9a-f]{4}", device_id):
                raise ValueError("invalid PCI ID")
            for path in self.pci_ids_paths:
                try:
                    # Optional local metadata, read once; no network lookup.
                    vendor = ""
                    for line in _read(path, 4 * 1024 * 1024).splitlines():
                        if re.match(r"^[0-9a-fA-F]{4}  ", line):
                            vendor = line[:4].lower()
                        elif vendor == "1002" and line.startswith(f"\t{device_id}  "):
                            return Metric.available(line[7:].strip()[:256], source=str(path),
                                                    detail=f"PCI 1002:{device_id}; {device}")
                except OSError:
                    continue
            return Metric.available(f"AMD GPU [1002:{device_id}]", source=str(id_path),
                                    detail="PCI identity; marketing name not exposed.")
        except (OSError, ValueError) as exc:
            return _error(id_path, "", exc)

    def _cpu_usage(self) -> Metric:
        path = self.proc / "stat"
        try:
            fields = _read(path, 4096).splitlines()[0].split()
            if fields[0] != "cpu" or len(fields) < 5:
                raise ValueError("aggregate CPU counters missing")
            # guest and guest_nice are already counted in user and nice.
            counters = tuple(int(x) for x in fields[1:9])
            if any(x < 0 for x in counters):
                raise ValueError("negative CPU counter")
            previous, self._cpu_previous = self._cpu_previous, counters
            if previous is None or len(previous) != len(counters):
                return _missing(path, "%", "Waiting for the second CPU sample.",
                                Availability.PENDING)
            delta = tuple(now - old for now, old in zip(counters, previous))
            if any(x < 0 for x in delta) or sum(delta) == 0:
                return _missing(path, "%", "CPU counters reset or have not advanced; rebaselining.",
                                Availability.PENDING)
            idle = delta[3] + (delta[4] if len(delta) > 4 else 0)
            return Metric.available(100 * (sum(delta) - idle) / sum(delta), "%", str(path),
                                    "Whole-machine utilization; idle and iowait excluded.")
        except (OSError, ValueError, IndexError) as exc:
            self._cpu_previous = None
            return _error(path, "%", exc)

    def _memory(self) -> dict[str, Metric]:
        path = self.proc / "meminfo"
        result = {}
        try:
            values = {}
            for line in _read(path, 65536).splitlines():
                key, _, remainder = line.partition(":")
                if key in ("MemTotal", "MemAvailable"):
                    parts = remainder.split()
                    if len(parts) != 2 or parts[1] != "kB":
                        raise ValueError("unexpected memory unit")
                    values[key] = int(parts[0]) * 1024
            total = values["MemTotal"]
            if total <= 0:
                raise ValueError("invalid total memory")
            if "ram_total" not in self._static or self._static["ram_total"].value != total:
                self._static["ram_total"] = Metric.available(total, "B", str(path))
            available = values["MemAvailable"]
            if not 0 <= available <= total:
                raise ValueError("invalid available memory")
            result["ram_used"] = Metric.available(total - available, "B", str(path),
                                                  "MemTotal minus MemAvailable (kernel estimate).")
        except (OSError, ValueError, KeyError) as exc:
            result["ram_used"] = _error(path, "B", exc)
            if "ram_total" not in self._static:
                result["ram_total"] = _error(path, "B", exc)
        if "ram_total" in self._static:
            result["ram_total"] = self._static["ram_total"]
        return result

    def _uptime(self) -> Metric:
        path = self.proc / "uptime"
        try:
            seconds = float(_read(path, 128).split()[0])
            if not math.isfinite(seconds) or seconds < 0:
                raise ValueError("invalid uptime")
            return Metric.available(seconds, "s", str(path), "Time since boot, including suspend.")
        except (OSError, ValueError, IndexError) as exc:
            return _error(path, "s", exc)

    def _gpu_metrics(self) -> dict[str, Metric]:
        if self._gpu is None:
            return {}
        gpu = self._gpu
        result = {"vram_used": _number(gpu / "mem_info_vram_used", "B",
                                      detail="Driver-reported VRAM allocation; all applications.")}
        paths = {
            "gpu_utilization": gpu / "gpu_busy_percent",
            "gpu_temperature": self._gpu_sensor.path if self._gpu_sensor else gpu / "hwmon",
            "gpu_power": self._gpu_power or gpu / "hwmon",
        }
        runtime = gpu / "power/runtime_status"
        try:
            status = _read(runtime, 64)
            if status not in ("active", "unsupported"):
                return result | {key: _missing(path, HARDWARE_UNITS[key],
                    f"Optional GPU sensor skipped: runtime status {status or 'unknown'}.")
                    for key, path in paths.items()}
        except OSError as exc:
            return result | {key: _missing(path, HARDWARE_UNITS[key],
                "Optional GPU sensor skipped: runtime power state cannot be verified.",
                Availability.PERMISSION_DENIED if isinstance(exc, PermissionError)
                else Availability.UNAVAILABLE) for key, path in paths.items()}
        result["gpu_utilization"] = _number(paths["gpu_utilization"], "%", maximum=100,
                                              detail="Machine-wide GPU activity; not inference state.")
        result["gpu_temperature"] = (
            _number(self._gpu_sensor.path, "°C", 1000, minimum=-273.15,
                    detail=self._gpu_sensor.label) if self._gpu_sensor else
            _error(paths["gpu_temperature"], "°C", self._gpu_sensor_error or FileNotFoundError()))
        result["gpu_power"] = (
            _number(self._gpu_power, "W", 1_000_000,
                    detail="GPU/SoC power; includes CPU on APUs. Not whole-computer power.")
            if self._gpu_power else _error(paths["gpu_power"], "W",
                                           self._gpu_sensor_error or FileNotFoundError()))
        return result

    def collect(self) -> HardwareSnapshot:
        if not self._ready:
            self._discover()
        metrics = dict(self._static)
        metrics["cpu_utilization"] = self._cpu_usage()
        metrics["cpu_temperature"] = (
            _number(self._cpu_sensor.path, "°C", 1000, minimum=-273.15,
                    detail=self._cpu_sensor.label + "; Tctl may be a control value, not die temperature.")
            if self._cpu_sensor else self._cpu_sensor_error or
            _missing(self.sys / "class/hwmon", "°C", "No supported CPU temperature sensor found."))
        metrics.update(self._memory())
        metrics["uptime"] = self._uptime()
        metrics.update(self._gpu_metrics())
        return HardwareSnapshot(metrics=metrics, hostname=self._hostname)

    def close(self):
        # No files, child processes or threads retained by this collector.
        pass
