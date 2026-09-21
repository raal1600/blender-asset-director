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
    with s.evidence.checkpoint('project_created') as check:
        s.click('[data-action="new-production"]')
        page.locator('#new-name').fill('Synthetic E2E Project')
        page.locator('#new-brief').fill('Audit and render the generated synthetic animated cube only.')
        s.click('[data-action="save-production"]')
        s.project = s.api('state')['projects'][0]
        s.project_dir = Path(s.project['directory'])
        assert s.project_dir.is_dir()
        s.click('[data-action="new-scene"]:visible >> nth=0')
        page.locator('#new-name').fill('Synthetic workbench scene')
        s.click('[data-action="save-scene"]')
        check.update(surface='new scene workbench', legacy_ui='REMOVED')
    with s.evidence.checkpoint('sources_verified'):
        s.click('[data-action="browse-assets"]:visible >> nth=0')
        s.click('[data-action="browser-tab"][data-tab="sources"]')
        def confirm_scan(dialog):
            dialog.accept()  # Explicit scripted confirmation for generated files only.
        page.on('dialog', confirm_scan)
        try:
            s.click('[data-action="scan"]')
        finally:
            page.remove_listener('dialog', confirm_scan)
        expect(page.locator('.browser-asset')).to_have_count(1)
        # Reference-only selection is deliberately behind package Details. It
        # must not imply preparation, geometry import or permission to use it.
        s.click('.browser-asset [data-action="source-detail"]')
        s.click('#dialog details > summary')
        s.click('#dialog [data-action="source"]')
        state = s.api('workbench/state?projectId='+s.project['id'])
        scene = state['project']['workbench']['scenes'][0]
        assert len(scene['sources']) == 1 and not scene.get('catalog')
        assert not scene['checkpoints'] and not scene.get('run')
        expect(page.locator('.browser-asset')).to_have_count(0)
        expect(page.locator('[data-location="production"] .location-count')).to_have_text('(1)')
        expect(page.locator('[data-location="library"] .location-count')).to_have_text('(0)')
        s.click('.browser-locations [data-action="browser-location"][data-location="production"]')
        expect(page.locator('.browser-asset')).to_have_count(1)
        s.click('.browser-locations [data-action="browser-location"][data-location="library"]')
        s.click('[data-action="browser-close"]')
        s.click('[data-action="settings"]')
        s.click('[data-action="diagnostics"]')
        s.click('[data-action="verify-sources"]')
        expect(page.locator('#source-verification')).to_contain_text('Source files verified')
        assert s.api('projects/verify', {'projectId': s.project['id']})['ok'] is True
        s.click('#dialog [data-action="close"]')
    with s.evidence.checkpoint('scene_audited') as check:
        s.scene = s.project_dir/'Scenes/synthetic.blend'
        shutil.copy2(s.source, s.scene)
        s.scene_hash = digest(s.scene)
        prior_pointer = s.api('project?projectId='+s.project['id'])['project']['scene']
        s.click('[data-action="settings"]')
        s.click('[data-action="diagnostics"]')
        page.locator('#diagnostic-scene').select_option('Scenes/synthetic.blend')
        s.click('[data-action="audit-saved"]')
        expect(page.locator('#diagnostic-jobs')).to_contain_text('SUCCEEDED')
        current = s.api('project?projectId='+s.project['id'])['project']
        assert current['scene'] == prior_pointer, 'Inspection must not retarget the project'
        jobs = current['jobs']
        records = [read(s.library/'jobs'/job['id']/'job.json') for job in jobs]
        assert any(job['state'] == 'SUCCEEDED' and job['specification']['operation'] == 'scene-audit' for job in records)
        check.update(jobs=[job['id'] for job in jobs], saved_file_pointer_preserved=True,
                     surface='workbench production diagnostics')
        s.click('#dialog [data-action="close"]')
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
        s.api('projects/audit', {'projectId': s.project['id'], 'scene':'Scenes/synthetic.blend'}, expected=409)
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
        expect(s.page.locator('.projectbar .production')).to_contain_text('Synthetic E2E Project')
        s.click('[data-action="settings"]')
        s.click('[data-action="diagnostics"]')
        expect(s.page.locator('#diagnostic-jobs')).to_contain_text('SUCCEEDED')
        s.click('#dialog [data-action="close"]')
    with s.evidence.checkpoint('trash_restored') as check:
        peer=s.api('projects/create',{'name':'Synthetic untouched production','brief':'Must remain unchanged when another production is archived.'})
        peer_manifest=Path(peer['directory'])/'project.json';peer_hash=digest(peer_manifest)
        original={p.relative_to(s.project_dir).as_posix():digest(p) for p in s.project_dir.rglob('*') if p.is_file()}
        s.click('[data-action="refresh"]')
        s.click('[data-action="picker"]')
        row='[data-production-id="'+s.project['id']+'"]'
        expect(s.page.locator(row+' [data-action="project"]')).to_be_visible()
        expect(s.page.locator(row+' [data-action="archive-production"]')).to_be_visible()
        s.page.screenshot(path=str(s.evidence.directory/'productions-archive-desktop.png'))
        s.page.set_viewport_size({'width':390,'height':844})
        assert s.page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        s.page.screenshot(path=str(s.evidence.directory/'productions-archive-mobile.png'))
        s.page.set_viewport_size({'width':1440,'height':1100})
        messages=[]
        def cancel_archive(dialog):
            messages.append(dialog.message);dialog.dismiss()
        s.page.once('dialog',cancel_archive)
        s.click(row+' [data-action="archive-production"]')
        assert 'Synthetic E2E Project' in messages[-1] and 'not permanent deletion' in messages[-1]
        assert s.project_dir.exists() and not s.api('state')['trash']['projects']
        assert original=={p.relative_to(s.project_dir).as_posix():digest(p) for p in s.project_dir.rglob('*') if p.is_file()}
        s.page.once('dialog',lambda dialog:dialog.accept())  # Generated fixture only, not a human decision.
        s.click(row+' [data-action="archive-production"]')
        assert not s.project_dir.exists()
        assert digest(s.source) == s.source_hash and s.png.exists()
        assert digest(peer_manifest)==peer_hash
        expect(s.page.locator('[data-production-id="'+peer['id']+'"]')).to_be_visible()
        expect(s.page.locator(row)).to_have_count(0)
        s.click('[data-action="archived-productions"]')
        s.page.once('dialog',lambda dialog:dialog.accept())  # Restore the generated fixture only.
        s.click('[data-action="restore-production"][data-id="'+s.project['id']+'"]')
        expect(s.page.locator('.projectbar .production')).to_contain_text('Synthetic E2E Project')
        assert digest(s.project_dir/'Renders/synthetic-preview.png') == digest(s.png)
        assert not s.api('state')['trash']['projects']
        assert original=={p.relative_to(s.project_dir).as_posix():digest(p) for p in s.project_dir.rglob('*') if p.is_file()}
        assert digest(peer_manifest)==peer_hash
        check.update(surface='Productions list',named_confirmation=True,cancel_preserved=True,
                     other_production_unchanged=True,complete_project_bytes_restored=True,
                     approval_input='scripted generated-fixture decisions only')
        s.preserve()
