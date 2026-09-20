"""Verify a candidate bundle and create a NEW studio; never upgrade in place.

This installer reads only executable paths from an explicitly selected existing
studio config. Assets, catalog contents, sessions, credentials, and preferences
are not copied. Checksum integrity is not an independent publisher signature.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
HOST_FILES = ('Asset Director.exe', 'Microsoft.Web.WebView2.Core.dll',
              'Microsoft.Web.WebView2.WinForms.dll', 'WebView2Loader.dll')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def verify_bundle(root):
    root = Path(root).resolve()
    manifest = read(root / 'CANDIDATE.json')
    if manifest.get('schema') != 'asset-director.workbench-candidate/1':
        raise ValueError('Unsupported candidate bundle')
    if not all(re.fullmatch('[a-f0-9]{40}', str(manifest.get(k, ''))) for k in ('source_commit','source_tree')):
        raise ValueError('Candidate source commit is missing')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files or len(files) > 5000:
        raise ValueError('Invalid candidate file manifest')
    required = {'tools/create_workbench_studio.py', 'tools/install_skill.py', 'tools/install_workbench_candidate.py',
                'launcher/server.mjs', 'launcher/public/workbench.html', 'launcher/windows-build.json',
                'src/asset_director/__init__.py', 'Setup.ps1', 'Setup.cmd'}
    required.update('launcher/' + n for n in HOST_FILES)
    if not required.issubset(files):
        raise ValueError('Candidate bundle is missing its runtime or setup files')
    for name, expected in files.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
            raise ValueError('Unsafe candidate path')
        file = root.joinpath(*relative.parts)
        if file.is_symlink() or not file.resolve().is_relative_to(root) or not file.is_file():
            raise ValueError('Candidate file is missing or leaves the bundle: ' + name)
        if not re.fullmatch('[a-f0-9]{64}', str(expected)):
            raise ValueError('Invalid candidate checksum')
        with file.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected:
            raise ValueError('Candidate file changed: ' + name)
    # Unexpected source code can shadow imports; do not ignore it during verification.
    actual = {f.relative_to(root).as_posix() for f in root.rglob('*')
              if f.is_file() and f.relative_to(root).as_posix() != 'CANDIDATE.json'}
    if actual != set(files):
        raise ValueError('Bundle contains unlisted or missing files')
    build = read(root / 'launcher/windows-build.json')
    if build.get('commit') != manifest['source_commit']:
        raise ValueError('Windows host and source come from different commits')
    if set(build.get('files', {})) != set(HOST_FILES):
        raise ValueError('Unexpected Windows build payload')
    for name, expected in build['files'].items():
        if files['launcher/' + name] != expected:
            raise ValueError('Windows host hash disagrees with its build receipt')
    return manifest


def install_candidate(target, config, bundle=ROOT):
    bundle = Path(bundle).resolve()
    manifest = verify_bundle(bundle)
    allowed = {'python', 'blender', 'codex', 'ffmpeg', 'ffprobe'}
    tools = {k: v for k, v in config.items() if k in allowed and v}
    for name in ('python', 'blender', 'codex', 'ffmpeg', 'ffprobe'):
        value = tools.get(name)
        if not isinstance(value, str) or not Path(value).is_absolute() or not Path(value).is_file():
            raise ValueError('Select an existing absolute ' + name + ' executable path')
    # Existing folders are refused by create() before any runtime file is copied.
    sys.path.insert(0, str(bundle / 'tools'))
    previous_bytecode = sys.dont_write_bytecode
    try:
        # Do not create cache files in the verified source bundle. Unexpected
        # bytecode is rejected above, since it can otherwise shadow source imports.
        sys.dont_write_bytecode = True
        from create_workbench_studio import create
        result = create(target, source_commit=manifest['source_commit'], **tools)
    finally:
        sys.dont_write_bytecode = previous_bytecode
    root = Path(result['root'])
    record = dict(schema=1, source_commit=manifest['source_commit'], source_tree=manifest['source_tree'],
                  ci=manifest.get('ci'), status='INSTALLING_HOST',
                  user_environment_accepted=False, production_replaced=False,
                  existing_assets_copied=False, credentials_copied=False,
                  host_files={n:manifest['files']['launcher/'+n] for n in HOST_FILES})
    receipt = root / 'candidate-install.json'
    try:
        receipt.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
        for name in (*HOST_FILES, 'windows-build.json'):
            source = bundle / 'launcher' / name
            destination = root / 'SystemRuntime/Launcher' / name
            # create() already copies the non-binary build receipt. Verify it,
            # never overwrite; binary host files were deliberately excluded.
            if name != 'windows-build.json':
                with source.open('rb') as src, destination.open('xb') as dst:
                    shutil.copyfileobj(src, dst)
            expected = manifest['files']['launcher/' + name]
            if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
                raise ValueError('Installed host verification failed: ' + name)
        verify_bundle(bundle)  # Reject a bundle edited while creating the studio.
        (root / 'Open Workbench.cmd').write_text('@echo off\r\nstart "" "%~dp0SystemRuntime\\Launcher\\Asset Director.exe"\r\n', encoding='utf-8')
        record['status'] = 'CANDIDATE_INSTALLED'
    except BaseException as exc:
        record.update(status='FAILED', error=type(exc).__name__ + ': ' + str(exc))
        raise
    finally:
        receipt.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    return record | {'root': str(root), 'open': str(root / 'Open Workbench.cmd')}



def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verify-only', action='store_true')
    p.add_argument('--root')
    p.add_argument('--config', help='Read executable paths only from this existing config; do not edit it')
    for name in ('python', 'blender', 'codex', 'ffmpeg', 'ffprobe'):
        p.add_argument('--' + name)
    a = p.parse_args()
    if a.verify_only:
        m = verify_bundle(ROOT)
        print('BUNDLE_INTEGRITY_VERIFIED '+m['source_commit'])
        return
    if not a.root:
        p.error('--root must name a new studio directory')
    config = read(a.config) if a.config else {}
    config.update({k:getattr(a,k) for k in ('python','blender','codex','ffmpeg','ffprobe') if getattr(a,k)})
    print(json.dumps(install_candidate(a.root, config), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as exc:
        print('CANDIDATE_SETUP_REFUSED: '+str(exc), file=sys.stderr)
        raise SystemExit(2)
