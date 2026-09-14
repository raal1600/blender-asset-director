"""Actual installer process test in an isolated home; no desktop or API account is assumed."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from package_release import build


def main(shell):
    with tempfile.TemporaryDirectory(prefix='bad bootstrap space ') as tmp:
        home = Path(tmp).resolve()
        # Local fixture source identity, never published as a real release.
        paths = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()
                 and not any(x in p.parts for x in ('.git', '__pycache__', 'dist'))]
        archive = build(home / 'package', paths=paths, commit=os.getenv('GITHUB_SHA', '0'*40))
        sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        # The test archive uses this checkout's version, not the installer
        # entrypoint's independently pinned release/development default.
        version = tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
        env = dict(os.environ)
        env.update(BAD_CONFIG=str(home/'config'/'runtime.json'), CODEX_HOME=str(home/'codex'),
                   BAD_LIBRARY='', BAD_BLENDER='', LOCALAPPDATA=str(home/'local'), BAD_PYTHON=sys.executable)
        (home / 'codex').mkdir()
        cfg = home/'codex'/'config.toml'
        cfg.write_text('model="untouched"\n[mcp_servers.blender]\ncommand="fixture-not-executed"\n')
        original = cfg.read_bytes()
        dest = home/'skills'/'blender-asset-director'; library = home/'CGI Library'
        if shell in ('powershell', 'pwsh'):
            command = [shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT/'install.ps1'),
                       '-Version', version, '-PythonPath', sys.executable, '-Archive', str(archive), '-Sha256', sha,
                       '-SkillPath', str(dest), '-LibraryPath', str(library)]
        elif shell == 'sh':
            command = ['sh', str(ROOT/'install.sh'), '--version', version, '--archive', str(archive), '--sha256', sha,
                       '--dest', str(dest), '--library', str(library)]
        else:
            command = [sys.executable, str(ROOT/'install.py'), '--version', version, '--archive', str(archive), '--sha256', sha,
                       '--dest', str(dest), '--library', str(library)]
        for repeat in range(2):
            result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=240, cwd=home)
            print(result.stdout)
            if result.returncode:
                print(result.stderr); raise RuntimeError('Bootstrap subprocess failed')
            assert ('ALREADY_INSTALLED' if repeat else 'INSTALLED') in result.stdout
        assert cfg.read_bytes() == original
        assert (dest/'scripts/runtime/asset_director/settings.py').is_file()
        assert (dest/'references/first-run.md').is_file()
        doctor = subprocess.run([sys.executable, str(dest/'scripts/director.py'), 'doctor'],
                                cwd=home, env=env, capture_output=True, text=True, check=True, timeout=30)
        report = json.loads(doctor.stdout)
        assert report['library'] == str(library)
        assert report['environment']['codex']['connection'] == 'NOT_TESTED'
        # Genuine update branch using a valid older receipt-owned file snapshot.
        (dest/'legacy-owned.txt').write_text('older managed release fixture')
        receipt = dest/'.asset-director-install.json'; record = json.loads(receipt.read_text())
        record['files']['legacy-owned.txt'] = hashlib.sha256(b'older managed release fixture').hexdigest()
        receipt.write_text(json.dumps(record))
        cmd = command + (['-Update'] if shell in ('powershell','pwsh') else ['--update'])
        subprocess.run(cmd, env=env, cwd=home, capture_output=True, text=True, check=True, timeout=240)
        assert not (dest/'legacy-owned.txt').exists()
        assert list((home/'local/BlenderAssetDirector/install-backups').glob('*'))
        # Offline removal through the installed manager, not the source checkout.
        subprocess.run([sys.executable, str(dest/'scripts/manage_install.py'), '--dest', str(dest), '--uninstall'],
                       env=env, cwd=home, capture_output=True, text=True, check=True, timeout=30)
        assert not dest.exists() and (library/'catalog.sqlite').exists()
        assert cfg.read_bytes() == original
        print(json.dumps({'status':'PASS','shell':shell,'checks':['offline archive SHA256','real bootstrap install',
              'repeat install','update with backup','saved path discovery','host config unchanged',
              'offline uninstall preserves library'], 'live_blender_mcp':'NOT_TESTED'}))

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--shell', choices=['python','sh','powershell','pwsh'], default='python')
    main(p.parse_args().shell)
