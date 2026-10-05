"""One process-scoped resource lane for local inference and Blender rendering.

Advisory OS locks release after normal completion, failure or process death.
The file remains intentionally; its existence never represents ownership.
"""
import contextlib
import os
from pathlib import Path
import tempfile
import time
from .core import require


@contextlib.contextmanager
def process_lease(path, check=lambda: None, *, timeout=900):
    require(type(timeout) in (float,int) and 0 < timeout <= 900,
            'RESOURCE_LIMIT', 'GPU queue timeout must be positive and at most 900 seconds')
    path = Path(path)
    start = time.monotonic()
    with path.open('a+b') as stream:
        stream.seek(0,2)
        if not stream.tell(): stream.write(b'0'); stream.flush()
        while True:
            check()
            require(time.monotonic()-start < timeout, 'RESOURCE_QUEUE_TIMEOUT', 'Local rendering/inference resource queue timed out')
            stream.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except (OSError,BlockingIOError): time.sleep(.05)
        try:
            check(); yield
        finally:
            stream.seek(0)
            if os.name == 'nt': msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


@contextlib.contextmanager
def gpu_lease(check=lambda: None, *, timeout=900):
    with process_lease(Path(tempfile.gettempdir())/'asset-director-heavy-operation.lock',check,timeout=timeout):
        yield
