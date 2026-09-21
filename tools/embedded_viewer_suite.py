"""Generate native inputs, then exercise the real authenticated 3D app in Chrome."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--blender', required=True)
    parser.add_argument('--node', default='node')
    parser.add_argument('--chrome')
    parser.add_argument('--native-fixture', help='Optional previously generated PASS fixture, never a user scene')
    parser.add_argument('--guided-world', action='store_true', help='Exercise real World import/review UI with scripted synthetic decisions')
    args = parser.parse_args()
    output = Path(args.evidence).resolve(); output.mkdir(parents=True, exist_ok=False)
    source = {'commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'tree': subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),
              'worktree_dirty': bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT))}
    (output/'source.json').write_text(json.dumps(source,indent=2),encoding='utf-8')
    if args.guided_world:
        with (output/'package-preparation.log').open('wb') as log:
            subprocess.run([args.blender,'--background','--factory-startup','--disable-autoexec','--threads','2',
                            '--python-exit-code','11','--python',str(ROOT/'tools/library_preparation_fixture.py'),'--',str(output/'package-preparation')],
                           cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=300,check=True)
    generated = Path(args.native_fixture).resolve() if args.native_fixture else output / 'native'
    if not args.native_fixture:
        with (output / 'native.log').open('wb') as log:
            subprocess.run([args.blender, '--background', '--factory-startup', '--disable-autoexec', '--threads', '2',
                            '--python-exit-code', '11', '--python', str(ROOT / 'tools/asset_preview_fixture.py'), '--', str(generated)],
                           cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=240, check=True)
    root = output / 'studio'; session_file = root / 'browser-session.json'
    env = dict(os.environ); env['PYTHONDONTWRITEBYTECODE'] = '1'
    with (output / 'server.log').open('wb') as log:
        fixture = 'world_guided_fixture.mjs' if args.guided_world else 'embedded_viewer_fixture.mjs'
        check = 'world_guided_check.py' if args.guided_world else 'embedded_viewer_check.py'
        process = subprocess.Popen([args.node, str(ROOT / 'tools' / fixture), str(root), str(generated), sys.executable, args.blender],
                                   cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)
        session = None
        try:
            deadline = time.monotonic() + 40
            while session is None:
                if process.poll() is not None: raise RuntimeError('Viewer fixture startup failed; see server.log')
                if time.monotonic() > deadline: raise TimeoutError('Viewer fixture did not start')
                try:
                    session = json.loads(session_file.read_text())
                except (FileNotFoundError, PermissionError, json.JSONDecodeError):
                    pass  # Publication is bounded; a partial/busy file is not a ready session.
                if session is not None: break
                time.sleep(.1)
            command = [sys.executable, '-B', str(ROOT / 'tools' / check), '--fixture', str(root), '--evidence', str(output / 'browser')]
            if args.chrome: command += ['--chrome', args.chrome]
            return subprocess.run(command, env=env, timeout=600 if args.guided_world else 300).returncode
        finally:
            if session and process.poll() is None:
                request = urllib.request.Request(session['origin']+'/api/stop', data=b'{}', headers={'Authorization':'Bearer '+session['token'], 'Content-Type':'application/json'})
                try:
                    with urllib.request.urlopen(request, timeout=5) as response: assert response.status == 200
                except Exception: pass
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate(); process.wait(timeout=10)


if __name__ == '__main__': raise SystemExit(main())
