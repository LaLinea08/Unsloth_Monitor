"""Terminal-native dashboard using the terminal palette and default background.

Curses is imported only when launching the interactive view. Pure rendering and
fixture tests therefore also run on hosts without a curses implementation.
"""

from datetime import datetime
import os
import math
import time
import unicodedata

from .integration.client import validate_base_url
from .metrics import Availability, Metric
from .settings import Settings


def _safe(value, limit=512):
    """Never send terminal control characters from a reading to the terminal."""
    return "".join(" " if unicodedata.category(char).startswith("C") else char
                   for char in str(value)[:limit])


def _cells(char):
    if unicodedata.combining(char):
        return 0
    return 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1


def _fit(value, width, pad=False):
    result, used = [], 0
    for char in _safe(value, 4096):
        size = _cells(char)
        if used + size > width:
            break
        result.append(char)
        used += size
    return "".join(result) + (" " * max(0, width - used) if pad else "")


def _wrap(value, width):
    """Bounded wrapping for source details, including wide Unicode characters."""
    if width <= 0:
        return []
    lines, current, used = [], [], 0
    for char in _safe(value):
        size = _cells(char)
        if used + size > width and current:
            lines.append("".join(current))
            current, used = [], 0
        if size <= width:
            current.append(char)
            used += size
    return lines + (["".join(current)] if current else [])


def format_metric(metric: Metric) -> str:
    if metric.availability != Availability.AVAILABLE or metric.value is None:
        return {Availability.PENDING: "Pending", Availability.STALE: "Stale",
                Availability.PERMISSION_DENIED: "Permission denied",
                Availability.UNSUPPORTED: "Unsupported"}.get(metric.availability, "--")
    value = metric.value
    if isinstance(value, str):
        return _safe(value)
    try:
        if not math.isfinite(value):
            return "--"
    except (TypeError, OverflowError):
        return "--"
    if metric.unit in ("bytes", "B"):
        return f"{value / 1024 ** 3:.1f} GiB"
    if metric.unit in ("seconds", "s"):
        return f"{value:.1f} s"
    if metric.unit in ("°C", "C", "celsius"):
        return f"{value:.0f} °C"
    if metric.unit == "%":
        return f"{value:.0f}%"
    if metric.unit == "operations":
        return f"{value:,.0f}"
    if metric.unit in ("tokens", ""):
        return f"{value:,.0f}" + (" tokens" if metric.unit else "")
    return f"{value:.1f} {_safe(metric.unit, 32)}"


def _value(metrics, key, inference=False):
    metric = metrics.get(key, Metric())
    if inference and metric.availability == Availability.UNSUPPORTED:
        return "Not exposed"
    return format_metric(metric)


def _bar(metric, width=18, total=None):
    percent = None
    if metric.availability == Availability.AVAILABLE and isinstance(metric.value, (int, float)):
        if total is None:
            percent = metric.value
        elif (total.availability == Availability.AVAILABLE
              and isinstance(total.value, (int, float)) and total.value > 0):
            percent = metric.value / total.value * 100
    if percent is None or not math.isfinite(percent):
        return "[" + "--".center(width) + "]"
    filled = round(min(100, max(0, percent)) / 100 * width)
    return "[" + "█" * filled + "·" * (width - filled) + "]"


def _uptime(metric):
    if (metric.availability != Availability.AVAILABLE
            or not isinstance(metric.value, (int, float)) or not math.isfinite(metric.value)):
        return format_metric(metric)
    days, seconds = divmod(max(0, int(metric.value)), 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return (f"{days}d " if days else "") + f"{hours:02}:{minutes:02}:{seconds:02}"


def _layout(width):
    # Avoid stretching related values across an ultrawide terminal.
    gutter = 2 if width >= 44 else 0
    return max(0, min(100, width - gutter * 2)), gutter


def _body_lines(hardware, connection, width):
    hw = hardware.metrics if hardware else {}
    api = connection.metrics if connection else {}
    bar_width = min(20, max(4, width // 5))
    lines = [
        "",
        f"GPU  {_value(hw, 'gpu_name')}",
        f"  Load  {_bar(hw.get('gpu_utilization', Metric()), bar_width)}  "
        f"{_value(hw, 'gpu_utilization')}",
        f"  VRAM  {_bar(hw.get('vram_used', Metric()), bar_width, hw.get('vram_total', Metric()))}  "
        f"{_value(hw, 'vram_used')} / {_value(hw, 'vram_total')}",
    ]
    sensors = [f"Temp {_value(hw, 'gpu_temperature')}",
               f"GPU/SoC power {_value(hw, 'gpu_power')}"]
    lines.extend(["  " + "   ·   ".join(sensors)] if width >= 60
                 else ["  " + item for item in sensors])
    lines += [
        "",
        f"SYSTEM  {_value(hw, 'cpu_name')}",
        f"  CPU   {_bar(hw.get('cpu_utilization', Metric()), bar_width)}  "
        f"{_value(hw, 'cpu_utilization')}",
        f"  RAM   {_bar(hw.get('ram_used', Metric()), bar_width, hw.get('ram_total', Metric()))}  "
        f"{_value(hw, 'ram_used')} / {_value(hw, 'ram_total')}",
    ]
    system = [f"CPU temp {_value(hw, 'cpu_temperature')}",
              f"Uptime: {_uptime(hw.get('uptime', Metric()))}"]
    lines.extend(["  " + "   ·   ".join(system)] if width >= 60
                 else ["  " + item for item in system])
    lines += ["", "UNSLOTH"]
    fields = (
        ("active_requests", "In-flight operations"), ("active_model", "Active model labels"),
        ("loaded_model", "Loaded model"), ("quantization", "Quantization"),
        ("context_limit", "Context limit"), ("backend", "Backend"),
        ("generation_state", "Generation state"), ("output_tps", "Output rate"),
        ("output_tokens", "Output count"), ("request_duration", "Duration"),
    )
    shown = [(key, label) for key, label in fields if key in api
             and api[key].availability in (Availability.AVAILABLE, Availability.STALE)]
    if shown:
        for key, label in shown:
            lines.extend("  " + part for part in _wrap(
                f"{label}: {_value(api, key, True)}", max(1, width - 2)))
        if any(key == "active_requests" for key, _ in shown):
            lines.extend("  " + part for part in _wrap(
                "Tracked operations include loading, queue and tool phases.",
                max(1, width - 2)))
        if len(shown) < len(fields):
            lines.extend("  " + part for part in _wrap(
                "Other model/inference details unavailable. Press d for sources.",
                max(1, width - 2)))
    else:
        if api.get("active_requests", Metric()).availability == Availability.PERMISSION_DENIED:
            lines.extend("  " + part for part in _wrap(
                "Activity needs a Studio token or API key. Press s to enter it locally.",
                max(1, width - 2)))
        message = ("Model and inference details are not exposed by this connection."
                   if connection and connection.status.value.startswith("online")
                   else "Model and inference details unavailable.")
        lines.extend("  " + part for part in _wrap(message, max(1, width - 2)))
        lines.extend("  " + part for part in _wrap(
            "Press d for individual fields, sources and availability.", max(1, width - 2)))
    return lines


def _detail_lines(hardware, connection, width):
    lines = ["SOURCES / UNITS / OBSERVATION TIME / STATE"]
    for heading, snapshot in (("HARDWARE (machine-wide)", hardware), ("UNSLOTH", connection)):
        lines += ["", heading]
        if heading.startswith("HARDWARE") and snapshot and snapshot.hostname:
            lines.extend(_wrap(f"Host: {_safe(snapshot.hostname)}", width))
        if snapshot is None:
            lines.append("Waiting for the first snapshot.")
            continue
        for key, metric in snapshot.metrics.items():
            stamp = datetime.fromtimestamp(metric.timestamp).astimezone().isoformat(timespec="seconds")
            lines.extend(_wrap(f"{key}: {format_metric(metric)} [{metric.availability.value}]", width))
            lines.extend(_wrap(f"source: {metric.source or 'No verified source'}", width))
            lines.extend(_wrap(f"unit: {metric.unit or '(text)'} | {stamp}", width))
            if metric.detail:
                lines.extend(_wrap(metric.detail, width))
            lines.append("")
    return lines


def render_lines(hardware, connection, width: int, height: int, *, details=False,
                 offset=0, quiet=False, interval=5, message="") -> list[str]:
    """Render a bounded viewport without curses, terminal escapes, or fake values."""
    width, height = max(0, min(int(width), 1000)), max(0, min(int(height), 500))
    if width == 0 or height == 0:
        return []
    content_width, gutter = _layout(width)
    state = connection.status.value.upper() if connection else "CHECKING"
    header = f"UNSLOTH MONITOR  |  {state}"
    mode = "quiet 30s" if quiet else f"refresh {interval}s"
    detail = (connection.detail if connection else "Checking local Unsloth…") or "Local Unsloth"
    if connection and connection.status.value.startswith("online"):
        detail = f"Local Unsloth connected  ·  {mode}"
    if height == 1:
        return [_fit(header, width)]
    if height < 5:
        return [_fit(line, width) for line in [header, detail, "q quit | r refresh"][:height]]
    body = (_detail_lines(hardware, connection, content_width) if details
            else _body_lines(hardware, connection, content_width))
    room = height - 4
    offset = max(0, min(int(offset), max(0, len(body) - room)))
    visible = body[offset:offset + room]
    footer = "q quit  r refresh  s settings  i rate  p quiet  d sources"
    if content_width < 65:
        footer = "q quit  r  s  i  p  d sources"
    stamp = (datetime.fromtimestamp(hardware.timestamp).astimezone().strftime("%H:%M:%S")
             if hardware else "waiting")
    note = message or f"{mode}  ·  hardware: this computer  ·  updated {stamp}"
    if offset or len(body) > room:
        note = message or f"{mode}  ·  rows {offset + 1}-{offset + len(visible)}/{len(body)}  ·  ↑↓ scroll"
    frame = [header, detail] + visible + [""] * max(0, room - len(visible)) + [footer, note]
    return [" " * gutter + _fit(line, content_width) for line in frame[:height]]


def terminal_palette(curses):
    """Use ANSI slots owned by the terminal, never change its palette/background."""
    bold = getattr(curses, "A_BOLD", 0)
    dim = getattr(curses, "A_DIM", 0)
    palette = {"heading": bold, "good": bold, "warning": bold, "bad": bold,
               "meter": 0, "memory": 0, "muted": dim}
    try:
        if not curses.has_colors():
            return palette
        curses.start_color()
        curses.use_default_colors()
        if "NO_COLOR" in os.environ:
            return palette
        for number, (role, color) in enumerate((
                ("heading", curses.COLOR_CYAN), ("good", curses.COLOR_GREEN),
                ("warning", curses.COLOR_YELLOW), ("bad", curses.COLOR_RED),
                ("meter", curses.COLOR_CYAN), ("memory", curses.COLOR_MAGENTA)), start=1):
            if number >= curses.COLOR_PAIRS or color >= curses.COLORS:
                continue
            curses.init_pair(number, color, -1)
            palette[role] |= curses.color_pair(number)
    except (curses.error, AttributeError):
        # Limited terminals retain the full dashboard, with text/bold cues.
        pass
    return palette


def line_role(line):
    """Roles are presentation hints only; state is always printed as text."""
    text = line.lstrip()
    if text.startswith(("UNSLOTH MONITOR", "GPU  ", "SYSTEM  ", "CONNECTION SETTINGS",
                        "HARDWARE (", "SOURCES /")) or text == "UNSLOTH":
        return "heading"
    if text.startswith(("Load  [", "CPU   [")):
        return "meter"
    if text.startswith(("VRAM  [", "RAM   [")):
        return "memory"
    if text.startswith(("q quit", "refresh ", "quiet ", "Local Unsloth", "Press d ",
                        "Other model/", "Model and inference", "Tracked operations",
                        "source:", "unit:")):
        return "muted"
    return ""


class TerminalDashboard:
    def __init__(self, stdscr, controller, *, curses_module=None, on_settings=None):
        if curses_module is None:
            import curses as curses_module
        self.curses = curses_module
        self.screen = stdscr
        self.controller = controller
        self.on_settings = on_settings
        self.hardware = None
        self.connection = None
        self.details = False
        self.offset = 0
        self.message = ""
        self.previous = None
        self.deadline = None
        self.palette = {}

    def _dimensions(self):
        height, width = self.screen.getmaxyx()
        # Leave the final column free: writing the bottom-right curses cell can
        # raise after drawing it. A racing terminal resize is handled below.
        return max(0, width - 1), max(0, height)

    def _draw(self, lines, force=False):
        size = self.screen.getmaxyx()
        frame = (size, tuple(lines))
        if not force and frame == self.previous:
            return
        self.screen.erase()
        for row, line in enumerate(lines[:size[0]]):
            try:
                shown = _fit(line, max(0, size[1] - 1))
                self.screen.addstr(row, 0, shown, self.palette.get(line_role(shown), 0))
                if shown.lstrip().startswith("UNSLOTH MONITOR") and " | " in shown:
                    start = shown.index("|") + 3
                    state = shown[start:]
                    role = ("good" if state.startswith("ONLINE") else
                            "bad" if state.startswith("OFFLINE") else "warning")
                    column = sum(_cells(char) for char in shown[:start])
                    self.screen.addstr(row, column, state, self.palette.get(role, 0))
            except self.curses.error:
                # The terminal can resize between getmaxyx and a write.
                pass
        self.screen.refresh()
        self.previous = frame

    def _key(self):
        try:
            return self.screen.get_wch()
        except self.curses.error:
            return None

    def _expired(self):
        return self.deadline is not None and time.monotonic() >= self.deadline

    def _edit(self, title, initial, maximum, secret=False):
        value = list(initial[:maximum])
        try:
            self.curses.curs_set(0 if secret else 1)
        except self.curses.error:
            pass
        try:
            while not self._expired():
                width, height = self._dimensions()
                shown = "(input hidden)" if secret else "".join(value)[-max(1, width - 2):]
                lines = ["CONNECTION SETTINGS", title, "", shown, "",
                         "Enter: accept | Esc: cancel | Ctrl-U: clear | Backspace: erase"]
                if secret:
                    lines.append("Token stays in memory; it is never displayed or saved.")
                self._draw([_fit(line, width) for line in lines[:height]])
                key = self._key()
                if key in ("\n", "\r", self.curses.KEY_ENTER):
                    return "".join(value)
                if key in ("\x1b", "\x03"):
                    return None
                if key == "\x15":
                    value.clear()
                elif key in ("\b", "\x7f", self.curses.KEY_BACKSPACE):
                    if value:
                        value.pop()
                elif isinstance(key, str) and len(key) == 1 and 32 <= ord(key) <= 126:
                    if len(value) < maximum:
                        value.append(key)
            return None
        finally:
            try:
                self.curses.curs_set(0)
            except self.curses.error:
                pass
            self.previous = None

    def _save(self, settings, token):
        try:
            self.controller.configure(settings, token)
        except (ValueError, OSError):
            self.message = "Settings were rejected. Check the local URL and token format."
            return False
        self.message = "Settings applied. Token is session-only."
        if self.on_settings:
            try:
                self.on_settings(settings)
            except OSError:
                self.message = "Settings apply to this session; preferences could not be saved."
        return True

    def _settings(self):
        url = self._edit("Local API URL (HTTP loopback only)", self.controller.settings.base_url, 2048)
        if url is None:
            return
        try:
            url = validate_base_url(url)
        except (ValueError, TypeError):
            self.message = "Use a local HTTP URL such as http://127.0.0.1:8888/v1."
            return
        token = self._edit("Bearer token (Enter keeps existing; Ctrl-U clears)",
                           self.controller.token, 4096, secret=True)
        if token is None:
            return
        if any(ord(char) < 33 or ord(char) > 126 for char in token):
            self.message = "Token must contain printable ASCII without spaces."
            return
        self._save(Settings(url, self.controller.settings.interval), token)

    def run(self, quit_after=None):
        self.deadline = None if quit_after is None else time.monotonic() + max(0, quit_after)
        self.screen.keypad(True)
        self.screen.timeout(500)
        self.curses.noecho()
        try:
            self.curses.curs_set(0)
        except self.curses.error:
            pass
        self.palette = terminal_palette(self.curses)
        try:
            while not self._expired():
                # Input still wakes immediately; quiet mode reduces idle UI wakeups.
                self.screen.timeout(2000 if self.controller.quiet else 500)
                hardware, connection = self.controller.take_updates()
                if hardware is not None:
                    self.hardware = hardware
                if connection is not None:
                    self.connection = connection
                width, height = self._dimensions()
                content_width, _ = _layout(width)
                body = (_detail_lines(self.hardware, self.connection, content_width) if self.details
                        else _body_lines(self.hardware, self.connection, content_width))
                self.offset = min(self.offset, max(0, len(body) - max(0, height - 4)))
                self._draw(render_lines(self.hardware, self.connection, width, height,
                    details=self.details, offset=self.offset, quiet=self.controller.quiet,
                    interval=self.controller.settings.interval, message=self.message))
                key = self._key()
                if key in ("q", "Q", "\x03"):
                    break
                if key in ("r", "R"):
                    self.controller.refresh()
                    self.message = "Refresh requested."
                elif key in ("p", "P"):
                    self.controller.set_quiet(not self.controller.quiet)
                    self.message = "Quiet mode: 30-second polling." if self.controller.quiet else "Normal polling restored."
                elif key in ("d", "D"):
                    self.details = not self.details
                    self.offset, self.message = 0, ""
                elif key in ("s", "S"):
                    self._settings()
                elif key in ("i", "I"):
                    intervals = (2, 5, 10, 15)
                    current = self.controller.settings.interval
                    interval = intervals[(intervals.index(current) + 1) % len(intervals)] if current in intervals else 5
                    if self._save(Settings(self.controller.settings.base_url, interval), self.controller.token):
                        self.message += f" Refresh {interval}s; faster polling increases overhead."
                elif key in (self.curses.KEY_DOWN, self.curses.KEY_NPAGE):
                    self.offset = min(2000, self.offset + (1 if key == self.curses.KEY_DOWN else max(1, height - 4)))
                elif key in (self.curses.KEY_UP, self.curses.KEY_PPAGE):
                    self.offset = max(0, self.offset - (1 if key == self.curses.KEY_UP else max(1, height - 4)))
                elif key == self.curses.KEY_HOME:
                    self.offset = 0
        except KeyboardInterrupt:
            pass
        finally:
            try:
                self._draw(["Stopping collectors..."], force=True)
            except self.curses.error:
                pass
            finally:
                self.controller.close()


def run_dashboard(controller, quit_after=None, on_settings=None):
    try:
        import curses
        return curses.wrapper(lambda screen: TerminalDashboard(
            screen, controller, curses_module=curses, on_settings=on_settings).run(quit_after))
    finally:
        # Also cover terminal initialization/import failures. close is idempotent.
        controller.close()
