/** One physical clock, aligned source stitches. No candidate time warping. */
export function reviewLabel(candidate,scope={}){
 return candidate.checkpointId===scope.acceptedCheckpointId?'Accepted result':scope.acceptedCheckpointIds?.includes(candidate.checkpointId)?'Previously accepted result':'Unaccepted candidate';
}
export function comparisonMarkup(candidates,chosen,esc,scope={}){
 const others=candidates.filter(c=>c.id!==chosen.id),before=others.at(-1)||chosen;
 const option=c=>'<option value="'+esc(c.id)+'">'+esc(c.id.slice(0,12))+' · '+esc(reviewLabel(c,scope))+' · '+esc(c.validation?.status||'Unvalidated')+'</option>';
 return '<p>Both views use the labeled baked checkpoint identified below. Playback uses one full-speed physical clock, with source stitches at 0 seconds. Target stitches may differ. Previewing a candidate does not accept it.</p>'+
 '<div class="transition-compare-grid"><section><label>View A<select data-compare-choice="a">'+[before,...candidates.filter(c=>c.id!==before.id)].map(option).join('')+'</select></label><p data-compare-identity="a"></p><div class="viewer-3d" data-compare-view="a"></div></section><section><label>View B<select data-compare-choice="b">'+[chosen,...candidates.filter(c=>c.id!==chosen.id)].map(option).join('')+'</select></label><p data-compare-identity="b"></p><div class="viewer-3d" data-compare-view="b"></div></section></div>'+
 '<div class="transition-compare-controls"><button type="button" data-compare-play>Play both at full speed</button><button type="button" data-compare-edge="0">Source stitch</button><button type="button" data-compare-edge="a">A target stitch</button><button type="button" data-compare-edge="b">B target stitch</button><label>Seconds from source stitch<input type="range" data-compare-time min="-0.5" max="3" step="0.001" value="0"></label><output data-compare-clock>0.000 s</output></div>';
}
export function openComparison(host,candidates,startViewer,scope={}){
 let disposed=false,raf=0,playing=false,origin=0,elapsed=0;
 const views={},current={},records={},time=host.querySelector('[data-compare-time]');
 const edge=c=>c?.transitions?.find(j=>j.provider==='motion-bricks.cpp')||null;
 const duration=side=>{const join=edge(current[side]);return join&&records[side]?(join.end-join.start)/records[side].playback.fps:0;};
 function seek(seconds){elapsed=seconds;time.value=String(seconds);host.querySelector('[data-compare-clock]').textContent=seconds.toFixed(3)+' s';for(const side of ['a','b']){const join=edge(current[side]),r=records[side];if(join&&r)views[side]?.seekFrameExact(join.start+seconds*r.playback.fps);}}
 function stop(){playing=false;cancelAnimationFrame(raf);host.querySelector('[data-compare-play]').textContent='Play both at full speed';}
 async function select(side){stop();views[side]?.dispose();const id=host.querySelector('[data-compare-choice="'+side+'"]').value,c=candidates.find(c=>c.id===id);current[side]=c;delete records[side];
  const viewer=startViewer(host.querySelector('[data-compare-view="'+side+'"]'),{kind:'checkpoint',id:c.checkpointId},{editable:false,focusPerformer:edge(c)?.performer});views[side]=viewer;
  const r=await viewer.ready;if(disposed||views[side]!==viewer||!r)return;records[side]=r;
  const join=edge(c);host.querySelector('[data-compare-identity="'+side+'"]').textContent=reviewLabel(c,scope)+' · baked '+c.sha256.slice(0,16)+' · '+(join?'bridge '+duration(side).toFixed(3)+' s; target stitch +'+duration(side).toFixed(3)+' s':'No generated stitch in this candidate');
  time.max=String(Math.max(duration('a'),duration('b'))+.5);seek(elapsed);viewer.framePerformer?.();
 }
 const change=e=>{if(e.target.dataset.compareChoice)void select(e.target.dataset.compareChoice);};
 const input=e=>{if(e.target===time){stop();seek(Number(time.value));}};
 const click=e=>{if(e.target.hasAttribute('data-compare-edge')){stop();const value=e.target.dataset.compareEdge;seek(value==='0'?0:duration(value));}
  if(e.target.hasAttribute('data-compare-play')){if(playing){stop();return;}if(!records.a||!records.b)return;playing=true;origin=performance.now()-elapsed*1000;e.target.textContent='Pause both';const tick=now=>{if(disposed||!playing)return;const seconds=(now-origin)/1000;if(seconds>Number(time.max)){stop();return;}seek(seconds);raf=requestAnimationFrame(tick);};raf=requestAnimationFrame(tick);}};
 host.addEventListener('change',change);host.addEventListener('input',input);host.addEventListener('click',click);
 // Existing converter serialization bounds preparation; views use separate leases.
 void select('a').then(()=>disposed?null:select('b'));
 return {dispose(){disposed=true;stop();for(const v of Object.values(views))v.dispose();host.removeEventListener('change',change);host.removeEventListener('input',input);host.removeEventListener('click',click);}};
}
