"""Observe the monitor process tree; never sends inference requests.

Run with the development environment (psutil is a dev-only dependency).
Measurement output goes to stdout only; it contains no settings or tokens.
"""

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--offscreen", action="store_true")
    parser.add_argument("--minimized", action="store_true")
    parser.add_argument("--executable", help="Packaged AppRun or AppImage path instead of source launch")
    args = parser.parse_args()
    if args.duration < 10 or args.warmup < 0:
        parser.error("duration must be >=10 seconds and warmup >=0")
    environment = dict(os.environ)
    if args.offscreen:
        environment["QT_QPA_PLATFORM"] = "offscreen"
    with tempfile.TemporaryDirectory(prefix="unsloth-monitor-measure-") as config:
        command = [args.executable] if args.executable else [sys.executable, "-m", "unsloth_monitor"]
        command += ["--config-dir", config, "--quit-after", str(args.warmup + args.duration + 3)]
        if args.minimized:
            command += ["--minimized"]
        start = time.monotonic()
        child = subprocess.Popen(command, env=environment, stdout=subprocess.DEVNULL)
        process = psutil.Process(child.pid)
        memory, startup_memory, samples, seen, peak_processes = [], [], [], {}, 0
        baseline_cpu, baseline_time = None, None
        try:
            while time.monotonic() - start < args.warmup + args.duration:
                if child.poll() is not None:
                    raise RuntimeError("Monitor exited before observation finished")
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
                elapsed = now - start
                if elapsed < args.warmup:
                    startup_memory.append(rss / 1024 ** 2)
                else:
                    if baseline_cpu is None:
                        baseline_cpu, baseline_time = sum(seen.values()), now
                    memory.append(rss / 1024 ** 2)
                    samples.append((now, sum(seen.values())))
                time.sleep(1)
            child.wait(timeout=10)
            if child.returncode != 0:
                raise RuntimeError("Monitor failed to exit cleanly")
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
        end_time, end_cpu = samples[-1]
        print(json.dumps({
            "platform": platform.platform(), "python": platform.python_version(),
            "packaged": bool(args.executable), "offscreen": args.offscreen,
            "minimized": args.minimized, "warmup_seconds": args.warmup,
            "observed_seconds": round(end_time - baseline_time, 2),
            "mean_tree_rss_mib": round(statistics.mean(memory), 2),
            "peak_tree_rss_mib": round(max(memory), 2),
            "first_tree_rss_mib": round(memory[0], 2), "last_tree_rss_mib": round(memory[-1], 2),
            "startup_sampled_peak_rss_mib": round(max(startup_memory, default=0), 2),
            "average_cpu_percent_one_logical_cpu": round((end_cpu - baseline_cpu) / (end_time - baseline_time) * 100, 3),
            "peak_process_count": peak_processes, "clean_exit": True,
            "limitations": "1-second observer sampling; short-lived helpers may be missed. "
                           "Observer excluded. Offscreen and non-Linux runs do not establish Linux visible overhead. "
                           "No inference benchmark performed.",
        }, indent=2))


if __name__ == "__main__":
    main()
