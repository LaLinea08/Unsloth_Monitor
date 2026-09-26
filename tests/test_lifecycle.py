"""Portable runtime tests: real workers and controlled, test-only collectors."""

from dataclasses import replace
import threading
import time

import pytest

from unsloth_monitor.metrics import (
    Availability, ConnectionSnapshot, ConnectionStatus, HardwareSnapshot, Metric,
)
from unsloth_monitor.runtime import Monitor
from unsloth_monitor.settings import Settings


def wait_until(predicate, timeout=1):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


class FakeHardware:
    def __init__(self):
        self.count = 0
        self.closed = threading.Event()

    def collect(self):
        self.count += 1
        return HardwareSnapshot(metrics={
            "cpu_utilization": Metric.available(self.count, "%", "test fixture")})

    def close(self):
        self.closed.set()


@pytest.fixture
def hardware(monkeypatch):
    collector = FakeHardware()
    monkeypatch.setattr("unsloth_monitor.runtime.create_collector", lambda: collector)
    return collector


def put_result(worker, result):
    with worker._lock:
        worker._latest = result


def test_slow_network_does_not_block_hardware_or_update_reads_and_close_joins(monkeypatch, hardware):
    entered = threading.Event()
    release = threading.Event()
    client_closed = threading.Event()

    class SlowClient:
        def __init__(self, **_kwargs):
            pass

        def poll(self):
            entered.set()
            release.wait(2)
            return ConnectionSnapshot(status=ConnectionStatus.OFFLINE)

        def close(self):
            client_closed.set()
            release.set()

    monkeypatch.setattr("unsloth_monitor.runtime.UnslothClient", SlowClient)
    monitor = Monitor(Settings())
    monitor.start()
    monitor.start()
    try:
        assert entered.wait(1)
        assert wait_until(lambda: hardware.count >= 1)
        for _ in range(3):
            previous = hardware.count
            monitor.refresh()
            assert wait_until(lambda: hardware.count > previous)
        before = time.monotonic()
        sample, _ = monitor.take_updates()
        assert time.monotonic() - before < 0.1
        assert sample.metrics["cpu_utilization"].value >= 3
        assert not client_closed.is_set()
        before = time.monotonic()
        monitor.close()
        assert time.monotonic() - before < 0.5
        assert hardware.closed.is_set() and client_closed.is_set()
        assert not monitor.hardware.thread.is_alive()
        assert not monitor.network.thread.is_alive()
        assert monitor.take_updates() == (None, None)
    finally:
        release.set()
        monitor.close()


def test_old_mailbox_timestamps_are_stale_once_and_values_keep_provenance(hardware):
    monitor = Monitor(Settings())
    old = time.time() - 120
    metric = Metric(value=17, unit="%", source="fixture", timestamp=old,
                    availability=Availability.AVAILABLE)
    try:
        put_result(monitor.hardware, HardwareSnapshot(metrics={"cpu_utilization": metric}, timestamp=old))
        put_result(monitor.network, (0, ConnectionSnapshot(status=ConnectionStatus.ONLINE,
                   metrics={"loaded_model": replace(metric, value="old model", unit="")}, timestamp=old)))
        hardware_sample, connection = monitor.take_updates()
        assert hardware_sample.metrics["cpu_utilization"].availability == Availability.STALE
        assert hardware_sample.metrics["cpu_utilization"].timestamp == old
        assert hardware_sample.metrics["cpu_utilization"].source == "fixture"
        assert hardware_sample.timestamp == old
        assert connection.status == ConnectionStatus.CHECKING
        assert connection.metrics["loaded_model"].availability == Availability.STALE
        assert connection.timestamp == old
        assert "stale" in connection.detail
        assert monitor.take_updates() == (None, None)
    finally:
        monitor.close()


def test_received_sample_becomes_stale_without_a_new_poll(hardware, monkeypatch):
    monitor = Monitor(Settings())
    try:
        sample = hardware.collect()
        put_result(monitor.hardware, sample)
        assert monitor.take_updates()[0] == sample
        observed = time.monotonic()
        monkeypatch.setattr("unsloth_monitor.runtime.time.monotonic", lambda: observed + 16)
        stale, _ = monitor.take_updates()
        assert stale.metrics["cpu_utilization"].availability == Availability.STALE
        assert stale.timestamp == sample.timestamp
        assert monitor.take_updates() == (None, None)
    finally:
        monitor.close()


def test_quiet_mode_uses_30_seconds_and_return_refreshes_both_workers(hardware):
    monitor = Monitor(Settings())
    try:
        assert monitor.hardware._interval == monitor.network._interval == 5
        monitor.set_quiet(True)
        assert monitor.quiet
        assert monitor.hardware._interval == monitor.network._interval == 30
        monitor.configure(Settings(interval=10))
        assert monitor.hardware._interval == monitor.network._interval == 30
        monitor.hardware._wake.clear()
        monitor.network._wake.clear()
        monitor.set_quiet(False)
        assert not monitor.quiet
        assert monitor.hardware._interval == monitor.network._interval == 10
        assert monitor.hardware._wake.is_set() and monitor.network._wake.is_set()
    finally:
        monitor.close()


def test_quiet_sample_does_not_expire_before_its_next_expected_collection(hardware):
    monitor = Monitor(Settings())
    monitor.set_quiet(True)
    try:
        timestamp = time.time() - 25
        put_result(monitor.hardware, HardwareSnapshot(metrics={
            "cpu_utilization": Metric.available(1, "%")}, timestamp=timestamp))
        sample, _ = monitor.take_updates()
        assert sample.metrics["cpu_utilization"].availability == Availability.AVAILABLE
        monitor.set_quiet(False)
        sample, _ = monitor.take_updates()
        assert sample.metrics["cpu_utilization"].availability == Availability.STALE
    finally:
        monitor.close()


def test_new_settings_discard_old_inflight_result_and_promptly_start_new_request(monkeypatch, hardware):
    old_entered = threading.Event()
    old_release = threading.Event()
    new_entered = threading.Event()
    new_release = threading.Event()

    class Client:
        def __init__(self, base_url, token):
            self.old = base_url.endswith(":8888/v1")
            self.release = old_release if self.old else new_release

        def poll(self):
            (old_entered if self.old else new_entered).set()
            self.release.wait(2)
            return ConnectionSnapshot(status=ConnectionStatus.ONLINE, metrics={
                "loaded_model": Metric.available("old" if self.old else "new", source="test fixture")})

        def close(self):
            self.release.set()

    monkeypatch.setattr("unsloth_monitor.runtime.UnslothClient", Client)
    monitor = Monitor(Settings())
    monitor.start()
    try:
        assert old_entered.wait(1)
        monitor.take_updates()
        monitor.configure(Settings("http://localhost:9999/v1", 5), "test-only-token")
        assert monitor.settings.base_url == "http://127.0.0.1:9999/v1"
        assert new_entered.wait(1)
        _, connection = monitor.take_updates()
        assert connection.status == ConnectionStatus.CHECKING
        assert not connection.metrics
        assert "test-only-token" not in repr(connection)
        new_release.set()
        received = []

        def got_new():
            connection = monitor.take_updates()[1]
            if connection is not None:
                received.append(connection)
            return bool(received)

        assert wait_until(got_new)
        assert received[-1].metrics["loaded_model"].value == "new"
    finally:
        new_release.set()
        old_release.set()
        monitor.close()
    assert monitor.token == ""


def test_offline_snapshot_replaces_all_prior_online_metrics(hardware):
    monitor = Monitor(Settings())
    try:
        put_result(monitor.network, (0, ConnectionSnapshot(status=ConnectionStatus.ONLINE,
                   metrics={"loaded_model": Metric.available("fixture model")})))
        assert monitor.take_updates()[1].metrics["loaded_model"].value == "fixture model"
        put_result(monitor.network, (0, ConnectionSnapshot(status=ConnectionStatus.OFFLINE,
                   metrics={"loaded_model": Metric(detail="Offline")})))
        connection = monitor.take_updates()[1]
        assert connection.status == ConnectionStatus.OFFLINE
        assert connection.metrics["loaded_model"].value is None
        assert monitor.take_updates() == (None, None)
    finally:
        monitor.close()


@pytest.mark.parametrize("settings, token", [
    (Settings(interval=1), ""), (Settings(interval=True), ""),
    (Settings("http://remote.invalid/v1"), ""),
    (Settings(), "secret contains spaces"), (Settings(), "secret\r\nInjected: yes"),
])
def test_bad_configuration_rejected_without_mutating_live_preferences(hardware, settings, token):
    monitor = Monitor(Settings())
    try:
        with pytest.raises(ValueError) as error:
            monitor.configure(settings, token)
        assert "secret" not in str(error.value)
        assert monitor.settings == Settings()
        assert monitor.token == ""
        assert monitor._revision == 0
    finally:
        monitor.close()


def test_close_before_start_is_idempotent_and_prevents_restarting(hardware):
    monitor = Monitor(Settings(), "test-only-token")
    monitor.close()
    monitor.close()
    monitor.refresh()
    assert hardware.closed.is_set()
    assert monitor.token == ""
    assert not monitor.hardware.thread.is_alive()
    assert not monitor.network.thread.is_alive()
    with pytest.raises(RuntimeError):
        monitor.start()
    with pytest.raises(RuntimeError):
        monitor.configure(Settings())
