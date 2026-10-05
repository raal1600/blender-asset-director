"""PID-reuse regression for read-only acceptance resource observation."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import transition_resources as resources


class ResourceIdentityTests(unittest.TestCase):
    def test_stale_parent_pid_does_not_adopt_older_unrelated_process(self):
        rows={10:{'parent':1,'birth':500,'resident_bytes':1},
              20:{'parent':10,'birth':600,'resident_bytes':2},
              30:{'parent':20,'birth':700,'resident_bytes':4},
              40:{'parent':20,'birth':100,'resident_bytes':1000000},
              50:{'parent':40,'birth':150,'resident_bytes':1000000}}
        self.assertEqual(resources._select_tree(rows,10,{'pid':10,'birth':500}),[10,20,30])
        self.assertEqual(resources._select_tree(rows,10,{'pid':10,'birth':499}),[])
        self.assertEqual(resources._select_tree(rows,99),[])

    def test_release_matches_birth_and_query_failure_is_unknown(self):
        original={'pid':20,'birth':100}
        with patch.object(resources,'process_identity',return_value={'pid':20,'birth':200}):
            self.assertIs(resources.identity_alive(original),False)
        with patch.object(resources,'process_identity',return_value=original):
            self.assertIs(resources.identity_alive(original),True)
        with patch.object(resources,'process_identity',side_effect=PermissionError('injected query denial')):
            self.assertIsNone(resources.identity_alive(original))

    def test_linux_stat_has_one_bound_parent_birth_and_rss_record(self):
        fields=['S','40']+['0']*17+['12345','4096','7']
        parsed=resources._linux_stat('70 (name with ) parentheses) '+' '.join(fields),4096)
        self.assertEqual(parsed,{'parent':40,'birth':12345,'resident_bytes':7*4096})
        fields[0]='Z'
        self.assertIsNone(resources._linux_stat('70 (zombie) '+' '.join(fields),4096))

    @unittest.skipUnless(os.name=='nt','Windows exact-handle/snapshot API contract')
    def test_windows_snapshot_rejects_a_pid_reused_before_open(self):
        class Kernel:
            def WaitForSingleObject(self,*args):return 258
            def GetProcessTimes(self,handle,created,*args):
                created._obj.dwHighDateTime=0;created._obj.dwLowDateTime=200;return 1
        with patch.object(resources,'_windows_api',return_value=Kernel()):
            self.assertIsNone(resources._windows_row(20,handle=1,upper_birth=150))
            self.assertEqual(resources._windows_row(20,handle=1,upper_birth=250)['birth'],200)

    @unittest.skipUnless(os.name=='nt' or Path('/proc').is_dir(),'OS RSS/creation observer available on Windows/Linux')
    def test_real_process_identity_and_exit_are_bound(self):
        child=subprocess.Popen([sys.executable,'-c','import time; x=bytearray(4*1024*1024); time.sleep(1.5)'])
        try:
            identity=resources.process_identity(child.pid,handle=getattr(child,'_handle',None))
            self.assertIsNotNone(identity)
            observed=resources.process_memory(child.pid,identity)
            self.assertIn(identity,observed['identities']);self.assertGreater(observed['resident_bytes'],0)
            self.assertEqual(resources.process_memory(child.pid,{'pid':child.pid,'birth':identity['birth']-1})['pids'],[])
            child.wait(timeout=5)
            self.assertIs(resources.identity_alive(identity),False)
        finally:
            if child.poll() is None:child.kill();child.wait(timeout=5)

    @unittest.skipUnless(os.name=='nt' or Path('/proc').is_dir(),'OS RSS/creation observer available on Windows/Linux')
    def test_real_guarded_measurement_releases_observed_identities(self):
        with tempfile.TemporaryDirectory(prefix='resource-identity-') as folder:
            root=Path(folder)
            result=resources.measured_run([sys.executable,'-c','import time; x=bytearray(4*1024*1024); time.sleep(1.2)'],root/'process.log',cwd=root,timeout=8)
            self.assertEqual(result['exit_code'],0);self.assertEqual(result['observed_process_release'],'PASS')
            self.assertTrue(result['observed_process_identities']);self.assertEqual(result['remaining_observed_identities'],[])
            self.assertGreater(result['peak_host_resident_bytes'],0)


    @unittest.skipUnless(os.name=='nt' or Path('/proc').is_dir(),'OS RSS/creation observer available on Windows/Linux')
    def test_absent_root_identity_does_not_report_verified_release(self):
        with tempfile.TemporaryDirectory(prefix='resource-unknown-root-') as folder, patch.object(resources,'process_identity',return_value=None):
            root=Path(folder)
            result=resources.measured_run([sys.executable,'-c','pass'],root/'process.log',cwd=root,timeout=8)
            self.assertEqual(result['exit_code'],0)
            self.assertEqual(result['observed_process_release'],'NOT_VERIFIED')
            self.assertEqual(result['observed_process_identities'],[])

    @unittest.skipUnless(os.name=='nt' or Path('/proc').is_dir(),'OS RSS/creation observer available on Windows/Linux')
    def test_unknown_observed_identity_does_not_pass_release(self):
        with tempfile.TemporaryDirectory(prefix='resource-unknown-exit-') as folder, patch.object(resources,'identity_alive',return_value=None):
            root=Path(folder)
            result=resources.measured_run([sys.executable,'-c','import time;time.sleep(.8)'],root/'process.log',cwd=root,timeout=8)
            self.assertEqual(result['exit_code'],0)
            self.assertEqual(result['observed_process_release'],'UNKNOWN')
            self.assertTrue(result['remaining_observed_identities'])
            self.assertTrue(all(r['status']=='UNKNOWN' for r in result['remaining_observed_identities']))


if __name__=='__main__':unittest.main()
