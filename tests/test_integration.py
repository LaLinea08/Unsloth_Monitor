"""Real local HTTP sockets, with fixture payloads used only by tests."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
import time

import pytest

from unsloth_monitor.integration import UnslothClient, validate_base_url
from unsloth_monitor.metrics import Availability, ConnectionStatus


@contextmanager
def server(payload=None, *, status=200, content_type="application/json", responder=None, port=0):
    calls = []
    current = {"payload": payload if payload is not None else
               {"service": "Unsloth UI Backend", "status": "alive"}, "status": status}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def handle(self):
            try:
                super().handle()
            except (ConnectionResetError, ConnectionAbortedError):
                # The client intentionally closes rejected/cancelled responses.
                # Windows can surface that peer close on the next request read.
                # Other server exceptions still propagate to the test runner.
                pass

        def log_message(self, *_args):
            pass

        def do_GET(self):
            calls.append((self.command, self.path, dict(self.headers), self.client_address[1]))
            if responder is not None:
                try:
                    responder(self)
                except (OSError, ValueError):
                    pass
                return
            body = current["payload"]
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(current["status"])
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if current.get("close"):
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            try:
                self.wfile.write(body)
            except OSError:
                pass

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    worker = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.01), daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}/v1", calls, current
    finally:
        httpd.shutdown()
        httpd.server_close()
        worker.join(timeout=1)


@pytest.mark.parametrize("value, expected", [
    ("http://localhost:8888/v1/", "http://127.0.0.1:8888/v1"),
    ("http://127.2.3.4:123", "http://127.2.3.4:123/v1"),
    ("http://[::1]/", "http://[::1]:80/v1"),
])
def test_local_urls_are_normalized(value, expected):
    assert validate_base_url(value) == expected


@pytest.mark.parametrize("value", [
    "http://192.168.1.2:8888/v1", "https://127.0.0.1:8888/v1",
    "http://example.com/v1", "http://user:secret@127.0.0.1/v1",
    "http://127.0.0.1/v1?secret=x", "http://127.0.0.1/v1#fragment",
    "http://127.0.0.1/v1?", "http://127.0.0.1/v1#",
    "http://127.0.0.1/other", "http://127.0.0.1:0/v1",
    "http://127.0.0.1:65536/v1", "http://127.0.0.1:/v1",
    "http://127.0.0.1\n/v1", "http://[::1%lo]/v1", "http://127.1/v1",
])
def test_invalid_urls_rejected_without_echoing_secrets(value):
    with pytest.raises(ValueError) as error:
        validate_base_url(value)
    assert "secret" not in str(error.value)


def test_liveness_is_get_only_and_connection_reused(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    with server() as (url, calls, _current):
        client = UnslothClient(url)
        try:
            first = client.poll()
            second = client.poll()
        finally:
            client.close()
        assert first.status == second.status == ConnectionStatus.ONLINE
        assert [(c[0], c[1]) for c in calls] == [("GET", "/api/liveness")] * 2
        assert calls[0][3] == calls[1][3]
        assert all(metric.value is None for metric in first.metrics.values())
        assert all(metric.availability == Availability.UNSUPPORTED for metric in first.metrics.values())
        assert all(metric.source and metric.timestamp > 0 for metric in first.metrics.values())
        assert first.metrics["output_tps"].unit == "tokens/s"


@pytest.mark.parametrize("payload", [
    {"object": "list", "data": [{"id": "model", "owned_by": "unsloth-studio", "loaded": True}]},
    {"status": "healthy"}, {"status": "alive", "service": "another server"},
    {"status": "alive", "service": "Unsloth UI Backend ", "active_model": "model"},
])
def test_catalog_or_familiar_names_do_not_establish_identity_or_loaded_models(payload):
    with server(payload) as (url, _calls, _current):
        client = UnslothClient(url)
        try:
            result = client.poll()
        finally:
            client.close()
        assert result.status == ConnectionStatus.API_REACHABLE
        assert result.metrics["loaded_model"].value is None


def test_activity_and_incidental_fields_not_interpreted_as_request_telemetry():
    with server({"status": "alive", "service": "Unsloth UI Backend", "inference_active": True,
                 "active_model": "not-in-liveness-schema", "tokens_per_second": 42}) as (url, _, _c):
        client = UnslothClient(url)
        try:
            result = client.poll()
        finally:
            client.close()
        assert result.status == ConnectionStatus.ONLINE
        assert all(metric.value is None for metric in result.metrics.values())


@pytest.mark.parametrize("status, expected", [
    (401, ConnectionStatus.AUTH_REQUIRED), (403, ConnectionStatus.AUTH_REQUIRED),
    (404, ConnectionStatus.UNSUPPORTED), (302, ConnectionStatus.UNSUPPORTED),
    (503, ConnectionStatus.UNSUPPORTED),
])
def test_failure_statuses(status, expected):
    with server(status=status) as (url, calls, _current):
        client = UnslothClient(url)
        try:
            result = client.poll()
        finally:
            client.close()
        assert result.status == expected
        assert len(calls) == 1
        assert all(metric.value is None for metric in result.metrics.values())


@pytest.mark.parametrize("payload, content_type", [
    (b"{broken", "application/json"), ([], "application/json"),
    (b"<html>login</html>", "text/html"), (b"x" * 40000, "application/json"),
    (b"\xff", "application/json"),
], ids=["malformed", "array", "html", "oversized", "invalid-utf8"])
def test_malformed_changed_and_oversized_responses(payload, content_type):
    with server(payload, content_type=content_type) as (url, _calls, _current):
        client = UnslothClient(url)
        try:
            assert client.poll().status == ConnectionStatus.UNSUPPORTED
        finally:
            client.close()


def test_next_poll_reconnects_after_auth_failure_and_clears_old_values():
    with server(status=401) as (url, calls, current):
        client = UnslothClient(url, token="test-only-token")
        try:
            assert client.poll().status == ConnectionStatus.AUTH_REQUIRED
            current["status"] = 200
            assert client.poll().status == ConnectionStatus.ONLINE
            current["status"] = 503
            snapshot = client.poll()
            assert snapshot.status == ConnectionStatus.UNSUPPORTED
            assert all(metric.value is None for metric in snapshot.metrics.values())
            assert "test-only-token" not in repr(snapshot)
            assert calls[0][2]["Authorization"] == "Bearer test-only-token"
        finally:
            client.close()


def test_offline_then_server_start_and_restart_detected():
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
        client = UnslothClient(f"http://127.0.0.1:{port}/v1", timeout=0.2)
        assert client.poll().status == ConnectionStatus.OFFLINE
    with server(port=port) as (_url, _calls, current):
        current["close"] = True
        assert client.poll().status == ConnectionStatus.ONLINE
    assert client.poll().status == ConnectionStatus.OFFLINE
    with server(port=port) as (_url, _calls, _current):
        assert client.poll().status == ConnectionStatus.ONLINE
        client.close()
        assert client.poll().status == ConnectionStatus.OFFLINE


@pytest.mark.parametrize("stage", ["header", "body"])
def test_overall_deadline_stops_trickle_response(stage):
    def trickle(handler):
        if stage == "body":
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", "1000")
            handler.end_headers()
        for _ in range(50):
            handler.wfile.write(b"x")
            handler.wfile.flush()
            time.sleep(0.02)

    with server(responder=trickle) as (url, _calls, _current):
        client = UnslothClient(url, timeout=0.15)
        started = time.monotonic()
        try:
            result = client.poll()
        finally:
            client.close()
        assert result.status == ConnectionStatus.OFFLINE
        assert time.monotonic() - started < 0.8


def test_close_cancels_inflight_request():
    started = threading.Event()

    def slow(handler):
        started.set()
        time.sleep(1)

    with server(responder=slow) as (url, _calls, _current):
        client = UnslothClient(url, timeout=2)
        worker = threading.Thread(target=client.poll)
        worker.start()
        assert started.wait(timeout=1)
        client.close()
        worker.join(timeout=0.5)
        assert not worker.is_alive()


@pytest.mark.parametrize("token", ["secret\r\nInjected: yes", "contains space", "ü"])
def test_token_rejects_header_injection(token):
    with pytest.raises(ValueError):
        UnslothClient(token=token)
