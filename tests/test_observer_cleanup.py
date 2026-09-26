"""Inject failed owned children; never launch or signal a real process."""

import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


def load_script(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=["pty_smoke", "measure_overhead"])
def script(request):
    return load_script(request.param)


class OwnedChild:
    def __init__(self, timeout_count):
        self.timeout_count = timeout_count
        self.calls = []

    def poll(self):
        return None

    def terminate(self):
        self.calls.append("terminate")

    def kill(self):
        self.calls.append("kill")

    def wait(self, timeout):
        self.calls.append(("wait", timeout))
        if self.timeout_count:
            self.timeout_count -= 1
            raise subprocess.TimeoutExpired("fixture child", timeout)
        return 0


def test_ignored_termination_escalates_only_owned_child_and_closes_pty(script, monkeypatch):
    closed = []
    monkeypatch.setattr(script, "os", SimpleNamespace(close=closed.append))
    child = OwnedChild(timeout_count=1)
    script._cleanup_owned_child(child, master=101, slave=102)
    assert child.calls == ["terminate", ("wait", 5), "kill", ("wait", 5)]
    assert closed == [102, 101]


def test_pty_closes_even_if_kill_wait_also_times_out(script, monkeypatch):
    closed = []
    monkeypatch.setattr(script, "os", SimpleNamespace(close=closed.append))
    child = OwnedChild(timeout_count=2)
    with pytest.raises(subprocess.TimeoutExpired):
        script._cleanup_owned_child(child, master=101, slave=102)
    assert child.calls == ["terminate", ("wait", 5), "kill", ("wait", 5)]
    assert closed == [102, 101]


def test_graceful_termination_does_not_kill(script, monkeypatch):
    closed = []
    monkeypatch.setattr(script, "os", SimpleNamespace(close=closed.append))
    child = OwnedChild(timeout_count=0)
    script._cleanup_owned_child(child, master=101)
    assert child.calls == ["terminate", ("wait", 5)]
    assert closed == [101]


def install_fake_linux_io(script, monkeypatch, *, pid=None):
    args = argparse.Namespace(executable=None, output=None, duration=10, warmup=0,
                              quiet=False, pid=pid)
    monkeypatch.setattr(script.argparse.ArgumentParser, "parse_args", lambda _self: args)
    monkeypatch.setattr(script, "sys", SimpleNamespace(platform="linux", executable=sys.executable))
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(ioctl=lambda *_args: None))
    monkeypatch.setitem(sys.modules, "termios", SimpleNamespace(TIOCSWINSZ=1))
    monkeypatch.setitem(sys.modules, "pty", SimpleNamespace(openpty=lambda: (101, 102)))
    closed = []
    monkeypatch.setattr(script, "os", SimpleNamespace(
        environ={}, close=closed.append, set_blocking=lambda *_args: None))
    return closed


def test_failed_spawn_still_closes_both_pty_descriptors(script, monkeypatch):
    closed = install_fake_linux_io(script, monkeypatch)

    def fail_spawn(*_args, **_kwargs):
        raise OSError("fixture spawn failure")

    monkeypatch.setattr(script.subprocess, "Popen", fail_spawn)
    with pytest.raises(OSError, match="fixture spawn failure"):
        script.main()
    assert closed == [102, 101]


def test_existing_pid_is_never_terminated_even_when_observation_fails(monkeypatch):
    script = load_script("measure_overhead")
    closed = install_fake_linux_io(script, monkeypatch, pid=123)

    class ExternalProcess:
        def is_running(self):
            raise RuntimeError("fixture observation failure")

        def terminate(self):
            pytest.fail("An observed external process must never be terminated")

        def kill(self):
            pytest.fail("An observed external process must never be killed")

    monkeypatch.setattr(script.psutil, "Process", lambda _pid: ExternalProcess())
    with pytest.raises(RuntimeError, match="fixture observation failure"):
        script.main()
    assert closed == []
