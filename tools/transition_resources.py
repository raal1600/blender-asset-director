"""Sample real acceptance process-tree RAM and device VRAM; no size estimates.

GPU figures are device-wide usage including the display and other applications,
not a claim that all measured VRAM belongs to the child process.
"""
import ctypes
import os
from pathlib import Path
import subprocess
import time
from owned_process import OwnedCommand


def _select_tree(rows, root_pid, root_identity=None):
    """A retained parent PID alone is not parentage after PID reuse."""
    root = rows.get(root_pid)
    if root is None or (root_identity and root['birth'] != root_identity['birth']):
        return []
    included = {root_pid}
    while True:
        more = {pid for pid, row in rows.items() if row['parent'] in included
                and row['birth'] >= rows[row['parent']]['birth']}
        if more <= included:
            return sorted(included)
        included |= more


def _windows_api():
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    kernel.WaitForSingleObject.restype = w.DWORD
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)]*4
    kernel.GetProcessTimes.restype = w.BOOL
    return kernel


def _windows_row(pid, *, handle=None, upper_birth=None, memory=False):
    from ctypes import wintypes as w
    kernel = _windows_api()
    owned = handle is None
    if owned:
        handle = kernel.OpenProcess(0x100410, False, pid)
    if not handle:
        code = ctypes.get_last_error()
        if code == 87:  # ERROR_INVALID_PARAMETER: PID no longer exists.
            return None
        raise ctypes.WinError(code)
    try:
        state = kernel.WaitForSingleObject(handle, 0)
        if state == 0:
            return None
        if state != 258:
            raise ctypes.WinError(ctypes.get_last_error())
        created, ended, system, user = (w.FILETIME() for _ in range(4))
        if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(ended),
                                      ctypes.byref(system), ctypes.byref(user)):
            raise ctypes.WinError(ctypes.get_last_error())
        birth = (created.dwHighDateTime << 32) | created.dwLowDateTime
        # The parent PID came from the earlier Toolhelp snapshot. A newer
        # occupant of that PID is not that snapshot's process, even if alive.
        if upper_birth is not None and birth > upper_birth:
            return None
        state = kernel.WaitForSingleObject(handle, 0)
        if state == 0:
            return None
        if state != 258:
            raise ctypes.WinError(ctypes.get_last_error())
        rss = 0
        if memory:
            class Memory(ctypes.Structure):
                _fields_ = [('cb', w.DWORD), ('faults', w.DWORD)] + [
                    (n, ctypes.c_size_t) for n in ('peak', 'rss', 'paged_peak', 'paged',
                                                  'nonpaged_peak', 'nonpaged', 'pagefile', 'pagefile_peak')]
            psapi = ctypes.WinDLL('psapi', use_last_error=True)
            psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(Memory), w.DWORD]
            usage = Memory(); usage.cb = ctypes.sizeof(usage)
            if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(usage), usage.cb):
                return None
            rss = usage.rss
        return {'pid': pid, 'birth': birth, 'resident_bytes': rss}
    finally:
        if owned:
            kernel.CloseHandle(handle)


def _linux_stat(text, page_size):
    # comm may itself contain spaces/parentheses. The trailing ')' ends it.
    fields = text[text.rindex(')')+2:].split()
    if fields[0] in {'Z', 'X', 'x'}:
        return None
    return {'parent': int(fields[1]), 'birth': int(fields[19]),
            'resident_bytes': max(0, int(fields[21]))*page_size}


def _linux_row(pid):
    try:
        # One kernel stat read binds PPID, start ticks and RSS to one occupant;
        # separate status/stat opens could observe different reused PIDs.
        return _linux_stat((Path('/proc')/str(pid)/'stat').read_text(), os.sysconf('SC_PAGE_SIZE'))
    except (FileNotFoundError, ProcessLookupError):
        return None


def process_identity(pid, *, handle=None):
    """Identity/liveness observation; never terminate or signal any process."""
    row = _windows_row(pid, handle=handle) if os.name == 'nt' else _linux_row(pid) if Path('/proc').is_dir() else None
    return {'pid': pid, 'birth': row['birth']} if row else None


def identity_alive(identity):
    try:
        return process_identity(identity['pid']) == identity
    except (OSError, ValueError, IndexError):
        return None  # Query denial/failure is unknown, never proof of exit.


def process_memory(root_pid, root_identity=None):
    """Summed RSS for sampled PID+birth identities, excluding stale ancestry."""
    if os.name == 'nt':
        from ctypes import wintypes as w
        class Entry(ctypes.Structure):
            _fields_ = [('size', w.DWORD), ('uses', w.DWORD), ('pid', w.DWORD),
                        ('heap', ctypes.c_size_t), ('module', w.DWORD), ('threads', w.DWORD),
                        ('parent', w.DWORD), ('priority', w.LONG), ('flags', w.DWORD),
                        ('name', w.WCHAR * 260)]
        kernel = _windows_api()
        kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
        kernel.Process32FirstW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
        kernel.Process32NextW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
        stamp = w.FILETIME()
        kernel.GetSystemTimePreciseAsFileTime.argtypes = [ctypes.POINTER(w.FILETIME)]
        kernel.GetSystemTimePreciseAsFileTime.restype = None
        kernel.GetSystemTimePreciseAsFileTime(ctypes.byref(stamp))
        upper_birth = (stamp.dwHighDateTime << 32) | stamp.dwLowDateTime
        snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            raise OSError(ctypes.get_last_error(), 'Cannot observe process tree')
        parents = {}
        try:
            item = Entry(); item.size = ctypes.sizeof(item)
            ok = kernel.Process32FirstW(snapshot, ctypes.byref(item))
            while ok:
                parents[item.pid] = item.parent
                ok = kernel.Process32NextW(snapshot, ctypes.byref(item))
        finally:
            kernel.CloseHandle(snapshot)
        candidates = {root_pid}
        while True:
            more = {p for p, parent in parents.items() if parent in candidates}
            if more <= candidates:
                break
            candidates |= more
        rows = {}
        for pid in candidates:
            try:
                row = _windows_row(pid, upper_birth=upper_birth, memory=True)
            except OSError:
                continue  # Sampling cannot attribute an inaccessible process.
            if row is not None:
                rows[pid] = dict(row, parent=parents.get(pid))
    elif Path('/proc').is_dir():
        rows = {}
        for folder in Path('/proc').iterdir():
            if folder.name.isdigit():
                try:
                    row = _linux_row(int(folder.name))
                except (OSError, ValueError, IndexError):
                    continue
                if row is not None:
                    rows[int(folder.name)] = row
    else:
        return {'resident_bytes': None, 'pids': [], 'identities': [], 'limitation': 'RAM sampling unavailable on this platform'}
    included = _select_tree(rows, root_pid, root_identity)
    return {'resident_bytes': sum(rows[p]['resident_bytes'] for p in included),
            'pids': included, 'identities': [{'pid': p, 'birth': rows[p]['birth']} for p in included]}


def gpu_memory():
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free',
                                 '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5,
                                creationflags=0x08000000 if os.name == 'nt' else 0)
        if result.returncode:
            return {'status': 'UNAVAILABLE', 'error': result.stderr.strip()[:500]}
        return {'status': 'MEASURED', 'scope': 'DEVICE_WIDE', 'devices': [
            {'name': row[0].strip(), 'total_mib': float(row[1]), 'used_mib': float(row[2]), 'free_mib': float(row[3])}
            for line in result.stdout.splitlines() if len(row := line.split(',')) == 4]}
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {'status': 'UNAVAILABLE', 'error': str(exc)}


def measured_run(command, log, *, cwd, env=None, timeout=900):
    """Execute a finite real test and retain measured samples even on failure."""
    before = gpu_memory(); started = time.monotonic(); samples = []
    guardian_report=Path(str(log)+'.guardian.json')
    with Path(log).open('w', encoding='utf-8') as stream:
        child = OwnedCommand(command, cwd=cwd, env=env, stdout=stream,
                             report=guardian_report, timeout=timeout)
        try:
            try:
                root_identity = process_identity(child.pid, handle=getattr(child.process, '_handle', None))
            except (OSError, ValueError, IndexError):
                root_identity = None
            while child.poll() is None:
                samples.append({'seconds': round(time.monotonic()-started, 3),
                                'host': process_memory(child.pid, root_identity) if root_identity else {'resident_bytes': None, 'pids': [], 'identities': [], 'limitation': 'Guardian process identity unavailable'}, 'gpu': gpu_memory()})
                time.sleep(.5)
            execution = child.wait(timeout=15)
        finally:
            child.close()
    timed_out = execution['state']=='TIMED_OUT'
    identities = sorted({(row['pid'], row['birth']) for sample in samples for row in sample['host']['identities']})
    observed = sorted({pid for pid, _ in identities})
    def remaining():
        rows = []
        for pid, birth in identities:
            identity = {'pid': pid, 'birth': birth}
            alive = identity_alive(identity)
            if alive is not False:
                rows.append(dict(identity, status='UNKNOWN' if alive is None else 'ALIVE'))
        return rows
    deadline=time.monotonic()+3
    live=remaining()
    while live and time.monotonic()<deadline:
        time.sleep(.1);live=remaining()
    release = ('NOT_VERIFIED' if root_identity is None or not identities else
               'UNKNOWN' if any(r['status']=='UNKNOWN' for r in live) else 'FAIL' if live else 'PASS')
    return {'command': [str(v) for v in command], 'exit_code': execution['exit_code'],
            'guardian':execution,'guardian_report':str(guardian_report),
            'observed_processes':observed,'observed_process_identities':[{'pid': pid, 'birth': birth} for pid, birth in identities],
            'remaining_observed_pids':[row['pid'] for row in live],'remaining_observed_identities':live,
            'observed_process_release':release,
            'release_observation_note': 'No attributable live process samples' if release=='NOT_VERIFIED' else 'Observed identities could not be queried' if release=='UNKNOWN' else 'Compared exact sampled PID+creation identities',
            'seconds': round(time.monotonic()-started, 3), 'timed_out': timed_out,
            'nominal_poll_delay_seconds': .5,
            'sampling_limitations':'Sampled maxima only; GPU queries add variable latency. Release checks match observed PID+creation identities, not an OS lifetime containment guarantee. Inaccessible/exited parents and between-sample children may be unobserved.', 'gpu_scope': 'device-wide, includes unrelated clients/display',
            'host_scope': 'summed observed resident memory of owned guardian, command and descendants',
            'peak_host_resident_bytes': max((s['host']['resident_bytes'] or 0 for s in samples), default=None),
            'peak_device_used_mib': max((g['used_mib'] for s in samples for g in s['gpu'].get('devices', [])), default=None),
            'before': before, 'after': gpu_memory(), 'samples': samples}
