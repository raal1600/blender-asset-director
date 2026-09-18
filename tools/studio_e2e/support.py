"""Disposable installed-studio E2E: real browser, launcher, MCP and Blender.

Never point this at an existing studio. No provider/model calls or personal data.
"""
from contextlib import closing
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/ci'))
from evidence import digest, read, write


def command(args, env, timeout=240):
    result = subprocess.run([str(x) for x in args], env=env, capture_output=True,
                            text=True, encoding='utf-8', timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{Path(str(args[0])).name} failed: {result.stdout[-3000:]} {result.stderr[-3000:]}')
    return result.stdout


def verify_catalog(path):
    """Check the real catalog without retaining a connection on an error path."""
    path = Path(path)
    assert path.is_file(), 'Installed SQLite catalog is absent'
    # sqlite3.Connection's context manager commits/rolls back; it does NOT close.
    # Explicit closure matters when a later Blender failure retains this frame.
    with closing(sqlite3.connect(str(path))) as db:
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert db.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0] > 0


class MCP:
    """Synthetic protocol client; answers authorize only generated test inputs."""
    def __init__(self, args, env):
        self.process = subprocess.Popen([str(x) for x in args], env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        text=True, encoding='utf-8', bufsize=1)
        self.lines = queue.Queue()
        def collect():
            try:
                for line in self.process.stdout:
                    self.lines.put(json.loads(line))
            except Exception as error:
                self.lines.put({'error': {'message': str(error)}})
            finally:
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



class Studio:
    """A real installed studio in a fresh temporary root; never accepts user paths."""
    def __init__(self, temporary, blender, evidence):
        self.root = Path(temporary) / 'Studio with spaces'
        self.root.mkdir()
        self.blender = str(Path(blender).resolve())
        self.evidence = evidence
        self.server = self.mcp = self.browser = self.page = None
        self.project = self.scene = None
        self.errors = []
        self.env = dict(os.environ)
        for key in ('PYTHONPATH', 'BAD_LIBRARY', 'BAD_BLENDER', 'SKETCHFAB_TOKEN',
                    'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPSEEK_API_KEY', 'PYTHONOPTIMIZE'):
            self.env.pop(key, None)
        # Only direct synthetic fixture/verification subprocesses use this setting.
        # Real harness workers retain their existing sanitized environment policy.
        if sys.platform == 'win32':
            self.env['TBB_MALLOC_DISABLE_REPLACEMENT'] = '1'
        self.evidence.report['fixture_allocator'] = (
            'standard CRT; oneTBB replacement disabled for direct fixture calls'
            if sys.platform == 'win32' else 'platform default')
        root = self.root
        self.env.update(BAD_CONFIG=str(root/'SystemRuntime/UserData/runtime.json'),
                        CODEX_HOME=str(root/'SystemRuntime/UserData/Codex'), PYTHONIOENCODING='utf-8',
                        BLENDER_USER_CONFIG=str(root/'SystemRuntime/UserData/Blender/config'),
                        BLENDER_USER_SCRIPTS=str(root/'SystemRuntime/UserData/Blender/scripts'),
                        HOME=str(root/'SystemRuntime/UserData/Home'),
                        USERPROFILE=str(root/'SystemRuntime/UserData/Home'),
                        LOCALAPPDATA=str(root/'SystemRuntime/UserData/Local'),
                        APPDATA=str(root/'SystemRuntime/UserData/Roaming'),
                        XDG_CONFIG_HOME=str(root/'SystemRuntime/UserData/Config'))
        for folder in ('Archive/Trash', 'Docs', 'Database/Animations', 'Database/Characters',
                       'Database/Meshes/Props', 'Workspace/Projects', 'SystemRuntime/Cache', 'SystemRuntime/Temp', 'SystemRuntime/UserData/Launcher', 'SystemRuntime/UserData/Codex',
                       'SystemRuntime/UserData/Blender/config', 'SystemRuntime/UserData/Blender/scripts',
                       'SystemRuntime/UserData/Home', 'SystemRuntime/UserData/Local',
                       'SystemRuntime/UserData/Roaming', 'SystemRuntime/UserData/Config'):
            (root/folder).mkdir(parents=True, exist_ok=True)
        (root/'AGENTS.md').write_text('# Synthetic CI studio\nPreserve originals; explicit projects only.\n')
        (root/'README.md').write_text('Disposable generated studio. No production assets or approvals.\n')
        self.codex_config = root/'SystemRuntime/UserData/Codex/config.toml'
        self.codex_config.write_text('model="synthetic-not-executed"\n')
        self.codex_hash = digest(self.codex_config)
        self.skill = root/'SystemRuntime/Harness/Installed'
        self.library = root/'Database/AssetDirector'
        self.launcher = root/'SystemRuntime/Launcher'
        self.director = [sys.executable, self.skill/'scripts/director.py', '--library', self.library]
        self.source = root/'Database/Meshes/Props/Synthetic/fixture.blend'
        self.session_file = root/'SystemRuntime/UserData/Launcher/session.json'

    def cmd(self, args, timeout=240):
        return command(args, self.env, timeout)

    def install(self):
        with self.evidence.checkpoint('installed_checkout'):
            shutil.copytree(ROOT/'launcher', self.launcher,
                            ignore=shutil.ignore_patterns('node_modules', '*.exe', '*.dll'))
            self.cmd([sys.executable, ROOT/'tools/install_skill.py', '--dest', self.skill,
                      '--configure', '--library', self.library, '--blender', self.blender])
            # Verify bundled runtime bytes, not merely an import from the checkout.
            for source in (ROOT/'src/asset_director').glob('*.py'):
                assert digest(source) == digest(self.skill/'scripts/runtime/asset_director'/source.name)
            assert digest(self.codex_config) == self.codex_hash
        with self.evidence.checkpoint('catalog_initialized'):
            verify_catalog(self.library/'catalog.sqlite')
            self.cmd([self.blender, '--background', '--factory-startup', '--disable-autoexec',
                      '--threads', '2', '--python-exit-code', '11',
                      '--python', ROOT/'tools/studio_e2e/scene.py', '--', self.source])
            self.source_hash = digest(self.source)
            self.evidence.report['blender'] = self.cmd([self.blender, '--version']).splitlines()[0]
        with self.evidence.checkpoint('launcher_authenticated'):
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            write(self.root/'SystemRuntime/UserData/Launcher/config.json',
                  {'python': sys.executable, 'blender': self.blender, 'skill': str(self.skill),
                   'library': str(self.library), 'codex': str(self.root/'NOT_INSTALLED_codex'),
                   'port': port, 'mcpPort': 1, 'ffmpeg': shutil.which('ffmpeg'), 'ffprobe': shutil.which('ffprobe')})
            self.start()
            assert self.api('health', {})['installed']['status'] == 'VERIFIED'
            self.api('state', expected=401, authenticated=False)

    def start(self):
        self.server = subprocess.Popen(['node', str(self.launcher/'server.mjs')], env=self.env,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if self.server.poll() is not None:
                raise RuntimeError('Launcher exited during startup')
            if self.session_file.exists():
                session = read(self.session_file)
                if session['pid'] == self.server.pid:
                    self.session = session
                    self.evidence.secrets.append(session['token'])
                    return
            time.sleep(.1)
        raise TimeoutError('Launcher startup timed out')

    def api(self, route, data=None, expected=200, authenticated=True, token=None):
        headers = {'Content-Type': 'application/json'}
        if authenticated:
            headers['Authorization'] = 'Bearer ' + (token or self.session['token'])
        request = urllib.request.Request(self.session['origin']+'/api/'+route, headers=headers,
                    data=None if data is None else json.dumps(data).encode())
        try:
            response = urllib.request.urlopen(request, timeout=220)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            assert response.status == expected, (route, response.status, response.read().decode())
            return json.load(response)

    def open_browser(self, pw):
        self.browser = pw.chromium.launch(channel="chrome")
        self.page = self.browser.new_page(viewport={'width': 1440, 'height': 1100})
        codec = self.page.evaluate("(mime) => document.createElement('video').canPlayType(mime)", 'video/mp4; codecs="avc1.42E01E"')
        self.evidence.report['browser'] = {'channel': 'chrome', 'version': self.browser.version, 'h264': codec}
        assert codec in {'probably', 'maybe'}, 'The installed browser cannot decode the MVP H.264 delivery format'
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(self.session['origin']+'/#'+self.session['token'])
        self.idle()

    def idle(self):
        from playwright.sync_api import expect
        expect(self.page.locator('body.busy')).to_have_count(0, timeout=220000)
        assert self.page.locator('#notice.error').count() == 0, self.page.locator('#notice').inner_text()

    def click(self, selector):
        self.page.locator(selector).click()
        self.idle()

    def preserve(self):
        assert digest(self.source) == self.source_hash
        assert digest(self.codex_config) == self.codex_hash
        if self.scene:
            assert digest(self.scene) == self.scene_hash

    def prepare(self, operation, scene, options=None):
        args = self.director + ['job-prepare', operation, '--input', scene]
        if options is not None:
            options_file = self.root/('synthetic-options-'+str(uuid.uuid4())+'.json')
            write(options_file, options)
            args += ['--options', options_file]
        job = json.loads(self.cmd(args))
        self.api('projects/bind-job', {'projectId': self.project['id'], 'jobId': job['id']})
        return job

    def connect_mcp(self):
        if self.mcp:
            return self.mcp
        ident = str(uuid.uuid4())
        write(self.project_dir/f'Docs/Codex/{ident}.json',
              {'projectId': self.project['id'], 'directory': str(self.project_dir), 'syntheticTest': True})
        self.mcp = MCP(['node', self.launcher/'tools/project-mcp.mjs', self.root, self.project['id'], ident], self.env)
        tools = self.mcp.call('tools/list', {})
        assert 'run_project_job' in {tool['name'] for tool in tools['tools']}
        return self.mcp

    def run_job(self, job, confirm=True):
        result = self.connect_mcp().call('tools/call',
                 {'name': 'run_project_job', 'arguments': {'jobId': job['id']}}, confirm=confirm)
        if result.get('state') == 'SUCCEEDED':
            assert result['outputs'], 'A succeeded job must retain output evidence'
            for output in result['outputs']:
                assert digest(self.library/output['path']) == output['sha256']
            self.preserve()
        return result

    def execute(self, operation, source, options=None):
        before = digest(source)
        result = self.run_job(self.prepare(operation, source, options))
        assert result['state'] == 'SUCCEEDED', result
        assert digest(source) == before
        directory = self.library/'jobs'/result['id']
        return result, read(directory/'result.json')['data'], directory

    def export_jobs(self):
        # Synthetic worker evidence only; never settings, sessions or whole studios.
        for folder in (self.library/'jobs').glob('j_*'):
            for name in ('job.json', 'result.json', 'worker.log'):
                source = folder/name
                if source.is_file():
                    destination = self.evidence.directory/'jobs'/folder.name/name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    content = source.read_text(encoding='utf-8', errors='replace')
                    destination.write_text(self.evidence.redact(content), encoding='utf-8')

    def close(self):
        if self.mcp:
            self.mcp.close()
            self.mcp = None
        if self.browser:
            self.browser.close()
            self.browser = self.page = None
        if self.server and self.server.poll() is None:
            self.server.terminate()
            try:
                self.server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.server.kill()
                self.server.wait(timeout=10)
