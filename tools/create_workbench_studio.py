"""Create an isolated, new-only workbench studio. Never upgrade a user's studio.

Copies source and the managed skill, not assets, secrets, model accounts or host
preferences. Executable paths are checked for existence; actual runtime readiness
and native GUI acceptance remain separate explicit checks.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director.core import Library
from install_skill import install


def _executable(value, label):
    path = Path(value)
    if not path.is_absolute() or not path.is_file():
        raise ValueError(label + ' must name an existing absolute executable path')
    return str(path.resolve())


def create(root, blender, python, codex, *, source_commit=None, ffmpeg=None, ffprobe=None):
    requested = Path(root).expanduser().absolute()
    if requested.exists() or requested.is_symlink():
        raise ValueError('Studio already exists; choose a new isolated directory')
    configured = {key: _executable(value, key) for key, value in
                  [('blender', blender), ('python', python), ('codex', codex)]}
    if source_commit is not None and not re.fullmatch(r'[a-f0-9]{40}', source_commit):
        raise ValueError('source_commit must be a complete Git commit SHA')
    if bool(ffmpeg) != bool(ffprobe):
        raise ValueError('Configure both FFmpeg and FFprobe, or neither')
    if ffmpeg:
        configured.update(ffmpeg=_executable(ffmpeg, 'FFmpeg'), ffprobe=_executable(ffprobe, 'FFprobe'))
    requested.parent.mkdir(parents=True, exist_ok=True)
    root = requested.parent.resolve() / requested.name
    root.mkdir()  # Exclusive; races with another creator fail, never overwrite.
    receipt = root / 'studio-setup.json'
    verified_commit=False
    if source_commit:
        try:
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL,timeout=10).strip()
            dirty=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL,timeout=10).strip()
            verified_commit=head==source_commit and not dirty
        except (OSError,subprocess.SubprocessError):pass
    result = {'schema': 1, 'status': 'CREATING', 'source_commit': source_commit,'source_commit_verified':verified_commit,
              'production_installed': False, 'runtime_ready': 'NOT_VERIFIED',
              'native_gui': 'NOT_TESTED', 'root': str(root)}
    receipt.write_text(json.dumps(result, indent=2), encoding='utf-8')
    try:
        for relative in ['Database/Animations', 'Database/Characters', 'Database/Meshes',
                         'Database/Registry', 'Workspace/Projects', 'Docs', 'Archive',
                         'SystemRuntime/UserData/Launcher']:
            (root / relative).mkdir(parents=True, exist_ok=True)
        skill = root / 'SystemRuntime/Skills/blender-asset-director'
        install(skill)
        launcher = root / 'SystemRuntime/Launcher'
        shutil.copytree(ROOT / 'launcher', launcher, ignore=shutil.ignore_patterns(
            '__pycache__', '*.pyc', 'node_modules', '.deps', '*.exe', '*.dll', '.git'))
        library = root / 'Database/AssetDirector'
        with Library(library):
            pass
        # Zero requests a distinct OS-assigned loopback port, not the live studio's port.
        configured.update(skill=str(skill), library=str(library), mcpPort=9876, port=0)
        (root / 'SystemRuntime/UserData/Launcher/config.json').write_text(
            json.dumps(configured, indent=2), encoding='utf-8')
        # Preserve the copied content independently of the Git label. A clean
        # HEAD check above verifies only source provenance, never GUI readiness.
        result.update(status='CREATED', files={
            f.relative_to(root).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
            for folder in (skill, launcher) for f in sorted(folder.rglob('*'))
            if f.is_file() and '__pycache__' not in f.parts})
        receipt.write_text(json.dumps(result, indent=2), encoding='utf-8')
        return result
    except BaseException as exc:
        result.update(status='FAILED', error=str(exc))
        receipt.write_text(json.dumps(result, indent=2), encoding='utf-8')
        raise  # Keep the new partial directory for inspection; no broad deletion.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--blender', required=True)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--codex', required=True)
    parser.add_argument('--source-commit')
    parser.add_argument('--ffmpeg')
    parser.add_argument('--ffprobe')
    args = vars(parser.parse_args())
    print(json.dumps(create(**args), indent=2))


if __name__ == '__main__':
    main()
