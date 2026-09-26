"""Bounded Unsloth liveness reads, without catalog scans or inference traffic.

See docs/TELEMETRY.md for the exact upstream revision and excluded endpoints.
One client belongs to one polling worker. No proxy or environment credentials are
consulted. Values not exposed by this adapter remain explicitly unsupported.
"""

import http.client
import ipaddress
import json
import math
import socket
import threading
import time
from urllib.parse import urlsplit

from unsloth_monitor.metrics import Availability, ConnectionSnapshot, ConnectionStatus, Metric

DEFAULT_BASE_URL = "http://127.0.0.1:8888/v1"
MAX_RESPONSE_BYTES = 32 * 1024
POLL_TIMEOUT_SECONDS = 2.0
SOURCE = "GET /api/liveness (local Unsloth service)"
_UNITS = {
    "loaded_model": "",
    "quantization": "",
    "context_limit": "tokens",
    "backend": "",
    "generation_state": "",
    "output_tps": "tokens/s",
    "output_tokens": "tokens",
    "request_duration": "s",
}


def validate_base_url(value: str) -> str:
    """Return a canonical loopback HTTP /v1 URL, or raise a safe ValueError.

    localhost is normalized without DNS. Numeric IPv4 and IPv6 loopback addresses
    are accepted. Remote hosts, userinfo, query strings, fragments, and alternate
    paths are outside this first release's deliberately narrow contract.
    """
    error = "Use a local HTTP URL such as http://127.0.0.1:8888/v1."
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise ValueError(error)
    if any(ord(char) <= 32 or ord(char) >= 127 for char in value):
        raise ValueError(error)
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "http" or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment
                or "?" in value or "#" in value
                or parsed.path not in ("", "/", "/v1", "/v1/")):
            raise ValueError(error)
        host = parsed.hostname
        if host == "localhost":
            host = "127.0.0.1"
        address = ipaddress.ip_address(host or "")
        if not address.is_loopback or "%" in (host or ""):
            raise ValueError(error)
        port = parsed.port if parsed.port is not None else 80
        if not 1 <= port <= 65535 or parsed.netloc.endswith(":"):
            raise ValueError(error)
    except (ValueError, TypeError):
        raise ValueError(error) from None
    display_host = f"[{address}]" if address.version == 6 else str(address)
    return f"http://{display_host}:{port}/v1"


class _DeadlineSocket(socket.socket):
    """Apply remaining overall budget before *every* underlying socket read.

    HTTPResponse uses SocketIO.recv_into, so even byte-at-a-time response headers
    cannot reset the overall timeout indefinitely. This needs no watchdog thread.
    """

    deadline: float
    cancelled: threading.Event

    def _remaining(self):
        if self.cancelled.is_set():
            raise OSError("Connection closed")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Poll deadline reached")
        self.settimeout(remaining)

    def connect(self, address):
        self._remaining()
        return super().connect(address)

    def recv_into(self, buffer, nbytes=0, flags=0):
        while True:
            self._remaining()
            # Windows does not reliably wake another thread's timed socket read
            # on shutdown(). A short cancellable wait bounds close as well.
            self.settimeout(min(self.gettimeout(), 0.1))
            try:
                return super().recv_into(buffer, nbytes, flags)
            except TimeoutError:
                continue

    def sendall(self, data, flags=0):
        self._remaining()
        return super().sendall(data, flags)


class _LocalConnection(http.client.HTTPConnection):
    deadline: float

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cancelled = threading.Event()

    def connect(self):
        # The URL validator supplies a numeric loopback address: no DNS, proxies,
        # redirects, environment settings, or resolver-dependent destinations.
        family = socket.AF_INET6 if ":" in self.host else socket.AF_INET
        sock = _DeadlineSocket(family, socket.SOCK_STREAM)
        sock.deadline = self.deadline
        sock.cancelled = self.cancelled
        self.sock = sock
        try:
            sock.connect((self.host, self.port))
        except BaseException:
            sock.close()
            self.sock = None
            raise


class UnslothClient:
    """Read the source-verified liveness endpoint once per poll.

    The worker controls intervals/backoff. This client never retries inside a
    poll; failed connections are replaced on the next scheduled call. close()
    cancels an in-flight socket read and permanently closes this client.
    """

    def __init__(self, base_url=DEFAULT_BASE_URL, token="", *, timeout=POLL_TIMEOUT_SECONDS):
        self.base_url = validate_base_url(base_url)
        if (not isinstance(token, str) or len(token) > 4096
                or any(ord(char) < 33 or ord(char) > 126 for char in token)):
            raise ValueError("Bearer token must contain only printable ASCII without spaces.")
        if not isinstance(timeout, (float, int)) or not math.isfinite(timeout) or not 0 < timeout <= 10:
            raise ValueError("Poll timeout must be greater than zero and at most 10 seconds.")
        self._token = token
        self._timeout = float(timeout)
        self._connection = None
        self._closed = False
        self._state_lock = threading.Lock()

    def _drop_connection(self):
        with self._state_lock:
            connection, self._connection = self._connection, None
        if connection is not None:
            connection.cancelled.set()
            if connection.sock is not None:
                try:
                    connection.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            connection.close()

    def close(self):
        with self._state_lock:
            self._closed = True
            self._token = ""
        self._drop_connection()

    def _snapshot(self, status, detail):
        now = time.time()
        available = status == ConnectionStatus.ONLINE
        missing = ("Not exposed by the passive liveness adapter; see telemetry documentation."
                   if available else "No verified Unsloth telemetry is available.")
        metrics = {
            key: Metric(unit=unit, source=SOURCE, timestamp=now,
                        availability=Availability.UNSUPPORTED if available else Availability.UNAVAILABLE,
                        detail=missing)
            for key, unit in _UNITS.items()
        }
        return ConnectionSnapshot(status=status, metrics=metrics, detail=detail, timestamp=now)

    def poll(self) -> ConnectionSnapshot:
        deadline = time.monotonic() + self._timeout
        try:
            with self._state_lock:
                if self._closed:
                    return self._snapshot(ConnectionStatus.OFFLINE, "Monitoring connection is closed.")
                if self._connection is None:
                    parsed = urlsplit(self.base_url)
                    self._connection = _LocalConnection(parsed.hostname, parsed.port)
                connection = self._connection
            connection.deadline = deadline
            if connection.sock is not None:
                connection.sock.deadline = deadline
            headers = {"Accept": "application/json", "Accept-Encoding": "identity",
                       "User-Agent": "Unsloth-Monitor/0.1"}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            connection.request("GET", "/api/liveness", headers=headers)
            response = connection.getresponse()
            if response.status in (401, 403):
                self._drop_connection()
                return self._snapshot(ConnectionStatus.AUTH_REQUIRED,
                                      "Local endpoint requires authentication or denied access.")
            if response.status != 200:
                status_code = response.status
                self._drop_connection()
                return self._snapshot(ConnectionStatus.UNSUPPORTED,
                                      f"Liveness endpoint returned HTTP {status_code}; no redirect followed.")
            content_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json" and not content_type.endswith("+json"):
                raise ValueError("Expected JSON response")
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("Encoded response unsupported")
            content_length = response.getheader("Content-Length")
            if content_length is not None and not 0 <= int(content_length) <= MAX_RESPONSE_BYTES:
                raise ValueError("Response too large")
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ValueError("Response too large")
            if content_length is not None and len(body) != int(content_length):
                raise ValueError("Truncated response")
            if time.monotonic() >= deadline:
                raise TimeoutError("Poll deadline reached")
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("Expected object")
            # Do not accept a familiar model owner/name as service identity. This
            # exact signature is supplied by the official liveness route itself.
            if payload.get("service") == "Unsloth UI Backend" and payload.get("status") == "alive":
                return self._snapshot(ConnectionStatus.ONLINE,
                                      "Unsloth liveness signature verified. Model and inference details are not read.")
            return self._snapshot(ConnectionStatus.API_REACHABLE,
                                  "Local API responded, but its Unsloth identity was not verified.")
        except (TimeoutError, OSError, http.client.RemoteDisconnected):
            self._drop_connection()
            return self._snapshot(ConnectionStatus.OFFLINE,
                                  "Local endpoint is unreachable or timed out; this does not prove a crash.")
        except (ValueError, UnicodeError, RecursionError, http.client.HTTPException):
            self._drop_connection()
            return self._snapshot(ConnectionStatus.UNSUPPORTED,
                                  "Liveness response is unsupported, malformed, or exceeded its size limit.")
