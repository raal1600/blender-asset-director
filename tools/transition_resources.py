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


def process_memory(root_pid):
    """Return summed resident bytes for the observed child process tree."""
    if os.name == 'nt':
        from ctypes import wintypes as w
        class Entry(ctypes.Structure):
            _fields_ = [('size', w.DWORD), ('uses', w.DWORD), ('pid', w.DWORD),
                        ('heap', ctypes.c_size_t), ('module', w.DWORD), ('threads', w.DWORD),
                        ('parent', w.DWORD), ('priority', w.LONG), ('flags', w.DWORD),
                        ('name', w.WCHAR * 260)]
        class Memory(ctypes.Structure):
            _fields_ = [('cb', w.DWORD), ('faults', w.DWORD)] + [
                (n, ctypes.c_size_t) for n in ('peak', 'rss', 'paged_peak', 'paged',
                                              'nonpaged_peak', 'nonpaged', 'pagefile', 'pagefile_peak')]
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
        kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        kernel.OpenProcess.restype = w.HANDLE
        kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        kernel.WaitForSingleObject.restype = w.DWORD
        kernel.CloseHandle.argtypes = [w.HANDLE]
        kernel.Process32FirstW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
        kernel.Process32NextW.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(Memory), w.DWORD]
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
        descendants = {root_pid}
        while True:
            more = {p for p, parent in parents.items() if parent in descendants}
            if more <= descendants:
                break
            descendants |= more
        total, observed = 0, []
        for pid in sorted(descendants):
            handle = kernel.OpenProcess(0x100410, False, pid)
            if not handle:
                continue
            try:
                # A retained Popen handle keeps an exited process object queryable.
                # Only an unsignalled exact handle denotes a live process.
                if kernel.WaitForSingleObject(handle, 0) != 258:
                    continue
                memory = Memory(); memory.cb = ctypes.sizeof(memory)
                if psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb):
                    total += memory.rss; observed.append(pid)
            finally:
                kernel.CloseHandle(handle)
        return {'resident_bytes': total, 'pids': observed}
    if Path('/proc').is_dir():
        rows = {}
        for folder in Path('/proc').iterdir():
            if not folder.name.isdigit():
                continue
            try:
                fields = dict(line.split(':', 1) for line in (folder/'status').read_text().splitlines() if ':' in line)
                rows[int(folder.name)] = (int(fields['PPid']), int(fields.get('VmRSS', '0 kB').split()[0])*1024)
            except (OSError, ValueError, KeyError):
                continue
        descendants = {root_pid}
        while True:
            more = {p for p, (parent, _) in rows.items() if parent in descendants}
            if more <= descendants:
                break
            descendants |= more
        return {'resident_bytes': sum(rows.get(p, (0, 0))[1] for p in descendants),
                'pids': sorted(descendants & rows.keys())}
    return {'resident_bytes': None, 'pids': [], 'limitation': 'RAM sampling unavailable on this platform'}


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
            while child.poll() is None:
                samples.append({'seconds': round(time.monotonic()-started, 3),
                                'host': process_memory(child.pid), 'gpu': gpu_memory()})
                time.sleep(.5)
            execution = child.wait(timeout=15)
        finally:
            child.close()
    timed_out = execution['state']=='TIMED_OUT'
    observed={pid for sample in samples for pid in sample['host']['pids']}
    def remaining():
        return [pid for pid in sorted(observed) if pid in process_memory(pid)['pids']]
    deadline=time.monotonic()+3
    live=remaining()
    while live and time.monotonic()<deadline:
        time.sleep(.1);live=remaining()
    return {'command': [str(v) for v in command], 'exit_code': execution['exit_code'],
            'guardian':execution,'guardian_report':str(guardian_report),
            'observed_processes':sorted(observed),'remaining_observed_pids':live,
            'observed_process_release':'PASS' if not live else 'FAIL',
            'seconds': round(time.monotonic()-started, 3), 'timed_out': timed_out,
            'nominal_poll_delay_seconds': .5,
            'sampling_limitations':'Sampled maxima only; GPU queries add variable latency. Release checks cover observed descendants, not an OS lifetime containment guarantee.', 'gpu_scope': 'device-wide, includes unrelated clients/display',
            'host_scope': 'summed observed resident memory of owned guardian, command and descendants',
            'peak_host_resident_bytes': max((s['host']['resident_bytes'] or 0 for s in samples), default=None),
            'peak_device_used_mib': max((g['used_mib'] for s in samples for g in s['gpu'].get('devices', [])), default=None),
            'before': before, 'after': gpu_memory(), 'samples': samples}
