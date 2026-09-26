import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from unsloth_monitor.metrics import Availability, HardwareSnapshot, Metric
from unsloth_monitor.ui.dashboard import Dashboard, format_metric


def test_missing_stale_and_units_are_honest():
    assert format_metric(Metric()) == "—"
    assert format_metric(Metric(value=42, availability=Availability.STALE)) == "Stale"
    assert format_metric(Metric.available(1024 ** 3, "bytes")) == "1.0 GiB"


def test_dashboard_small_window_and_real_snapshot_fields():
    app = QApplication.instance() or QApplication([])
    window = Dashboard()
    window.resize(460, 460)
    window.show()
    window.show_hardware(HardwareSnapshot(metrics={
        "gpu_name": Metric.available("<b>GPU names must be plain text</b>"),
        "gpu_utilization": Metric(availability=Availability.PERMISSION_DENIED),
        "ram_used": Metric.available(1024 ** 3, "bytes"),
        "ram_total": Metric.available(2 * 1024 ** 3, "bytes"),
    }, hostname="fixture"))
    app.processEvents()
    assert window.readings["gpu_utilization"].value.text() == "Permission denied"
    assert window.readings["ram_used"].value.text() == "1.0 GiB / 2.0 GiB"
    assert window.readings["gpu_utilization"].bar.value() == 0
    assert window.centralWidget().horizontalScrollBar().maximum() == 0
    window.allow_close = True
    window.close()
