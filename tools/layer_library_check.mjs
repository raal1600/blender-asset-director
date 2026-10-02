/** Metadata-only library routes; no Blender execution or human approval claimed. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {fixture} from './catalog_browser_fixture.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,module,chrome]=process.argv.slice(2);
assert([out,module].every(x=>x&&path.isAbsolute(x))&&(!chrome||path.isAbsolute(chrome))&&!await exists(out));await fs.mkdir(out,{recursive:true});
const report={kind:'synthetic-layer-library-routes',checks:[],errors:[],blender:'NOT_TESTED',human_review:'NOT_TESTED'};let app,browser,page;
try{
 const root=path.join(out,'Studio');app=await fixture(root);const session=await json(path.join(root,'browser-session.json'));
 const before=await fileHash(path.join(root,'Database/Registry/sources.json'));
 const {chromium}=await import(pathToFileURL(module).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 page.on('pageerror',e=>report.errors.push(e.message.replaceAll(app.token,'[REDACTED]')));
 const idle=()=>page.waitForFunction(()=>!document.body.classList.contains('working'));
 const click=async selector=>{await page.locator(selector).click();await idle();assert.equal(await page.locator('#notice').isVisible(),false);};
 await page.goto(app.origin+'/workbench#'+app.token);await idle();await click('[data-action="project"][data-id="'+session.projectId+'"]');
 const projectBefore=await app.store.get(session.projectId);
 const writes=[];page.on('request',r=>{if(r.method()!=='GET'&&r.method()!=='HEAD')writes.push(new URL(r.url()).pathname);});
 // Visibility alone misses a menu obscured by the sticky Save bar. Use normal
 // pointer hit-testing and keyboard navigation, never force or DOM dispatch.
 for(const [width,height] of [[1280,900],[1024,768],[390,844]]){
  await page.setViewportSize({width,height});
  await click('.world-more > summary');await page.screenshot({path:path.join(out,'world-menu-'+width+'.png')});
  await page.locator('.world-menu [data-action="new-scene"]').click({timeout:5000});await idle();
  assert.equal(await page.locator('#detail-title').innerText(),'Create a scene');assert.equal(await page.locator('#new-name').inputValue(),'');
  assert.equal(await page.locator('.world-more').getAttribute('open'),null,'Selecting an item dismisses More before opening its dialog');
  await click('#dialog [data-action="close"]');
  await click('.world-more > summary');
  await page.locator('.world-menu [data-action="history"]').click({timeout:5000});await idle();
  assert.equal(await page.locator('#detail-title').innerText(),'Scene checkpoints');assert.match(await page.locator('#dialog').innerText(),/No saved checkpoints yet/);
  await page.keyboard.press('Escape');assert.equal(await page.locator('#dialog').isVisible(),false);
  await page.locator('.world-more > summary').focus();
  await page.keyboard.press('Enter');await page.keyboard.press('Tab');
  assert.equal(await page.locator('.world-menu [data-action="new-scene"]').evaluate(e=>e===document.activeElement),true);
  await page.keyboard.press('Enter');assert.equal(await page.locator('#detail-title').innerText(),'Create a scene');
  await page.keyboard.press('Escape');assert.equal(await page.locator('#dialog').isVisible(),false);
  assert.equal(await page.locator('.world-more').getAttribute('open'),null);
  await click('.world-more > summary');await page.keyboard.press('Escape');
  assert.equal(await page.locator('.world-more').getAttribute('open'),null,'Escape dismisses the menu');
  assert.equal(await page.locator('.world-more > summary').evaluate(e=>e===document.activeElement),true);
  await click('.world-more > summary');await click('.titlebar strong');
  assert.equal(await page.locator('.world-more').getAttribute('open'),null,'Outside pointer dismisses without triggering an action');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  report.checks.push('World '+width+': real pointer and keyboard menu actions, action/Escape/outside dismissal and focus return; no approval');
 }
 await page.setViewportSize({width:1280,height:900});
 // The guided native journey returns from this nested dialog to Save. No menu
 // may remain over that button after the modal/library path has completed.
 await click('.world-more > summary');await click('[data-action="world-ingredients"]');
 await click('#dialog [data-action="browse-assets"].primary');await page.keyboard.press('Escape');await idle();
 assert.equal(await page.locator('.world-more').getAttribute('open'),null);
 await page.locator('.world-savebar [role="status"]').click({timeout:5000});
 report.checks.push('Ingredients -> library -> Escape leaves the Save bar unobstructed');
 await click('[data-action="browse-assets"]:visible >> nth=0');
 for(const [width,height] of [[1280,900],[1024,768],[390,844]]){
  await page.setViewportSize({width,height});await click('.browser-filters > summary');
  await page.screenshot({path:path.join(out,'world-filters-'+width+'.png')});
  for(const selector of ['#browser-activity','#browser-kind','#browser-scope','[data-layout="grid"]','[data-layout="list"]']){
   await page.locator(selector).click({trial:true,timeout:5000});
  }
  await click('[data-layout="list"]');assert.match(await page.locator('.browser-results').getAttribute('class'),/list/);
  assert.equal(await page.locator('.browser-filters').getAttribute('open'),null);
  await click('.browser-filters > summary');await click('[data-layout="grid"]');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  report.checks.push('World library '+width+': filters receive pointer hits above Save; actual layout changes; no data mutation');
 }
 await click('[data-action="browser-close"]');await page.setViewportSize({width:1280,height:900});
 for(const [sceneId,activity,catalogCount,sourceCount,kinds,label] of [
  [session.sceneId,'world',4000,6666,['model','pack'],null],
  [session.motionSceneId,'action',2000,3334,['animation'],'Find motion in library'],
  [session.lookSceneId,'light',4000,0,['material','hdri'],'Find materials / HDRIs']]){
  await page.locator('#scene-picker').selectOption(sceneId);await idle();
  if(label){await click('.world-more > summary');assert.equal(await page.getByRole('button',{name:label,exact:true}).isVisible(),true);}
  await click('[data-action="browse-assets"]:visible >> nth=0');assert.equal(await page.locator('#browser-activity').inputValue(),activity);
  assert.equal(await page.locator('.browser-asset').count(),24);assert((await page.locator('.browser-asset').evaluateAll(nodes=>nodes.map(n=>n.dataset.kind))).every(k=>kinds.includes(k)));
  assert.match(await page.locator('.browser-footer [role="status"]').innerText(),new RegExp('of '+catalogCount+' assets'));
  assert.equal(await page.locator('[data-location="production"] .location-count').innerText(),'(0)');
  await page.screenshot({path:path.join(out,activity+'-catalog.png')});await click('[data-action="browser-tab"][data-tab="sources"]');
  assert.equal(await page.locator('.browser-asset').count(),Math.min(sourceCount,24));assert.match(await page.locator('.browser-footer [role="status"]').innerText(),new RegExp('of '+sourceCount+' packages'));
  await click('[data-action="browser-close"]');report.checks.push(activity+': visible scoped route, exact paginated catalog/package counts and disjoint production/library');
 }
 await page.setViewportSize({width:390,height:844});if(await page.locator('.world-more').getAttribute('open')===null)await click('.world-more > summary');await click('[data-action="browse-assets"]:visible >> nth=0');
 await page.screenshot({path:path.join(out,'light-mobile.png')});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 assert.deepEqual(await fileHash(path.join(root,'Database/Registry/sources.json')),before);assert.deepEqual(await app.store.get(session.projectId),projectBefore);assert.deepEqual(writes,[]);assert.deepEqual(report.errors,[]);report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;await page?.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify(report));}
