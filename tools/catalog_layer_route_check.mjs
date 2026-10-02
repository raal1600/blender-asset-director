/** Metadata-only catalog routes. Not native execution or lifecycle acceptance. */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {fixture} from './catalog_browser_fixture.mjs';
import {exists,fileHash,json,writeJson} from '../launcher/lib/storage.mjs';
const [out,playwright,chrome]=process.argv.slice(2);
assert(path.isAbsolute(out)&&path.isAbsolute(playwright)&&!await exists(out));await fs.mkdir(out,{recursive:true});
let app,browser,page;const report={scope:'SYNTHETIC_CATALOG_ROUTES',checks:[],errors:[],native_execution:'NOT_TESTED'};
try{
 app=await fixture(path.join(out,'Studio'));const session=await json(path.join(out,'Studio/browser-session.json'));
 const registry=path.join(out,'Studio/Database/Registry/sources.json'),original=await fileHash(registry);
 const {chromium}=await import(pathToFileURL(playwright).href);browser=await chromium.launch(chrome?{executablePath:chrome}:{channel:'chrome'});
 page=await browser.newPage({viewport:{width:1280,height:800},serviceWorkers:'block'});page.setDefaultTimeout(15000);
 page.on('pageerror',e=>report.errors.push(e.message.replaceAll(app.token,'[REDACTED]')));
 const idle=async()=>{await page.waitForFunction(()=>!document.body.classList.contains('working'));assert.equal(await page.locator('#notice').isVisible(),false);};
 await page.goto(app.origin+'/workbench#'+app.token);await idle();await page.locator('[data-action="project"][data-id="'+session.projectId+'"]').click();await idle();
 for(const [id,activity,total,kinds] of [[session.sceneId,'world',4000,['model','pack']],[session.motionSceneId,'action',2000,['animation']],[session.lookSceneId,'light',4000,['material','hdri']]]){
  await page.locator('body').ariaSnapshot();
  if(await page.locator('#scene-picker').isVisible())await page.locator('#scene-picker').selectOption(id);
  else await page.locator('[data-action="scene"][data-id="'+id+'"]').click();await idle();
  if(activity==='action'){await page.locator('.world-more > summary').click();assert.equal(await page.getByRole('button',{name:'Find motion in library',exact:true}).isVisible(),true);}
  await page.locator('[data-action="browse-assets"]:visible').first().click();await idle();
  assert.equal(await page.locator('#browser-activity').inputValue(),activity);assert.equal(await page.locator('.browser-asset').count(),24);
  assert((await page.locator('.browser-asset').evaluateAll(rows=>rows.map(r=>r.dataset.kind))).every(k=>kinds.includes(k)));
  assert.match(await page.locator('.browser-footer [role="status"]').innerText(),new RegExp('of '+total+' assets'));
  await page.screenshot({path:path.join(out,activity+'.png')});
  await page.locator('[data-action="browser-close"]').click();await idle();
  assert.equal(await page.locator('[data-action="browse-assets"]').first().evaluate(e=>e===document.activeElement),true);
  report.checks.push(activity+': real visible library entry, activity filter, 24-card bound and focus return');
 }
 assert.deepEqual(await fileHash(registry),original);assert.deepEqual(report.errors,[]);report.status='PASS';
}catch(error){report.status='FAIL';report.error=String(error).replaceAll(app?.token||'never-match-token','[REDACTED]');process.exitCode=1;await page?.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});}
finally{await browser?.close();if(app){app.server.closeAllConnections();await new Promise(resolve=>app.server.close(resolve));}await writeJson(path.join(out,'RESULTS.json'),report);console.log(JSON.stringify({status:report.status,checks:report.checks.length,error:report.error}));}
