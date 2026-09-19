"""User-visible installed-studio journeys. Every dependency is real except the MCP client.

Copying generated scenes/derived outputs is deliberate test orchestration, not a
claim that a model autonomously authored or delivered those files.
"""
import json
from pathlib import Path
import shutil

from support import ROOT, digest, read


def onboarding(studio):
    from playwright.sync_api import expect
    s = studio
    page = s.page
    with s.evidence.checkpoint('project_created'):
        s.click('#new-project')
        page.locator('#project-name').fill('Synthetic E2E Project')
        s.click('#create-form button[type=submit]')
        page.locator('#brief').fill('Audit and render the generated synthetic animated cube only.')
        s.click('#wizard-next')
        s.click('#wizard-next')
        s.project = s.api('state')['projects'][0]
        s.project_dir = Path(s.project['directory'])
        assert s.project_dir.is_dir()
    with s.evidence.checkpoint('sources_verified'):
        s.click('#scan-library')
        expect(page.locator('.source-card')).to_have_count(1)
        s.click('.source-card button')
        s.click('#verify-assets')
        expect(page.locator('#project-assets')).to_contain_text('VERIFIED')
        s.click('#wizard-next')
        expect(page.locator('#open-codex')).to_be_enabled()
        assert s.api('projects/verify', {'projectId': s.project['id']})['ok'] is True
    with s.evidence.checkpoint('scene_audited') as check:
        s.scene = s.project_dir/'Scenes/synthetic.blend'
        shutil.copy2(s.source, s.scene)
        s.scene_hash = digest(s.scene)
        s.click('[aria-label="Step 6: Working scenes"]')
        page.locator('#scene-select').select_option('Scenes/synthetic.blend')
        s.idle()
        s.click('#audit-scene')
        expect(page.locator('#jobs')).to_contain_text('SUCCEEDED')
        jobs = s.api('project?projectId='+s.project['id'])['project']['jobs']
        assert jobs
        records = [read(s.library/'jobs'/job['id']/'job.json') for job in jobs]
        assert any(job['state'] == 'SUCCEEDED' and job['specification']['operation'] == 'scene-audit' for job in records)
        check['jobs'] = [job['id'] for job in jobs]
        s.preserve()


def execution(s):
    s.preview_job = s.prepare('preview', s.scene, {'frames': [1], 'width': 64, 'height': 64, 'samples': 1})
    with s.evidence.checkpoint('foreign_binding_refused'):
        other = s.api('projects/create', {'name': 'Synthetic Other Project'})
        s.api('projects/bind-job', {'projectId': other['id'], 'jobId': s.preview_job['id']}, expected=409)
    with s.evidence.checkpoint('cancellation_blocks'):
        blocked = s.run_job(s.preview_job, confirm=False)
        assert blocked['state'] == 'BLOCKED'
        folder = s.library/'jobs'/s.preview_job['id']
        assert read(folder/'job.json')['state'] == 'PLANNED'
        assert not (folder/'preview_0001.png').exists()
    with s.evidence.checkpoint('confirmed_render') as check:
        rendered = s.run_job(s.preview_job, confirm=True)
        assert rendered['state'] == 'SUCCEEDED', rendered
        assert s.mcp.questions == 2
        s.png = s.library/'jobs'/s.preview_job['id']/'preview_0001.png'
        validate_png(s.png)
        shutil.copy2(s.png, s.project_dir/'Renders/synthetic-preview.png')
        shutil.copy2(s.png, s.evidence.directory/'synthetic-preview.png')
        check['job'] = s.preview_job['id']
        check['preview_sha256'] = digest(s.png)
    with s.evidence.checkpoint('idempotent_replay'):
        folder = s.png.parent
        before = {name: digest(folder/name) for name in ('job.json', 'result.json', 'worker.log', 'preview_0001.png')}
        reused = s.run_job(s.preview_job)
        assert reused['state'] == 'SUCCEEDED' and reused['id'] == s.preview_job['id']
        assert s.mcp.questions == 2  # No invented new approval; same bound source-use scope.
        assert before == {name: digest(folder/name) for name in before}


def validate_png(path):
    data = Path(path).read_bytes()
    assert data.startswith(b'\x89PNG\r\n\x1a\n')
    assert int.from_bytes(data[16:20], 'big') == 64
    assert int.from_bytes(data[20:24], 'big') == 64


def production(s):
    # Each derivative becomes a separate project-owned scene before the next job.
    # Binding a library-external file or editing a job receipt is never necessary.
    def derive(operation, source, options):
        result, data, directory = s.execute(operation, source, options)
        target = s.project_dir/'Scenes'/('synthetic-'+operation+'.blend')
        shutil.copy2(directory/'result.blend', target)
        return target, data

    with s.evidence.checkpoint('camera_authored'):
        scene, camera = derive('camera-plan', s.scene,
            {'mode': 'create', 'subjects': ['Synthetic_E2E_Cube'], 'lens_mm': 50,
             'fps': 24, 'frame_range': [1, 12], 'keyframes': [
                {'frame': 1, 'aim': {'subject': 'Synthetic_E2E_Cube'},
                 'direction': [.3, -1, .25], 'fit': {'margin': .32}, 'screen': [.5, .5]},
                {'frame': 12, 'aim': {'subject': 'Synthetic_E2E_Cube'},
                 'direction': [.5, -1, .18], 'fit': {'margin': .20}, 'screen': [.5, .5]}]})
        assert camera['mode'] == 'create' and len(camera['keyframes']) == 2
        assert camera['verification']['all_fit'] is True
    with s.evidence.checkpoint('look_authored'):
        scene, _ = derive('light-adjust', scene, {'lights': [{'name': 'Synthetic_E2E_Key', 'energy': 125}]})
        scene, _ = derive('world-adjust', scene, {'strength': .3, 'color': [.2, .3, .4]})
        scene, _ = derive('look-adjust', scene, {'exposure': .25})
    with s.evidence.checkpoint('camera_verified'):
        _, qa, _ = s.execute('camera-check', scene, {'subjects': ['Synthetic_E2E_Cube'],
            'camera': camera['camera'], 'frames': [1, 12], 'occlusion': True})
        assert qa['all_fit'] is True and len(qa['checkpoints']) == 2
    with s.evidence.checkpoint('production_preview') as check:
        result, data, directory = s.execute('preview', scene, {'frames': [12], 'width': 64, 'height': 64, 'samples': 1})
        validate_png(directory/'preview_0012.png')
        assert data['production_settings_restored'] is True and data['delivery_master'] is False
        assert data['production_settings']['resolution'] == [320, 180]
        assert data['production_settings']['samples'] == 7
        verification = s.evidence.directory/'production-scene.json'
        s.cmd([s.blender, '--background', '--factory-startup', '--disable-autoexec', '--threads', '2',
               '--python-exit-code', '11', '--python', ROOT/'tools/studio_e2e/verify_scene.py', '--',
               s.scene, directory/'result.blend', camera['camera'], verification])
        assert read(verification)['status'] == 'PASS'
        shutil.copy2(directory/'preview_0012.png', s.evidence.directory/'production-preview.png')
        check['job'] = result['id']
        check['preview_sha256'] = digest(directory/'preview_0012.png')
        s.preserve()
    from workbench import review_scene
    review_scene(s)


def recovery(s):
    from playwright.sync_api import expect
    with s.evidence.checkpoint('source_drift_refused'):
        with s.source.open('ab') as stream:
            stream.write(b'\nsynthetic-change')
        assert s.api('projects/verify', {'projectId': s.project['id']})['ok'] is False
        s.api('projects/audit', {'projectId': s.project['id']}, expected=409)
        # Restore only our generated bytes, not an approval or a pinned receipt.
        shutil.copy2(s.scene, s.source)
        s.preserve()
        assert s.api('projects/verify', {'projectId': s.project['id']})['ok'] is True
    with s.evidence.checkpoint('session_rotated'):
        s.mcp.close()
        s.mcp = None
        old_token = s.session['token']
        s.api('stop', {})
        s.server.wait(timeout=15)
        s.start()
        assert s.session['token'] != old_token
        s.api('state', expected=401, token=old_token)
    with s.evidence.checkpoint('restart_persisted'):
        jobs = s.api('project?projectId='+s.project['id'])['project']['jobs']
        assert s.preview_job['id'] in {job['id'] for job in jobs}
        s.page.goto('about:blank')
        s.page.goto(s.session['origin']+'/#'+s.session['token'])
        s.idle()
        expect(s.page.locator('#project-title')).to_have_text('Synthetic E2E Project')
        expect(s.page.locator('#jobs')).to_contain_text('SUCCEEDED')
    with s.evidence.checkpoint('trash_restored'):
        s.page.on('dialog', lambda dialog: dialog.accept())
        s.click('[aria-label="Project menu: Synthetic E2E Project"]')
        s.click('.project-selector-row:has-text("Synthetic E2E Project") .trash-action')
        assert not s.project_dir.exists()
        assert digest(s.source) == s.source_hash and s.png.exists()
        s.click('[data-view="system"]')
        s.click('#trash-list button')
        expect(s.page.locator('#project-title')).to_have_text('Synthetic E2E Project')
        assert digest(s.project_dir/'Renders/synthetic-preview.png') == digest(s.png)
        assert not s.api('state')['trash']['projects']
        s.preserve()
