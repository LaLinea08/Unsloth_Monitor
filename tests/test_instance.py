import os
import subprocess
import sys

import pytest

from unsloth_monitor.instance import SingleInstance


@pytest.mark.skipif(sys.platform != "linux", reason="Linux flock lifecycle")
def test_kernel_lock_blocks_second_process_and_releases(tmp_path):
    lock = SingleInstance(tmp_path / "instance.lock")
    assert lock.acquire()
    script = "from pathlib import Path; from unsloth_monitor.instance import SingleInstance; import sys; lock=SingleInstance(Path(sys.argv[1])); sys.exit(0 if lock.acquire() else 2)"
    command = [sys.executable, "-c", script, str(lock.path)]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src")
    assert subprocess.run(command, env=environment, timeout=5).returncode == 2
    lock.release()
    assert subprocess.run(command, env=environment, timeout=5).returncode == 0
    lock.release()
