"""Real Chrome clicks -> authenticated API -> genuine GLB -> rendered WebGL frames.

Only accepts a new synthetic viewer fixture session. No native desktop input,
licensed inputs or human approval claims. All evidence remains in the chosen folder.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect


def sha(file): return hashlib.sha256(Path(file).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fixture',required=True);parser.add_argument('--evidence',required=True);parser.add_argument('--chrome');args=parser.parse_args()
    root=Path(args.fixture);session=json.loads((root/'browser-session.json').read_text())
    assert session.get('fixture')=='synthetic-embedded-viewer','Refuse live or unrelated sessions'
    output=Path(args.evidence);output.mkdir(parents=True,exist_ok=False)
    before=sha(session['projectManifest']);catalog_before=sha(session['catalog'])
    report={'kind':'real-webgl-synthetic-viewer','checks':[],'errors':[],'requests':[],'external_requests':[],
            'not_tested':['human creative acceptance','licensed inputs','native desktop host','live Blender link (not implemented)']}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**({'executable_path':args.chrome} if args.chrome else {'channel':'chrome'}))
        report['browser']=browser.version
        context=browser.new_context(viewport={'width':1280,'height':900},service_workers='block')
        page=context.new_page();page.set_default_timeout(20000)
        page.on('pageerror',lambda e:report['errors'].append(str(e).replace(session['token'],'[REDACTED]')))
        page.on('console',lambda m:report['errors'].append({'text':m.text.replace(session['token'],'[REDACTED]'),'location':m.location}) if m.type=='error' else None)
        def request(r):
            if r.url.startswith(('data:','blob:')):return
            if not r.url.startswith(session['origin']+'/'):report['external_requests'].append(urlsplit(r.url).netloc)
            report['requests'].append({'path':urlsplit(r.url).path,'method':r.method})
        page.on('request',request);page.on('dialog',lambda d:d.dismiss())
        def idle(): expect(page.locator('body')).not_to_have_class(re.compile(r'\bworking\b'));expect(page.locator('#notice')).to_be_hidden()
        def click(selector):page.locator(selector).click();idle()
        def ready(selector):
            host=page.locator(selector)
            expect(host).to_have_attribute('data-viewer-state','ready',timeout=205000)
            expect(host.locator('canvas')).to_be_visible()
            return host
        try:
            page.goto(session['origin']+'/workbench#'+session['token']);idle()
            click('[data-action="project"][data-id="'+session['projectId']+'"]')
            assert 'Saved scene' in page.locator('body').inner_text()
            click('[data-action="scene-viewer"]');host=ready('[data-scene-viewer]')
            page.screenshot(path=str(output/'01-saved-checkpoint.png'))
            report['checks'].append('Camera-free checkpoint conversion and actual WebGL canvas')
            canvas=host.locator('canvas');before_orbit=canvas.screenshot(path=str(output/'02-before-orbit.png'))
            bounds=canvas.bounding_box();x=bounds['x']+bounds['width']*.5;y=bounds['y']+bounds['height']*.5
            page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+110,y+35,steps=12);page.mouse.up();page.wait_for_timeout(350)
            after_orbit=canvas.screenshot(path=str(output/'03-after-orbit.png'));assert before_orbit!=after_orbit,'Orbit did not change the rendered view'
            page.mouse.wheel(0,-220);page.wait_for_timeout(350);assert canvas.screenshot()!=after_orbit,'Zoom did not change the view'
            page.mouse.move(x,y);page.mouse.down(button='right');page.mouse.move(x+55,y+20,steps=8);page.mouse.up(button='right');page.wait_for_timeout(350)
            canvas.screenshot(path=str(output/'04-pan-zoom.png'));host.get_by_role('button',name='Reset view',exact=True).click()
            report['checks'].append('Real pointer orbit, wheel zoom, right-drag pan and reset')
            expect(host.locator('[data-view="take"] option')).to_have_count(1)
            host.locator('[data-view="time"]').fill('0');host.locator('[data-view="time"]').dispatch_event('input');page.wait_for_timeout(100)
            at_start=canvas.screenshot(path=str(output/'05-animation-start.png'))
            duration=float(host.locator('[data-view="time"]').get_attribute('max'));assert duration>0
            midpoint=round(duration*.5,3)
            host.locator('[data-view="time"]').fill(str(midpoint));host.locator('[data-view="time"]').dispatch_event('input');page.wait_for_timeout(100)
            at_mid=canvas.screenshot(path=str(output/'06-animation-middle.png'));assert at_start!=at_mid,'Skinned animation did not change pixels'
            host.get_by_role('button',name='Play',exact=True).click();page.wait_for_timeout(180)
            assert float(host.locator('[data-view="time"]').input_value())!=midpoint
            host.get_by_role('button',name='Pause',exact=True).click()
            report['checks'].append('Actual skinned playback, pause and timeline change rendered pixels')
            host.get_by_role('button',name='Grid',exact=True).click();expect(host.get_by_role('button',name='Grid',exact=True)).to_have_attribute('aria-pressed','false')
            host.get_by_role('button',name='Wireframe',exact=True).click();expect(host.get_by_role('button',name='Wireframe',exact=True)).to_have_attribute('aria-pressed','true')
            report['graphics']=canvas.evaluate("e=>{const g=e.getContext('webgl2');return {version:g.getParameter(g.VERSION),renderer:g.getParameter(g.RENDERER)}}")
            click('[data-action="browse-assets"].primary');click('#library-dialog [data-action="catalog-detail"]')
            select=page.locator('#catalog-file');values=select.locator('option').evaluate_all('(rows)=>rows.map(n=>n.value)');select.select_option(next(v for v in values if v.endswith('.glb')))
            click('#dialog [data-action="viewer-open"]');asset=ready('#dialog [data-viewer-host]')
            page.screenshot(path=str(output/'07-asset-in-app.png'))
            assert asset.locator('[data-view="take"] option').count()>=1
            first=asset.get_attribute('data-preview-id');click('#dialog [data-action="viewer-open"]');asset=ready('#dialog [data-viewer-host]')
            assert asset.get_attribute('data-preview-id')==first
            assert 'verified cached copy' in asset.inner_text()
            report['checks'].append('Catalog preselection GLB fast path and verified cache reuse')
            expect(page.locator('#dialog [data-action="asset-preview-open"]')).to_be_visible()
            select.select_option(next(v for v in values if v.endswith('.blend')));expect(asset.locator('canvas')).to_have_count(0)
            report['checks'].append('Member change disposes obsolete view; native Blender option remains separate')
            select.select_option(next(v for v in values if v.endswith('.glb')));click('#dialog [data-action="viewer-open"]');asset=ready('#dialog [data-viewer-host]')
            page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(output/'08-mobile.png'))
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.keyboard.press('Escape');expect(page.locator('#dialog')).not_to_be_visible();expect(page.locator('#dialog canvas')).to_have_count(0)
            report['checks'].append('Responsive 390px layout and Escape releases the asset canvas')
            page.keyboard.press('Escape');click('[data-action="tab"][data-tab="film"]');expect(page.locator('[data-scene-viewer] canvas')).to_have_count(0)
            assert sha(session['projectManifest'])==before,'Viewer changed project manifest'
            assert sha(session['catalog'])==catalog_before,'Viewer changed live synthetic catalog'
            assert all(sha(f['path'])==f['sha256'] for f in session['sourceFiles'])
            assert not report['errors'],report['errors'];assert not report['external_requests'],report['external_requests']
            forbidden=['asset-preview','catalog-select','catalog-job','approve','keep-building','run','task-open']
            assert not any(r['method']=='POST' and r['path'].split('/')[-1] in forbidden for r in report['requests'])
            report['checks'].extend(['Scene navigation releases canvas','Originals, catalog and manifest unchanged','No external fetches or scene/approval/native-window requests'])
            report['status']='PASS'
        except Exception as error:
            report['status']='FAIL';report['failure']=str(error).replace(session['token'],'[REDACTED]');page.screenshot(path=str(output/'failure.png'));raise
        finally:
            (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');context.close();browser.close()
    print(json.dumps({'status':report['status'],'checks':len(report['checks']),'evidence':str(output)}))


if __name__=='__main__':main()
