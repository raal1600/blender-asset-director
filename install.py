#!/usr/bin/env python3
"""Install a versioned Asset Director release; standard library, no Git or administrator needed."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

DEFAULT_VERSION = '0.5.0'
REPOSITORY = 'raal1600/blender-asset-director'
ALLOWED_HOSTS = {'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}
MAX_ARCHIVE = 16 * 1024 * 1024


def check_url(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or p.hostname not in ALLOWED_HOSTS or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Release download redirected outside the approved HTTPS hosts')


class ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, limit):
    check_url(url)
    request = urllib.request.Request(url, headers={'User-Agent': 'blender-asset-director-installer/0.2.1'})
    opener = urllib.request.build_opener(ReleaseRedirect())
    try:
        with opener.open(request, timeout=60) as response:
            check_url(response.url)
            data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError('Release download exceeds the installer size limit')
            return data
    except urllib.error.HTTPError as exc:
        raise ValueError(f'Release download returned HTTP {exc.code}. Check the published version; no fallback to main is allowed') from None
    except urllib.error.URLError:
        raise ValueError('Could not reach the release server. Check HTTPS/proxy access, or use the offline archive route') from None


def checksum_for(text, filename):
    matches = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip('*') == filename and re.fullmatch(r'[0-9a-fA-F]{64}', parts[0]):
            matches.append(parts[0].lower())
    if len(matches) != 1:
        raise ValueError('Release checksum is missing or ambiguous')
    return matches[0]


def extract(archive, destination, expected):
    if not re.fullmatch(r'[0-9a-fA-F]{64}', expected or ''):
        raise ValueError('Provide an explicit SHA256 checksum for the archive')
    if archive.stat().st_size > MAX_ARCHIVE:
        raise ValueError('Archive exceeds the size limit')
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != expected.lower():
        raise ValueError('SHA256 mismatch. Nothing was extracted or executed')
    with zipfile.ZipFile(archive) as z:
        records = z.infolist()
        if len(records) > 3000 or sum(i.file_size for i in records) > 64 * 1024 * 1024:
            raise ValueError('Expanded release exceeds the size limit')
        seen = set(); regular_files = set()
        for i in records:
            # Inspect raw names before ZipInfo's platform-specific normalization.
            name = i.orig_filename.rstrip('/')
            parts = name.split('/')
            if not name or '\\' in name or ':' in name or '\x00' in name or any(c in name for c in '\r\n\t'):
                raise ValueError('Unsafe archive path')
            if PurePosixPath(name).is_absolute() or any(p in ('', '.', '..') or p.rstrip(' .') != p for p in parts):
                raise ValueError('Archive path traversal or invalid Windows path')
            if any(re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p, re.I) for p in parts):
                raise ValueError('Reserved Windows archive path')
            if stat.S_ISLNK(i.external_attr >> 16) or i.flag_bits & 1:
                raise ValueError('Symlinks and encrypted archive members are not allowed')
            key = name.casefold()
            if key in seen:
                raise ValueError('Archive filename collision')
            seen.add(key)
            if not i.is_dir():
                regular_files.add(key)
        for name in seen:
            if any('/'.join(name.split('/')[:n]) in regular_files for n in range(1, len(name.split('/')))):
                raise ValueError('Archive file/directory collision')
        # All paths validated before the first write. Extract into a fresh private temp directory.
        z.extractall(destination)


def run_installer(source, args):
    env = dict(os.environ); env.pop('PYTHONPATH', None)
    print('Checking the downloaded release (offline tests and installer smoke test)...', flush=True)
    checked = subprocess.run([sys.executable, str(source / 'tools' / 'run_checks.py'), '--offline'],
                             cwd=source, env=env, capture_output=True, text=True, timeout=180)
    if checked.returncode:
        # Only source test output is included; no configuration/env dumps are requested.
        print(checked.stdout[-4000:]); print(checked.stderr[-6000:], file=sys.stderr)
        raise ValueError('Release checks failed; existing skill was not replaced')
    command = [sys.executable, str(source / 'tools' / 'install_skill.py'), '--dest', str(args.dest), '--configure']
    if args.update:
        command.append('--update')
    for flag, value in (('--library', args.library), ('--blender', args.blender)):
        if value:
            command.extend([flag, value])
    installed = subprocess.run(command, cwd=source, env=env, capture_output=True, text=True, timeout=90)
    if installed.returncode:
        print(installed.stdout[-3000:], file=sys.stderr)
        raise ValueError('Installation/setup did not complete. Preserve any existing edited installation and read the error above')
    result = json.loads(installed.stdout)
    print(f"\nBlender Asset Director {result['version']} - {result['status']}")
    print('Skill:   ' + result['path'])
    conf = result['configuration']; health = result['health']
    print('Library: ' + conf['library'])
    print('Python:  ' + health['python_executable'])
    print('Blender: ' + (conf['blender'] or 'NOT FOUND - install Blender or re-run with --blender <executable>'))
    print('Codex:   ' + ('CLI FOUND' if health['codex']['cli_on_path'] else 'CLI NOT ON PATH - verify local Codex/IDE is installed'))
    print('MCP:     ' + health['codex']['blender_mcp'])
    print('Codex/DeepSeek/MCP configuration: UNCHANGED')
    print('Live Blender connection, model vision and Codex skill discovery: NOT TESTED by this installer')
    if result.get('backup'):
        print('Previous managed skill backup: ' + result['backup'])
    print('\nOpen a NEW Codex session, then paste:\n')
    print('$blender-asset-director\nRun the first-run check. Verify the existing Blender MCP read-only. Do not modify my scene.')
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version', default=DEFAULT_VERSION, help='Explicit published release version; never moving main')
    p.add_argument('--dest', type=Path, default=Path.home() / '.agents' / 'skills' / 'blender-asset-director')
    p.add_argument('--library'); p.add_argument('--blender'); p.add_argument('--update', action='store_true')
    p.add_argument('--archive', type=Path, help='Offline release archive (requires --sha256)')
    p.add_argument('--sha256', help='Expected SHA256 of the offline archive')
    args = p.parse_args(argv)
    try:
        if sys.version_info < (3, 11):
            raise ValueError('Python 3.11+ is required. Install Python from python.org and retry')
        if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?', args.version):
            raise ValueError('Invalid release version')
        if bool(args.archive) != bool(args.sha256):
            raise ValueError('--archive and --sha256 must be provided together')
        with tempfile.TemporaryDirectory(prefix='blender-director-install-') as tmp:
            source = Path(tmp) / 'source'; source.mkdir()
            filename = 'blender-asset-director-' + args.version + '.zip'
            if args.archive:
                archive = args.archive.resolve(); expected = args.sha256
            else:
                base = f'https://github.com/{REPOSITORY}/releases/download/v{args.version}/'
                print('Downloading pinned release v' + args.version + ' (no Git or login needed)...', flush=True)
                expected = checksum_for(fetch(base + 'SHA256SUMS.txt', 16384).decode('utf-8'), filename)
                archive = Path(tmp) / filename
                archive.write_bytes(fetch(base + filename, MAX_ARCHIVE))
            extract(archive, source, expected)
            meta = json.loads((source / '_release.json').read_text(encoding='utf-8'))
            if meta.get('version') != args.version or not re.fullmatch('[0-9a-f]{40}', meta.get('commit', '')):
                raise ValueError('Release identity is missing or does not match the selected version')
            if not (source / 'tools' / 'install_skill.py').is_file():
                raise ValueError('This is not an Asset Director installer package')
            print('Verified package SHA256; source commit ' + meta['commit'], flush=True)
            run_installer(source, args)
        return 0
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print('SETUP FAILED: ' + str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
