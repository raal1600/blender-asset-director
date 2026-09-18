"""Candidate integrity/refusal tests use fake host bytes, not a native GUI pass."""
import copy
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from install_workbench_candidate import verify_bundle, HOST_FILES

SHA = 'a' * 40


def bundle(root):
    names = ['tools/create_workbench_studio.py','tools/install_skill.py','tools/install_workbench_candidate.py',
             'launcher/server.mjs','launcher/public/workbench.html','src/asset_director/__init__.py',
             'Setup.ps1','Setup.cmd', *('launcher/'+n for n in HOST_FILES)]
    for name in names:
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('SYNTHETIC FILE: '+name)
    build={'commit':SHA,'files':{n:hashlib.sha256((root/'launcher'/n).read_bytes()).hexdigest() for n in HOST_FILES}}
    (root/'launcher/windows-build.json').write_text(json.dumps(build))
    m={'schema':'asset-director.workbench-candidate/1','source_commit':SHA,'source_tree':'b'*40,
       'files':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}}
    (root/'CANDIDATE.json').write_text(json.dumps(m))
    return m,build


class CandidateTests(unittest.TestCase):
    def test_intact_bundle_has_no_production_acceptance_side_effect(self):
        with TemporaryDirectory() as d:
            root=Path(d);m,_=bundle(root)
            self.assertEqual(verify_bundle(root)['source_commit'],SHA)
            self.assertFalse((root/'candidate-install.json').exists())
    def test_changed_missing_extra_and_escaped_files_refused(self):
        for case in ('changed','missing','extra','escape','source-id','tree-id','host-id','host-hash'):
            with self.subTest(case=case),TemporaryDirectory() as d:
                root=Path(d);m,b= bundle(root)
                if case=='changed':(root/'Setup.ps1').write_text('changed')
                if case=='missing':(root/'Setup.ps1').unlink()
                if case=='extra':(root/'tools/extra.py').write_text('unlisted')
                if case=='escape':m['files']['../outside.py']='c'*64
                if case=='source-id':m['source_commit']='main'
                if case=='tree-id':m.pop('source_tree')
                if case.startswith('host-'):
                    if case=='host-id':b['commit']='c'*40
                    else:b['files']['Asset Director.exe']='d'*64
                    (root/'launcher/windows-build.json').write_text(json.dumps(b))
                    m['files']['launcher/windows-build.json']=hashlib.sha256((root/'launcher/windows-build.json').read_bytes()).hexdigest()
                (root/'CANDIDATE.json').write_text(json.dumps(m))
                with self.assertRaises(ValueError):verify_bundle(root)

    def test_full_new_studio_setup_keeps_original_bundle_and_refuses_reinstallation(self):
        import subprocess
        import shutil
        repository=Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as d:
            root=Path(d)/'bundle';root.mkdir()
            for name in ('tools','src','skills','launcher'):
                shutil.copytree(repository/name,root/name,ignore=shutil.ignore_patterns('__pycache__','.deps','*.pyc','node_modules','*.exe','*.dll'))
            for name in ('pyproject.toml','LICENSE','THIRD_PARTY_NOTICES.md'):shutil.copy2(repository/name,root/name)
            for name in HOST_FILES:(root/'launcher'/name).write_text('SYNTHETIC HOST NEVER EXECUTED')
            (root/'Setup.ps1').write_text('# synthetic bootstrap')
            (root/'Setup.cmd').write_text('rem synthetic bootstrap')
            build={'commit':SHA,'files':{n:hashlib.sha256((root/'launcher'/n).read_bytes()).hexdigest() for n in HOST_FILES}}
            (root/'launcher/windows-build.json').write_text(json.dumps(build))
            manifest={'schema':'asset-director.workbench-candidate/1','source_commit':SHA,'source_tree':'b'*40,
                'files':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}}
            (root/'CANDIDATE.json').write_text(json.dumps(manifest))
            target=Path(d)/'new-studio'
            args=[sys.executable,str(root/'tools/install_workbench_candidate.py'),'--root',str(target)]
            for name in ('python','blender','codex','ffmpeg','ffprobe'):args+=['--'+name,sys.executable]
            result=subprocess.run(args,capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            receipt=json.loads((target/'candidate-install.json').read_text())
            self.assertEqual(receipt['status'],'CANDIDATE_INSTALLED');self.assertFalse(receipt['user_environment_accepted'])
            self.assertTrue((target/'Open Workbench.cmd').exists())
            original=(target/'candidate-install.json').read_bytes()
            again=subprocess.run(args,capture_output=True,text=True,timeout=60)
            self.assertNotEqual(again.returncode,0);self.assertEqual((target/'candidate-install.json').read_bytes(),original)
            verify_bundle(root)
