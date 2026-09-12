"""Explicit, receipt-owned Codex skill deployment. Never edits Codex/MCP config."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
RECEIPT='.asset-director-install.json'


def hashes(root):
    result={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():raise RuntimeError('Symlinks are not permitted in a managed skill')
        if p.is_file() and p.name!=RECEIPT and '__pycache__' not in p.parts:
            result[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def owned(dest):
    receipt=dest/RECEIPT
    if not receipt.is_file():raise RuntimeError('Existing destination has no Asset Director ownership receipt; refusing to overwrite')
    data=json.loads(receipt.read_text(encoding='utf-8'))
    if data.get('owner')!='blender-asset-director' or data.get('files')!=hashes(dest):
        raise RuntimeError('Installed files changed or unowned files were added; preserve edits and resolve manually')


def install(dest,update=False):
    dest=Path(dest).expanduser().absolute()
    if dest.is_symlink():raise RuntimeError('Skill destination may not be a symlink')
    if dest.exists():
        if not update:raise RuntimeError('Already installed. Use --update only after reviewing changes')
        owned(dest)
    dest.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='bad-install-',dir=dest.parent))
    backup=None
    try:
        shutil.copytree(ROOT/'skills'/'blender-asset-director',stage,dirs_exist_ok=True)
        shutil.copytree(ROOT/'src'/'asset_director',stage/'scripts'/'runtime'/'asset_director',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        license_file=ROOT/'LICENSE'
        if license_file.exists():shutil.copy2(license_file,stage/'LICENSE')
        data={'owner':'blender-asset-director','version':'0.1.0','files':hashes(stage)}
        (stage/RECEIPT).write_text(json.dumps(data,sort_keys=True,indent=2),encoding='utf-8')
        if dest.exists():
            base=Path(os.getenv('LOCALAPPDATA',str(Path.home()/'.local'/'share')))/'BlenderAssetDirector'/'install-backups'
            base.mkdir(parents=True,exist_ok=True)
            backup=base/(dest.name+'-'+str(time.time_ns()))
            shutil.move(str(dest),str(backup))
        try:os.replace(stage,dest)
        except BaseException:
            if backup and backup.exists():shutil.move(str(backup),str(dest))
            raise
        return {'status':'INSTALLED','path':str(dest),'backup':str(backup) if backup else None,
                'host_config_modified':False,'next':'Start a fresh host session if its skill discovery is cached; verify $blender-asset-director is listed'}
    finally:
        if stage.exists():shutil.rmtree(stage)


def uninstall(dest):
    dest=Path(dest).expanduser().absolute();owned(dest);shutil.rmtree(dest)
    return {'status':'UNINSTALLED','path':str(dest),'asset_library_removed':False,'host_config_modified':False}


def self_test():
    with tempfile.TemporaryDirectory() as d:
        dest=Path(d)/'skills'/'blender-asset-director';install(dest)
        cmd=[sys.executable,str(dest/'scripts'/'director.py'),'--library',str(Path(d)/'library'),'plan','warrior walks and stops']
        result=subprocess.run(cmd,capture_output=True,text=True,check=True)
        assert json.loads(result.stdout)['motions']
        (dest/'SKILL.md').write_text('user edit',encoding='utf-8')
        try:install(dest,True)
        except RuntimeError:pass
        else:raise AssertionError('Installer overwrote user edits')
        # Restore exact receipt-owned bytes then verify explicit uninstall.
        shutil.copy2(ROOT/'skills'/'blender-asset-director'/'SKILL.md',dest/'SKILL.md')
        uninstall(dest);assert not dest.exists();assert (Path(d)/'library').exists()
    print(json.dumps({'status':'PASS','checks':['fresh install','bundled runtime launch','edited-file protection','uninstall preserves library']}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dest',default=str(Path.home()/'.agents'/'skills'/'blender-asset-director'))
    p.add_argument('--update',action='store_true');p.add_argument('--uninstall',action='store_true');p.add_argument('--self-test',action='store_true');a=p.parse_args()
    if a.self_test:self_test()
    else:print(json.dumps(uninstall(a.dest) if a.uninstall else install(a.dest,a.update)))
