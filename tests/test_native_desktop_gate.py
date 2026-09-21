"""Synthetic parser tests; not native desktop pass evidence."""
import copy
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native_desktop_contract import DESKTOP_CHECKS, ARTIFACTS, SCHEMA, verify
from evidence import write, digest


class NativeGateTests(unittest.TestCase):
    def test_missing_stale_skipped_and_tampered_native_evidence_is_refused(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            for name in ARTIFACTS:(root/name).write_text('parser fixture only')
            report=dict(schema=SCHEMA,kind='desktop',partition='native-roundtrip',platform='win32',status='PASS',
                        commit='a'*40,checks=[dict(id=k,status='PASS') for k in DESKTOP_CHECKS],
                        artifacts={n:digest(root/n) for n in ARTIFACTS})
            write(root/'report.json',report);verify(root,'a'*40)
            for key,value in [('commit','b'*40),('status','SKIPPED'),('platform','linux'),('checks',report['checks'][:-1]),('artifacts',{})]:
                wrong=copy.deepcopy(report);wrong[key]=value;write(root/'report.json',wrong)
                with self.assertRaises(ValueError):verify(root,'a'*40)
            write(root/'report.json',report);(root/'native-blender.png').write_text('tampered')
            with self.assertRaises(ValueError):verify(root,'a'*40)
