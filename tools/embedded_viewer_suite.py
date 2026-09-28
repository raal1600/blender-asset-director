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
    with (output/'world-layers.log').open('wb') as log:
        subprocess.run([args.blender,'--background','--factory-startup','--disable-autoexec','--threads','2',
                        '--python-exit-code','11','--python',str(ROOT/'tools/world_layers_fixture.py'),'--',str(output/'world-layers')],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
    with (output/'world-transform.log').open('wb') as log:
        subprocess.run([args.blender,'--background','--factory-startup','--disable-autoexec','--threads','2',
                        '--python-exit-code','11','--python',str(ROOT/'tools/world_transform_fixture.py'),'--',
                        str(output/'world-layers/placed.blend'),str(output/'world-transform')],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=300,check=True)
    with (output/'action-layer.log').open('wb') as log:
        subprocess.run([args.blender,'--background','--factory-startup','--disable-autoexec','--threads','2',
                        '--python-exit-code','11','--python',str(ROOT/'tools/action_layer_fixture.py'),'--',
                        str(output/'world-layers/placed.blend'),str(output/'action-layer')],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=300,check=True)
    with (output/'action-preview.log').open('wb') as log:
        subprocess.run([args.blender,'--background','--factory-startup','--disable-autoexec','--threads','2',
                        '--python-exit-code','11','--python',str(ROOT/'tools/action_preview_fixture.py'),'--',
                        str(output/'action-layer/source.blend'),str(output/'action-preview')],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
    with (output/'action-http.log').open('wb') as log:
        subprocess.run([args.node,str(ROOT/'tools/action_layer_check.mjs'),str(output/'action-http'),
                        str(output/'action-layer'),sys.executable,args.blender],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=300,check=True)
    with (output/'action-static.log').open('wb') as log:
        subprocess.run([args.blender,'--background','--factory-startup','--disable-autoexec','--threads','2',
                        '--python-exit-code','11','--python',str(ROOT/'tools/action_static_preview_fixture.py'),'--',
                        str(output/'action-layer/source.blend'),str(output/'action-static')],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
    with (output/'action-task.log').open('wb') as log:
        subprocess.run([args.node,str(ROOT/'tools/action_task_check.mjs'),str(output/'action-task'),
                        str(output/'action-layer'),sys.executable,args.blender],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=300,check=True)
    with (output/'scene-layers-native.log').open('wb') as log:
        subprocess.run([args.blender,'--background','--factory-startup','--disable-autoexec','--threads','2',
                        '--python-exit-code','11','--python',str(ROOT/'tools/scene_layer_fixture.py'),'--',
                        str(output/'action-layer/source.blend'),str(output/'scene-layers-native')],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=300,check=True)
    with (output/'scene-layers-http.log').open('wb') as log:
        subprocess.run([args.node,str(ROOT/'tools/scene_layer_check.mjs'),str(output/'scene-layers-http'),
                        str(output/'scene-layers-native'),sys.executable,args.blender],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=300,check=True)
    with (output/'shot-view-native.log').open('wb') as log:
        subprocess.run([args.blender,'--background','--factory-startup','--disable-autoexec','--threads','2',
                        '--python-exit-code','11','--python',str(ROOT/'tools/shot_view_fixture.py'),'--',str(output/'shot-view-native')],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
    with (output/'world-append.log').open('wb') as log:
        subprocess.run([args.blender,'--background','--factory-startup','--disable-autoexec','--threads','2',
                        '--python-exit-code','11','--python',str(ROOT/'tools/world_append_fixture.py'),'--',str(output/'world-append')],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=300,check=True)
    with (output/'world-save-return.log').open('wb') as log:
        saved = subprocess.run([args.node,str(ROOT/'tools/task_save_native.mjs'),str(output/'world-save-return'),
                        args.blender,str(output/'world-layers')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                       timeout=180)
    if saved.returncode:
        print((output/'world-save-return.log').read_text(encoding='utf-8',errors='replace')[-6000:],file=sys.stderr)
        saved.check_returncode()
    if args.guided_world:
        with (output/'package-preparation.log').open('wb') as log:
            subprocess.run([args.blender,'--background','--factory-startup','--disable-autoexec','--threads','2',
                            '--python-exit-code','11','--python',str(ROOT/'tools/library_preparation_fixture.py'),'--',str(output/'package-preparation')],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=300,check=True)
    else:
        # Reuse Playwright's installed Node driver package; no npm/CDN download.
        import playwright
        module = Path(playwright.__file__).parent / 'driver/package/index.mjs'
        command = [args.node, str(ROOT/'tools/shot_view_check.mjs'), str(output/'shot-view-browser'),
                   str(output/'shot-view-native'), sys.executable, args.blender, str(module)]
        if args.chrome: command.append(args.chrome)
        with (output/'shot-view-browser.log').open('wb') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=300, check=True)
        command = [args.node, str(ROOT/'tools/world_edit_check.mjs'), str(output/'world-direct-edit'),
                   str(output/'world-layers'), sys.executable, args.blender, str(module)]
        if args.chrome: command.append(args.chrome)
        with (output/'world-direct-edit.log').open('wb') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=300, check=True)
        command = [args.node, str(ROOT/'tools/action_browser_check.mjs'), str(output/'action-browser'),
                   str(output/'action-layer'), str(output/'action-preview'), sys.executable, args.blender, str(module)]
        if args.chrome: command.append(args.chrome)
        with (output/'action-browser.log').open('wb') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=300, check=True)
        command = [args.node, str(ROOT/'tools/action_static_browser_check.mjs'), str(output/'action-static-browser'),
                   str(output/'action-static'), sys.executable, args.blender, str(module)]
        if args.chrome: command.append(args.chrome)
        with (output/'action-static-browser.log').open('wb') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=300, check=True)
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
