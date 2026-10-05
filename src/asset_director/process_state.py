"""Read-only process identity and a watchdog for an explicitly owned child."""
import ctypes
import os
from pathlib import Path
import threading
import time
from .core import DirectorError, require


def identity(pid):
    require(type(pid) is int and pid > 0, 'PROCESS_IDENTITY', 'Invalid process identity')
    if os.name == 'nt':
        from ctypes import wintypes as w
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
        kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];kernel.WaitForSingleObject.restype=w.DWORD
        kernel.GetProcessTimes.argtypes=[w.HANDLE]+[ctypes.POINTER(w.FILETIME)]*4;kernel.GetProcessTimes.restype=w.BOOL
        kernel.CloseHandle.argtypes=[w.HANDLE]
        handle=kernel.OpenProcess(0x101000,False,pid) # query limited information + synchronize; no VM access
        if not handle:
            if ctypes.get_last_error()==87:return None
            raise DirectorError('PROCESS_STATE_UNKNOWN','Cannot verify the retained process identity; no recovery was performed')
        try:
            state=kernel.WaitForSingleObject(handle,0)
            if state==0:return None
            require(state==258,'PROCESS_STATE_UNKNOWN','Process liveness could not be verified')
            created,ended,system,user=(w.FILETIME() for _ in range(4))
            require(bool(kernel.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(ended),ctypes.byref(system),ctypes.byref(user))),
                    'PROCESS_STATE_UNKNOWN','Process creation time could not be verified')
            return {'pid':pid,'birth':(created.dwHighDateTime<<32)|created.dwLowDateTime}
        finally:kernel.CloseHandle(handle)
    if Path('/proc').is_dir():
        try:stat=(Path('/proc')/str(pid)/'stat').read_text()
        except (FileNotFoundError,ProcessLookupError):return None
        except OSError:raise DirectorError('PROCESS_STATE_UNKNOWN','Cannot inspect the retained process identity') from None
        values=stat[stat.rindex(')')+2:].split()
        if values[0] in {'Z','X','x'}:return None
        return {'pid':pid,'birth':int(values[19])}
    # Without a supported birth-time source, a live/reused PID is conservatively live.
    try:os.kill(pid,0)
    except ProcessLookupError:return None
    except OSError:raise DirectorError('PROCESS_STATE_UNKNOWN','Cannot inspect the retained process identity') from None
    return {'pid':pid,'birth':None}


def stopped(expected):
    current=identity(expected.get('pid'))
    return current is None or (expected.get('birth') is not None and current.get('birth') is not None and expected['birth']!=current['birth'])


def watch_parent(expected):
    """Exit this owned worker if its original executor dies; never signal another PID."""
    require(not stopped(expected),'JOB_OWNER_EXITED','The owning job executor has already stopped')
    if os.name=='nt':
        from ctypes import wintypes as w
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
        kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];kernel.WaitForSingleObject.restype=w.DWORD
        handle=kernel.OpenProcess(0x100000,False,expected['pid'])
        require(bool(handle),'JOB_OWNER_EXITED','The owning job executor stopped during startup')
        try:require(not stopped(expected),'JOB_OWNER_EXITED','The owning job executor stopped during startup')
        except BaseException:
            kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle(handle);raise
        def watch():
            while kernel.WaitForSingleObject(handle,100)==258:pass
            os._exit(125)
    else:
        require(os.getppid()==expected['pid'],'JOB_OWNER_EXITED','The owning job executor has stopped')
        def watch():
            while os.getppid()==expected['pid']:time.sleep(.1)
            os._exit(125)
    threading.Thread(target=watch,name='blender-job-owner-watch',daemon=True).start()
