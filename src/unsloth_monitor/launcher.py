"""Open an existing host terminal for manual launches without a TTY.

No shell commands, terminal installation, preferences, or background launcher.
The terminal child owns the normal process lock and monitoring workers.
"""

import configparser
import os
from pathlib import Path
import shutil
import sys


class LaunchError(Exception):
    """A safe, user-facing launch failure without private environment details."""


# Each terminal's remainder-of-argv execution form, never its shell-string form.
_TERMINALS = {
    "konsole": ("--separate", "-e"),
    "gnome-terminal": ("--wait", "--"),
    "xfce4-terminal": ("--disable-server", "--execute"),
    "x-terminal-emulator": ("-e",),
    "kitty": (),
    "alacritty": ("-e",),
    "foot": ("--",),
    "xterm": ("-e",),
}


def kde_terminal(environment: dict[str, str]) -> str:
    """Read only KDE's explicit terminal executable, with bounded config input."""
    configured = environment.get("XDG_CONFIG_HOME", "")
    base = Path(configured) if configured and Path(configured).is_absolute() else Path.home() / ".config"
    path = base / "kdeglobals"
    try:
        if not path.is_file():
            return ""
        with path.open(encoding="utf-8") as stream:
            content = stream.read(65537)
        if len(content) > 65536:
            return ""
        config = configparser.ConfigParser(interpolation=None, strict=False)
        config.read_string(content)
        preferred = config.get("General", "TerminalApplication", fallback="").strip()
        if Path(preferred).name in _TERMINALS:
            return preferred
    except (OSError, UnicodeError, configparser.Error):
        pass
    return ""


def terminal_command(command: list[str], environment: dict[str, str]) -> list[str]:
    """Prefer the desktop's configured launcher, then installed host terminals."""
    search_path = environment.get("PATH", os.defpath)
    configured = shutil.which("xdg-terminal-exec", path=search_path)
    if configured:
        return [configured, "--", *command]

    candidates = []
    # TERMINAL may name an executable (including an absolute path with spaces).
    # Deliberately do not evaluate a shell command or interpret TERM as a program.
    preferred = environment.get("TERMINAL", "")
    if Path(preferred).name in _TERMINALS:
        candidates.append(preferred)
    desktops = environment.get("XDG_CURRENT_DESKTOP", "").upper().split(":")
    if "KDE" in desktops or environment.get("KDE_FULL_SESSION") == "true":
        preference = kde_terminal(environment)
        if preference:
            candidates.append(preference)
        candidates.append("konsole")
    if "GNOME" in desktops:
        candidates.append("gnome-terminal")
    if "XFCE" in desktops:
        candidates.append("xfce4-terminal")
    candidates.extend(("x-terminal-emulator", *_TERMINALS))
    for name in dict.fromkeys(candidates):
        executable = shutil.which(name, path=search_path)
        if executable:
            return [executable, *_TERMINALS[Path(name).name], *command]
    raise LaunchError("No supported terminal was found. Open your usual terminal and run the AppImage there.")


def system_environment(environment: dict[str, str], *, frozen: bool) -> dict[str, str]:
    """Keep the bundled native libraries out of the host terminal process."""
    clean = dict(environment)
    if frozen:
        original = clean.pop("LD_LIBRARY_PATH_ORIG", None)
        if original is None:
            clean.pop("LD_LIBRARY_PATH", None)
        else:
            clean["LD_LIBRARY_PATH"] = original
        # A terminal such as kitty can itself use Python. Do not inject the
        # packaged interpreter's configuration into that system application.
        clean.pop("PYTHONHOME", None)
        clean.pop("PYTHONPATH", None)
        clean["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return clean


def relaunch_command(arguments: list[str], environment: dict[str, str], *, frozen: bool) -> list[str]:
    if frozen:
        image = environment.get("APPIMAGE")
        if image:
            # AppImage's original mount can disappear when the launch process
            # exits. Reopen the outer file so the child owns its own mount.
            if not Path(image).is_absolute() or not Path(image).is_file():
                raise LaunchError("The AppImage could not be found. Run the downloaded file from your terminal.")
            command = [image]
        else:
            # An explicitly extracted bundle has a stable executable path.
            command = [sys.executable]
    else:
        command = [sys.executable, "-m", "unsloth_monitor"]
    return [*command, "--terminal-child", *arguments]


def launch_terminal(arguments: list[str]) -> None:
    """Replace this no-TTY launcher with the host terminal; never start workers."""
    environment = dict(os.environ)
    if not (environment.get("DISPLAY") or environment.get("WAYLAND_DISPLAY")):
        raise LaunchError("No graphical desktop was detected. Open a terminal and run the AppImage there.")
    frozen = bool(getattr(sys, "frozen", False))
    command = relaunch_command(arguments, environment, frozen=frozen)
    clean = system_environment(environment, frozen=frozen)
    if frozen:
        # DBus-based emulators may start the command through an already running
        # server. Pass the reset flag as argv too, so it reaches the new bundle.
        env_executable = shutil.which("env", path=clean.get("PATH", os.defpath))
        if not env_executable:
            raise LaunchError("The system env utility is unavailable. Run the AppImage from your terminal.")
        command = [env_executable, "PYINSTALLER_RESET_ENVIRONMENT=1", *command]
    terminal = terminal_command(command, clean)
    try:
        os.execve(terminal[0], terminal, clean)
    except OSError:
        raise LaunchError("The desktop terminal could not start. Open your terminal and run the AppImage there.") from None
