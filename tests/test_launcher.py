"""Desktop launch boundaries without launching a real terminal on the test host."""

import io
import sys

import pytest

from unsloth_monitor import app, launcher


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher.Path, "home", lambda: tmp_path)


def installed(monkeypatch, *names):
    monkeypatch.setattr(launcher.shutil, "which", lambda name, **kwargs:
                        f"/host/bin/{name}" if name in names else None)


def test_desktop_default_takes_precedence_and_preserves_arguments(monkeypatch):
    installed(monkeypatch, "xdg-terminal-exec", "konsole")
    command = ["/Downloads/Monitor with spaces.AppImage", "--config-dir", "a;$(literal)"]
    assert launcher.terminal_command(command, {"XDG_CURRENT_DESKTOP": "KDE"}) == [
        "/host/bin/xdg-terminal-exec", "--", *command]


@pytest.mark.parametrize("desktop, name, flags", [
    ("KDE", "konsole", ["--separate", "-e"]),
    ("ubuntu:GNOME", "gnome-terminal", ["--wait", "--"]),
    ("XFCE", "xfce4-terminal", ["--disable-server", "--execute"]),
])
def test_desktop_prefers_its_terminal_over_generic_fallback(monkeypatch, desktop, name, flags):
    installed(monkeypatch, name, "x-terminal-emulator", "xterm")
    assert launcher.terminal_command(["/app"], {"XDG_CURRENT_DESKTOP": desktop}) == [
        f"/host/bin/{name}", *flags, "/app"]


def test_explicit_known_terminal_executable_can_override_desktop(monkeypatch):
    installed(monkeypatch, "kitty", "konsole")
    assert launcher.terminal_command(["/app"], {"TERMINAL": "kitty", "XDG_CURRENT_DESKTOP": "KDE"}) == [
        "/host/bin/kitty", "/app"]


def test_kde_existing_preference_is_read_without_modification(monkeypatch, tmp_path):
    config = tmp_path / "kdeglobals"
    content = "[General]\nTerminalApplication=kitty\nTerminalService=kitty.desktop\n"
    config.write_text(content)
    installed(monkeypatch, "kitty", "konsole")
    assert launcher.terminal_command(["/app"], {
        "XDG_CURRENT_DESKTOP": "KDE", "XDG_CONFIG_HOME": str(tmp_path)}) == ["/host/bin/kitty", "/app"]
    assert config.read_text() == content


@pytest.mark.parametrize("content", ["not config", "[General]\nTerminalApplication=sh -c anything\n",
                                     "[General]\nTerminalApplication=kitty\n" + "#" * 65537],
                         ids=["malformed", "shell-command", "oversized"])
def test_unsupported_or_bad_kde_config_uses_safe_fallback(monkeypatch, tmp_path, content):
    (tmp_path / "kdeglobals").write_text(content)
    installed(monkeypatch, "konsole", "sh")
    assert launcher.terminal_command(["/app"], {
        "XDG_CURRENT_DESKTOP": "KDE", "XDG_CONFIG_HOME": str(tmp_path)}) == [
            "/host/bin/konsole", "--separate", "-e", "/app"]


def test_terminal_preference_with_spaces_is_not_a_shell_string(monkeypatch, tmp_path):
    preferred = str(tmp_path / "terminal tools" / "konsole")
    monkeypatch.setattr(launcher.shutil, "which", lambda name, **kwargs:
                        preferred if name == preferred else None)
    assert launcher.terminal_command(["/app"], {"TERMINAL": preferred}) == [
        preferred, "--separate", "-e", "/app"]


def test_term_is_not_executed_and_shell_terminal_preference_is_ignored(monkeypatch):
    installed(monkeypatch, "xterm", "sh", "xterm-256color")
    assert launcher.terminal_command(["/app"], {"TERMINAL": "sh -c anything", "TERM": "xterm-256color"}) == [
        "/host/bin/xterm", "-e", "/app"]


def test_missing_terminal_returns_actionable_error(monkeypatch):
    installed(monkeypatch)
    with pytest.raises(launcher.LaunchError, match="Open your usual terminal"):
        launcher.terminal_command(["/app"], {})


@pytest.mark.parametrize("original", [None, "", "/system/custom-libs"])
def test_frozen_environment_restores_original_system_libraries(original):
    environment = {"LD_LIBRARY_PATH": "/tmp/mount/bundled", "PYTHONHOME": "/bundled",
                   "PYTHONPATH": "/private", "WAYLAND_DISPLAY": "wayland-0"}
    if original is not None:
        environment["LD_LIBRARY_PATH_ORIG"] = original
    clean = launcher.system_environment(environment, frozen=True)
    assert clean.get("LD_LIBRARY_PATH") == original
    assert "LD_LIBRARY_PATH_ORIG" not in clean
    assert "PYTHONHOME" not in clean and "PYTHONPATH" not in clean
    assert clean["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert clean["WAYLAND_DISPLAY"] == "wayland-0"
    assert environment["LD_LIBRARY_PATH"] == "/tmp/mount/bundled"


def test_source_environment_keeps_developer_runtime():
    environment = {"LD_LIBRARY_PATH": "/custom", "PYTHONPATH": "/checkout/src"}
    assert launcher.system_environment(environment, frozen=False) == environment


def test_frozen_appimage_restarts_outer_file_not_temporary_binary(monkeypatch, tmp_path):
    image = tmp_path / "download with spaces.AppImage"
    image.touch()
    monkeypatch.setattr(launcher.sys, "executable", "/tmp/.mount_old/usr/bin/unsloth-monitor")
    assert launcher.relaunch_command(["--quiet"], {"APPIMAGE": str(image)}, frozen=True) == [
        str(image), "--terminal-child", "--quiet"]


def test_missing_outer_appimage_does_not_restart_temporary_mount(tmp_path):
    with pytest.raises(launcher.LaunchError, match="AppImage could not be found"):
        launcher.relaunch_command([], {"APPIMAGE": str(tmp_path / "gone.AppImage")}, frozen=True)


def test_extracted_bundle_uses_stable_executable(monkeypatch):
    monkeypatch.setattr(launcher.sys, "executable", "/extracted/usr/bin/unsloth-monitor")
    assert launcher.relaunch_command([], {}, frozen=True) == [
        "/extracted/usr/bin/unsloth-monitor", "--terminal-child"]


def test_source_launch_uses_current_python_and_ignores_unrelated_appimage():
    assert launcher.relaunch_command(["--quiet"], {"APPIMAGE": "/unrelated"}, frozen=False) == [
        sys.executable, "-m", "unsloth_monitor", "--terminal-child", "--quiet"]


def test_recursion_guard_precedes_end_of_options_marker():
    assert launcher.relaunch_command(["--"], {}, frozen=False)[-2:] == ["--terminal-child", "--"]


def test_headless_launch_does_not_attempt_an_emulator(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(launcher, "terminal_command", lambda *_args: pytest.fail("must not launch"))
    with pytest.raises(launcher.LaunchError, match="No graphical desktop"):
        launcher.launch_terminal([])


def test_frozen_launch_replaces_process_with_sanitized_host_terminal(monkeypatch, tmp_path):
    image = tmp_path / "image.AppImage"
    image.touch()
    monkeypatch.setattr(launcher.sys, "frozen", True, raising=False)
    monkeypatch.setenv("DISPLAY", ":test")
    monkeypatch.setenv("APPIMAGE", str(image))
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/bundled")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/original")
    installed(monkeypatch, "env", "xdg-terminal-exec")
    captured = []
    monkeypatch.setattr(launcher.os, "execve", lambda *args: captured.append(args))
    launcher.launch_terminal(["--config-dir", "settings with spaces"])
    executable, command, environment = captured[0]
    assert executable == "/host/bin/xdg-terminal-exec"
    assert command == [executable, "--", "/host/bin/env", "PYINSTALLER_RESET_ENVIRONMENT=1",
                       str(image), "--terminal-child", "--config-dir", "settings with spaces"]
    assert environment["LD_LIBRARY_PATH"] == "/original"


def test_terminal_exec_failure_does_not_expose_environment(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":test")
    installed(monkeypatch, "xdg-terminal-exec")

    def fail(*_args):
        raise OSError("sensitive diagnostic")

    monkeypatch.setattr(launcher.os, "execve", fail)
    with pytest.raises(launcher.LaunchError) as error:
        launcher.launch_terminal([])
    assert "sensitive" not in str(error.value)


@pytest.fixture
def no_tty(monkeypatch):
    monkeypatch.setattr(app.sys, "platform", "linux")
    monkeypatch.setattr(app.sys, "stdin", io.StringIO())
    monkeypatch.setattr(app.sys, "stdout", io.StringIO())
    monkeypatch.setattr(app, "Monitor", lambda *_args: pytest.fail("no launcher collectors"))
    monkeypatch.setattr(app, "SingleInstance", lambda *_args: pytest.fail("no launcher lock"))


def test_app_no_tty_hands_off_before_preferences_or_workers(monkeypatch, no_tty, tmp_path):
    config = tmp_path / "not created"
    calls = []
    monkeypatch.setattr(app, "launch_terminal", lambda arguments: calls.append(arguments))
    args = ["--quiet", "--config-dir", str(config)]
    assert app.main(args) == 0
    assert calls == [args]
    assert not config.exists()


def test_child_without_tty_stops_instead_of_recursive_terminals(monkeypatch, no_tty, capsys):
    monkeypatch.setattr(app, "launch_terminal", lambda *_args: pytest.fail("must not recurse"))
    assert app.main(["--terminal-child"]) == 1
    assert "did not provide an interactive console" in capsys.readouterr().err


def test_app_reports_launch_error(monkeypatch, no_tty, capsys):
    def fail(*_args):
        raise launcher.LaunchError("Open your terminal manually.")

    monkeypatch.setattr(app, "launch_terminal", fail)
    assert app.main([]) == 1
    assert "Open your terminal manually" in capsys.readouterr().err


def test_validation_happens_before_desktop_launch(monkeypatch, no_tty):
    monkeypatch.setattr(app, "launch_terminal", lambda *_args: pytest.fail("invalid launch"))
    with pytest.raises(SystemExit) as result:
        app.main(["--quit-after", "-1"])
    assert result.value.code == 2


def test_existing_terminal_skips_launcher(monkeypatch, tmp_path):
    class Tty(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(app.sys, "platform", "linux")
    monkeypatch.setattr(app.sys, "stdin", Tty())
    monkeypatch.setattr(app.sys, "stdout", Tty())
    monkeypatch.setattr(app, "launch_terminal", lambda *_args: pytest.fail("already in terminal"))

    class Duplicate:
        def __init__(self, _path):
            pass

        def acquire(self):
            return False

    monkeypatch.setattr(app, "SingleInstance", Duplicate)
    assert app.main(["--config-dir", str(tmp_path)]) == 2
