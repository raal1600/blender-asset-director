"""Actual browser/HTTP checkpoint journey on generated installed-studio files.

User confirmations here are scripted acceptance inputs, not artistic approval.
No Blender GUI or model is launched by this browser check.
"""
import re
import json
import time
from playwright.sync_api import expect
from support import digest, write



def wait_for_media(page, selector, *, started=False):
    """Read real media properties without wait_for_function's nested unsafe eval.

    The launcher's restrictive Content-Security-Policy remains enabled.
    """
    media = page.locator(selector)
    deadline = time.monotonic() + 30
    observed = None
    while time.monotonic() < deadline:
        observed = media.evaluate('(v) => ({ready: v.readyState, time: v.currentTime, error: v.error ? v.error.code : null})')
        assert observed['error'] is None, 'Browser media decode failed: ' + str(observed)
        if observed['ready'] >= 2 and (not started or observed['time'] > 0):
            return observed
        page.wait_for_timeout(100)
    raise AssertionError('Real browser media did not become ready/play: ' + str(observed))


def review_scene(s):
    page = s.page
    package_images = []
    def image_response(response):
        if '/api/workbench/source-image?' in response.url:
            package_images.append(response.status)
    page.on('response', image_response)

    def idle():
        expect(page.locator('#app.busy')).to_have_count(0, timeout=220000)
        expect(page.locator('#notice')).to_be_hidden()

    def click(selector):
        if selector == '[data-action="import"]' and page.locator('.world-more').count():
            page.locator('.world-more summary').click()
        if selector.startswith('.ingredient') and not page.locator(selector).count():
            page.locator('.world-more summary').click()
            page.locator('[data-action="world-ingredients"]').click()
        if selector == '[data-action="preview"]':
            if page.locator('.world-inspection').count() and page.locator('.world-inspection').get_attribute('open') is None:
                page.locator('.world-inspection > summary').click()
            panel = page.locator('.rendered-evidence')
            if panel.get_attribute('open') is None:
                panel.locator('summary').click()
        page.locator(selector).click()
        idle()

    with s.evidence.checkpoint('workbench_scene_review') as check:
        page.goto(s.session['origin'] + '/workbench#' + s.session['token'])
        idle()
        if page.locator('[data-action="project"][data-id="'+s.project['id']+'"]').count():
            click('[data-action="project"][data-id="' + s.project['id'] + '"]')
        if not s.api('workbench/state?projectId='+s.project['id'])['project']['workbench']['scenes']:
            click('[data-action="new-scene"]:visible >> nth=0')
            page.locator('#new-name').fill('Synthetic workbench scene')
            click('[data-action="save-scene"]')
        click('[data-action="browse-assets"]:visible >> nth=0')
        click('[data-action="browser-tab"][data-tab="sources"]')
        expect(page.locator('.browser-asset')).to_have_count(1)
        if not page.locator('.browser-asset').evaluate("e=>e.classList.contains('selected')"):
            click('.browser-asset [data-action="source"]')
        click('[data-action="browser-close"]')
        state = s.api('workbench/state?projectId=' + s.project['id'])
        scene = state['project']['workbench']['scenes'][0]
        assert len(scene['sources']) == 1 and not scene['checkpoints']
        expect(page.locator('[data-action="stage"][data-stage="render"]')).to_be_disabled()
        click('[data-action="import"]')
        page.locator('#import-file').select_option('Scenes/synthetic.blend')
        click('[data-action="save-import"]')
        state = s.api('workbench/state?projectId=' + s.project['id'])
        scene = state['project']['workbench']['scenes'][0]
        candidate = scene['candidate']
        assert candidate and scene['current'] is None and not scene['completed']
        checkpoint = next(c for c in scene['checkpoints'] if c['id'] == candidate)
        assert digest(s.project_dir / checkpoint['path']) == s.scene_hash

        def confirm(dialog):
            dialog.accept()
        page.on('dialog', confirm)
        try:
            click('[data-action="keep-building"]')
            assert not s.api('workbench/state?projectId='+s.project['id'])['project']['workbench']['scenes'][0]['completed']
            click('[data-action="approve"]')
        finally:
            page.remove_listener('dialog', confirm)
        expect(page.locator('[data-action="stage"][data-stage="action"]')).to_have_class(re.compile(r'\bactive\b'))
        state = s.api('workbench/state?projectId=' + s.project['id'])
        scene = state['project']['workbench']['scenes'][0]
        assert scene['current'] == candidate and scene['candidate'] is None
        assert scene['completed']['world'] == candidate
        assert not scene['completed'].get('action')
        assert digest(s.scene) == s.scene_hash
        page.reload()
        idle()
        expect(page.locator('h1')).to_have_text('Synthetic workbench scene')
        page.screenshot(path=str(s.evidence.directory / 'workbench-desktop.png'))
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile page overflow'
        expect(page.locator('#scene-picker')).to_be_visible()
        page.screenshot(path=str(s.evidence.directory / 'workbench-mobile.png'), full_page=True)
        page.set_viewport_size({'width': 1440, 'height': 1100})
        check.update(scene=scene['id'], checkpoint=candidate, sha256=checkpoint['sha256'],
                     original_preserved=True, approval_input='scripted synthetic user confirmation',
                     blender_gui='NOT_TESTED')
        catalog_and_film(s, click, idle, check)
        assert package_images and all(status == 204 for status in package_images), package_images
        check.update(optional_package_images=package_images, missing_image_console_404=False)
        page.remove_listener('response', image_response)
        s.preserve()
        # Reopen the same workbench for the existing recovery/trash journey.
        page.goto(s.session['origin'] + '/#' + s.session['token'])
        s.idle()


def catalog_and_film(s, click, idle, check):
    """Real local catalog -> native import -> reviewed checkpoint -> browser movie.

    Decisions are synthetic test input. Blender and FFmpeg execute for real.
    This is not proof of human creative acceptance or an authenticated model.
    """
    page = s.page
    evidence = s.root / 'synthetic-catalog-evidence.json'
    write(evidence, {'title': 'Synthetic catalog set', 'kind': 'model',
                     'source_url': 'https://example.invalid/generated-ci-fixture',
                     'license_id': 'CC0-1.0', 'license_url': 'https://example.invalid/synthetic-license',
                     'author': 'Synthetic fixture generator', 'price': 0, 'attested': True})
    asset = json.loads(s.cmd(s.director + ['intake', str(s.source), '--evidence', str(evidence), '--preserve-existing']))
    aid = asset['asset_id']
    click('[data-action="stage"][data-stage="world"]')
    click('.projectbar [data-action="refresh"]')
    click('[data-action="browse-assets"]:visible >> nth=0')
    click('[data-action="browser-tab"][data-tab="catalog"]')
    click('[data-action="catalog-select"][data-id="' + aid + '"]')
    click('[data-action="browser-close"]')
    use = s.api('workbench/state?projectId=' + s.project['id'])['sourceUse']
    assert not use['ready'] and any(a['sourceId'] == aid for a in use['scope']['sources'])
    click('[data-action="source-review"]')
    click('[data-action="source-confirm"]')

    def state():
        return s.api('workbench/state?projectId=' + s.project['id'])

    def settle():
        deadline = time.monotonic() + 220
        while time.monotonic() < deadline:
            current = state()
            if not current['locked']:
                scene = current['project']['workbench']['scenes'][0]
                failures = [r for r in current['runs'] if r.get('sceneId') == scene['id'] and r['state'] == 'FAILED']
                assert not failures, failures
                click('.projectbar [data-action="refresh"]')
                return scene
            time.sleep(.2)
        raise AssertionError('Workbench native operation did not finish')

    click('.ingredient[data-action="catalog-detail"][data-id="' + aid + '"]')
    click('[data-action="catalog-inspect"]')
    scene = settle()
    assert scene['assetContents'][aid]['collections']
    click('.ingredient[data-action="catalog-detail"][data-id="' + aid + '"]')
    page.locator('[name="catalog-collection"]').first.check()
    def confirm(dialog):
        dialog.accept()
    page.on('dialog', confirm)
    click('[data-action="catalog-import"]')
    scene = settle()
    imported = next(c for c in scene['checkpoints'] if c['id'] == scene['candidate'])
    assert any(o.get('asset_id') == aid and o.get('import_job') == imported['jobId'] for o in imported['audit']['objects'])
    assert scene['current'] != imported['id']
    # Preview the still-unapproved candidate through the actual UI and worker.
    # Cancelling the dialog must not prepare a job or synthesize a review.
    before_jobs = len(state()['project']['jobs'])
    before_current, before_completed = scene['current'], dict(scene['completed'])
    click('[data-action="preview"]')
    click('#dialog [data-action="close"]')
    assert len(state()['project']['jobs']) == before_jobs
    click('[data-action="preview"]')
    click('[data-action="save-preview"]')
    scene = settle()
    assert scene['candidate'] == imported['id'] and scene['current'] == before_current
    assert scene['completed'] == before_completed
    assert scene['preview']['checkpointId'] == imported['id']
    preview = page.locator('img[data-media="preview"]')
    # Returning from the real render must preserve the user's open inspection
    # tools. Never force-click a hidden control to conceal a product regression.
    expect(page.locator('.world-inspection')).to_have_attribute('open','')
    expect(page.locator('.rendered-evidence')).to_have_attribute('open','')
    if page.locator('.rendered-evidence').get_attribute('open') is None:
        page.locator('.rendered-evidence summary').click()
    expect(preview).to_be_visible()
    deadline = time.monotonic() + 30
    while not preview.evaluate('(image) => image.complete && image.naturalWidth > 0'):
        assert time.monotonic() < deadline, 'Actual candidate PNG did not decode'
        page.wait_for_timeout(100)
    assert digest(s.project_dir / imported['path']) == imported['sha256']
    page.screenshot(path=str(s.evidence.directory / 'workbench-candidate-preview.png'))
    check.update(candidate_preview_job=scene['preview']['jobId'],
                 candidate_preview_without_approval=True, candidate_preview_browser_decoded=True)
    click('[data-action="keep-building"]')
    scene = state()['project']['workbench']['scenes'][0]
    assert scene['stage'] == 'world' and scene['current'] == imported['id'] and not scene['candidate']
    assert not scene['completed'].get('world')
    page.screenshot(path=str(s.evidence.directory / 'workbench-native-import.png'))
    # The generated asset already contains keyframed action, cameras and lights.
    # These confirmations test state transitions, not manual authoring/quality.
    for activity in ['world', 'action']:
        assert state()['project']['workbench']['scenes'][0]['stage'] == activity
        click('[data-action="approve"]')
    # Save a named shot from observed camera metadata; never invent cameras.
    camera_names = [o['name'] for o in imported['audit']['objects'] if o['type'] == 'CAMERA']
    assert len(camera_names) >= 2
    click('[data-action="new-shot"]')
    page.locator('#shot-name').fill('Synthetic arrival')
    page.locator('#shot-camera').select_option(camera_names[-1])
    page.locator('#shot-start').fill('1')
    page.locator('#shot-end').fill('4')
    click('[data-action="save-shot"]')
    scene = state()['project']['workbench']['scenes'][0]
    definition = scene['shots'][0]
    assert scene['selectedShot'] == definition['id'] and definition['revision'] == 1
    click('[data-action="preview"]')
    click('[data-action="save-preview"]')
    scene = settle()
    assert scene['preview']['camera'] == definition['camera']
    assert scene['preview']['shotId'] == definition['id'] and scene['preview']['shotRevision'] == 1
    for activity in ['shots', 'light']:
        assert state()['project']['workbench']['scenes'][0]['stage'] == activity
        click('[data-action="approve"]')
    assert s.api('workbench/capabilities')['encoder'], 'Film journey needs real FFmpeg and FFprobe' 
    click('[data-action="readiness"]')
    scene = settle()
    assert not scene['readiness']['data']['blockers']
    expect(page.locator('#render-start')).to_be_disabled()
    expect(page.locator('#render-end')).to_be_disabled()
    expect(page.locator('#render-camera')).to_have_value(definition['camera'])
    page.locator('#render-width').fill('64')
    page.locator('#render-height').fill('64')
    page.locator('#render-samples').fill('1')
    click('[data-action="render"]')
    scene = settle()
    shot = scene['renders'][-1]
    assert shot['shotId'] == definition['id'] and shot['shotRevision'] == definition['revision']
    assert shot['video']['frames'] == 4 and shot['video']['state'] == 'SUCCEEDED' and not shot['approved']
    click('[data-action="play-render"][data-id="' + shot['id'] + '"]')
    wait_for_media(page, '#review-video')
    page.locator('#review-video').evaluate('(v) => v.play()')
    wait_for_media(page, '#review-video', started=True)
    click('#dialog [data-action="close"]')
    click('[data-action="approve-render"][data-id="' + shot['id'] + '"]')
    click('[data-action="tab"][data-tab="film"]')
    click('[data-action="add-clip"][data-id="' + shot['id'] + '"]')
    click('[data-action="build-film"]')
    settle()
    cut = state()['project']['workbench']['film']['cuts'][-1]
    assert not cut['approved'] and cut['result']['frames'] == 4
    wait_for_media(page, 'video[aria-label="Final film"]')
    page.locator('video[aria-label="Final film"]').evaluate('(v) => v.play()')
    wait_for_media(page, 'video[aria-label="Final film"]', started=True)
    click('[data-action="approve-cut"]')
    cut = state()['project']['workbench']['film']['cuts'][-1]
    assert cut['approved'] and cut['result']['human_acceptance'] == 'PENDING'
    check.update(native_catalog_asset=aid, imported_checkpoint=imported['id'],
                 import_job=imported['jobId'], render_job=shot['jobId'],
                 film_sha256=cut['result']['sha256'], browser_movie_playback=True,
                 approval_input='scripted generated-fixture decisions only')

    with s.evidence.checkpoint('workbench_shot_roundtrip') as shot_check:
        # Revise timing without changing scene bytes: the old render must become
        # historical. Old green scene hashes cannot validate a changed shot.
        click('[data-action="edit-source"][data-id="' + scene['id'] + '"]')
        click('[data-action="stage"][data-stage="shots"]')
        click('[data-action="edit-shot"][data-id="' + definition['id'] + '"]')
        page.locator('#shot-end').fill('3')
        click('[data-action="save-shot"]')
        changed = state()['project']['workbench']['scenes'][0]
        assert changed['current'] == imported['id'] and changed['shots'][0]['revision'] == 2
        assert changed['renders'][0]['approved'] and not changed['completed'].get('light')
        click('[data-action="return-film"]')
        expect(page.locator('.film-inspector h2')).to_have_text('Historical cut')
        expect(page.locator('[data-action="approve-cut"]')).to_be_disabled()
        # Independently require server refusal; a disabled button alone is not a gate.
        response = page.request.post(s.session['origin'] + '/api/workbench/approve-cut',
            headers={'Authorization': 'Bearer ' + s.session['token']},
            data={'projectId': s.project['id'], 'revision': state()['project']['revision'], 'cutId': cut['id']})
        assert response.status == 409, response.text()
        click('[data-action="remove-clip"][data-index="0"]')
        assert not state()['project']['workbench']['film']['clips']
        assert state()['project']['workbench']['film']['cuts'][-1]['result']['sha256'] == cut['result']['sha256']
        page.screenshot(path=str(s.evidence.directory / 'workbench-shot-revision.png'))
        shot_check.update(shot_id=definition['id'], rendered_revision=1, revised_definition=2,
                          camera=definition['camera'], scene_hash_unchanged=True,
                          stale_approval_http=409, historical_cut_preserved=True,
                          approval_input='scripted generated-fixture decisions only')

    page.remove_listener('dialog', confirm)
