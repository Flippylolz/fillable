"""Coordinate the existing manager and Fillable's scoped configuration writes."""

import fcntl
import functools
import threading
import time
from contextlib import contextmanager
from pathlib import Path

_local = threading.local()


@contextmanager
def locked(edge_root, timeout=60):
    path = Path(edge_root).resolve() / "state" / "fillable-mutation.lock"
    held = getattr(_local, "held", set())
    if path in held:
        yield
        return
    with path.open("a") as stream:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Shared manager is busy") from None
                time.sleep(0.1)
        _local.held = held | {path}
        try:
            yield
        finally:
            _local.held = held
            fcntl.flock(stream, fcntl.LOCK_UN)


def serialize(function):
    @functools.wraps(function)
    def run(edge_root, *args, **kwargs):
        with locked(edge_root):
            return function(edge_root, *args, **kwargs)

    return run
