"""Real no-version public bootstrap in a disposable home; explicitly requires HTTPS.

This is separate from portable/offline tests. It never changes the caller's
installation, connects to Blender, publishes a release or downloads private assets.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main(shell: str, output: Path) -> None:
    pin = json.loads((ROOT / 'published-release.json').read_text(encoding='utf-8'))
    report = {'status': 'FAIL', 'shell': shell, 'source_sha': os.getenv('GITHUB_SHA'),
              'run_id': os.getenv('GITHUB_RUN_ID'), 'published_release': pin,
              'version_argument_supplied': False, 'checks': [],
              'live_blender_mcp': 'NOT_TESTED', 'private_assets': 'NOT_ACCESSED'}
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='bad public default space ') as tmp:
            home = Path(tmp).resolve()
            env = dict(os.environ)
            for key in ('GH_TOKEN', 'GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN', 'PYTHONPATH'):
                env.pop(key, None)
            env.update(HOME=str(home), USERPROFILE=str(home),
                       XDG_CONFIG_HOME=str(home / '.config'), APPDATA=str(home / 'roaming'),
                       LOCALAPPDATA=str(home / 'local'), BAD_CONFIG=str(home / 'runtime.json'),
                       CODEX_HOME=str(home / 'codex'), BAD_LIBRARY='', BAD_BLENDER='', BAD_PYTHON=sys.executable)
            (home / 'codex').mkdir()
            config = home / 'codex' / 'config.toml'
            original = b'model="untouched"\n[mcp_servers.blender]\ncommand="fixture-not-executed"\n'
            config.write_bytes(original)
            dest, library = home / 'managed skill', home / 'CGI Library'
            if shell in ('powershell', 'pwsh'):
                command = [shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'install.ps1'),
                           '-PythonPath', sys.executable, '-SkillPath', str(dest), '-LibraryPath', str(library)]
            elif shell == 'sh':
                command = ['sh', str(ROOT / 'install.sh'), '--dest', str(dest), '--library', str(library)]
            else:
                command = [sys.executable, str(ROOT / 'install.py'), '--dest', str(dest), '--library', str(library)]
            # No --version/-Version, --archive/-Archive, substitute transport, or authenticated download.
            for repeat in (False, True):
                result = subprocess.run(command, env=env, cwd=home, text=True, capture_output=True, timeout=240)
                print(result.stdout, end='')
                print(result.stderr, end='', file=sys.stderr)
                require(result.returncode == 0, f'Default {shell} installer exited {result.returncode}')
                require('Downloading pinned release v' + pin['version'] in result.stdout,
                        'Bootstrap did not select the documented published version')
                require('Verified package SHA256; source commit ' + pin['source_commit'] in result.stdout,
                        'Downloaded source identity does not match the reviewed release')
                status = 'ALREADY_INSTALLED' if repeat else 'INSTALLED'
                require(f"Blender Asset Director {pin['version']} - {status}" in result.stdout,
                        'Unexpected installed version or repeat-install status')
                receipt = json.loads((dest / '.asset-director-install.json').read_text(encoding='utf-8'))
                require(receipt['version'] == pin['version'], 'Installed receipt version mismatch')
                require(config.read_bytes() == original, 'Host configuration changed')
                report['checks'].append('idempotent default reinstall' if repeat else 'real default HTTPS install')
            manager = dest / 'scripts' / 'manage_install.py'
            for operation in ('--verify', '--uninstall'):
                result = subprocess.run([sys.executable, str(manager), '--dest', str(dest), operation],
                                        env=env, cwd=home, text=True, capture_output=True, timeout=60)
                print(result.stdout, end='')
                print(result.stderr, end='', file=sys.stderr)
                require(result.returncode == 0, 'Installed manager failed: ' + operation)
                report['checks'].append(operation.lstrip('-'))
            require(not dest.exists(), 'Managed skill remains after uninstall')
            require((library / 'catalog.sqlite').is_file(), 'Uninstall removed the independent library')
            require(config.read_bytes() == original, 'Host configuration changed')
            report['checks'].extend(['published source SHA verified', 'library preserved', 'host config unchanged'])
            report['status'] = 'PASS'
    except Exception as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        if summary := os.getenv('GITHUB_STEP_SUMMARY'):
            with open(summary, 'a', encoding='utf-8') as stream:
                stream.write(f"\n## Real published installer default: {shell}\n\n")
                stream.write(f"Result: **{report['status']}**. No version override or offline archive supplied.\n\n")
                stream.write(f"Expected published version: `{pin['version']}`; source `{pin['source_commit']}`.\n\n")
                stream.write('Separate from development-archive bootstrap tests; no live Blender or artistic acceptance.\n')
        print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell', choices=['python', 'sh', 'powershell', 'pwsh'], default='python')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    main(args.shell, args.output)
