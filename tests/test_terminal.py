"""Portable terminal renderer and keyboard tests; not a real curses session."""

import importlib
import sys
import unicodedata

import pytest

from unsloth_monitor.metrics import Availability, ConnectionSnapshot, ConnectionStatus, HardwareSnapshot, Metric
from unsloth_monitor.settings import Settings
from unsloth_monitor.terminal import TerminalDashboard, format_metric, render_lines


def fixture_hardware():
    return HardwareSnapshot(metrics={
        "gpu_name": Metric.available("Fixture GPU"),
        "gpu_utilization": Metric.available(50, "%", "/fixture/gpu_busy_percent"),
        "gpu_temperature": Metric.available(62.5, "°C"),
        "gpu_power": Metric.available(137.5, "W"),
        "vram_used": Metric.available(5 * 1024**3, "B"),
        "vram_total": Metric.available(16 * 1024**3, "B"),
        "cpu_name": Metric.available("Fixture CPU"),
        "cpu_utilization": Metric.available(12.5, "%"),
        "cpu_temperature": Metric.available(51, "°C"),
        "ram_used": Metric.available(3 * 1024**3, "B"),
        "ram_total": Metric.available(8 * 1024**3, "B"),
        "uptime": Metric.available(24200.5, "s"),
    }, hostname="fixture-host")


def test_renderer_has_no_curses_or_qt_import_dependency(monkeypatch):
    monkeypatch.setitem(sys.modules, "curses", None)
    monkeypatch.setitem(sys.modules, "PySide6", None)
    module = importlib.import_module("unsloth_monitor.terminal")
    assert "UNSLOTH MONITOR" in module.render_lines(None, None, 80, 24)[0]


def test_full_dashboard_in_normal_80_by_24_terminal_contains_actual_units():
    output = "\n".join(render_lines(fixture_hardware(), ConnectionSnapshot(
        status=ConnectionStatus.OFFLINE), 80, 24))
    for expected in ("MODEL", "INFERENCE", "OFFLINE", "GPU: Fixture GPU", "CPU: Fixture CPU",
                     "5.0 GiB / 16.0 GiB", "3.0 GiB / 8.0 GiB", "137.5 W", "06:43:20",
                     "50%", "51 °C", "q quit", "d sources"):
        assert expected in output


def test_unavailable_values_never_look_like_zero_activity():
    output = "\n".join(render_lines(None, None, 80, 24))
    assert "[????????????????]" in output
    assert "0%" not in output
    assert "0.0 GiB" not in output
    assert "Loaded: --" in output
    assert format_metric(Metric(value=42, availability=Availability.STALE)) == "Stale"
    assert format_metric(Metric(availability=Availability.PERMISSION_DENIED)) == "Permission denied"


def test_online_liveness_does_not_fill_inference_metrics():
    connection = ConnectionSnapshot(status=ConnectionStatus.ONLINE, metrics={
        "loaded_model": Metric(availability=Availability.UNSUPPORTED),
        "generation_state": Metric(availability=Availability.UNSUPPORTED),
    })
    output = "\n".join(render_lines(fixture_hardware(), connection, 80, 24))
    assert "ONLINE" in output
    assert "Loaded: Not exposed" in output
    assert "State: Not exposed" in output
    assert "GENERATING" not in output


@pytest.mark.parametrize("width,height", [(0, 24), (80, 0), (1, 1), (10, 3), (28, 12), (80, 24), (120, 40)])
def test_resized_output_stays_within_character_cell_bounds(width, height):
    hardware = fixture_hardware()
    hardware.metrics["gpu_name"] = Metric.available("界" * 100 + "e\u0301" * 100)
    lines = render_lines(hardware, None, width, height)
    assert len(lines) <= height
    for line in lines:
        cells = sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in "WF" else 1
                    for c in line)
        assert cells <= width


def test_narrow_view_can_scroll_to_hardware_and_retains_keys():
    hardware = fixture_hardware()
    initial = "\n".join(render_lines(hardware, None, 42, 12))
    last = "\n".join(render_lines(hardware, None, 42, 12, offset=2000))
    assert "MODEL" in initial
    assert "Uptime: 06:43:20" in last
    assert "q quit" in initial and "q quit" in last


def test_terminal_escape_sequences_and_bidi_controls_are_never_emitted():
    hardware = HardwareSnapshot(metrics={"gpu_name": Metric.available("test\x1b[2J\x07\n\u202eevil")})
    lines = render_lines(hardware, None, 80, 24)
    assert not any(unicodedata.category(char).startswith("C") for line in lines for char in line)


def test_source_view_exposes_timestamp_state_source_and_units():
    hardware = HardwareSnapshot(metrics={"gpu_utilization": Metric.available(
        12, "%", "/sys/fixture/gpu_busy_percent", "Machine-wide GPU activity.")})
    output = "\n".join(render_lines(hardware, None, 80, 24, details=True))
    assert "[available]" in output
    assert "/sys/fixture/gpu_busy_percent" in output
    assert "unit: %" in output
    assert "Machine-wide GPU activity." in output


class FakeCurses:
    class error(Exception):
        pass

    KEY_ENTER, KEY_BACKSPACE, KEY_DOWN, KEY_NPAGE, KEY_UP, KEY_PPAGE, KEY_HOME = range(1000, 1007)

    def __init__(self):
        self.defaults_used = False
        self.echo_disabled = False

    def noecho(self):
        self.echo_disabled = True

    def curs_set(self, value):
        pass

    def use_default_colors(self):
        self.defaults_used = True


class FakeScreen:
    def __init__(self, keys):
        self.keys = iter(keys)
        self.lines = {}
        self.frames = []
        self.size = (24, 80)

    def getmaxyx(self):
        return self.size

    def erase(self):
        self.lines = {}

    def addstr(self, row, column, value):
        assert row < self.size[0]
        self.lines[row] = value

    def refresh(self):
        self.frames.append("\n".join(self.lines.values()))

    def keypad(self, enabled):
        pass

    def timeout(self, milliseconds):
        self.timeout_ms = milliseconds

    def get_wch(self):
        key = next(self.keys, "q")
        if key is None:
            raise FakeCurses.error()
        if isinstance(key, BaseException):
            raise key
        return key


class FakeController:
    def __init__(self):
        self.settings = Settings()
        self.token = ""
        self.quiet = False
        self.closed = 0
        self.refreshed = 0
        self.updates = [(fixture_hardware(), ConnectionSnapshot(status=ConnectionStatus.OFFLINE))]

    def take_updates(self):
        return self.updates.pop(0) if self.updates else (None, None)

    def refresh(self):
        self.refreshed += 1

    def configure(self, settings, token):
        self.settings, self.token = settings, token

    def set_quiet(self, quiet):
        self.quiet = quiet

    def close(self):
        self.closed += 1


def dashboard(keys, on_settings=None):
    screen, controller, curses = FakeScreen(keys), FakeController(), FakeCurses()
    view = TerminalDashboard(screen, controller, curses_module=curses, on_settings=on_settings)
    return view, screen, controller, curses


def test_keyboard_loop_reuses_unchanged_frame_and_preserves_terminal_defaults():
    view, screen, controller, curses = dashboard([None, None, "q"])
    view.run()
    assert len(screen.frames) == 2  # first dashboard and final stopping message
    assert screen.frames[-1] == "Stopping collectors..."
    assert controller.closed == 1
    assert curses.defaults_used and curses.echo_disabled


def test_keys_refresh_quiet_rate_and_source_view_without_losing_readings():
    saved = []
    view, screen, controller, _ = dashboard(["r", "p", "i", "d", FakeCurses.KEY_DOWN, "q"], saved.append)
    view.run()
    assert controller.refreshed == 1
    assert controller.quiet
    assert controller.settings.interval == 10
    assert saved == [controller.settings]
    assert any("SOURCES / UNITS" in frame for frame in screen.frames)
    assert any("fixture/gpu_busy_percent" in frame for frame in screen.frames)


def test_connection_editor_never_echoes_or_saves_token():
    saved = []
    token = "private-token-example"
    keys = ["s", "\x15"] + list("http://localhost:9000/v1") + ["\n"] + list(token) + ["\n", "q"]
    view, screen, controller, _ = dashboard(keys, saved.append)
    view.run()
    assert controller.settings.base_url == "http://127.0.0.1:9000/v1"
    assert controller.token == token
    assert saved == [Settings("http://127.0.0.1:9000/v1", 5)]
    assert all(token not in frame for frame in screen.frames)


def test_cancelled_url_does_not_change_settings():
    view, _, controller, _ = dashboard(["s", "\x15", "x", "\x1b", "q"])
    view.run()
    assert controller.settings == Settings()


def test_invalid_secret_reports_only_fixed_message_and_keeps_old_configuration():
    token = "secret with spaces"
    keys = ["s", "\n"] + list(token) + ["\n", "q"]
    view, screen, controller, _ = dashboard(keys)
    view.run()
    assert controller.token == ""
    assert any("without spaces" in frame for frame in screen.frames)
    assert all(token not in frame for frame in screen.frames)


def test_failed_preference_write_is_session_only_and_never_echoes_error():
    def fail(settings):
        raise OSError("private file path must not be displayed")

    view, screen, controller, _ = dashboard(["i", "q"], fail)
    view.run()
    assert controller.settings.interval == 10
    assert any("could not be saved" in frame for frame in screen.frames)
    assert all("private file path" not in frame for frame in screen.frames)


def test_unexpected_view_failure_still_closes_controller():
    view, _, controller, _ = dashboard([RuntimeError("fixture failure")])
    with pytest.raises(RuntimeError):
        view.run()
    assert controller.closed == 1


def test_auto_quit_closes_without_entering_keyboard_loop():
    view, _, controller, _ = dashboard([])
    view.run(quit_after=0)
    assert controller.closed == 1


def test_scrolling_past_end_does_not_require_many_up_keys_to_move_back():
    view, screen, _, _ = dashboard([FakeCurses.KEY_UP, "q"])
    screen.size = (12, 42)
    view.offset = 2000
    view.run()
    assert view.offset < 100
    assert screen.frames[0] != screen.frames[1]
