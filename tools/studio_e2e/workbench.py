"""Actual browser/HTTP checkpoint journey on generated installed-studio files.

User confirmations here are scripted acceptance inputs, not artistic approval.
No Blender GUI or model is launched by this browser check.
"""
import re
from playwright.sync_api import expect
from support import digest


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
        s.preserve()
        # Restore the legacy surface for the existing recovery/trash journey.
        page.goto(s.session['origin'] + '/#' + s.session['token'])
        s.idle()
