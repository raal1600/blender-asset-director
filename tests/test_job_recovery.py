"""Crash recovery keeps evidence and never guesses that a live process stopped."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from asset_director import jobs
from asset_director.core import Library, DirectorError, atomic_json

class JobRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.lib=Library(Path(self.tmp.name)/'library');self.addCleanup(self.lib.close)
        self.job=jobs.prepare(self.lib,'inspect');self.directory=self.lib.root/'jobs'/self.job['id'];self.path=self.directory/'job.json'
        self.job.update(state='RUNNING',started_at=1.);atomic_json(self.path,self.job)
        child=subprocess.Popen([sys.executable,'-c','pass']);self.dead=child.pid;child.wait(timeout=10)
        self.runlock=self.lib.root/('.run-'+self.job['id']+'.lock');self.runlock.write_text(str(self.dead))
        self.marker={'job_id':self.job['id'],'implementation':self.job['specification']['implementation'],'pid':self.dead,'started_at':1.}
        atomic_json(self.directory/'worker-process.json',self.marker)
    def recover(self):return jobs.recover(self.lib,self.job['id'],confirmed=True)
    def test_dead_legacy_worker_and_executor_recover_without_adopting_output(self):
        (self.directory/'result.blend').write_bytes(b'unaccepted partial scene');(self.directory/'worker.log').write_text('interrupted execution')
        result=self.recover();self.assertEqual(result['state'],'INTERRUPTED');self.assertEqual(result['outputs'],[])
        self.assertFalse(self.runlock.exists());self.assertEqual((self.directory/'result.blend').read_bytes(),b'unaccepted partial scene')
        self.assertEqual(json.loads((self.directory/'recovery.json').read_text())['original_state'],'RUNNING')
        self.assertEqual(self.recover()['state'],'INTERRUPTED')
        jobs.retry(self.lib,self.job['id']);self.assertTrue(list(self.directory.glob('attempt-*/recovery.json')))
    def test_explicit_confirmation_is_required(self):
        with self.assertRaises(DirectorError):jobs.recover(self.lib,self.job['id'])
        self.assertEqual(json.loads(self.path.read_text())['state'],'RUNNING')
    def test_live_worker_refuses_and_preserves_receipt(self):
        child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
        try:
            atomic_json(self.directory/'worker-process.json',self.marker|{'pid':child.pid})
            before=self.path.read_bytes()
            with self.assertRaises(DirectorError) as caught:self.recover()
            self.assertEqual(caught.exception.code,'JOB_STILL_RUNNING');self.assertEqual(self.path.read_bytes(),before);self.assertTrue(self.runlock.exists())
        finally:
            child.kill();child.wait(timeout=10)
    def test_live_executor_refuses_even_after_worker_exit(self):
        self.runlock.write_text(str(os.getpid()))
        with self.assertRaises(DirectorError) as caught:self.recover()
        self.assertEqual(caught.exception.code,'JOB_STILL_RUNNING')
    def test_missing_or_wrong_worker_marker_refuses(self):
        for marker in [None,self.marker|{'job_id':'j_'+'0'*24},self.marker|{'implementation':'0'*64}]:
            p=self.directory/'worker-process.json'
            if marker is None:p.unlink(missing_ok=True)
            else:atomic_json(p,marker)
            with self.assertRaises(DirectorError):self.recover()
            self.assertEqual(json.loads(self.path.read_text())['state'],'RUNNING')
    def test_recovery_after_code_change_cannot_bypass_execution_validation(self):
        with patch('asset_director.jobs.implementation_hash',return_value='changed'):
            self.assertEqual(self.recover()['state'],'INTERRUPTED')
            with self.assertRaises(DirectorError) as caught:jobs.retry(self.lib,self.job['id'])
            self.assertEqual(caught.exception.code,'STALE_IMPLEMENTATION')
    def test_running_worker_is_not_inferred_dead_from_changed_birth_without_identity(self):
        from asset_director.process_state import stopped
        with patch('asset_director.process_state.identity',return_value={'pid':12,'birth':99}):
            self.assertTrue(stopped({'pid':12,'birth':98}))
            self.assertFalse(stopped({'pid':12,'birth':99}))
            self.assertFalse(stopped({'pid':12}))
    def test_execution_lease_refuses_concurrent_recovery(self):
        from asset_director.execution_resources import process_lease
        with process_lease(self.lib.root/('.execution-'+self.job['id']+'.lock')):
            with self.assertRaises(DirectorError) as caught:self.recover()
            self.assertEqual(caught.exception.code,'RESOURCE_QUEUE_TIMEOUT')
        self.assertEqual(json.loads(self.path.read_text())['state'],'RUNNING')
    def test_owned_worker_exits_after_executor_death(self):
        import time
        from asset_director.process_state import identity,stopped
        marker=Path(self.tmp.name)/'owned-worker.json'
        child_code="import sys,time,json,os;from pathlib import Path;from asset_director.process_state import watch_parent,identity;watch_parent(json.loads(sys.argv[1]));Path(sys.argv[2]).write_text(json.dumps(identity(os.getpid())));time.sleep(30)"
        parent_code="import sys,time,json,subprocess,os;from asset_director.process_state import identity;subprocess.Popen([sys.executable,'-c',sys.argv[1],json.dumps(identity(os.getpid())),sys.argv[2]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);time.sleep(30)"
        parent=subprocess.Popen([sys.executable,'-c',parent_code,child_code,str(marker)]);worker=None
        try:
            deadline=time.monotonic()+10
            while not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(marker.exists(),'Owned child never started');worker=json.loads(marker.read_text())
            self.assertFalse(stopped(worker));parent.kill();parent.wait(timeout=10)
            deadline=time.monotonic()+5
            while not stopped(worker) and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(stopped(worker),'Owned child remained alive after executor exit')
        finally:
            if parent.poll() is None:parent.kill();parent.wait(timeout=10)
            if worker and not stopped(worker):os.kill(worker['pid'],__import__('signal').SIGTERM)

    def test_unknown_process_state_is_not_treated_as_exit(self):
        with patch('asset_director.process_state.identity',side_effect=DirectorError('PROCESS_STATE_UNKNOWN','Unknown')):
            with self.assertRaises(DirectorError):self.recover()
        self.assertEqual(json.loads(self.path.read_text())['state'],'RUNNING')

if __name__=='__main__':unittest.main()
