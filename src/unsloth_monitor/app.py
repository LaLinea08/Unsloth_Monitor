"""Manual terminal launch, user preferences, and Linux process-instance locking."""

import argparse
import os
from pathlib import Path
import signal
import sys

from unsloth_monitor.instance import SingleInstance
from unsloth_monitor.launcher import LaunchError, launch_terminal
from unsloth_monitor.runtime import Monitor
from unsloth_monitor.settings import load_settings, save_settings


def configuration_directory() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(configured) if configured and Path(configured).is_absolute() else Path.home() / ".config"
    return base / "unsloth-monitor"


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Unsloth Monitor — passive dashboard inside your terminal")
    parser.add_argument("--smoke-test", action="store_true", help="Use actual collectors and exit after 3 seconds")
    parser.add_argument("--quit-after", type=float, help="Exit after N seconds for validation")
    parser.add_argument("--config-dir", type=Path, help="Isolated preference directory for validation")
    parser.add_argument("--quiet", action="store_true", help="Start with 30-second polling")
    parser.add_argument("--terminal-child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(arguments)
    if sys.platform != "linux":
        print("The terminal dashboard currently targets Linux. Windows support is planned later.", file=sys.stderr)
        return 1
    if args.quit_after is not None and not 0 < args.quit_after <= 86400:
        parser.error("--quit-after must be greater than zero and at most 86400 seconds")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        if args.terminal_child:
            print("The desktop terminal did not provide an interactive console. "
                  "Open your normal terminal and run the AppImage there.", file=sys.stderr)
            return 1
        try:
            launch_terminal(arguments)
        except LaunchError as error:
            print(str(error), file=sys.stderr)
            return 1
        return 0
    config_dir = args.config_dir or configuration_directory()
    try:
        config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        instance = SingleInstance(config_dir / "instance.lock")
        if not instance.acquire():
            print("Unsloth Monitor is already running with this configuration.", file=sys.stderr)
            return 2
    except OSError:
        print("Cannot create or lock the application preference directory.", file=sys.stderr)
        return 1
    settings_path = config_dir / "settings.json"
    monitor = Monitor(load_settings(settings_path))
    monitor.set_quiet(args.quiet)
    shutdown_signals = (signal.SIGTERM, signal.SIGHUP)
    previous_handlers = {item: signal.getsignal(item) for item in shutdown_signals}

    def stop_on_signal(signum, frame):
        raise KeyboardInterrupt

    for item in shutdown_signals:
        signal.signal(item, stop_on_signal)
    try:
        from unsloth_monitor.terminal import run_dashboard
        monitor.start()
        run_dashboard(monitor, quit_after=3 if args.smoke_test else args.quit_after,
                      on_settings=lambda settings: save_settings(settings_path, settings))
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        # Raw exceptions may contain private endpoint or terminal details.
        print("The terminal interface could not run. Check that TERM describes your terminal "
              "and that its terminfo entry is available.", file=sys.stderr)
        return 1
    finally:
        monitor.close()
        instance.release()
        for item, handler in previous_handlers.items():
            signal.signal(item, handler)


if __name__ == "__main__":
    raise SystemExit(main())
