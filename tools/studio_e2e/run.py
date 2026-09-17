"""Disposable installed-studio E2E: real browser, launcher, MCP and Blender.

Never point this at an existing studio. No provider/model calls or personal data.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2), encoding='utf-8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args, env, timeout=240):
    result = subprocess.run([str(x) for x in args], env=env, capture_output=True,
                            text=True, encoding='utf-8', timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{Path(str(args[0])).name} failed: {result.stdout[-3000:]} {result.stderr[-3000:]}')
    return result.stdout


class MCP:
    """Synthetic protocol client; answers authorize only generated test inputs."""
    def __init__(self, args, env):
        self.process = subprocess.Popen([str(x) for x in args], env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        text=True, encoding='utf-8', bufsize=1)
        self.lines = queue.Queue()
        def collect():
            for line in self.process.stdout:
                self.lines.put(json.loads(line))
            self.lines.put({'error': {'message': 'MCP exited unexpectedly'}})
        threading.Thread(target=collect, daemon=True).start()
        self.counter = 0
        self.questions = 0
        self.call('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {'elicitation': {'form': {}}},
                                'clientInfo': {'name': 'synthetic-studio-e2e', 'version': '1'}})
        self.send({'method': 'notifications/initialized'})

    def send(self, message):
        self.process.stdin.write(json.dumps({'jsonrpc': '2.0', **message}) + '\n')
        self.process.stdin.flush()

    def call(self, method, params, confirm=False):
        self.counter += 1
        ident = self.counter
        self.send({'id': ident, 'method': method, 'params': params})
        deadline = time.monotonic() + 220
        while True:
            message = self.lines.get(timeout=max(0.01, deadline-time.monotonic()))
            if message.get('method') == 'elicitation/create':
                self.questions += 1
                assert message['params']['requestedSchema']['properties']['decision']['enum'] == [
                    'Not sure yet', 'Provide license details', 'Confirm project use']
                response = {'action': 'accept', 'content': {'decision': 'Confirm project use',
                            'details': 'Synthetic CI-generated geometry only; no production approval.'}} if confirm else {'action': 'cancel'}
                self.send({'id': message['id'], 'result': response})
            elif 'error' in message:
                raise RuntimeError(str(message['error']))
            elif message.get('id') == ident:
                result = message['result']
                if method == 'tools/call':
                    assert not result.get('isError'), result
                    return result['structuredContent']
                return result

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', required=True)
    parser.add_argument('--evidence', required=True)
    args = parser.parse_args()
    blender = str(Path(args.blender).resolve())
    evidence = Path(args.evidence).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    report = {'status': 'FAIL', 'commit': command(['git', 'rev-parse', 'HEAD'], os.environ).strip(),
              'platform': sys.platform, 'checks': [], 'not_tested': [
                  'authenticated Codex/model calls', 'desktop EXE focus/tray', 'live Blender add-on MCP',
                  'private/licensed assets and retargeting', 'human visual acceptance'],
              'source_use_answers': 'Synthetic protocol client, generated inputs only'}
    server = None
    mcp = None
    browser = None
    page = None
    with tempfile.TemporaryDirectory(prefix='synthetic-studio-e2e-') as temporary:
        studio = Path(temporary) / 'Studio with spaces'
        studio.mkdir()
        env = dict(os.environ)
        for key in ['PYTHONPATH', 'BAD_LIBRARY', 'BAD_BLENDER', 'SKETCHFAB_TOKEN']:
            env.pop(key, None)
        env.update(BAD_CONFIG=str(studio/'SystemRuntime/UserData/runtime.json'),
                   CODEX_HOME=str(studio/'SystemRuntime/UserData/Codex'), PYTHONIOENCODING='utf-8',
                   BLENDER_USER_CONFIG=str(studio/'SystemRuntime/UserData/Blender/config'),
                   BLENDER_USER_SCRIPTS=str(studio/'SystemRuntime/UserData/Blender/scripts'))
        for folder in ['Archive/Trash', 'Docs', 'Database/Animations', 'Database/Characters',
                       'Database/Meshes/Props', 'Workspace/Projects', 'SystemRuntime/Cache', 'SystemRuntime/Temp',
                       'SystemRuntime/UserData/Launcher', 'SystemRuntime/UserData/Codex',
                       'SystemRuntime/UserData/Blender/config', 'SystemRuntime/UserData/Blender/scripts']:
            (studio/folder).mkdir(parents=True, exist_ok=True)
        (studio/'AGENTS.md').write_text('# Synthetic CI studio\nPreserve originals; explicit projects only.\n')
        (studio/'README.md').write_text('Disposable generated test studio. No production assets or approvals.\n')
        skill = studio/'SystemRuntime/Harness/Installed'
        library = studio/'Database/AssetDirector'
        launcher = studio/'SystemRuntime/Launcher'
        shutil.copytree(ROOT/'launcher', launcher, ignore=shutil.ignore_patterns('node_modules', '*.exe', '*.dll'))
        director = [sys.executable, skill/'scripts/director.py', '--library', library]
        source = studio/'Database/Meshes/Props/Synthetic/fixture.blend'
        try:
            command([sys.executable, ROOT/'tools/install_skill.py', '--dest', skill,
                     '--configure', '--library', library, '--blender', blender], env)
            command([blender, '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
                     '--python', ROOT/'tools/studio_e2e/scene.py', '--', source], env)
            original_hash = digest(source)
            assert (library/'catalog.sqlite').is_file()
            report['blender'] = command([blender, '--version'], env).splitlines()[0]
            report['checks'].append('installed exact checkout; real SQLite catalog; generated animated Blender scene')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            config = {'python': sys.executable, 'blender': blender, 'skill': str(skill), 'library': str(library),
                      'codex': str(studio/'NOT_INSTALLED_codex'), 'port': port, 'mcpPort': 1}
            write(studio/'SystemRuntime/UserData/Launcher/config.json', config)
            session_file = studio/'SystemRuntime/UserData/Launcher/session.json'

            def start():
                proc = subprocess.Popen(['node', str(launcher/'server.mjs')], env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError('Launcher exited during startup')
                    if session_file.exists():
                        session = read(session_file)
                        if session['pid'] == proc.pid:
                            return proc, session
                    time.sleep(.1)
                proc.kill(); proc.wait()
                raise TimeoutError('Launcher startup timed out')

            server, session = start()

            def api(route, data=None, expected=200, authenticated=True):
                headers = {'Content-Type': 'application/json'}
                if authenticated:
                    headers['Authorization'] = 'Bearer '+session['token']
                request = urllib.request.Request(session['origin']+'/api/'+route, headers=headers,
                    data=None if data is None else json.dumps(data).encode())
                try:
                    response = urllib.request.urlopen(request, timeout=220)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    assert response.status == expected, (route, response.status, response.read().decode())
                    return json.load(response)

            assert api('health', {})['installed']['status'] == 'VERIFIED'
            api('state', expected=401, authenticated=False)
            from playwright.sync_api import sync_playwright, expect
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={'width': 1440, 'height': 1100})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))

                def idle():
                    page.wait_for_function("!document.body.classList.contains('busy')", timeout=220000)
                    assert page.locator('#notice.error').count() == 0, page.locator('#notice').inner_text()

                def click(selector):
                    page.locator(selector).click(); idle()

                page.goto(session['origin']+'/#'+session['token']); idle()
                click('#new-project')
                page.locator('#project-name').fill('Synthetic E2E Project')
                click('#create-form button[type=submit]')
                page.locator('#brief').fill('Audit and render the generated synthetic animated cube only.')
                click('#wizard-next'); click('#wizard-next')
                click('#scan-library')
                expect(page.locator('.source-card')).to_have_count(1)
                click('.source-card button')
                click('#verify-assets')
                expect(page.locator('#project-assets')).to_contain_text('VERIFIED')
                click('#wizard-next')
                expect(page.locator('#open-codex')).to_be_enabled()
                project = api('state')['projects'][0]
                project_dir = Path(project['directory'])
                scene = project_dir/'Scenes/synthetic.blend'
                shutil.copy2(source, scene)
                scene_hash = digest(scene)
                click('[aria-label="Step 6: Working scenes"]')
                page.locator('#scene-select').select_option('Scenes/synthetic.blend'); idle()
                click('#audit-scene')
                expect(page.locator('#jobs')).to_contain_text('SUCCEEDED')
                report['checks'].append('browser onboarding, scan, attach, verify, saved scene selection and real harness audit')
                options = studio/'preview-options.json'
                write(options, {'frames': [1], 'width': 64, 'height': 64, 'samples': 1})
                job = json.loads(command(director+['job-prepare', 'preview', '--input', scene, '--options', options], env))
                api('projects/bind-job', {'projectId': project['id'], 'jobId': job['id']})
                other = api('projects/create', {'name': 'Synthetic Other Project'})
                api('projects/bind-job', {'projectId': other['id'], 'jobId': job['id']}, expected=409)
                session_id = str(uuid.uuid4())
                write(project_dir/f'Docs/Codex/{session_id}.json', {'projectId': project['id'], 'directory': str(project_dir),
                      'syntheticTest': True})
                mcp = MCP(['node', launcher/'tools/project-mcp.mjs', studio, project['id'], session_id], env)
                request = {'name': 'run_project_job', 'arguments': {'jobId': job['id']}}
                blocked = mcp.call('tools/call', request)
                assert blocked['state'] == 'BLOCKED'
                assert read(library/f"jobs/{job['id']}/job.json")['state'] == 'PLANNED'
                rendered = mcp.call('tools/call', request, confirm=True)
                assert rendered['state'] == 'SUCCEEDED', rendered
                assert mcp.questions == 2
                mcp.close(); mcp = None
                png = library/f"jobs/{job['id']}/preview_0001.png"
                assert png.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
                assert int.from_bytes(png.read_bytes()[16:20], 'big') == 64
                assert int.from_bytes(png.read_bytes()[20:24], 'big') == 64
                for output in rendered['outputs']:
                    assert digest(library/output['path']) == output['sha256']
                shutil.copy2(png, project_dir/'Renders/synthetic-preview.png')
                shutil.copy2(png, evidence/'synthetic-preview.png')
                report['checks'].append('MCP cancellation blocks execution; synthetic confirmation permits real CPU render; output hashes verified; cross-project binding refused')
                assert digest(source) == original_hash and digest(scene) == scene_hash
                with source.open('ab') as stream:
                    stream.write(b'\nsynthetic-change')
                assert api('projects/verify', {'projectId': project['id']})['ok'] is False
                api('projects/audit', {'projectId': project['id']}, expected=409)
                # Restore generated fixture bytes, never modify pinned manifests/receipts.
                shutil.copy2(scene, source)
                assert digest(source) == original_hash
                assert api('projects/verify', {'projectId': project['id']})['ok'] is True
                api('stop', {})
                server.wait(timeout=15)
                server, session = start()
                assert api('project?projectId='+project['id'])['project']['jobs']
                page.goto(session['origin']+'/#'+session['token']); idle()
                expect(page.locator('#project-title')).to_have_text('Synthetic E2E Project')
                expect(page.locator('#jobs')).to_contain_text('SUCCEEDED')
                page.on('dialog', lambda dialog: dialog.accept())
                click('[aria-label="Project menu: Synthetic E2E Project"]')
                click('.project-selector-row:has-text("Synthetic E2E Project") .trash-action')
                assert not project_dir.exists()
                assert digest(source) == original_hash and png.exists()
                click('[data-view="system"]')
                click('#trash-list button')
                expect(page.locator('#project-title')).to_have_text('Synthetic E2E Project')
                assert digest(scene) == scene_hash
                assert digest(project_dir/'Renders/synthetic-preview.png') == digest(png)
                assert not api('state')['trash']['projects']
                report['checks'].append('changed sources refused; originals preserved; restart persistence; browser Trash/restore preserves scenes, render and job evidence')
                assert not errors, errors
                page.screenshot(path=str(evidence/'studio.png'))
                browser.close(); browser = None
            # Export only synthetic job evidence, never configuration or session tokens.
            for ref in api('project?projectId='+project['id'])['project']['jobs']:
                job_dir = library/'jobs'/ref['id']
                for name in ['job.json', 'worker.log', 'result.json']:
                    if (job_dir/name).is_file():
                        dest = evidence/'jobs'/ref['id']/name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(job_dir/name, dest)
            api('stop', {}); server.wait(timeout=15)
            report['status'] = 'PASS'
        except Exception as error:
            report['error'] = str(error)
            # Worker logs contain synthetic fixture data only. Never upload the studio.
            for log in library.glob('jobs/*/worker.log'):
                dest = evidence/'jobs'/log.parent.name/log.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(log, dest)
            raise
        finally:
            if mcp:
                mcp.close()
            if server and server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill(); server.wait()
            write(evidence/'report.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
