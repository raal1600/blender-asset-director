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

    def idle():
        expect(page.locator('#app.busy')).to_have_count(0, timeout=220000)
        expect(page.locator('#notice')).to_be_hidden()

    def click(selector):
        page.locator(selector).click()
        idle()

    with s.evidence.checkpoint('workbench_scene_review') as check:
        page.goto(s.session['origin'] + '/workbench#' + s.session['token'])
        idle()
        click('[data-action="project"][data-id="' + s.project['id'] + '"]')
        click('[data-action="new-scene"]:visible >> nth=0')
        page.locator('#new-name').fill('Synthetic workbench scene')
        click('[data-action="save-scene"]')
        expect(page.locator('.asset')).to_have_count(1)
        click('.asset [data-action="source"]')
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
        s.preserve()
        # Restore the legacy surface for the existing recovery/trash journey.
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
    click('[data-action="catalog-select"][data-id="' + aid + '"]')
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

    click('[data-action="catalog-detail"][data-id="' + aid + '"]')
    click('[data-action="catalog-inspect"]')
    scene = settle()
    assert scene['assetContents'][aid]['collections']
    click('[data-action="catalog-detail"][data-id="' + aid + '"]')
    page.locator('[name="catalog-collection"]').first.check()
    def confirm(dialog):
        dialog.accept()
    page.on('dialog', confirm)
    click('[data-action="catalog-import"]')
    scene = settle()
    imported = next(c for c in scene['checkpoints'] if c['id'] == scene['candidate'])
    assert any(o.get('asset_id') == aid and o.get('import_job') == imported['jobId'] for o in imported['audit']['objects'])
    assert scene['current'] != imported['id']
    click('[data-action="keep-building"]')
    scene = state()['project']['workbench']['scenes'][0]
    assert scene['stage'] == 'world' and scene['current'] == imported['id'] and not scene['candidate']
    assert not scene['completed'].get('world')
    page.screenshot(path=str(s.evidence.directory / 'workbench-native-import.png'))
    # The generated asset already contains keyframed action, cameras and lights.
    # These confirmations test state transitions, not manual authoring/quality.
    for activity in ['world', 'action', 'shots', 'light']:
        assert state()['project']['workbench']['scenes'][0]['stage'] == activity
        click('[data-action="approve"]')
    assert s.api('workbench/capabilities')['encoder'], 'Film journey needs real FFmpeg and FFprobe'
    click('[data-action="readiness"]')
    scene = settle()
    assert not scene['readiness']['data']['blockers']
    page.locator('#render-start').fill('1')
    page.locator('#render-end').fill('4')
    page.locator('#render-width').fill('64')
    page.locator('#render-height').fill('64')
    page.locator('#render-samples').fill('1')
    click('[data-action="render"]')
    scene = settle()
    shot = scene['renders'][-1]
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

    page.remove_listener('dialog', confirm)
