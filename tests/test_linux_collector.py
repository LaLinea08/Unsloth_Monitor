"""Procfs/sysfs fixture tests; these do not establish Linux hardware support."""

from pathlib import Path

import pytest

from unsloth_monitor.collectors import HARDWARE_UNITS, create_collector
from unsloth_monitor.collectors.linux import LinuxCollector
from unsloth_monitor.metrics import Availability


def put(root: Path, path: str, value: str | int):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(value), encoding="utf-8")
    return target


@pytest.fixture
def machine(tmp_path):
    proc, sys = tmp_path / "proc", tmp_path / "sys"
    put(proc, "cpuinfo", "processor: 0\nmodel name: Fixture CPU\n")
    put(proc, "stat", "cpu 100 20 30 400 50 10 20 0 90 10\ncpu0 0 0 0 0\n")
    put(proc, "meminfo", "MemTotal: 16000000 kB\nMemAvailable: 6000000 kB\n")
    put(proc, "uptime", "24200.50 83210.1\n")
    put(sys, "class/hwmon/hwmon7/name", "k10temp")
    put(sys, "class/hwmon/hwmon7/temp1_label", "Tctl")
    put(sys, "class/hwmon/hwmon7/temp1_input", "61000")
    put(sys, "class/hwmon/hwmon7/temp2_label", "Tdie")
    put(sys, "class/hwmon/hwmon7/temp2_input", "51000")
    # card0 is a different vendor; display connectors must not match cardN.
    put(sys, "class/drm/card0/device/vendor", "0x8086")
    put(sys, "class/drm/card0-DP-1/device/vendor", "0x1002")
    put(sys, "class/drm/card0-DP-1/device/mem_info_vram_total", 100 * 1024**3)
    gpu = sys / "class/drm/card3/device"
    for path, value in {
        "vendor": "0x1002", "device": "0xabcd", "product_name": "Fixture GPU",
        "mem_info_vram_total": 16 * 1024**3, "mem_info_vram_used": 5 * 1024**3,
        "gpu_busy_percent": 42, "power/runtime_status": "active",
        "hwmon/hwmon8/name": "amdgpu", "hwmon/hwmon8/temp1_input": 62500,
        "hwmon/hwmon8/temp1_label": "edge", "hwmon/hwmon8/power1_average": 137500000,
    }.items():
        put(gpu, path, value)
    return proc, sys, gpu


def collector(machine):
    proc, sys, _ = machine
    return LinuxCollector(proc, sys, pci_ids_paths=())


def test_units_sources_and_real_baseline_interval(machine):
    c = collector(machine)
    initial = c.collect().metrics
    assert set(initial) == set(HARDWARE_UNITS)
    assert initial["cpu_utilization"].availability == Availability.PENDING
    assert initial["cpu_utilization"].value is None
    assert initial["cpu_name"].value == "Fixture CPU"
    assert initial["cpu_temperature"].value == 51
    assert "Tdie" in initial["cpu_temperature"].detail
    assert initial["ram_total"].value == 16000000 * 1024
    assert initial["ram_used"].value == 10000000 * 1024
    assert initial["uptime"].value == 24200.5
    assert initial["gpu_name"].value == "Fixture GPU"
    assert initial["gpu_utilization"].value == 42
    assert initial["gpu_temperature"].value == 62.5
    assert initial["gpu_power"].value == 137.5
    assert initial["vram_used"].value == 5 * 1024**3
    assert initial["vram_total"].value == 16 * 1024**3
    assert all(metric.source and metric.timestamp > 0 for metric in initial.values())
    assert all(metric.unit == HARDWARE_UNITS[key] for key, metric in initial.items())
    # 40 busy ticks and 60 idle ticks. Large guest increments must not double-count.
    put(machine[0], "stat", "cpu 120 20 40 450 60 15 25 0 190 110\n")
    assert c.collect().metrics["cpu_utilization"].value == pytest.approx(40.0)


def test_counter_reset_no_elapsed_time_and_read_error_rebaseline(machine):
    c = collector(machine)
    c.collect()
    assert c.collect().metrics["cpu_utilization"].availability == Availability.PENDING
    put(machine[0], "stat", "cpu 1 1 1 1 0 0 0 0\n")
    assert c.collect().metrics["cpu_utilization"].availability == Availability.PENDING
    put(machine[0], "stat", "not a cpu counter")
    assert c.collect().metrics["cpu_utilization"].availability == Availability.UNAVAILABLE
    put(machine[0], "stat", "cpu 11 1 1 11 0 0 0 0\n")
    assert c.collect().metrics["cpu_utilization"].availability == Availability.PENDING


def test_iowait_counter_decrease_is_not_a_false_usage_reading(machine):
    c = collector(machine)
    c.collect()
    put(machine[0], "stat", "cpu 120 20 40 450 49 15 25 0\n")
    assert c.collect().metrics["cpu_utilization"].availability == Availability.PENDING


@pytest.mark.parametrize("status", ["suspended", "suspending", "resuming", "error", "unknown", ""])
def test_suspended_gpu_never_reads_optional_sensor_inputs(machine, monkeypatch, status):
    c = collector(machine)
    put(machine[2], "power/runtime_status", status)
    original = Path.open
    forbidden = {"gpu_busy_percent", "temp1_input", "power1_average", "power1_input"}

    def guarded_open(path, *args, **kwargs):
        if path.name in forbidden and machine[2] in path.parents:
            pytest.fail(f"Read suspended GPU input: {path}")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    metrics = c.collect().metrics
    for key in ("gpu_utilization", "gpu_temperature", "gpu_power"):
        assert metrics[key].availability == Availability.UNAVAILABLE
        assert metrics[key].value is None
    assert metrics["ram_used"].availability == Availability.AVAILABLE
    assert metrics["vram_used"].value == 5 * 1024**3


def test_absent_runtime_status_skips_optional_queries(machine):
    (machine[2] / "power/runtime_status").unlink()
    assert collector(machine).collect().metrics["gpu_power"].value is None


def test_runtime_pm_disabled_does_allow_sensors(machine):
    put(machine[2], "power/runtime_status", "unsupported")
    assert collector(machine).collect().metrics["gpu_power"].value == 137.5


def test_denied_sensor_keeps_other_metrics_working(machine, monkeypatch):
    c = collector(machine)
    c.collect()
    original = Path.open

    def deny_sensor(path, *args, **kwargs):
        if path.name == "gpu_busy_percent":
            raise PermissionError("fixture")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_sensor)
    snapshot = c.collect()
    assert snapshot.metrics["gpu_utilization"].availability == Availability.PERMISSION_DENIED
    assert snapshot.metrics["gpu_temperature"].value == 62.5
    assert snapshot.metrics["ram_used"].value == 10000000 * 1024


def test_discovery_denied_is_not_reported_as_unsupported(tmp_path, monkeypatch):
    original = Path.iterdir

    def deny_drm(path):
        if path.name == "drm":
            raise PermissionError("fixture")
        return original(path)

    monkeypatch.setattr(Path, "iterdir", deny_drm)
    metrics = LinuxCollector(tmp_path / "proc", tmp_path / "sys", ()).collect().metrics
    assert metrics["gpu_name"].availability == Availability.PERMISSION_DENIED
    assert metrics["cpu_name"].availability == Availability.UNAVAILABLE


def test_missing_tree_never_falls_back_to_demo(tmp_path):
    metrics = LinuxCollector(tmp_path / "proc", tmp_path / "sys", ()).collect().metrics
    assert set(metrics) == set(HARDWARE_UNITS)
    assert all(m.value is None for m in metrics.values())
    assert metrics["gpu_name"].availability == Availability.UNAVAILABLE


def test_existing_drm_tree_without_supported_vendor_is_unsupported(machine):
    put(machine[2], "vendor", "0x10de")
    assert collector(machine).collect().metrics["gpu_name"].availability == Availability.UNSUPPORTED


@pytest.mark.parametrize("value", ["nan", "inf", "-1", "broken", ""])
def test_invalid_uptime_never_becomes_a_real_value(machine, value):
    put(machine[0], "uptime", value)
    assert collector(machine).collect().metrics["uptime"].availability == Availability.UNAVAILABLE


def test_missing_memavailable_is_not_guessed_from_free_memory(machine):
    put(machine[0], "meminfo", "MemTotal: 16000000 kB\nMemFree: 100000 kB\n")
    metrics = collector(machine).collect().metrics
    assert metrics["ram_total"].value == 16000000 * 1024
    assert metrics["ram_used"].value is None


def test_gpu_name_uses_local_metadata_and_static_data_are_cached(machine, tmp_path):
    (machine[2] / "product_name").unlink()
    ids = put(tmp_path, "pci.ids", "1002  AMD\n\tabcd  Fixture from PCI database\n8086  Intel\n")
    c = LinuxCollector(machine[0], machine[1], (ids,))
    first = c.collect().metrics
    assert first["gpu_name"].value == "Fixture from PCI database"
    put(machine[0], "cpuinfo", "model name: changed\n")
    ids.unlink()
    second = c.collect().metrics
    assert second["cpu_name"] is first["cpu_name"]
    assert second["gpu_name"] is first["gpu_name"]
    assert second["vram_total"] is first["vram_total"]


def test_gpu_without_marketing_name_uses_verified_pci_identity(machine):
    (machine[2] / "product_name").unlink()
    assert collector(machine).collect().metrics["gpu_name"].value == "AMD GPU [1002:abcd]"


def test_selects_largest_vram_even_if_card_zero_exists(machine):
    put(machine[1], "class/drm/card1/device/vendor", "0x1002")
    put(machine[1], "class/drm/card1/device/mem_info_vram_total", 512 * 1024**2)
    put(machine[1], "class/drm/card1/device/product_name", "Fixture integrated GPU")
    assert collector(machine).collect().metrics["gpu_name"].value == "Fixture GPU"


@pytest.mark.parametrize("value", ["-1", "101", "nan", "12.5"])
def test_invalid_gpu_percent_is_unavailable(machine, value):
    put(machine[2], "gpu_busy_percent", value)
    assert collector(machine).collect().metrics["gpu_utilization"].availability == Availability.UNAVAILABLE


def test_non_linux_factory_is_an_explicit_unsupported_platform(monkeypatch):
    monkeypatch.setattr("unsloth_monitor.collectors.platform.system", lambda: "Windows")
    c = create_collector()
    assert all(m.availability == Availability.UNSUPPORTED for m in c.collect().metrics.values())
    c.close()
