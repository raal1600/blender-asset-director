"""Real OS lock contention, cancellation and process-exit release tests."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from asset_director.execution_resources import gpu_lease
from asset_director.core import DirectorError


class ResourceLaneTests(unittest.TestCase):
    def test_queue_is_cancellable_and_times_out_then_releases(self):
        # Separate process: this exercises actual advisory locking on Windows/Linux.
        code="from asset_director.execution_resources import gpu_lease; import time; lock=gpu_lease(); lock.__enter__(); print('HELD',flush=True); time.sleep(20)"
        env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
        child=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
        try:
            # The child has a finite life even if a failed assertion interrupts us.
            import threading
            lines=[];ready=threading.Event()
            def read(): lines.append(child.stdout.readline().strip());ready.set()
            reader=threading.Thread(target=read,daemon=True);reader.start()
            self.assertTrue(ready.wait(5),'Resource owner did not start')
            self.assertEqual(lines,['HELD'])
            with self.assertRaises(DirectorError) as failed:
                with gpu_lease(timeout=.12): self.fail('Concurrent heavy operation entered')
            self.assertEqual(failed.exception.code,'RESOURCE_QUEUE_TIMEOUT')
            calls=0
            def cancel():
                nonlocal calls
                calls+=1
                if calls>=2: raise DirectorError('TEST_CANCELLED','Explicit queued cancellation')
            with self.assertRaises(DirectorError) as failed:
                with gpu_lease(cancel): self.fail('Cancelled operation entered')
            self.assertEqual(failed.exception.code,'TEST_CANCELLED')
        finally:
            child.kill(); child.communicate(timeout=5)
        # Process death releases ownership; no lock-file deletion or PID guessing.
        with gpu_lease(timeout=.3): pass

    def test_failure_inside_lease_releases_ownership(self):
        with self.assertRaisesRegex(ValueError,'injected'):
            with gpu_lease(timeout=.3): raise ValueError('injected')
        with gpu_lease(timeout=.3): pass
