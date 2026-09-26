"""Exercise actual Qt lifecycle and process locking with controlled collectors."""

import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QDialog

from unsloth_monitor.app import Controller
from unsloth_monitor.metrics import ConnectionSnapshot, ConnectionStatus, HardwareSnapshot, Metric
from unsloth_monitor.settings import Settings, save_settings
from unsloth_monitor.ui.dashboard import Dashboard, SettingsDialog


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def pump(app, predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


class FakeHardware:
    def __init__(self):
        self.count = 0
        self.closed = threading.Event()

    def collect(self):
        self.count += 1
        return HardwareSnapshot(metrics={"cpu_utilization": Metric.available(self.count, "%")})

    def close(self):
        self.closed.set()


def test_slow_network_does_not_block_hardware_or_qt_and_close_cleans_workers(qt_app, tmp_path, monkeypatch):
    hardware = FakeHardware()
    entered = threading.Event()
    release = threading.Event()
    client_closed = threading.Event()

    class SlowClient:
        def __init__(self, **kwargs):
            pass

        def poll(self):
            entered.set()
            release.wait(3)
            return ConnectionSnapshot(status=ConnectionStatus.OFFLINE)

        def close(self):
            client_closed.set()

    monkeypatch.setattr("unsloth_monitor.app.create_collector", lambda: hardware)
    monkeypatch.setattr("unsloth_monitor.app.UnslothClient", SlowClient)
    window = Dashboard()
    controller = Controller(window, Settings(interval=0.02), tmp_path / "settings.json")
    window.show()
    controller.start()
    try:
        assert pump(qt_app, lambda: entered.is_set() and hardware.count >= 3)
        controller.tick()
        assert window.readings["cpu_utilization"].value.text() != "—"
        assert not client_closed.is_set()
        # The real close event is ignored until workers stop; Qt remains usable.
        window.close()
        assert controller.closing
        assert window.isVisible()
        release.set()
        assert pump(qt_app, lambda: not window.isVisible())
        assert hardware.closed.is_set()
        assert client_closed.is_set()
        assert not controller.hardware.thread.is_alive()
        assert not controller.network.thread.is_alive()
        assert not controller.timer.isActive()
    finally:
        release.set()
        controller.shutdown()
        controller.hardware.thread.join(3)
        controller.network.thread.join(3)
        controller.timer.stop()
        window.allow_close = True
        window.close()


def test_minimize_restore_keeps_old_mailbox_readings_stale(qt_app, tmp_path, monkeypatch):
    monkeypatch.setattr("unsloth_monitor.app.create_collector", FakeHardware)
    window = Dashboard()
    controller = Controller(window, Settings(), tmp_path / "settings.json")
    window.show()
    qt_app.processEvents()
    try:
        window.showMinimized()
        qt_app.processEvents()
        assert not controller.visible
        assert controller.hardware._interval == 30
        assert controller.network._interval == 30
        old = time.time() - 120
        controller.hardware._latest = HardwareSnapshot(
            metrics={"cpu_utilization": Metric.available(17, "%")}, timestamp=old)
        controller.network._latest = (0, ConnectionSnapshot(status=ConnectionStatus.ONLINE,
                                                            timestamp=old))
        controller.tick()
        assert window.readings["cpu_utilization"].value.text() == "—"
        window.showNormal()
        qt_app.processEvents()
        assert controller.visible
        assert controller.hardware._interval == 5
        assert controller.network._interval == 5
        assert window.readings["cpu_utilization"].value.text() == "Stale"
        assert "stale" in window.connection_detail.text()
        assert controller.hardware._wake.is_set()
        assert controller.network._wake.is_set()
    finally:
        controller.timer.stop()
        window.allow_close = True
        window.close()


def test_token_validation_matches_client_and_never_accepts_embedded_spaces(qt_app):
    dialog = SettingsDialog(Settings(), "abc def")
    dialog.validate()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "without spaces" in dialog.error.text()
    dialog.token.setText("abc.def-ghi_123")
    dialog.validate()
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_default_window_fits_readings_and_displays_collector_units(qt_app):
    window = Dashboard()
    window.show_hardware(HardwareSnapshot(metrics={
        "cpu_name": Metric.available("Fixture processor name"),
        "cpu_temperature": Metric.available(51.5, "°C"),
        "gpu_name": Metric.available("Fixture graphics processor"),
        "gpu_power": Metric.available(137.5, "W"),
        "vram_used": Metric.available(5 * 1024**3, "B"),
        "vram_total": Metric.available(16 * 1024**3, "B"),
        "uptime": Metric.available(24200.5, "s"),
    }, hostname="fixture-machine"))
    window.show_connection(ConnectionSnapshot(status=ConnectionStatus.OFFLINE,
        detail="Local endpoint is unreachable or timed out; this does not prove a crash."))
    window.show()
    qt_app.processEvents()
    try:
        assert window.readings["cpu_temperature"].value.text() == "52 °C"
        assert window.readings["gpu_power"].value.text() == "137.5 W"
        assert window.readings["vram_used"].value.text() == "5.0 GiB / 16.0 GiB"
        assert window.readings["uptime"].value.text() == "06:43:20"
        assert window.centralWidget().verticalScrollBar().maximum() == 0
        assert window.centralWidget().horizontalScrollBar().maximum() == 0
    finally:
        window.allow_close = True
        window.close()


def test_real_second_process_is_rejected_and_lock_is_released(tmp_path):
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    config = tmp_path / "app-config"
    # A bound, non-listening loopback port ensures a controlled offline endpoint
    # without probing any user service on the default port.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
        save_settings(config / "settings.json", Settings(f"http://127.0.0.1:{port}/v1"))
        command = [sys.executable, "-m", "unsloth_monitor.app", "--config-dir", str(config)]
        process = subprocess.Popen(command + ["--quit-after", "3"], env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not (config / "instance.lock").exists() and time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail(f"First application exited early: {process.communicate()}")
                time.sleep(0.01)
            assert (config / "instance.lock").exists()
            duplicate = subprocess.run(command + ["--smoke-test"], env=env, capture_output=True,
                                       timeout=8)
            assert duplicate.returncode == 2, duplicate.stderr.decode(errors="replace")
            _, errors = process.communicate(timeout=10)
            assert process.returncode == 0, errors.decode(errors="replace")
            assert not (config / "instance.lock").exists()
            reopened = subprocess.run(command + ["--quit-after", "0.05"], env=env,
                                      capture_output=True, timeout=8)
            assert reopened.returncode == 0, reopened.stderr.decode(errors="replace")
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=5)
