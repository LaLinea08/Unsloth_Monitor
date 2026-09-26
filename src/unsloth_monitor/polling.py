"""One thread and one replaceable result per source, never an executor queue."""

from collections.abc import Callable
import threading


class PollWorker:
    def __init__(self, name: str, collect: Callable, interval: float = 5,
                 retry: Callable = lambda result: False, cleanup: Callable = lambda: None):
        self.collect = collect
        self.retry = retry
        self.cleanup = cleanup
        self._interval = interval
        self._lock = threading.Lock()
        self._latest = None
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._failures = 0
        self.thread = threading.Thread(target=self._run, name=name, daemon=False)

    def start(self):
        self.thread.start()

    def set_interval(self, seconds: float, refresh: bool = False):
        with self._lock:
            self._interval = seconds
        if refresh:
            self._wake.set()

    def refresh(self):
        self._wake.set()

    def take_latest(self):
        with self._lock:
            result, self._latest = self._latest, None
            return result

    def stop(self):
        self._stop.set()
        self._wake.set()

    def _run(self):
        try:
            while not self._stop.is_set():
                # Clear before work so a refresh during a slow poll is not lost.
                self._wake.clear()
                try:
                    result = self.collect()
                except Exception:
                    # Never surface exception strings: HTTP errors may contain secrets.
                    result = None
                failed = result is None or self.retry(result)
                self._failures = min(self._failures + 1, 4) if failed else 0
                with self._lock:
                    self._latest = result
                    delay = self._interval
                if failed:
                    delay = min(30, delay * 2 ** max(0, self._failures - 1))
                self._wake.wait(delay)
        finally:
            self.cleanup()
