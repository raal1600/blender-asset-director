/** Additive scene domain. Project schema 1 and the legacy scene pointer remain valid. */
import {assert, relativeName} from './storage.mjs';
export const stages = [
  {id:'world', label:'Assemble world', short:'World', role:'Production design'},
  {id:'action', label:'Stage action', short:'Action', role:'Performance'},
  {id:'shots', label:'Capture shots', short:'Shots', role:'Cinematography'},
  {id:'light', label:'Light the scene', short:'Light', role:'Lighting / look'},
  {id:'render', label:'Render & review', short:'Render', role:'Rendering'}
];
export const validId = (value, prefix) => typeof value === 'string' && new RegExp('^'+prefix+'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$').test(value);
export const validHash = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
export const stageIndex = id => stages.findIndex(s => s.id === id);
export const initialWorkbench = () => ({schema:1,scenes:[],film:{clips:[],cuts:[]}});
export function validateWorkbench(w) {
  if(w === undefined) return;
  assert(w && w.schema === 1 && Array.isArray(w.scenes) && w.scenes.length <= 200,'Unsupported workbench manifest.');
  const pins=w.catalogPins||[];
  assert(Array.isArray(pins)&&pins.length<=2000&&new Set(pins.map(p=>p.id)).size===pins.length,'Invalid catalog pins.');
  for(const pin of pins){
    assert(/^a_[a-f0-9]{24}$/.test(pin.id)&&validHash(pin.version)&&typeof pin.title==='string'&&pin.title.length<=2048&&Array.isArray(pin.files)&&pin.files.length<=10000,'Invalid catalog pin.');
    for(const file of pin.files){relativeName(file.path);assert(validHash(file.sha256)&&Number.isSafeInteger(file.size)&&file.size>=0,'Invalid pinned catalog file.');}
  }
  const ids = new Set();
  for(const s of w.scenes) {
    assert(validId(s.id,'sc_') && !ids.has(s.id),'Invalid or duplicate scene ID.'); ids.add(s.id);
    assert(typeof s.name === 'string' && s.name.trim().length >= 2 && s.name.length <= 100,'Invalid scene name.');
    assert(stageIndex(s.stage) >= 0 && Array.isArray(s.sources) && s.sources.every(x=>validId(x,'src_')),'Invalid scene activity or sources.');
    assert(Array.isArray(s.checkpoints) && Array.isArray(s.renders) && s.completed && typeof s.completed === 'object','Invalid scene state.');
    for(const [key,prefix] of [['task','task_'],['run','run_']])assert(s[key]==null||validId(s[key],prefix),'Invalid active operation.');
    assert(new Set(s.sources).size===s.sources.length,'Duplicate scene source.');
    assert(s.catalog===undefined||Array.isArray(s.catalog)&&new Set(s.catalog).size===s.catalog.length&&s.catalog.every(id=>pins.some(p=>p.id===id)),'Unknown or duplicate catalog source.');
    assert(!s.selectedMotion||(s.catalog||[]).includes(s.selectedMotion)&&pins.some(a=>a.id===s.selectedMotion&&a.kind==='animation'),'Unknown selected motion.');
    const cp = new Set();
    for(const c of s.checkpoints) {
      assert(validId(c.id,'cp_') && !cp.has(c.id) && validHash(c.sha256),'Invalid checkpoint identity.'); cp.add(c.id);
      assert(Number.isSafeInteger(c.size)&&c.size>=7&&stageIndex(c.stage)>=0,'Invalid checkpoint metadata.');
      relativeName(c.path); assert(/^Scenes\/[^/]+\.blend$/.test(c.path),'Checkpoint must stay in project Scenes.');
    }
    assert((!s.current || cp.has(s.current)) && (!s.candidate || cp.has(s.candidate)),'Unknown selected checkpoint.');
    assert(Object.entries(s.completed).every(([stage,id])=>stageIndex(stage)>=0&&cp.has(id)),'Unknown activity checkpoint.');
    if(s.shots!==undefined){
      assert(Array.isArray(s.shots)&&s.shots.length<=200&&new Set(s.shots.map(x=>x.id)).size===s.shots.length,'Invalid shot list.');
      for(const shot of s.shots)assert(validId(shot.id,'shot_')&&Number.isInteger(shot.revision)&&shot.revision>=1&&typeof shot.name==='string'&&shot.name.trim().length>0&&shot.name.length<=100&&!/[\r\n\0]/.test(shot.name)&&typeof shot.camera==='string'&&shot.camera.length>0&&shot.camera.length<=255&&!/[\r\n\0]/.test(shot.camera)&&Number.isInteger(shot.start)&&Number.isInteger(shot.end)&&shot.start>=-100000&&shot.end<=100000&&shot.end>=shot.start&&shot.end-shot.start<360&&(!shot.checkpointId||cp.has(shot.checkpointId)),'Invalid shot record.');
      assert(!s.selectedShot||s.shots.some(x=>x.id===s.selectedShot),'Unknown selected shot.');
    }
    assert(s.shots!==undefined||!s.selectedShot,'Unknown selected shot.');
    for(const r of s.renders) {
      assert(validId(r.id,'rnd_') && /^j_[a-f0-9]{24}$/.test(r.jobId) && cp.has(r.checkpointId),'Invalid scene render.');
      assert(!r.shotId||validId(r.shotId,'shot_')&&(s.shots||[]).some(x=>x.id===r.shotId)&&Number.isInteger(r.shotRevision)&&r.shotRevision>=1,'Invalid rendered shot reference.');
    }
  }
  assert(w.film && Array.isArray(w.film.clips) && w.film.clips.length <= 32 && Array.isArray(w.film.cuts),'Invalid film state.');
  assert(new Set(w.film.cuts.map(c=>c.id)).size===w.film.cuts.length&&w.film.cuts.every(c=>validId(c.id,'cut_')&&Array.isArray(c.refs)&&typeof c.approved==='boolean'),'Invalid cut history.');
  for(const clip of w.film.clips) {
    const s=w.scenes.find(s=>s.id===clip.sceneId);
    assert(s && s.renders.some(r=>r.id===clip.renderId),'Unknown film input.');
  }
}
export function checkpointFor(scene, id=scene.current) {return scene.checkpoints.find(c=>c.id===id) || null;}
export function canEnter(scene, stage) {
  const n=stageIndex(stage);
  return n===0 || n>0 && stages.slice(0,n).every(s=>scene.completed[s.id]);
}
export function approveCheckpoint(scene, stage, checkpointId,finish=true) {
  assert(stageIndex(stage)>=0 && canEnter(scene,stage),'Complete the preceding activity before approval.',409);
  assert(checkpointFor(scene,checkpointId),'Unknown checkpoint.');
  if(scene.current !== checkpointId) {
    for(const key of Object.keys(scene.completed)) if(stageIndex(key)>=stageIndex(stage)) delete scene.completed[key];
    scene.readiness=null; scene.preview=null;
  }
  scene.current=checkpointId; scene.candidate=null;
  if(finish){scene.completed[stage]=checkpointId;scene.stage=stages[Math.min(stageIndex(stage)+1,stages.length-1)].id;}
  else scene.stage=stage;
}
