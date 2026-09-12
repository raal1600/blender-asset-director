"""Reproducible release archive of tracked files, plus source identity and checksums."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(output, *, paths=None, commit=None):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    if commit is None:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('An exact source commit is required')
    if paths is None:
        paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    archive = output / f'blender-asset-director-{version}.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in sorted(p for p in paths if p):
            p = ROOT / name
            if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(ROOT.resolve()):
                raise ValueError('Invalid tracked source entry')
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, p.read_bytes())
        info = zipfile.ZipInfo('_release.json', (2026, 1, 1, 0, 0, 0))
        info.external_attr = 0o100644 << 16
        z.writestr(info, json.dumps({'version': version, 'commit': commit}, sort_keys=True))
    files = [archive]
    for name in ('install.py', 'install.ps1', 'install.sh'):
        dest = output / name; dest.write_bytes((ROOT / name).read_bytes()); files.append(dest)
    (output / 'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in files), encoding='utf-8')
    return archive

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output', default='dist'); args = p.parse_args()
    print(build(args.output))
