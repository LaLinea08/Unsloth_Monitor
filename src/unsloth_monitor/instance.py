"""Kernel-managed Linux lock: no stale PID files and no background service."""

import os
from pathlib import Path


class SingleInstance:
    def __init__(self, path: Path):
        self.path = path
        self._fd = None

    def acquire(self) -> bool:
        import fcntl
        if self._fd is not None:
            return True
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return False
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd
        return True

    def release(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        # Do not unlink the inode: that would let another process lock a new file
        # while an already-waiting process still holds the old inode.
