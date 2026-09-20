"""Real Chrome UI regression against the disposable synthetic catalog fixture.

Never connect to a live studio. This verifies UI/HTTP behavior, not Blender,
licensed inputs, model authentication, or human creative approval.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

def main():
    p=argparse.ArgumentParser();p.add_argument('--fixture',required=True);p.add_argument('--evidence',required=True);p.add_argument('--chrome');a=p.parse_args()
    root=Path(a.fixture);session=json.loads((root/'browser-session.json').read_text())
    assert session.get('fixture')=='synthetic-catalog-browser', 'Refuse a non-fixture session'
    output=Path(a.evidence);output.mkdir(parents=True,exist_ok=False)
    report={'kind':'synthetic-browser-ui','checks':[],'captures':[],'errors':[],'requests':[]}
    def save_report(): (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    registry=root/'Database/Registry/sources.json';before=hashlib.sha256(registry.read_bytes()).hexdigest()
    with sync_playwright() as pw:
        options={'executable_path':a.chrome} if a.chrome else {'channel':'chrome'}
        browser=pw.chromium.launch(**options)
        report['browser']=browser.version
        context=browser.new_context(viewport={'width':1280,'height':800},service_workers='block')
        page=context.new_page();page.set_default_timeout(15000)
        page.on('pageerror',lambda e:report['errors'].append(str(e).replace(session['token'],'[REDACTED]')))
        page.on('request',lambda r:report['requests'].append({'path':r.url.split('?')[0].removeprefix(session['origin']),'method':r.method}))
        page.on('dialog',lambda d:d.dismiss())
        def idle():
            expect(page.locator('body')).not_to_have_class(__import__('re').compile(r'\bworking\b'))
            expect(page.locator('#notice')).to_be_hidden()
        def click(selector):page.locator(selector).click();idle()
        def choose_scene(scene_id):
            if page.locator('#scene-picker').is_visible():
                page.locator('#scene-picker').select_option(scene_id);idle()
            else:click('[data-action="scene"][data-id="'+scene_id+'"]')
        def filters():
            panel=page.locator('.browser-filters')
            if panel.count() and panel.get_attribute('open') is None:click('.browser-filters > summary')
        def capture(name):
            page.screenshot(path=str(output/(name+'.png')))
            metrics=page.evaluate('''() => ({width:innerWidth,height:innerHeight,pageWidth:document.documentElement.scrollWidth,pageHeight:document.documentElement.scrollHeight,
                cards:document.querySelectorAll('.browser-asset').length,dialog:(()=>{const r=document.querySelector('#library-dialog').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}})()})''')
            assert metrics['pageWidth']<=metrics['width'],metrics
            report['captures'].append({'name':name,'metrics':metrics})
        try:
            page.goto(session['origin']+'/workbench#'+session['token']);idle()
            click('[data-action="project"][data-id="'+session['projectId']+'"]')
            assert not any('/api/workbench/catalog' in r['path'] or '/api/workbench/sources'==r['path'] for r in report['requests'])
            capture('01-compact-scene')
            assert not page.get_by_text('Legacy launcher',exact=True).count()
            # Explicit metadata-only scenes, not lifecycle/Blender approval evidence.
            for scene_id,activity,catalog_count,source_count,kinds in [
                (session['sceneId'],'world',4000,6666,{'model','pack'}),
                (session['motionSceneId'],'action',2000,3334,{'animation'}),
                (session['lookSceneId'],'light',4000,0,{'material','hdri'})]:
                choose_scene(scene_id)
                click('[data-action="browse-assets"]:visible >> nth=0')
                expect(page.locator('#browser-activity')).to_have_value(activity)
                expect(page.locator('.browser-asset')).to_have_count(24)
                assert set(page.locator('.browser-asset').evaluate_all('(rows)=>rows.map(r=>r.dataset.kind)'))<=kinds
                assert 'of '+str(catalog_count)+' assets' in page.locator('.browser-footer [role="status"]').inner_text()
                capture('workflow-'+activity+'-catalog')
                click('[data-action="browser-tab"][data-tab="sources"]')
                expect(page.locator('.browser-asset')).to_have_count(min(source_count,24))
                assert 'of '+str(source_count)+' packages' in page.locator('.browser-footer [role="status"]').inner_text()
                capture('workflow-'+activity+'-sources')
                click('[data-action="browser-close"]')
            choose_scene(session['sceneId'])
            click('[data-action="browse-assets"]:visible >> nth=0')
            filters();page.keyboard.press('Escape')
            expect(page.locator('#library-dialog')).to_be_visible()
            expect(page.locator('.browser-filters')).not_to_have_attribute('open','')
            expect(page.locator('.browser-filters > summary')).to_be_focused()
            filters();page.locator('#library-title').click()
            expect(page.locator('.browser-filters')).not_to_have_attribute('open','')
            filters()
            page.locator('#browser-activity').select_option('all');idle()
            click('[data-action="browser-tab"][data-tab="catalog"]')
            expect(page.locator('.browser-asset')).to_have_count(24)
            capture('02-wide-catalog')
            page.locator('.browser-results').evaluate('(e)=>e.scrollTop=350')
            click('[data-action="browser-page"]:has-text("Next")')
            expect(page.locator('.browser-footer [role="status"]')).to_have_text('25–48 of 10000 assets')
            assert page.locator('.browser-results').evaluate('(e)=>e.scrollTop')==0
            page.locator('.browser-results').evaluate('(e)=>e.scrollTop=220')
            click('[data-action="browser-close"]')
            expect(page.locator('[data-action="browse-assets"]').first).to_be_focused()
            click('[data-action="browse-assets"]:visible >> nth=0')
            expect(page.locator('.browser-footer [role="status"]')).to_have_text('25–48 of 10000 assets')
            assert page.locator('.browser-results').evaluate('(e)=>e.scrollTop')>=200
            page.locator('#browser-query').fill('09999');page.locator('#browser-query').press('Enter');idle()
            expect(page.locator('.browser-asset')).to_have_count(1)
            click('[data-action="browser-tab"][data-tab="sources"]')
            expect(page.locator('#browser-query')).to_have_value('09999')
            expect(page.locator('.browser-asset')).to_have_count(1)
            expect(page.locator('.browser-asset h3')).to_have_text('Source package 09999')
            click('[data-action="source-detail"]');expect(page.locator('#dialog')).to_be_visible()
            click('#dialog [data-action="close"]')
            expect(page.locator('#library-dialog')).to_be_visible()
            page.locator('#browser-query').fill('');page.locator('#browser-query').press('Enter');idle()
            expect(page.locator('.browser-asset')).to_have_count(24)
            capture('03-source-packages')
            filters();page.locator('#browser-kind').select_option('Animations');idle()
            expect(page.locator('.browser-filters')).to_have_attribute('open','')
            expect(page.locator('[data-action="browser-layout"][data-layout="list"]')).to_be_visible()
            click('[data-action="browser-layout"][data-layout="list"]')
            expect(page.locator('.browser-results')).to_have_class(__import__('re').compile(r'\blist\b'))
            expect(page.locator('[data-layout="list"]')).to_have_attribute('aria-pressed','true')
            assert page.locator('[data-source-image]').count()==0
            capture('04-motion-list')
            filters();page.locator('#browser-kind').select_option('');idle()
            click('[data-action="browser-tab"][data-tab="catalog"]')
            page.locator('#browser-query').fill('00000');page.locator('#browser-query').press('Enter');idle()
            click('#library-dialog [data-action="catalog-detail"]')
            expect(page.locator('[data-action="catalog-import"]')).to_be_disabled()
            page.keyboard.press('Escape');expect(page.locator('#dialog')).not_to_be_visible()
            expect(page.locator('#library-dialog')).to_be_visible()
            if not page.locator('.browser-asset').evaluate("(e)=>e.classList.contains('selected')"):
                click('[data-action="catalog-select"]')
            expect(page.locator('.browser-asset')).to_have_class(__import__('re').compile(r'\bselected\b'))
            filters();page.locator('#browser-scope').select_option('selected');idle()
            expect(page.locator('.browser-asset')).to_have_count(1)
            assert 'Selected · not imported' in page.locator('.browser-asset').inner_text()
            page.locator('#browser-query').fill('missing');page.locator('#browser-query').press('Enter');idle()
            expect(page.get_by_text('No matching assets',exact=True)).to_be_visible()
            page.locator('#browser-query').fill('');page.locator('#browser-query').press('Enter');idle()
            # Tab cycles inside the modal; Escape restores the scene button.
            for _ in range(24):
                page.keyboard.press('Tab')
                assert page.evaluate("document.querySelector('#library-dialog').contains(document.activeElement)"), page.evaluate("document.activeElement.outerHTML.slice(0,200)")
            page.keyboard.press('Escape');expect(page.locator('[data-action="browse-assets"]').first).to_be_focused()
            for width,height in [(1024,768),(390,844)]:
                page.set_viewport_size({'width':width,'height':height})
                capture('05-scene-'+str(width))
                if width==1024:
                    task=page.locator('.world-next .primary').bounding_box()
                    assert task['y']+task['height']<=height, 'Primary scene action is below the first screen'
                click('[data-action="browse-assets"]:visible >> nth=0')
                capture('06-browser-'+str(width))
                metrics=report['captures'][-1]['metrics']['dialog']
                assert metrics['y']>=0 and metrics['height']<=height
                page.keyboard.press('Escape')
            assert hashlib.sha256(registry.read_bytes()).hexdigest()==before
            assert not report['errors'],report['errors']
            report['checks']=['World: models/packs only','Action: movement only','Light: materials/HDRIs only','workflow filter before pagination','source packages filtered by activity','activity-specific browser state','legacy entry removed','explicit entire-library escape','lazy catalog/package requests','24-card bound with 10000 entries','next page','reopen restores page/scroll','search across full library','search retained across sources','source inspector','motion rows without atlas requests','native inspector refuses import','selection survives refresh without import','selected filter','empty search','modal keyboard containment','nested Escape and focus return','1024 and 390 responsive layouts','registry preserved']
            report['status']='PASS'
        except Exception as e:
            report['status']='FAIL';report['failure']=str(e).replace(session['token'],'[REDACTED]')
            page.screenshot(path=str(output/'failure.png'))
            raise
        finally:
            save_report();context.close();browser.close()
    print(json.dumps({'status':report['status'],'checks':len(report['checks']),'evidence':str(output)}))
if __name__=='__main__':main()
