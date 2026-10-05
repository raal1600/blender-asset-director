"""Own bounded CI children without PID polling or unrelated-process cleanup.

An anonymous stdin pipe is the owner lease: EOF means the launching process
closed it or died. Windows containment uses a non-inherited kill-on-close Job
Object before spawning; POSIX keeps this guardian alive as the session/group
leader until it kills its own group after writing the result. No child PID is
used to discover or kill a possibly reused group. This is for trusted commands,
not a sandbox against a child deliberately escaping its POSIX process group.
Abruptly SIGKILLing only the POSIX guardian is outside this containment; owner
exit through pipe EOF, child failures and deadlines are covered.

References: learn.microsoft.com/windows/win32/procthread/job-objects and
https://docs.python.org/3/library/os.html#os.killpg.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time


def python_executable():
    """Use an explicit interpreter or the observed runtime, including Blender's."""
    explicit = os.environ.get('ASSET_DIRECTOR_TEST_PYTHON')
    if explicit:
        path = Path(explicit).resolve()
        if not path.is_file():
            raise RuntimeError('ASSET_DIRECTOR_TEST_PYTHON must name an existing Python executable')
        return str(path)
    current = Path(sys.executable)
    if current.name.lower().startswith('python') and current.is_file():
        return str(current.resolve())
    names = ('python.exe',) if os.name == 'nt' else (f'python{sys.version_info.major}.{sys.version_info.minor}', 'python3')
    for name in names:
        candidate = Path(sys.prefix)/'bin'/name
        if candidate.is_file():
            return str(candidate.resolve())
    raise RuntimeError('Set ASSET_DIRECTOR_TEST_PYTHON to the external Python interpreter for this test runtime')


class OwnedCommand:
    """Launch a guardian, retain its owner pipe, and expose its observable PID."""
    def __init__(self, command, *, report, stdout, cwd=None, env=None, timeout=600, python=None):
        if not command or not 0 < timeout <= 7200:
            raise ValueError('Owned command requires a finite 0..7200 second timeout')
        self.report = Path(report).resolve()
        if self.report.exists():
            raise FileExistsError(self.report)
        args = [python or python_executable(), '-u', str(Path(__file__).resolve()),
                '--report', str(self.report), '--timeout', str(timeout), '--', *map(str, command)]
        self.process = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.PIPE,
            stdout=stdout, stderr=subprocess.STDOUT, close_fds=True,
            creationflags=0x08000000 if os.name == 'nt' else 0,
            start_new_session=os.name != 'nt')
        self.pid = self.process.pid

    def poll(self):
        return self.process.poll()

    def wait(self, timeout=None):
        self.process.wait(timeout=timeout)
        data = json.loads(self.report.read_text(encoding='utf-8'))
        if data['guardian_pid'] != self.pid:
            raise RuntimeError('Guardian report identity differs from its owned process')
        return data

    def close(self):
        if not self.process.stdin.closed:
            self.process.stdin.close()
        # EOF remains observable even when the owner itself is force-terminated.
        # Do not fall back to killing a stored/unbound PID.
        self.process.wait(timeout=15)


def _windows_job():
    """Assign this guardian before any command runs; children inherit the job."""
    from ctypes import wintypes as w
    class Basic(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                    ('flags', w.DWORD), ('min_working_set', ctypes.c_size_t),
                    ('max_working_set', ctypes.c_size_t), ('active_limit', w.DWORD),
                    ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
    class Extended(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t),
                    ('job_memory', ctypes.c_size_t), ('peak_process_memory', ctypes.c_size_t),
                    ('peak_job_memory', ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = Extended(); limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
        error = ctypes.WinError(ctypes.get_last_error()); kernel.CloseHandle(handle); raise error
    if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        error = ctypes.WinError(ctypes.get_last_error()); kernel.CloseHandle(handle); raise error
    # Deliberately retain the sole non-inherited handle until os._exit. Closing
    # it in this process would terminate the guardian along with its children.
    return handle


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--timeout', type=float, required=True)
    p.add_argument('command', nargs=argparse.REMAINDER)
    args = p.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or not 0 < args.timeout <= 7200 or args.report.exists():
        raise ValueError('Invalid guardian command, timeout or existing report')
    started = time.monotonic(); owner_lost = threading.Event(); child = None; job = None
    result = {'state': 'FAILED', 'exit_code': 125, 'guardian_pid': os.getpid(),
              'command': command, 'containment': 'WINDOWS_JOB' if os.name == 'nt' else 'POSIX_PROCESS_GROUP',
              'owner_identity': 'ANONYMOUS_PIPE', 'timeout_seconds': args.timeout}
    def watch_owner():
        try:
            sys.stdin.buffer.read(1)
        finally:
            owner_lost.set()
    threading.Thread(target=watch_owner, daemon=True).start()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: owner_lost.set())
    try:
        if os.name == 'nt':
            job = _windows_job()
        else:
            if os.getpgrp()!=os.getpid() or os.getsid(0)!=os.getpid():
                raise RuntimeError('POSIX guardian must own its new session and process group')
            signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        if owner_lost.is_set():
            result.update(state='OWNER_EXITED', exit_code=125)
        else:
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, close_fds=True,
                creationflags=0x08000000 if os.name == 'nt' else 0,
                start_new_session=False)
            result['child_pid'] = child.pid
            while True:
                if owner_lost.is_set():
                    result.update(state='OWNER_EXITED', exit_code=125); break
                if time.monotonic()-started >= args.timeout:
                    result.update(state='TIMED_OUT', exit_code=124); break
                if child.poll() is not None:
                    result.update(state='EXITED',exit_code=child.returncode)
                    break
                owner_lost.wait(.025)
    except BaseException as error:
        result.update(state='FAILED', exit_code=125, error=repr(error))
    finally:
        result['seconds'] = time.monotonic()-started
        result['cleanup'] = 'KILL_ON_GUARDIAN_EXIT' if job else 'OWNED_GROUP_KILL_AFTER_REPORT' if child else 'NO_CHILD'
        try:
            with args.report.open('x', encoding='utf-8') as stream:
                json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        except BaseException as error:
            result.update(state='FAILED', exit_code=125)
            try:
                print('GUARDIAN_REPORT_FAILED: '+repr(error), file=sys.stderr, flush=True)
            except BaseException:
                pass # Even an unusable log cannot prevent owned-tree cleanup.
        finally:
            if child is not None and os.name != 'nt':
                # The still-live guardian reserves this PGID. A receipt-write
                # failure must also terminate the whole group. The separate
                # report carries the command result on successful publication;
                # a missing/invalid report remains an error for OwnedCommand.
                os.killpg(os.getpid(),signal.SIGKILL)
            # Always avoid interpreter finalization: the daemon owner watcher
            # can still hold stdin's buffered lock. Windows closes the sole Job
            # handle here even if publishing the receipt or diagnostic failed.
            os._exit(result['exit_code'] if 0 <= result['exit_code'] <= 255 else 1)


if __name__ == '__main__':
    main()
