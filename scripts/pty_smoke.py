"""Launch the real Linux terminal application in a bounded test pseudoterminal."""

import argparse
import os
from pathlib import Path
import select
import struct
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("The packaged terminal smoke test requires Linux")
    import fcntl
    import pty
    import termios
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 32, 100, 0, 0))
    environment = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "VIRTUAL_ENV")}
    environment["TERM"] = "xterm-256color"
    output = bytearray()
    with tempfile.TemporaryDirectory(prefix="unsloth-monitor-smoke-") as directory:
        command = [args.executable] if args.executable else [sys.executable, "-m", "unsloth_monitor"]
        command += ["--smoke-test", "--config-dir", directory]
        process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave,
                                   env=environment, start_new_session=True, cwd=directory)
        os.close(slave)
        start = time.monotonic()
        try:
            while process.poll() is None and time.monotonic() - start < 10:
                if select.select([master], [], [], 0.1)[0]:
                    try:
                        chunk = os.read(master, 8192)
                    except OSError:
                        break
                    output.extend(chunk[:max(0, 128 * 1024 - len(output))])
            process.wait(timeout=3)
            if process.returncode:
                raise RuntimeError(f"Terminal smoke failed with code {process.returncode}: {output.decode(errors='replace')}")
            if b"UNSLOTH" not in output.upper():
                raise RuntimeError("No dashboard heading was rendered")
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            os.close(master)
    if args.output:
        args.output.write_bytes(output)
    print("Terminal smoke passed: actual collectors, bounded PTY output, clean exit.")


if __name__ == "__main__":
    main()
