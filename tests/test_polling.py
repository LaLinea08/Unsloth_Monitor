import threading
import time

from unsloth_monitor.polling import PollWorker


def test_no_overlapping_work_and_one_latest_result():
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def collect():
        calls.append(len(calls))
        entered.set()
        release.wait(2)
        return len(calls)

    worker = PollWorker("test", collect, interval=60)
    worker.start()
    assert entered.wait(1)
    for _ in range(100):
        worker.refresh()
    assert len(calls) == 1
    release.set()
    deadline = time.monotonic() + 2
    while len(calls) < 2 and time.monotonic() < deadline:
        time.sleep(.01)
    worker.stop()
    worker.thread.join(2)
    assert not worker.thread.is_alive()
    assert worker.take_latest() == 2
    assert worker.take_latest() is None


def test_stop_interrupts_wait_and_runs_cleanup():
    completed = threading.Event()
    cleaned = threading.Event()
    worker = PollWorker("test", lambda: completed.set() or 1, interval=30, cleanup=cleaned.set)
    worker.start()
    assert completed.wait(1)
    worker.stop()
    worker.thread.join(1)
    assert not worker.thread.is_alive()
    assert cleaned.is_set()


def test_collector_errors_do_not_kill_worker():
    completed = threading.Event()

    def broken():
        completed.set()
        raise OSError("secret-like content must not be surfaced")

    worker = PollWorker("test", broken)
    worker.start()
    assert completed.wait(1)
    worker.stop()
    worker.thread.join(1)
    assert worker.take_latest() is None
