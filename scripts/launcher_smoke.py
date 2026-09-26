"""Exercise no-TTY -> host-terminal handoff using a Linux PTY terminal stand-in.

This verifies real source or packaged child startup, argument preservation, and
clean worker exit. It does not certify a graphical desktop or terminal emulator.
"""

import argparse
import os
from pathlib import Path
import select
import signal
import struct
import subprocess
import sys
import tempfile
import time

from pty_smoke import _cleanup_owned_child


def emulate_terminal(arguments):
    """Only the private fixture executable calls this entrypoint."""
    import fcntl
    import pty
    import termios

    if not arguments or arguments[0] != "--":
        raise RuntimeError("Expected the xdg-terminal-exec argument boundary")
    child_command = arguments[1:]
    if "--terminal-child" not in child_command:
        raise RuntimeError("Missing recursion guard")
    master, slave, process = None, None, None
    output = bytearray()

    def interrupted(_signal, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    try:
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 32, 100, 0, 0))
        environment = dict(os.environ, TERM="xterm-256color")
        process = subprocess.Popen(child_command, stdin=slave, stdout=slave, stderr=slave,
                                   env=environment, start_new_session=True)
        os.close(slave)
        slave = None
        deadline = time.monotonic() + 20
        while process.poll() is None and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    chunk = os.read(master, 8192)
                except OSError:
                    break
                output.extend(chunk[:max(0, 128 * 1024 - len(output))])
        process.wait(timeout=3)
        if process.returncode:
            raise RuntimeError(f"Dashboard child exited with code {process.returncode}")
        if b"UNSLOTH" not in output.upper():
            raise RuntimeError("No dashboard heading was rendered after desktop handoff")
    finally:
        _cleanup_owned_child(process, master, slave)
    Path(os.environ["UNSLOTH_LAUNCHER_SMOKE_OUTPUT"]).write_bytes(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--appimage", action="store_true",
                        help="Use AppImage extract-and-run to test outer-file relaunch without FUSE")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("The terminal launcher smoke test requires Linux")
    if args.appimage and not args.executable:
        parser.error("--appimage requires --executable")
    script = str(Path(__file__).resolve())
    with tempfile.TemporaryDirectory(prefix="unsloth launcher smoke ") as directory:
        root = Path(directory)
        fixture = root / "xdg-terminal-exec"
        fixture.write_text(
            f"#!{sys.executable}\nimport os, sys\n"
            f"os.execv({sys.executable!r}, [{sys.executable!r}, {script!r}, "
            "'--emulate-terminal', *sys.argv[1:]])\n", encoding="utf-8")
        fixture.chmod(0o700)
        capture = root / "capture.txt"
        config = root / "settings with spaces ; literal"
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("PYTHONPATH", "VIRTUAL_ENV", "APPIMAGE", "APPDIR")}
        environment.update({"PATH": str(root) + os.pathsep + os.environ.get("PATH", os.defpath),
                            "WAYLAND_DISPLAY": "smoke-fixture-no-display-connection",
                            "UNSLOTH_LAUNCHER_SMOKE_OUTPUT": str(capture)})
        if args.appimage:
            environment["APPIMAGE_EXTRACT_AND_RUN"] = "1"
        command = [str(args.executable.resolve())] if args.executable else [sys.executable, "-m", "unsloth_monitor"]
        command.extend(("--smoke-test", "--config-dir", str(config)))
        process = None
        try:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, env=environment, cwd=root)
            output, _ = process.communicate(timeout=30)
            if process.returncode:
                raise RuntimeError(f"Desktop handoff failed ({process.returncode}): "
                                   f"{output[:8192].decode(errors='replace')}")
        finally:
            _cleanup_owned_child(process)
        if not capture.is_file() or not (config / "instance.lock").is_file():
            raise RuntimeError("Desktop handoff did not run the child with its original arguments")
        # The child really exited and released its kernel-managed instance lock.
        import fcntl
        with (config / "instance.lock").open("r+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.output:
            args.output.write_bytes(capture.read_bytes())
    print("Desktop handoff smoke passed: no initial TTY, argument preservation, real collectors, clean child exit.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--emulate-terminal":
        emulate_terminal(sys.argv[2:])
    else:
        main()
