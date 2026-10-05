"""Real subprocess containment tests; no Blender or mocked executables."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

TOOLS = Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0, str(TOOLS))
from owned_process import OwnedCommand


class OwnedProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.processes = []
        self.guards = []
        self.streams = []
        self.worker = self.root/'tree.py'
        self.worker.write_text('''import json, os, subprocess, sys, time
from pathlib import Path
root=Path(sys.argv[1])
if len(sys.argv)>2 and sys.argv[2]=='grandchild':
    (root/'grandchild.json').write_text(json.dumps({'pid':os.getpid()}))
    time.sleep(30)
else:
    child=subprocess.Popen([sys.executable,__file__,str(root),'grandchild'])
    (root/'child.json').write_text(json.dumps({'pid':os.getpid(),'grandchild':child.pid}))
    if len(sys.argv)>2 and sys.argv[2]=='exit':
        deadline=time.monotonic()+5
        while not (root/'grandchild.json').exists() and time.monotonic()<deadline:time.sleep(.01)
        sys.exit(7)
    time.sleep(30)
''', encoding='utf-8')

    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:process.kill()
            process.wait(timeout=10)
        for guard in self.guards:guard.close()
        owner_metadata=self.root/'owner.json'
        if owner_metadata.is_file():self.gone(json.loads(owner_metadata.read_text())['guardian'])
        for stream in self.streams:stream.close()
        self.tmp.cleanup()

    def ready(self, path, timeout=10):
        deadline = time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:return json.loads(path.read_text())
            except (OSError, ValueError):time.sleep(.025)
        self.fail('Expected real subprocess evidence: '+str(path)+'; guardian='+((self.root/'guardian.json').read_text() if (self.root/'guardian.json').exists() else 'no report'))

    def gone(self, pid, timeout=10):
        deadline = time.monotonic()+timeout
        while time.monotonic()<deadline:
            if os.name == 'nt':
                # Python 3.11's os.kill(dead_pid, 0) can raise SystemError
                # chained from WinError 87. Inspect the OS waitable process
                # handle directly; access errors must still fail the test.
                from ctypes import wintypes as w
                kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]
                kernel.OpenProcess.restype=w.HANDLE
                kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD]
                kernel.WaitForSingleObject.restype=w.DWORD
                kernel.CloseHandle.argtypes=[w.HANDLE]
                handle=kernel.OpenProcess(0x100000,False,pid)
                if not handle:
                    error=ctypes.get_last_error()
                    if error==87:return  # ERROR_INVALID_PARAMETER: PID absent
                    raise ctypes.WinError(error)
                try:
                    state=kernel.WaitForSingleObject(handle,0)
                    if state==0:return
                    if state!=258:raise ctypes.WinError(ctypes.get_last_error())
                finally:kernel.CloseHandle(handle)
            else:
                try:os.kill(pid,0)
                except ProcessLookupError:return
            # An exited Unix orphan can remain a zombie until the host init
            # reaps it. It executes nothing and holds no live worker resources.
            stat = Path('/proc')/str(pid)/'stat'
            if stat.exists():
                try:
                    if stat.read_text().split(') ', 1)[1].startswith('Z '):return
                except OSError:return
            time.sleep(.025)
        self.fail('Owned worker remains live: '+str(pid))

    def guard(self, mode='wait', timeout=5):
        stream = (self.root/'worker.log').open('w', encoding='utf-8');self.streams.append(stream)
        guard = OwnedCommand([sys.executable,self.worker,self.root,mode],
            report=self.root/'guardian.json',stdout=stream,timeout=timeout)
        self.guards.append(guard)
        return guard

    def test_real_timeout_reaps_child_and_grandchild_without_touching_sentinel(self):
        sentinel = subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
        self.processes.append(sentinel)
        guard = self.guard(timeout=2)
        child = self.ready(self.root/'child.json');self.ready(self.root/'grandchild.json')
        result = guard.wait(10)
        self.assertEqual((result['state'],result['exit_code']),('TIMED_OUT',124))
        self.gone(child['pid']);self.gone(child['grandchild'])
        self.assertIsNone(sentinel.poll())

    def test_real_owner_death_closes_lease_and_reaps_tree(self):
        owner = self.root/'owner.py'
        owner.write_text('''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from owned_process import OwnedCommand
root=Path(sys.argv[2])
with (root/'worker.log').open('w') as stream:
    guard=OwnedCommand([sys.executable,root/'tree.py',root],report=root/'guardian.json',stdout=stream,timeout=20)
    (root/'owner.json').write_text(json.dumps({'guardian':guard.pid}))
    guard.wait(25)
''', encoding='utf-8')
        process = subprocess.Popen([sys.executable,owner,TOOLS,self.root])
        self.processes.append(process)
        metadata = self.ready(self.root/'owner.json')
        child = self.ready(self.root/'child.json');self.ready(self.root/'grandchild.json')
        process.kill();process.wait(timeout=10)
        result = self.ready(self.root/'guardian.json')
        self.assertEqual(result['state'],'OWNER_EXITED')
        self.gone(metadata['guardian']);self.gone(child['pid']);self.gone(child['grandchild'])

    def test_real_normal_exit_preserves_status_and_cleans_lingering_descendant(self):
        guard = self.guard('exit')
        child = self.ready(self.root/'child.json')
        result = guard.wait(10)
        self.assertEqual((result['state'],result['exit_code']),('EXITED',7))
        self.gone(child['pid']);self.gone(child['grandchild'])

    def test_real_receipt_write_failure_still_terminates_owned_tree(self):
        guard=self.guard(timeout=2)
        child=self.ready(self.root/'child.json');self.ready(self.root/'grandchild.json')
        # The worker is already running. Make only its new report path unusable,
        # exercising real filesystem failure instead of a mocked writer.
        (self.root/'guardian.json').mkdir()
        with self.assertRaises(OSError):guard.wait(10)
        self.assertNotEqual(guard.process.returncode,0)
        self.gone(child['pid']);self.gone(child['grandchild'])

    def test_exited_process_with_retained_handle_is_not_observed_live(self):
        from transition_resources import process_memory
        process = subprocess.Popen([sys.executable,'-c','pass'])
        self.processes.append(process)
        process.wait(timeout=10)
        self.assertNotIn(process.pid,process_memory(process.pid)['pids'])

    def test_real_missing_command_records_failure_before_any_child(self):
        stream = (self.root/'worker.log').open('w', encoding='utf-8');self.streams.append(stream)
        guard = OwnedCommand([self.root/'missing-executable'],report=self.root/'guardian.json',stdout=stream,timeout=2)
        self.guards.append(guard)
        result = guard.wait(10)
        self.assertEqual(result['state'],'FAILED')
        self.assertNotIn('child_pid',result)


if __name__ == '__main__':
    unittest.main()
