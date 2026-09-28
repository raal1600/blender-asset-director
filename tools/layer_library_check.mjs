/** Metadata-only library routes; no Blender execution or human approval claimed. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {fixture} from './catalog_browser_fixture.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,module,chrome]=process.argv.slice(2);
assert([out,module,chrome].every(x=>x&&path.isAbsolute(x))&&!await exists(out));await fs.mkdir(out,{recursive:true});
const report={kind:'synthetic-layer-library-routes',checks:[],errors:[],blender:'NOT_TESTED',human_review:'NOT_TESTED'};let app,browser,page;
try{
 const root=path.join(out,'Studio');app=await fixture(root);const session=await json(path.join(root,'browser-session.json'));
 const before=await fileHash(path.join(root,'Database/Registry/sources.json'));
 const {chromium}=await import(pathToFileURL(module).href);browser=await chromium.launch({executablePath:chrome});page=await browser.newPage({viewport:{width:1280,height:900},serviceWorkers:'block'});
 page.on('pageerror',e=>report.errors.push(e.message.replaceAll(app.token,'[REDACTED]')));
 const idle=()=>page.waitForFunction(()=>!document.body.classList.contains('working'));
 const click=async selector=>{await page.locator(selector).click();await idle();assert.equal(await page.locator('#notice').isVisible(),false);};
 await page.goto(app.origin+'/workbench#'+app.token);await idle();await click('[data-action="project"][data-id="'+session.projectId+'"]');
 const projectBefore=await app.store.get(session.projectId);
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
 assert.deepEqual(await fileHash(path.join(root,'Database/Registry/sources.json')),before);assert.deepEqual(await app.store.get(session.projectId),projectBefore);assert.deepEqual(report.errors,[]);report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;await page?.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify(report));}
