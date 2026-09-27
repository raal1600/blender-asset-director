/** Real Chrome -> authenticated API -> Blender -> stage-specific WebGL.
 * Accepts only generated embedded-viewer fixtures. No native-window control.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';

const [fixture,evidence,playwrightModule,chrome]=process.argv.slice(2);
assert(fixture&&evidence&&playwrightModule&&chrome,'Expected fixture, new evidence, existing Playwright module and Chrome');
const session=JSON.parse(await fs.readFile(path.join(fixture,'browser-session.json'),'utf8'));
assert.equal(session.fixture,'synthetic-embedded-viewer');
assert.equal(path.resolve(session.root),path.resolve(fixture));
await fs.mkdir(evidence);
const sha=async file=>createHash('sha256').update(await fs.readFile(file)).digest('hex');
const guarded=[session.projectManifest,session.actionManifest,session.catalog,...session.sourceFiles.map(f=>f.path)];
const before=await Promise.all(guarded.map(sha));
const report={status:'RUNNING',story:'World static view and Action playback through actual saved-source conversion',checks:[],errors:[],requests:[],not_tested:['native Blender UI','human review','live installation']};
const {chromium}=await import(pathToFileURL(playwrightModule).href);
const browser=await chromium.launch({executablePath:chrome,headless:true,chromiumSandbox:true});
const context=await browser.newContext({viewport:{width:1440,height:960},serviceWorkers:'block'});
const page=await context.newPage();page.setDefaultTimeout(25000);
const safe=value=>String(value).replaceAll(session.token,'[REDACTED]');
page.on('pageerror',e=>report.errors.push(safe(e.message)));
page.on('console',m=>{if(m.type()==='error')report.errors.push(safe(m.text()));});
const models=[],records=[],pending=[];
page.on('response',response=>{
  const url=new URL(response.url());
  if(url.origin!==session.origin)return;
  report.requests.push({path:url.pathname,status:response.status(),method:response.request().method()});
  if(url.pathname==='/api/workbench/viewer-prepare'&&response.ok())pending.push(response.json().then(value=>records.push(value)));
  if(url.pathname==='/api/workbench/viewer-model'&&response.ok())pending.push(response.body().then(raw=>{
    assert.equal(raw.toString('ascii',0,4),'glTF');
    const doc=JSON.parse(raw.toString('utf8',20,20+raw.readUInt32LE(12)));models.push(doc);
  }));
});
const external=[];page.on('request',r=>{if(/^https?:/.test(r.url())&&!r.url().startsWith(session.origin+'/'))external.push(new URL(r.url()).origin);});
page.on('dialog',d=>d.dismiss());
async function idle(){await page.waitForFunction(()=>!document.body.classList.contains('working'));assert.equal(await page.locator('#notice').isVisible(),false,await page.locator('#notice').innerText());}
async function click(selector){await page.locator('body').ariaSnapshot();await page.locator(selector).click();await idle();}
async function ready(){const host=page.locator('[data-scene-viewer]');await host.locator('canvas').waitFor({timeout:205000});await page.waitForFunction(()=>document.querySelector('[data-scene-viewer]')?.dataset.viewerState==='ready');return host;}
async function shot(name){await page.screenshot({path:path.join(evidence,name+'.png'),fullPage:true});await fs.writeFile(path.join(evidence,name+'.txt'),safe(await page.locator('body').ariaSnapshot()),{flag:'wx'});}
try{
  await page.goto(session.origin+'/workbench#'+session.token);await idle();
  await click('[data-action="project"][data-id="'+session.projectId+'"]');
  const world=await ready(),canvas=world.locator('canvas');
  assert.equal(await world.locator('.viewer-animation').isVisible(),false);
  assert.match(await world.locator('.viewer-disclaimer').innerText(),/Static World preview at frame/);
  await page.waitForTimeout(250);const still=await canvas.screenshot();await page.waitForTimeout(350);
  assert.deepEqual(await canvas.screenshot(),still,'World must not animate');
  const bounds=await canvas.boundingBox(),x=bounds.x+bounds.width*.5,y=bounds.y+bounds.height*.5;
  await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+100,y+40,{steps:12});await page.mouse.up();await page.waitForTimeout(350);
  assert.notDeepEqual(await canvas.screenshot(),still,'Orbit must change rendered geometry');
  await world.getByRole('button',{name:'Reset view',exact:true}).click();await shot('01-world-static');
  await Promise.all(pending);assert.equal(records[0].profile,'world-static-v1');assert.equal((models[0].animations||[]).length,0);
  report.checks.push('Static evaluated World GLB, no motion controls, real orbit pixels');
  await click('[data-action="picker"]');await click('[data-action="project"][data-id="'+session.actionProjectId+'"]');
  await click('[data-action="scene-viewer"]');const action=await ready(),moving=action.locator('canvas');
  assert.equal(await action.locator('.viewer-animation').isVisible(),true);
  const slider=action.locator('[data-view="time"]'),duration=Number(await slider.getAttribute('max'));assert(duration>0);
  await slider.fill('0');await slider.dispatchEvent('input');await page.waitForTimeout(100);const first=await moving.screenshot();
  const midpoint=Number((duration/2).toFixed(3));await slider.fill(String(midpoint));await slider.dispatchEvent('input');await page.waitForTimeout(100);
  assert.notDeepEqual(await moving.screenshot(),first,'Actual skin playback must move geometry');
  await action.getByRole('button',{name:'Play',exact:true}).click();await page.waitForTimeout(200);assert.notEqual(Number(await slider.inputValue()),midpoint);
  await action.getByRole('button',{name:'Pause',exact:true}).click();await shot('02-action-playback');
  await Promise.all(pending);assert.equal(records.at(-1).profile,'inspection-v1');assert(models.at(-1).animations.length>0);
  report.checks.push('Action scrubbing/play/pause changes real pixels and retains native animation');
  await click('[data-action="picker"]');await click('[data-action="project"][data-id="'+session.projectId+'"]');
  const cached=await ready();await Promise.all(pending);
  assert.equal(records.at(-1).profile,'world-static-v1');assert.equal(records.at(-1).cached,true);
  assert.equal(await cached.locator('.viewer-animation').isVisible(),false);
  await page.setViewportSize({width:390,height:844});await shot('03-world-mobile');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  report.checks.push('Returning to World reuses correct static cache; responsive 390px view');
  assert.deepEqual(await Promise.all(guarded.map(sha)),before,'Preview must not change projects, catalog or originals');
  assert.equal(report.errors.length,0,JSON.stringify(report.errors));assert.equal(external.length,0);
  assert(!report.requests.some(r=>r.status>=400));
  assert(!report.requests.some(r=>r.method==='POST'&&/\/(approve|run|task-open|catalog-select|catalog-job|keep-building|source-confirm)$/.test(r.path)));
  report.checks.push('Original/project/catalog hashes preserved; no external calls, hidden jobs or approvals');
  report.browser=browser.version();report.status='PASS';
}catch(error){report.status='FAIL';report.failure=safe(error.stack);await shot('failure');throw error;}
finally{await fs.writeFile(path.join(evidence,'report.json'),JSON.stringify(report,null,2),{flag:'wx'});await context.close();await browser.close();}
console.log(JSON.stringify({status:report.status,checks:report.checks,evidence}));
