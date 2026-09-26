"""UI-independent monitoring lifecycle with one bounded worker per source.

The terminal/CLI calls public methods from its main thread. Blocking hardware
and network work stays in the two workers; no Qt or terminal module is imported.
"""

from dataclasses import replace
import threading
import time

from unsloth_monitor.collectors import create_collector
from unsloth_monitor.integration.client import UnslothClient, validate_base_url
from unsloth_monitor.metrics import (
    Availability, ConnectionSnapshot, ConnectionStatus, HardwareSnapshot,
)
from unsloth_monitor.polling import PollWorker
from unsloth_monitor.settings import Settings


def _validated(settings: Settings, token: str) -> Settings:
    if not isinstance(settings, Settings):
        raise ValueError("Expected monitor connection and interval settings.")
    if type(settings.interval) is not int or settings.interval not in (2, 5, 10, 15):
        raise ValueError("Refresh interval must be 2, 5, 10, or 15 seconds.")
    base_url = validate_base_url(settings.base_url)
    if (not isinstance(token, str) or len(token) > 4096
            or any(ord(char) < 33 or ord(char) > 126 for char in token)):
        raise ValueError("Bearer token must contain only printable ASCII without spaces.")
    return Settings(base_url, settings.interval)


def _stale_metrics(metrics):
    return {
        key: replace(metric, availability=Availability.STALE)
        if metric.availability == Availability.AVAILABLE else metric
        for key, metric in metrics.items()
    }


class Monitor:
    """Shared runtime for an interactive terminal or a one-shot CLI.

    Each take_updates() result replaces the corresponding complete snapshot.
    None means there is no new observation or state transition for that source.
    Settings and bearer tokens are held only in memory here; persistence belongs
    to the entrypoint. Quiet mode is explicit because terminal minimization
    cannot be detected reliably.
    """

    def __init__(self, settings: Settings, token=""):
        self.settings = _validated(settings, token)
        self.token = token
        self.quiet = False
        self._lock = threading.Lock()
        self._started = False
        self._closed = False
        self._revision = 0
        self._client_revision = -1
        self._client = None
        self._last_hardware = None
        self._last_connection = None
        self._hardware_received = time.monotonic()
        self._connection_received = time.monotonic()
        self._hardware_stale = False
        self._connection_stale = False
        self._pending_connection = ConnectionSnapshot(detail="Checking local Unsloth connection…")
        self.collector = create_collector()
        self.hardware = PollWorker("hardware", self.collector.collect, self.settings.interval,
                                   cleanup=self.collector.close)
        self.network = PollWorker("unsloth", self._poll_network, self.settings.interval,
                                  retry=lambda result: result[1].status in (
                                      ConnectionStatus.OFFLINE, ConnectionStatus.AUTH_REQUIRED,
                                      ConnectionStatus.UNSUPPORTED), cleanup=self._close_client)

    def start(self):
        if self._closed:
            raise RuntimeError("The monitor is closed.")
        if self._started:
            return
        self._started = True
        self.hardware.start()
        self.network.start()

    def _poll_network(self):
        previous = None
        with self._lock:
            revision = self._revision
            if self._closed:
                return revision, ConnectionSnapshot(status=ConnectionStatus.OFFLINE,
                                                     detail="Monitoring is closed.")
            if self._client_revision != revision:
                previous = self._client
                self._client = UnslothClient(base_url=self.settings.base_url, token=self.token)
                self._client_revision = revision
            client = self._client
        if previous is not None:
            previous.close()
        return revision, client.poll()

    def _close_client(self):
        with self._lock:
            client, self._client = self._client, None
            self._client_revision = -1
        if client is not None:
            client.close()

    def configure(self, settings: Settings, token=""):
        """Apply validated preferences, clear old connection state, and refresh."""
        settings = _validated(settings, token)
        with self._lock:
            if self._closed:
                raise RuntimeError("The monitor is closed.")
            self.settings, self.token = settings, token
            self._revision += 1
            self._last_connection = None
            self._connection_stale = False
            self._pending_connection = ConnectionSnapshot(
                detail="Checking updated connection settings…")
            old_client, self._client = self._client, None
            self._client_revision = -1
            interval = 30 if self.quiet else settings.interval
        # Interrupt an obsolete request; its revision still makes any late
        # result ineligible for display. No new worker or request queue is made.
        if old_client is not None:
            old_client.close()
        self.hardware.set_interval(interval, refresh=True)
        self.network.set_interval(interval, refresh=True)

    def refresh(self):
        if not self._closed:
            self.hardware.refresh()
            self.network.refresh()

    def set_quiet(self, quiet: bool):
        """Use 30-second collection while explicitly quiet; refresh on return."""
        with self._lock:
            if self._closed:
                return
            quiet = bool(quiet)
            if quiet == self.quiet:
                return
            self.quiet = quiet
            interval = 30 if quiet else self.settings.interval
        self.hardware.set_interval(interval, refresh=not quiet)
        self.network.set_interval(interval, refresh=not quiet)

    def take_updates(self) -> tuple[HardwareSnapshot | None, ConnectionSnapshot | None]:
        """Take latest observations or one-shot stale transitions.

        Snapshot acquisition time determines age even if a caller did not drain
        the mailbox for a long time. A monotonic anchor prevents later wall-clock
        changes from keeping an already received sample fresh indefinitely.
        """
        if self._closed:
            return None, None
        hardware = self.hardware.take_latest()
        network = self.network.take_latest()
        now, wall = time.monotonic(), time.time()
        with self._lock:
            connection, self._pending_connection = self._pending_connection, None
            if hardware is not None:
                self._last_hardware = hardware
                self._hardware_received = now - max(0, wall - hardware.timestamp)
                self._hardware_stale = False
            if network is not None and network[0] == self._revision:
                connection = network[1]
                self._last_connection = connection
                self._connection_received = now - max(0, wall - connection.timestamp)
                self._connection_stale = False
            interval = 30 if self.quiet else self.settings.interval
            if (self._last_hardware is not None and not self._hardware_stale
                    and now - self._hardware_received > max(15, interval * 3)):
                hardware = replace(self._last_hardware,
                                   metrics=_stale_metrics(self._last_hardware.metrics))
                self._hardware_stale = True
            if (self._last_connection is not None and not self._connection_stale
                    and now - self._connection_received > max(40, interval * 3)):
                connection = replace(
                    self._last_connection, status=ConnectionStatus.CHECKING,
                    metrics=_stale_metrics(self._last_connection.metrics),
                    detail="Connection check is stale; retrying.")
                self._connection_stale = True
        return hardware, connection

    def close(self):
        """Stop and join both workers; idempotent and safe before start().

        The HTTP client has a two-second overall budget and supports cancellation.
        An OS driver stuck inside a sysfs read can delay hardware shutdown; no
        Python thread can safely force that kernel operation to finish.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self.token = ""
        self.hardware.stop()
        self.network.stop()
        self._close_client()
        if self._started:
            self.hardware.thread.join()
            self.network.thread.join()
        else:
            self.collector.close()
