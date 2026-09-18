/** Only fresh, identified task observations may be described as active editing. */
export function taskObservation(status,taskId,at=Date.now()) {
  if(!status||status.taskId!==taskId)return {kind:'waiting',focus:false,message:'Waiting for the dedicated Blender task. No live connection is claimed.'};
  if(status.state==='FAILED')return {kind:'failed',focus:false,message:'Blender could not prepare this task. '+(status.message||'')};
  const age=at/1000-status.observed_at;
  if(!Number.isFinite(age)||age< -5||age>10)return {kind:'unavailable',focus:false,message:'Blender status is unavailable or stale. Your files are preserved; inspect the task before continuing.'};
  if(status.checkpoint_available)return {kind:'saved',focus:false,message:'A checkpoint is saved. Collect it here to review. Later Blender edits are not part of that checkpoint.'};
  if(status.expected_file!==true)return {kind:'drift',focus:false,message:'Blender is no longer on this task working file. Return to that copy before checkpointing; unrelated files are preserved.'};
  return {kind:'editing',focus:status.gui_configured===true,message:status.dirty?'Editing in Blender · changes since its last save. Agent writes remain paused.':'The task working copy is open in Blender. Save a checkpoint when you are ready to review.'};
}
export function observationKey(status,taskId,at=Date.now()) {
  // Timestamps and viewport dimensions must not steal focus/restart a playing
  // preview by rebuilding the whole UI on every heartbeat. State changes do.
  return JSON.stringify([taskObservation(status,taskId,at),status?.workspace,status?.active_object]);
}
export function taskBanner(scene,status,esc,b) {
  const v=taskObservation(status,scene.task);
  return `<div class="note"><strong>${v.kind==='saved'?'Checkpoint ready to collect':'Blender · '+esc(scene.name)}</strong><p>${esc(v.message)}</p><p>Use <strong>Save checkpoint &amp; return</strong> in Blender's top bar (or F3). Saving is not approval.</p><div class="row">${b('Continue in Blender','focus-task',{},'',!v.focus)}${b('Collect saved checkpoint','collect',{},v.kind==='saved'?'primary':'')}${b('Inspect / recover task','recover',{run:scene.task})}</div></div>`;
}
