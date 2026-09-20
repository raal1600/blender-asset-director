"""Create a source/Windows-host candidate only after matching native evidence.

An Actions artifact, not a release or automatic installed-runtime update.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
from install_workbench_candidate import HOST_FILES, verify_bundle
from native_desktop_contract import verify as verify_native


def pack(destination, host, native):
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
    if os.environ.get('GITHUB_SHA') and os.environ['GITHUB_SHA'] != commit:
        raise ValueError('Package source is not the accepted workflow revision')
    if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT):
        raise ValueError('Tracked source changed after acceptance')
    build = json.loads((Path(host) / 'windows-build.json').read_text(encoding='utf-8-sig'))
    if build['commit'] != commit or set(build['files']) != set(HOST_FILES):
        raise ValueError('Windows host source identity or payload mismatch')
    report = verify_native(native, commit)
    if report['checks'][0]['exe_sha256'] != build['files']['Asset Director.exe']:
        raise ValueError('Native acceptance executed a different desktop binary')
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')[:-1]
    with tempfile.TemporaryDirectory(prefix='ad-candidate-') as d:
        folder = Path(d) / 'Asset-Director-Candidate'; folder.mkdir()
        for name in names:
            file = ROOT / name
            if file.is_symlink() or not file.is_file():
                raise ValueError('Non-file candidate source: ' + name)
            out = folder / name; out.parent.mkdir(parents=True, exist_ok=True);shutil.copy2(file, out)
        for name in (*HOST_FILES, 'windows-build.json'):
            file = Path(host) / name
            if name in HOST_FILES and hashlib.sha256(file.read_bytes()).hexdigest() != build['files'][name]:
                raise ValueError('Windows host bytes changed: ' + name)
            shutil.copy2(file, folder / 'launcher' / name)
        shutil.copy2(ROOT / 'tools/setup_workbench_candidate.ps1', folder / 'Setup.ps1')
        (folder / 'Setup.cmd').write_text('@echo off\r\npowershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup.ps1"\r\npause\r\n', encoding='utf-8')
        (folder / 'START-HERE.txt').write_text(
            'ASSET DIRECTOR - WINDOWS CANDIDATE\n\n'
            'Extract the entire folder, then run Setup.cmd.\n'
            'Existing Python, Node.js, Blender, Codex, FFmpeg and FFprobe are required.\n'
            'Setup only reads executable paths from a studio you select. It creates a NEW studio;\n'
            'no assets, catalog contents, credentials or preferences are copied.\n'
            'After setup, use the new studio Open Workbench.cmd.\n\n'
            'Supported initial output: short silent H.264 films. See docs/SCENE_WORKBENCH_MVP.md.\n'
            'Read docs/WORKBENCH_LOCAL_ACCEPTANCE.md before production use.\n'
            'Public CI and native scripted tests do not replace your environment and creative review.\n'
            'This is not a signed release, and setup does not download dependencies.\n\n'
            'Source: '+commit+'\nTree: '+tree+'\n', encoding='utf-8')
        identity = dict(schema='asset-director.workbench-candidate/1', source_commit=commit, source_tree=tree,
            ci=dict(repository=os.environ.get('GITHUB_REPOSITORY'),run_id=os.environ.get('GITHUB_RUN_ID'),
                    native_report_sha256=hashlib.sha256((Path(native)/'report.json').read_bytes()).hexdigest()),
            production_accepted=False, scope='NEW_ONLY_WINDOWS_CANDIDATE',
            files={f.relative_to(folder).as_posix():hashlib.sha256(f.read_bytes()).hexdigest()
                   for f in sorted(folder.rglob('*')) if f.is_file()})
        (folder/'CANDIDATE.json').write_text(json.dumps(identity,indent=2)+'\n',encoding='utf-8')
        verify_bundle(folder)
        destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(folder.rglob('*')):
                if file.is_file():archive.write(file,file.relative_to(folder.parent).as_posix())
    digest=hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix('.sha256').write_text(digest+'  '+destination.name+'\n',encoding='utf-8')
    return {'source_commit':commit,'source_tree':tree,'sha256':digest,'path':str(destination)}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--host',type=Path,required=True);p.add_argument('--native',type=Path,required=True)
    a=p.parse_args();print(json.dumps(pack(a.output,a.host,a.native),indent=2))
