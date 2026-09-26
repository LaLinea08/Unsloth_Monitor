#!/usr/bin/env python3
"""Read-only, standard-library diagnostic; run from this source checkout.

No installation, model requests, subprocesses, privileged reads, or files written.
Output is deliberately selected metrics, never raw server response or environment.
"""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8888/v1",
                        help="Loopback HTTP API base URL; no embedded credentials.")
    parser.add_argument("--token-env", metavar="VARIABLE",
                        help="Read an optional bearer token from this environment variable.")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    try:
        from unsloth_monitor.collectors import create_collector
        from unsloth_monitor.integration import UnslothClient
    except ImportError:
        parser.error("Run this script from a complete Unsloth Monitor source checkout using Python 3.11+.")
    token = ""
    if args.token_env:
        token = os.environ.get(args.token_env, "")
        if not token:
            parser.error("The selected token environment variable is empty or unset.")
    try:
        client = UnslothClient(args.base_url, token)
    except ValueError as error:
        parser.error(str(error))
    collector = create_collector()
    try:
        collector.collect()
        baseline = time.monotonic()
        connection = client.poll()
        time.sleep(max(0.0, 1.0 - (time.monotonic() - baseline)))
        hardware = collector.collect()
    finally:
        collector.close()
        client.close()
    os_release = {}
    if platform.system() == "Linux":
        try:
            release = platform.freedesktop_os_release()
            os_release = {key: release[key] for key in ("ID", "VERSION_ID", "PRETTY_NAME")
                          if key in release}
        except OSError:
            pass
    result = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"system": platform.system(), "release": platform.release(),
                        "architecture": platform.machine(), "python": platform.python_version(),
                        "os_release": os_release},
        "hardware": {key: asdict(value) for key, value in hardware.metrics.items()},
        "connection": asdict(connection),
        "limitations": ["Source-verified liveness only; installed Unsloth version is not identified.",
                        "No model, inference content, token counts, or backend details are requested.",
                        "Hardware describes this computer only."],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
