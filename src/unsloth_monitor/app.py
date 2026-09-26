"""Manual launch entry point and bounded worker lifecycle."""

import argparse
from dataclasses import replace
from pathlib import Path
import sys
import threading
import time

from PySide6.QtCore import QLockFile, QStandardPaths, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from unsloth_monitor.collectors import create_collector
from unsloth_monitor.integration.client import UnslothClient
from unsloth_monitor.metrics import Availability, ConnectionSnapshot, ConnectionStatus
from unsloth_monitor.polling import PollWorker
from unsloth_monitor.settings import Settings, load_settings, save_settings
from unsloth_monitor.ui.dashboard import Dashboard, SettingsDialog


class Controller:
    def __init__(self, window, settings, settings_path):
        self.window = window
        self.settings = settings
        self.settings_path = settings_path
        self.token = ""
        self._config_lock = threading.Lock()
        self._revision = 0
        self._client_revision = -1
        self._client = None
        self._last_hardware = None
        self._last_connection = None
        self._hardware_received = time.monotonic()
        self._connection_received = time.monotonic()
        self._hardware_stale = False
        self._connection_stale = False
        self.visible = True
        self.closing = False
        self.collector = create_collector()
        self.hardware = PollWorker("hardware", self.collector.collect, settings.interval,
                                   cleanup=self.collector.close)
        self.network = PollWorker("unsloth", self._poll_network, settings.interval,
                                  retry=lambda result: result[1].status in (
                                      ConnectionStatus.OFFLINE, ConnectionStatus.AUTH_REQUIRED,
                                      ConnectionStatus.UNSUPPORTED), cleanup=self._close_client)
        self.timer = QTimer(window)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.tick)
        window.settings_requested.connect(self.edit_settings)
        window.visibility_changed.connect(self.set_visible)
        window.close_requested.connect(self.shutdown)

    def start(self):
        self.hardware.start()
        self.network.start()
        self.timer.start()

    def _poll_network(self):
        with self._config_lock:
            revision, settings, token = self._revision, self.settings, self.token
        if revision != self._client_revision:
            self._close_client()
            self._client = UnslothClient(base_url=settings.base_url, token=token)
            self._client_revision = revision
        return revision, self._client.poll()

    def _close_client(self):
        if self._client:
            self._client.close()
            self._client = None

    def set_visible(self, visible):
        self.visible = visible
        interval = self.settings.interval if visible else 30
        self.hardware.set_interval(interval, refresh=visible)
        self.network.set_interval(interval, refresh=visible)
        self.timer.setInterval(500 if visible else 5000)
        if visible:
            self.tick()

    def tick(self):
        if self.closing:
            if not self.hardware.thread.is_alive() and not self.network.thread.is_alive():
                self.timer.stop()
                self.window.allow_close = True
                self.window.close()
            return
        if not self.visible:
            return
        hardware = self.hardware.take_latest()
        if hardware is not None:
            self._last_hardware = hardware
            # A result can wait in the one-slot mailbox while minimized. Its
            # observation time, not the time the GUI dequeues it, determines age.
            self._hardware_received = time.monotonic() - max(0, time.time() - hardware.timestamp)
            self._hardware_stale = False
            self.window.show_hardware(hardware)
        network = self.network.take_latest()
        if network is not None and network[0] == self._revision:
            self._last_connection = network[1]
            self._connection_received = time.monotonic() - max(0, time.time() - network[1].timestamp)
            self._connection_stale = False
            self.window.show_connection(network[1])
        if (self._last_hardware and not self._hardware_stale and
                time.monotonic() - self._hardware_received > max(15, self.settings.interval * 3)):
            snapshot = replace(self._last_hardware, metrics={
                key: replace(metric, availability=Availability.STALE)
                if metric.availability == Availability.AVAILABLE else metric
                for key, metric in self._last_hardware.metrics.items()})
            self.window.show_hardware(snapshot)
            self._hardware_stale = True
        if (self._last_connection and not self._connection_stale and
                time.monotonic() - self._connection_received > 40):
            self.window.show_connection(ConnectionSnapshot(
                status=ConnectionStatus.CHECKING, detail="Connection check is stale; retrying."))
            self._connection_stale = True

    def edit_settings(self):
        dialog = SettingsDialog(self.settings, self.token, self.window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = Settings(dialog.url.text().strip(), dialog.interval.value())
        try:
            save_settings(self.settings_path, settings)
        except OSError:
            QMessageBox.warning(self.window, "Preferences", "Preferences could not be saved. "
                                "Changes will still apply for this session.")
        with self._config_lock:
            self.settings, self.token = settings, dialog.token.text()
            self._revision += 1
        self._last_connection = None
        self.window.show_connection(ConnectionSnapshot(detail="Checking updated connection settings…"))
        self.set_visible(not self.window.isMinimized())

    def shutdown(self):
        if self.closing:
            return
        self.closing = True
        self.window.settings_button.setEnabled(False)
        self.window.status.setText("CLOSING · STOPPING COLLECTORS")
        self.hardware.stop()
        self.network.stop()
        self.timer.setInterval(50)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Unsloth Monitor — passive Linux desktop telemetry")
    parser.add_argument("--smoke-test", action="store_true", help="Launch real collectors and close after 3 seconds")
    parser.add_argument("--screenshot", type=Path, help="Save one actual UI screenshot (no demo readings)")
    parser.add_argument("--quit-after", type=float, help="Close after N seconds; for launch/overhead validation")
    parser.add_argument("--minimized", action="store_true", help="Launch minimized for overhead validation")
    parser.add_argument("--config-dir", type=Path, help="Isolated preference directory for automated validation")
    args = parser.parse_args(argv)
    app = QApplication([sys.argv[0]])
    app.setApplicationName("Unsloth Monitor")
    app.setOrganizationName("UnslothMonitor")
    app.setQuitOnLastWindowClosed(True)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "unsloth-monitor.svg")))
    config_dir = args.config_dir or Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        print("Cannot create the application preference directory.", file=sys.stderr)
        return 1
    lock = QLockFile(str(config_dir / "instance.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        if not args.smoke_test:
            QMessageBox.information(None, "Unsloth Monitor", "Another instance is already running, "
                                    "or the application configuration directory cannot be locked.")
        return 2
    settings_path = config_dir / "settings.json"
    window = Dashboard()
    controller = Controller(window, load_settings(settings_path), settings_path)
    controller.start()
    if args.minimized:
        window.showMinimized()
        controller.set_visible(False)
    else:
        window.show()
    if args.screenshot:
        QTimer.singleShot(2500, lambda: window.grab().save(str(args.screenshot)))
    duration = 3 if args.smoke_test else args.quit_after
    if duration is not None:
        QTimer.singleShot(max(1, int(duration * 1000)), controller.shutdown)
    try:
        return app.exec()
    finally:
        for worker in (controller.hardware, controller.network):
            worker.stop()
        for worker in (controller.hardware, controller.network):
            worker.thread.join()
        lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
