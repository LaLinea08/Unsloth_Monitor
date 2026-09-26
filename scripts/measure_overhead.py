"""Observe a Linux monitor process tree. No inference requests or benchmarks."""

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time

import psutil


def _cleanup_owned_child(child, master=None, slave=None):
    """Stop only our Popen child; an observed --pid is never passed here."""
    try:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
    finally:
        try:
            if slave is not None:
                os.close(slave)
        finally:
            if master is not None:
                os.close(master)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--quiet", action="store_true", help="Observe explicit 30-second polling mode")
    parser.add_argument("--executable", help="Packaged AppRun/AppImage instead of source")
    parser.add_argument("--pid", type=int, help="Observe an already-running monitor without closing it")
    args = parser.parse_args()
    if args.duration < 10 or args.warmup < 0:
        parser.error("duration must be >=10 seconds and warmup >=0")
    if sys.platform != "linux":
        parser.error("Terminal process observation currently targets Linux")
    if args.pid and (args.executable or args.quiet):
        parser.error("--pid observes the existing process's settings; omit --executable/--quiet")
    import fcntl
    import pty
    import struct
    import termios
    child, master, slave = None, None, None
    environment = dict(os.environ)
    environment["TERM"] = "xterm-256color"
    with tempfile.TemporaryDirectory(prefix="unsloth-monitor-measure-") as config:
        start = time.monotonic()
        memory, startup_memory, samples, seen, peak_processes = [], [], [], {}, 0
        baseline_cpu, baseline_time = None, None
        try:
            if args.pid:
                process = psutil.Process(args.pid)
            else:
                master, slave = pty.openpty()
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 32, 100, 0, 0))
                os.set_blocking(master, False)
                command = [args.executable] if args.executable else [sys.executable, "-m", "unsloth_monitor"]
                command += ["--config-dir", config, "--quit-after", str(args.warmup + args.duration + 3)]
                if args.quiet:
                    command += ["--quiet"]
                child = subprocess.Popen(command, env=environment, stdin=slave, stdout=slave,
                                         stderr=slave, start_new_session=True)
                os.close(slave)
                slave = None
                process = psutil.Process(child.pid)
            while time.monotonic() - start < args.warmup + args.duration:
                if not process.is_running() or (child and child.poll() is not None):
                    raise RuntimeError("Monitor exited before observation finished")
                if master is not None:
                    try:
                        # Discard output; retained samples contain no screen or inference data.
                        for _ in range(16):
                            if not os.read(master, 8192):
                                break
                    except (BlockingIOError, OSError):
                        pass
                members = [process] + process.children(recursive=True)
                peak_processes = max(peak_processes, len(members))
                rss = 0
                for member in members:
                    try:
                        rss += member.memory_info().rss
                        cpu = member.cpu_times()
                        seen[(member.pid, member.create_time())] = cpu.user + cpu.system
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                now = time.monotonic()
                if now - start < args.warmup:
                    startup_memory.append(rss / 1024 ** 2)
                else:
                    if baseline_cpu is None:
                        baseline_cpu, baseline_time = sum(seen.values()), now
                    memory.append(rss / 1024 ** 2)
                    samples.append((now, sum(seen.values())))
                time.sleep(1)
            if child:
                child.wait(timeout=10)
                if child.returncode != 0:
                    raise RuntimeError("Monitor failed to exit cleanly")
        finally:
            _cleanup_owned_child(child, master, slave)
        end_time, end_cpu = samples[-1]
        print(json.dumps({
            "platform": platform.platform(), "observer_python": platform.python_version(),
            "packaged": bool(args.executable), "existing_process": bool(args.pid),
            "synthetic_pty": not bool(args.pid), "quiet_mode": args.quiet if not args.pid else "existing settings",
            "warmup_seconds": args.warmup, "observed_seconds": round(end_time - baseline_time, 2),
            "mean_tree_rss_mib": round(statistics.mean(memory), 2),
            "peak_tree_rss_mib": round(max(memory), 2),
            "first_tree_rss_mib": round(memory[0], 2), "last_tree_rss_mib": round(memory[-1], 2),
            "startup_sampled_peak_rss_mib": round(max(startup_memory, default=0), 2),
            "average_cpu_percent_one_logical_cpu": round((end_cpu - baseline_cpu) / (end_time - baseline_time) * 100, 3),
            "peak_process_count": peak_processes, "clean_exit": True if child else "existing process left running",
            "limitations": "1-second sampling; short-lived helpers may be missed. Observer excluded. "
                           "Synthetic PTY excludes terminal-emulator rendering overhead. An existing terminal "
                           "emulator is outside the monitor process tree. No inference benchmark performed.",
        }, indent=2))


if __name__ == "__main__":
    main()
