/** Read-only cut selection/playback context, distinct from the editable film arrangement. */
import {cutIsCurrent,renderIsCurrent} from './workbench-lineage.mjs';
export function filmViewing(){
 const selections=new Map(),times=new Map(),key=(project,cut)=>JSON.stringify([project,cut]);
 return {
  selected(project,workbench){const id=selections.get(project);return workbench.film.cuts.find(c=>c.id===id)||workbench.film.cuts.at(-1)||null;},
  select(project,workbench,id){if(!workbench.film.cuts.some(c=>c.id===id))throw Error('Choose a saved cut from this production.');selections.set(project,id);},
  followLatest(project){selections.delete(project);},
  remember(project,cut,time){if(project&&cut&&Number.isFinite(time)&&time>=0)times.set(key(project,cut),time);},
  time(project,cut){return times.get(key(project,cut))||0;}
 };
}
export function filmCutPicker(workbench,selected,esc){
 if(!selected)return '';
 return '<label class="film-cut-picker">Watch a saved cut<select id="film-cut">'+[...workbench.film.cuts].reverse().map((cut,i)=>'<option value="'+esc(cut.id)+'" '+(cut.id===selected.id?'selected':'')+'>'+esc((i===0?'Latest · ':'')+cut.id.slice(4,12)+' · '+(cutIsCurrent(workbench,cut)?cut.approved?'reviewed current arrangement':'current arrangement · needs review':'historical')+' · '+(cut.createdAt||'retained'))+'</option>').join('')+'</select></label><p class="muted">Choosing an old cut only changes playback. It never restores or replaces the working arrangement.</p>';
}
export function staleFilmInputs(workbench){
 return workbench.film.clips.filter(ref=>{
  const scene=workbench.scenes.find(s=>s.id===ref.sceneId),render=scene?.renders.find(r=>r.id===ref.renderId);
  return !render||!render.approved||!renderIsCurrent(scene,render);
 });
}
export function mediaIdentity(node){
 const d=node.dataset;return JSON.stringify([d.projectId||'',d.media||'',d.id||'',d.media==='render'?d.sceneId||'':'']);
}
