"""Receipt-owned Codex skill installation; no host/provider/MCP config changes."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = '.asset-director-install.json'


def is_link(path):
    return path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0) &
                                   getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0))


def hashes(root):
    if is_link(root):
        raise RuntimeError('Managed destination may not be a symlink or junction')
    result = {}
    for p in sorted(root.rglob('*')):
        if is_link(p):
            raise RuntimeError('Symlinks/junctions are not permitted in a managed skill')
        if p.is_file() and p.name != RECEIPT and '__pycache__' not in p.parts:
            result[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def owned(dest):
    receipt = dest / RECEIPT
    if not receipt.is_file():
        raise RuntimeError('Destination is not a managed Asset Director installation; refusing to overwrite')
    data = json.loads(receipt.read_text(encoding='utf-8'))
    if data.get('owner') != 'blender-asset-director' or data.get('files') != hashes(dest):
        raise RuntimeError('Installed files changed or unowned files were added; preserve edits and resolve manually')
    return data


def install(dest, update=False):
    if sys.version_info < (3, 11):
        raise RuntimeError('Python 3.11 or newer is required')
    dest = Path(dest).expanduser().absolute()
    if dest.exists():
        owned(dest)
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.bad-install-', dir=dest.parent))
    backup = None
    try:
        shutil.copytree(ROOT / 'skills' / 'blender-asset-director', stage, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copytree(ROOT / 'src' / 'asset_director', stage / 'scripts' / 'runtime' / 'asset_director',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        # A local, offline verify/uninstall entry point; it cannot update itself from main.
        shutil.copy2(ROOT / 'tools' / 'install_skill.py', stage / 'scripts' / 'manage_install.py')
        for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
            shutil.copy2(ROOT / name, stage / name)
        if (ROOT / '_release.json').is_file():
            shutil.copy2(ROOT / '_release.json', stage / 'RELEASE.json')
        expected = hashes(stage)
        if dest.exists() and owned(dest)['files'] == expected:
            return {'status': 'ALREADY_INSTALLED', 'version': version, 'path': str(dest), 'host_config_modified': False}
        if dest.exists() and not update:
            raise RuntimeError('A different managed version exists. Re-run with --update after reviewing the release')
        # Prove the bundled entry point can import/run before replacing a good installation.
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env.pop('PYTHONPATH', None)
            env['BAD_CONFIG'] = str(Path(tmp) / 'absent-settings.json')
            check = subprocess.run([sys.executable, str(stage / 'scripts' / 'director.py'), '--help'],
                                   capture_output=True, text=True, env=env, timeout=30)
            if check.returncode:
                raise RuntimeError('Bundled runtime smoke test failed; previous installation unchanged')
        data = {'owner': 'blender-asset-director', 'version': version, 'files': hashes(stage)}
        (stage / RECEIPT).write_text(json.dumps(data, sort_keys=True, indent=2), encoding='utf-8')
        if dest.exists():
            base = Path(os.getenv('LOCALAPPDATA', str(Path.home() / '.local' / 'share'))) / 'BlenderAssetDirector' / 'install-backups'
            base.mkdir(parents=True, exist_ok=True)
            backup = base / (dest.name + '-' + str(time.time_ns()))
            shutil.move(str(dest), str(backup))
        try:
            os.replace(stage, dest)
        except BaseException:
            if backup and backup.exists():
                shutil.move(str(backup), str(dest))
            raise
        return {'status': 'INSTALLED', 'version': version, 'path': str(dest),
                'backup': str(backup) if backup else None, 'host_config_modified': False}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def uninstall(dest):
    dest = Path(dest).expanduser().absolute()
    owned(dest)
    shutil.rmtree(dest)
    return {'status': 'UNINSTALLED', 'path': str(dest), 'asset_library_removed': False,
            'runtime_settings_removed': False, 'host_config_modified': False}


def self_test():
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / 'skills' / 'blender-asset-director'
        install(dest)
        assert install(dest)['status'] == 'ALREADY_INSTALLED'
        env = dict(os.environ); env['BAD_CONFIG'] = str(Path(d) / 'runtime.json')
        cmd = [sys.executable, str(dest / 'scripts' / 'director.py'), '--library', str(Path(d) / 'library'),
               'plan', 'Present the supplied object clearly']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env, timeout=30)
        assert json.loads(result.stdout)['status'] == 'HOST_INTERPRETATION_REQUIRED'
        assert (dest / 'references' / 'roles' / 'cinematography.md').is_file()
        assert (dest / 'references' / 'upstream-licenses.md').is_file()
        (dest / 'SKILL.md').write_text('user edit', encoding='utf-8')
        try:
            install(dest, True)
        except RuntimeError:
            pass
        else:
            raise AssertionError('Installer overwrote user edits')
        shutil.copy2(ROOT / 'skills' / 'blender-asset-director' / 'SKILL.md', dest / 'SKILL.md')
        uninstall(dest)
        assert not dest.exists() and (Path(d) / 'library').exists()
    print(json.dumps({'status': 'PASS', 'checks': ['fresh install', 'repeat install', 'bundled runtime launch',
                     'role and license files', 'edited-file protection', 'uninstall preserves library']}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dest', default=str(Path.home() / '.agents' / 'skills' / 'blender-asset-director'))
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--update', action='store_true'); mode.add_argument('--uninstall', action='store_true')
    mode.add_argument('--verify', action='store_true'); mode.add_argument('--self-test', action='store_true')
    p.add_argument('--configure', action='store_true', help='Save only Asset Director local paths and initialize its library')
    p.add_argument('--library'); p.add_argument('--blender')
    a = p.parse_args()
    try:
        if a.self_test:
            self_test(); return 0
        if a.uninstall:
            result = uninstall(a.dest)
        elif a.verify:
            result = {'status': 'VERIFIED', 'version': owned(Path(a.dest))['version']}
        else:
            result = install(a.dest, a.update)
            if a.configure:
                sys.path.insert(0, str(Path(a.dest) / 'scripts' / 'runtime'))
                from asset_director import settings
                result['configuration'] = settings.configure(library=a.library, blender=a.blender, skill_path=a.dest)
                result['health'] = settings.health()
            result['next'] = 'Open a new Codex session and invoke $blender-asset-director for a read-only first-run check'
        print(json.dumps(result, ensure_ascii=True)); return 0
    except Exception as exc:
        print(json.dumps({'status': 'ERROR', 'message': str(exc)}, ensure_ascii=True)); return 2

if __name__ == '__main__':
    raise SystemExit(main())
