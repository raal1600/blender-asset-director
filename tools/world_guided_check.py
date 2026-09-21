"""Real browser -> real local API -> real Blender import, synthetic inputs only.

Scripted confirmations exercise controls; they are never human acceptance.
"""
import argparse,hashlib,json,re,struct,time,urllib.request
from urllib.parse import urlsplit
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fixture',required=True);parser.add_argument('--evidence',required=True);parser.add_argument('--chrome');args=parser.parse_args()
    root=Path(args.fixture);session=json.loads((root/'browser-session.json').read_text())
    assert session['fixture']=='synthetic-guided-world' and Path(session['root']).resolve()==root.resolve()
    out=Path(args.evidence);out.mkdir(exist_ok=False)
    report={'status':'RUNNING','kind':'real-guided-world-synthetic','checks':[],'errors':[],'decisions':'SCRIPTED_TEST_INPUTS_NOT_HUMAN_APPROVAL','not_tested':['native desktop host','manual Blender task edits','Codex execution','licensed production assets','live installation']}
    def api(route):
        request=urllib.request.Request(session['origin']+'/api/'+route,headers={'Authorization':'Bearer '+session['token']})
        with urllib.request.urlopen(request,timeout=60) as response:return json.load(response)
    def state():return api('workbench/state?projectId='+session['projectId'])
    def scene():return state()['project']['workbench']['scenes'][0]
    def digest(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**({'executable_path':args.chrome} if args.chrome else {'channel':'chrome'}),chromium_sandbox=True)
        context=browser.new_context(viewport={'width':1440,'height':960},service_workers='block');page=context.new_page();page.set_default_timeout(25000)
        page.on('pageerror',lambda e:report['errors'].append(str(e).replace(session['token'],'[REDACTED]')))
        page.on('console',lambda m:report['errors'].append(m.text.replace(session['token'],'[REDACTED]')) if m.type=='error' else None)
        models=[]
        def observed_model(response):
            if urlsplit(response.url).path=='/api/workbench/viewer-model' and response.status==200:
                raw=response.body();size,kind=struct.unpack_from('<II',raw,12)
                assert raw[:4]==b'glTF' and kind==0x4e4f534a
                value=json.loads(raw[20:20+size]);models.append({n['name'] for n in value['nodes'] if 'mesh' in n})
        page.on('response',observed_model)
        accept=False
        page.on('dialog',lambda dialog:dialog.accept() if accept else dialog.dismiss())
        def idle():expect(page.locator('body')).not_to_have_class(re.compile(r'\bworking\b'),timeout=30000)
        def click(selector):
            page.locator('body').aria_snapshot()
            page.locator(selector).click();idle()
        def capture(name):
            idle();assert session['token'] not in page.url
            page.screenshot(path=str(out/(name+'.png')),animations='disabled')
            (out/(name+'.txt')).write_text(page.locator('body').aria_snapshot(),encoding='utf-8')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Horizontal overflow'
        def ready(selector):
            expect(page.locator(selector)).to_have_attribute('data-viewer-state',re.compile('^(ready|failed)$'),timeout=210000)
            expect(page.locator(selector)).to_have_attribute('data-viewer-state','ready')
        def finish_job():
            deadline=time.monotonic()+230
            while time.monotonic()<deadline:
                current=state()
                if not current['locked']:
                    assert not [r for r in current['runs'] if r['state']=='FAILED'],current['runs']
                    click('.projectbar [data-action="refresh"]');return scene()
                page.wait_for_timeout(400)
            raise AssertionError('Bounded Blender job did not settle')
        try:
            page.goto(session['origin']+'/workbench#'+session['token']);idle()
            click('[data-action="project"][data-id="'+session['projectId']+'"]')
            expect(page.locator('[data-world-state]')).to_have_attribute('data-world-state','empty')
            expect(page.get_by_role('button',name='Find an asset',exact=True)).to_be_visible();capture('01-empty-world')
            report['checks'].append('Real page loads with one contextual next step and no console errors')
            click('.world-canvas-actions [data-action="browse-assets"]')
            expect(page.locator('.browser-results')).to_have_attribute('aria-busy','false')
            expect(page.locator('.browser-filters')).not_to_have_attribute('open','')
            capture('02-simple-browser')
            click('.browser-filters summary');page.locator('#browser-activity').select_option('all');idle()
            expect(page.locator('#library-title')).to_have_text('Entire library')
            page.locator('#browser-activity').select_option('world');idle()
            click('.browser-filters summary')
            click('[data-action="catalog-preview-detail"][data-id="'+session['assetId']+'"]');expect(page.locator('dialog[open]')).to_have_count(1)
            ready('#dialog [data-viewer-host]');capture('03-asset-preview')
            assert not scene().get('catalog') and not scene().get('candidate')
            page.keyboard.press('Escape');idle();expect(page.locator('#library-dialog')).to_be_visible()
            click('[data-action="catalog-preview-detail"][data-id="'+session['assetId']+'"]');ready('#dialog [data-viewer-host]')
            before=digest(session['projectManifest']);click('[data-action="catalog-import"]')
            assert digest(session['projectManifest'])==before
            report['checks'].append('Preview/Back preserve navigation; cancelled add writes no selection, job or checkpoint')
            accept=True;click('[data-action="catalog-import"]')
            expect(page.locator('[data-world-state]')).to_have_attribute('data-world-state','rights')
            assert not state()['project']['jobs'] and not scene()['candidate']
            capture('04-source-review-required')
            click('[data-action="source-review"]');click('[data-action="source-confirm"]')
            expect(page.locator('[data-world-state]')).to_have_attribute('data-world-state','add')
            report['checks'].append('New pin stops at exact source-use review; no dependent import ran')
            click('.world-next [data-action="catalog-detail"]');ready('#dialog [data-viewer-host]')
            click('[data-action="catalog-import"]')
            current=finish_job();cp=next(c for c in current['checkpoints'] if c['id']==current['candidate'])
            assert any(o.get('asset_id')==session['assetId'] and o.get('type')=='MESH' for o in cp['audit']['objects'])
            ready('[data-scene-viewer]');capture('05-import-review')
            click('.world-more > summary');click('[data-action="world-ingredients"]')
            click('#dialog [data-action="browse-assets"].primary');page.keyboard.press('Escape');idle()
            expect(page.get_by_role('button',name='Add assets',exact=True)).to_be_focused()
            assert not current['current'] and not current['completed']
            canvas=page.locator('[data-scene-viewer] canvas');before_orbit=canvas.screenshot();box=canvas.bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']/2
            page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+90,y+20,steps=9);page.mouse.up();page.wait_for_timeout(300)
            assert before_orbit!=canvas.screenshot()
            click('[data-action="keep-building"]');current=scene()
            assert current['current']==cp['id'] and not current['candidate'] and not current['completed']
            assert digest(Path(session['projectManifest']).parent/cp['path'])==cp['sha256']
            report['checks'].append('Actual Blender import yields observed mesh; real 3D orbit; keep is distinct from World completion')
            capture('06-kept-world')
            first_cp=cp;first_meshes=models[-1]
            jobs_before=len(state()['project']['jobs'])
            click('.world-canvas-actions [data-action="browse-assets"]')
            click('[data-action="browser-location"][data-location="production"]')
            expect(page.locator('.browser-asset')).to_have_count(1)
            expect(page.locator('.browser-results')).to_contain_text('In this scene')
            capture('06a-production-library')
            click('[data-action="browser-location"][data-location="library"]')
            click('[data-action="browser-tab"][data-tab="sources"]')
            expect(page.locator('.browser-results')).to_contain_text('Local · needs preparation')
            row=page.locator('[data-item-id="'+session['secondSourceId']+'"]')
            row.get_by_role('button',name='Details',exact=True).click();idle()
            click('[data-action="source-prepare-form"]')
            expect(page.locator('#prepare-confirm')).not_to_be_checked()
            expect(page.locator('#prepare-license')).to_have_value('')
            before_prepare=digest(session['projectManifest'])
            capture('06a-preparation-rights')
            # Cancelled evidence form never reaches preparation or catalog intake.
            click('#dialog [data-action="close"]')
            assert digest(session['projectManifest'])==before_prepare
            assert len(api('workbench/catalog?projectId='+session['projectId'])['items'])==1
            row.get_by_role('button',name='Details',exact=True).click();idle()
            click('[data-action="source-prepare-form"]')
            page.locator('#prepare-source-url').fill('https://example.invalid/generated-second-fixture')
            page.locator('#prepare-author').fill('Synthetic fixture generator')
            page.locator('#prepare-license').select_option('CC0-1.0')
            page.locator('#prepare-license-url').fill('https://example.invalid/synthetic-license')
            page.locator('#prepare-confirm').check()
            click('[data-action="source-prepare"]');finish_job()
            prepared=next(r for r in state()['runs'] if r['action']=='source-prepare')
            assert prepared['state']=='SUCCEEDED'
            session['secondAssetId']=prepared['assetId']
            assert session['secondAssetId']!=session['assetId']
            assert len(api('workbench/catalog?projectId='+session['projectId'])['items'])==2
            source=api('workbench/source-detail?projectId='+session['projectId']+'&sourceId='+session['secondSourceId'])
            assert source['prepared']['assetId']==session['secondAssetId']
            report['checks'].append('Production/library states; cancelled rights form writes nothing; real package inspection and intake create a reusable catalog version without importing or approving')
            assert len(scene()['catalog'])==2 and scene()['current']==cp['id'] and not scene()['candidate']
            assert len(state()['project']['jobs'])==jobs_before,'Selection must not run an import'
            idle()
            expect(page.locator('[data-world-state]')).to_have_attribute('data-world-state','rights')
            expect(page.get_by_role('button',name='Add assets',exact=True)).to_be_enabled()
            click('.world-ingredient-list > summary')
            expect(page.locator('.world-ingredient-list')).to_contain_text('1 in saved world · 1 to add')
            expect(page.locator('.world-ingredient[data-id="'+session['secondAssetId']+'"]')).to_contain_text('Selected · not imported')
            capture('06b-two-selected-one-imported')
            click('.projectbar [data-action="refresh"]')
            expect(page.locator('.world-ingredient-list')).to_have_attribute('open','')
            assert len(state()['project']['jobs'])==jobs_before
            click('[data-action="source-review"]');click('[data-action="source-confirm"]')
            click('.world-next [data-action="catalog-detail"]');ready('#dialog [data-viewer-host]')
            expect(page.locator('#dialog')).to_contain_text('Single-asset preview')
            click('[data-action="catalog-import"]');combined=finish_job()
            cp=next(c for c in combined['checkpoints'] if c['id']==combined['candidate'])
            ids={o.get('asset_id') for o in cp['audit']['objects']}
            assert {session['assetId'],session['secondAssetId']}<=ids and cp['parent']==first_cp['id']
            ready('[data-scene-viewer]')
            assert first_meshes<=models[-1] and 'SecondSyntheticTriangle' in models[-1] and len(models[-1])>=2
            expect(page.locator('.world-ingredient-list')).to_contain_text('2 in this change')
            capture('06c-combined-world-candidate')
            click('[data-action="keep-building"]')
            expect(page.locator('.world-ingredient-list')).to_contain_text('2 in saved world')
            assert digest(Path(session['projectManifest']).parent/first_cp['path'])==first_cp['sha256']
            assert digest(session['secondInput'])==session['secondOriginal']['sha256']
            assert digest(session['secondBinary'])==session['secondBinaryOriginal']['sha256']
            report['checks'].append('Two distinct selected assets do not auto-import; reviewed second import preserves first world and serves both real meshes together')
            report['combined_meshes']=sorted(models[-1]);report['first_checkpoint_id']=first_cp['id']
            click('.world-ingredient-list > summary')
            click('.world-inspection > summary');click('.rendered-evidence > summary')
            click('.projectbar [data-action="refresh"]')
            expect(page.locator('.world-inspection')).to_have_attribute('open','')
            expect(page.locator('.rendered-evidence')).to_have_attribute('open','')
            click('.world-inspection > summary')
            report['checks'].append('Inspection and rendered-still panels retain their open state across authenticated refresh')
            for width,height in [(1024,768),(640,900)]:
                page.set_viewport_size({'width':width,'height':height});capture('07-layout-'+str(width))
                expect(page.get_by_role('button',name='Continue to Action',exact=True)).to_be_visible()
                if width==1024:
                    box=page.locator('.world-next .primary').bounding_box()
                    assert box['y']+box['height']<=height,'Primary action fell below the desktop viewport'
            primary=page.locator('.world-next .primary');primary.hover()
            assert primary.evaluate("e=>getComputedStyle(e).backgroundColor")=='rgb(197, 212, 255)','Primary hover must retain light background and readable contrast'
            page.set_viewport_size({'width':1440,'height':960})
            click('.world-canvas-actions [data-action="browse-assets"]');click('[data-action="browser-tab"][data-tab="catalog"]');click('[data-action="catalog-preview-detail"][data-id="'+session['assetId']+'"]');ready('#dialog [data-viewer-host]')
            expect(page.get_by_role('button',name='Add another copy',exact=True)).to_be_visible()
            click('[data-action="catalog-import"]');second=finish_job();second_cp=next(c for c in second['checkpoints'] if c['id']==second['candidate'])
            assert second_cp['id']!=cp['id'];click('[data-action="discard"]')
            assert scene()['current']==cp['id'] and not scene()['candidate']
            for saved in (cp,second_cp):assert digest(Path(session['projectManifest']).parent/saved['path'])==saved['sha256']
            report['checks'].append('Explicit second-copy import; discard retains previous world and both immutable checkpoint files')
            click('[data-action="approve"]');assert scene()['stage']=='action'
            expect(page.get_by_role('heading',name='Performers & action',exact=True)).to_be_visible()
            capture('08-continue-action')
            click('[data-action="stage"][data-stage="world"]');page.reload();idle()
            expect(page.locator('[data-world-state]')).to_have_attribute('data-world-state','ready')
            assert scene()['current']==cp['id'];assert digest(session['input'])==session['original']['sha256']
            assert not report['errors'],report['errors']
            report['checks'].extend(['Scripted completion opens existing Action flow; reload retains saved context','Source bytes and historical checkpoints preserved','Responsive layouts have no horizontal overflow; no browser errors'])
            report.update(status='PASS',checkpoint_id=cp['id'],checkpoint_sha256=cp['sha256'],discarded_checkpoint_id=second_cp['id'],browser=browser.version)
        except BaseException as error:
            report.update(status='FAIL',error=str(error).replace(session['token'],'[REDACTED]'))
            page.screenshot(path=str(out/'failure.png'),animations='disabled');raise
        finally:
            (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');context.close();browser.close()
    print(json.dumps({'status':report['status'],'checks':report['checks']}))

if __name__=='__main__':main()
