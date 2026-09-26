from datetime import datetime
import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QProgressBar, QPushButton, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget,
)

from unsloth_monitor.metrics import Availability, Metric
from unsloth_monitor.settings import Settings
from unsloth_monitor.integration.client import validate_base_url


STYLE = """
QWidget { background: #171b20; color: #e5e9ed; font-family: 'Segoe UI', 'DejaVu Sans'; font-size: 13px; }
QMainWindow, QScrollArea, #canvas { background: #111418; }
QScrollArea { border: none; }
QFrame#card { border: 1px solid #343b43; border-radius: 3px; }
QLabel { background: transparent; border: none; }
QLabel[role='eyebrow'] { color: #a2aeb9; font-size: 11px; font-weight: 600; }
QLabel[role='value'] { font-size: 22px; font-weight: 600; }
QLabel[role='muted'] { color: #a2aeb9; font-size: 12px; }
QLabel#brand { font-size: 19px; font-weight: 700; letter-spacing: 2px; }
QLabel#status { color: #b4c5d0; font-weight: 600; }
QPushButton { border: 1px solid #4a5661; border-radius: 3px; padding: 7px 12px; }
QPushButton:hover { background: #303941; }
QPushButton:focus { border-color: #77c8b2; }
QLineEdit, QSpinBox { border: 1px solid #4a5661; padding: 6px; }
QProgressBar { border: 0; background: #2d343c; height: 7px; max-height: 7px; }
QProgressBar::chunk { background: #75c9af; }
"""


def label(text: str = "", role: str = "") -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    if role:
        widget.setProperty("role", role)
    return widget


def set_text(widget: QLabel, value: str):
    if widget.text() != value:
        widget.setText(value)


def format_metric(metric: Metric) -> str:
    if metric.availability != Availability.AVAILABLE or metric.value is None:
        return {Availability.PENDING: "Pending", Availability.STALE: "Stale",
                Availability.PERMISSION_DENIED: "Permission denied"}.get(metric.availability, "—")
    value = metric.value
    if isinstance(value, str):
        return value
    if not math.isfinite(value):
        return "—"
    if metric.unit in ("bytes", "B"):
        return f"{value / 1024 ** 3:.1f} GiB"
    if metric.unit in ("seconds", "s"):
        return f"{value:.1f} s"
    if metric.unit in ("°C", "C", "celsius"):
        return f"{value:.0f} °C"
    if metric.unit == "%":
        return f"{value:.0f}%"
    if metric.unit in ("tokens", ""):
        return f"{value:,.0f}" + (" tokens" if metric.unit else "")
    return f"{value:.1f} {metric.unit}"


class Reading(QWidget):
    def __init__(self, title: str, large: bool = False, bar: bool = False):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(label(title, "eyebrow"))
        self.value = label("—", "value" if large else "")
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.value)
        self.bar = None
        if bar:
            self.bar = QProgressBar()
            self.bar.setTextVisible(False)
            self.bar.setRange(0, 100)
            self.bar.setValue(0)
            self.bar.setAccessibleName(title)
            layout.addWidget(self.bar)

    def update_metric(self, metric: Metric, total: Metric | None = None, uptime=False):
        rendered = format_metric(metric)
        if uptime and metric.availability == Availability.AVAILABLE:
            seconds = max(0, int(metric.value))
            days, seconds = divmod(seconds, 86400)
            hours, seconds = divmod(seconds, 3600)
            minutes, seconds = divmod(seconds, 60)
            rendered = (f"{days}d " if days else "") + f"{hours:02}:{minutes:02}:{seconds:02}"
        if total:
            rendered += " / " + format_metric(total)
        set_text(self.value, rendered)
        metrics = [metric] + ([total] if total else [])
        tooltip = "\n".join(f"{m.availability.value} · {m.source or 'No verified source'}\n"
                            f"{datetime.fromtimestamp(m.timestamp).astimezone().isoformat(timespec='seconds')}"
                            f"\n{m.detail}" for m in metrics)
        if self.toolTip() != tooltip:
            self.setToolTip(tooltip)
        if self.bar:
            percent = 0
            if metric.availability == Availability.AVAILABLE and isinstance(metric.value, (int, float)):
                if total and total.availability == Availability.AVAILABLE and total.value:
                    percent = metric.value / total.value * 100
                elif total is None:
                    percent = metric.value
            value = min(100, max(0, round(percent)))
            if self.bar.value() != value:
                self.bar.setValue(value)


class Dashboard(QMainWindow):
    settings_requested = Signal()
    visibility_changed = Signal(bool)
    close_requested = Signal()

    def __init__(self):
        super().__init__()
        self.allow_close = False
        self.setWindowTitle("Unsloth Monitor")
        self.resize(820, 900)
        self.setMinimumSize(460, 460)
        self.setStyleSheet(STYLE)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        canvas = QWidget()
        canvas.setObjectName("canvas")
        layout = QVBoxLayout(canvas)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        heading = QHBoxLayout()
        brand = label("UNSLOTH MONITOR")
        brand.setObjectName("brand")
        heading.addWidget(brand, 1)
        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.settings_requested)
        heading.addWidget(self.settings_button)
        layout.addLayout(heading)
        layout.addWidget(label("PASSIVE TELEMETRY  /  LOCAL MACHINE", "eyebrow"))
        connection = self.card(layout)
        self.status = label("UNSLOTH · CHECKING")
        self.status.setObjectName("status")
        connection.addWidget(self.status)
        self.connection_detail = label("Checking the configured loopback endpoint…", "muted")
        connection.addWidget(self.connection_detail)

        top = QHBoxLayout()
        top.setSpacing(10)
        layout.addLayout(top)
        model = self.card(top)
        inference = self.card(top)
        self.readings = {}
        for key, title, large in [("loaded_model", "LOADED MODEL", True),
                                  ("quantization", "QUANTIZATION", False),
                                  ("context_limit", "CONFIGURED CONTEXT LIMIT", False),
                                  ("backend", "VERIFIED BACKEND", False)]:
            self.add_reading(model, key, title, large)
        for key, title, large in [("generation_state", "INFERENCE STATE", True),
                                  ("output_tps", "OUTPUT TOKENS / SECOND", False),
                                  ("output_tokens", "GENERATED OUTPUT TOKENS", False),
                                  ("request_duration", "REQUEST DURATION", False)]:
            self.add_reading(inference, key, title, large)

        gpu = self.card(layout)
        self.add_reading(gpu, "gpu_name", "GRAPHICS PROCESSOR · MACHINE-WIDE", True)
        self.add_reading(gpu, "gpu_utilization", "GPU UTILIZATION", bar=True)
        self.add_reading(gpu, "vram_used", "DRIVER-REPORTED VRAM", bar=True)
        sensors = QHBoxLayout()
        gpu.addLayout(sensors)
        self.add_reading(sensors, "gpu_temperature", "GPU TEMPERATURE")
        self.add_reading(sensors, "gpu_power", "GPU / SOC POWER")

        system = self.card(layout)
        self.add_reading(system, "cpu_name", "PROCESSOR · MACHINE-WIDE")
        row = QGridLayout()
        row.setSpacing(18)
        system.addLayout(row)
        for index, (key, title) in enumerate([("cpu_utilization", "CPU UTILIZATION"),
                                             ("cpu_temperature", "CPU SENSOR"),
                                             ("ram_used", "SYSTEM RAM"), ("uptime", "SYSTEM UPTIME")]):
            reading = Reading(title)
            self.readings[key] = reading
            row.addWidget(reading, index // 2, index % 2)
        self.footer = label("Waiting for the first hardware snapshot. Hover a reading for its source.", "muted")
        layout.addWidget(self.footer)
        layout.addStretch()
        scroll.setWidget(canvas)
        self.setCentralWidget(scroll)

    def card(self, parent_layout):
        frame = QFrame()
        frame.setObjectName("card")
        box = QVBoxLayout(frame)
        box.setContentsMargins(16, 12, 16, 12)
        box.setSpacing(10)
        parent_layout.addWidget(frame)
        return box

    def add_reading(self, layout, key, title, large=False, bar=False):
        widget = Reading(title, large, bar)
        self.readings[key] = widget
        layout.addWidget(widget)

    def show_hardware(self, snapshot):
        for key, metric in snapshot.metrics.items():
            if key in self.readings:
                total_key = {"vram_used": "vram_total", "ram_used": "ram_total"}.get(key)
                total = snapshot.metrics.get(total_key, Metric()) if total_key else None
                self.readings[key].update_metric(metric, total, uptime=(key == "uptime"))
        stamp = datetime.fromtimestamp(snapshot.timestamp).astimezone().strftime("%H:%M:%S")
        set_text(self.footer, f"Hardware: {snapshot.hostname or 'this machine'} · Updated {stamp} · "
                 "Hover a reading for source and availability.")

    def show_connection(self, snapshot):
        from unsloth_monitor.metrics import ConnectionStatus
        prefix = "UNSLOTH OFFLINE" if snapshot.status == ConnectionStatus.OFFLINE else snapshot.status.value.upper()
        set_text(self.status, prefix)
        set_text(self.connection_detail, snapshot.detail)
        for key in ("loaded_model", "quantization", "context_limit", "backend", "generation_state",
                    "output_tps", "output_tokens", "request_duration"):
            self.readings[key].update_metric(snapshot.metrics.get(key, Metric(detail="Not exposed by a verified interface")))

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.WindowStateChange:
            self.visibility_changed.emit(not self.isMinimized())
        super().changeEvent(event)

    def closeEvent(self, event):
        if self.allow_close:
            event.accept()
        else:
            event.ignore()
            self.close_requested.emit()


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, token: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connection & refresh")
        self.resize(510, 290)
        layout = QFormLayout(self)
        self.url = QLineEdit(settings.base_url)
        self.token = QLineEdit(token)
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.setMaxLength(4096)
        self.interval = QSpinBox()
        self.interval.setRange(2, 15)
        self.interval.setValue(settings.interval)
        self.interval.setSuffix(" seconds")
        layout.addRow("Local API base URL", self.url)
        layout.addRow("Bearer token (this session only)", self.token)
        layout.addRow("Refresh interval", self.interval)
        layout.addRow(label("Loopback endpoints only. Tokens are never saved. Faster refresh increases "
                            "overhead. Minimized polling: 30 seconds. Retry backoff: up to 30 seconds.", "muted"))
        self.error = label("")
        layout.addRow(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def validate(self):
        try:
            validate_base_url(self.url.text())
            if self.interval.value() not in (2, 5, 10, 15):
                raise ValueError("Choose 2, 5, 10 or 15 seconds.")
            if any(ord(c) < 33 or ord(c) > 126 for c in self.token.text()):
                raise ValueError("The token must contain printable ASCII without spaces.")
        except (ValueError, TypeError) as exc:
            set_text(self.error, str(exc))
            return
        self.accept()
