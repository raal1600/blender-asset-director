'use strict';
const video = document.querySelector('#comparison');
const names = {cut:'Hard cut',nla:'Unaligned NLA',aligned:'Aligned NLA',director:'Director bridge'};
const colors = {cut:'#ed988d',nla:'#e6bc77',aligned:'#9cbddd',director:'#99ecc8'};
const $ = id => document.getElementById(id);
let measured;
document.querySelectorAll('[data-rate]').forEach(button => button.addEventListener('click', () => {
  video.playbackRate = Number(button.dataset.rate);
  document.querySelectorAll('[data-rate]').forEach(other => {const on = other === button;other.classList.toggle('selected',on);other.setAttribute('aria-pressed',String(on));});
}));
$('restart').addEventListener('click',()=>{video.currentTime=0; video.play().catch(()=>{});});
$('join').addEventListener('click',()=>{video.currentTime=Math.max(0,(measured?.methods.nla.transition_seconds[0]??0.62)-0.1); video.play().catch(()=>{});});
function plot(){
  if(!measured)return;
  const canvas=$('trajectory'), width=canvas.clientWidth,height=230,dpr=window.devicePixelRatio||1;
  canvas.width=Math.round(width*dpr);canvas.height=height*dpr;
  const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
  const l=42,r=14,t=16,b=30,w=width-l-r,h=height-t-b;
  const all=Object.values(measured.methods).flatMap(m=>m.anchor_positions.map(p=>p[0]));
  const max=Math.max(...all,1)*1.12,min=Math.min(...all,0)-.06;
  const x=seconds=>l+(seconds/measured.rendered_seconds)*w,y=value=>t+h-(value-min)/(max-min)*h;
  ctx.font='10px monospace';ctx.fillStyle='#9daebc';ctx.lineWidth=1;
  for(let i=0;i<=4;i++){const value=min+(max-min)*i/4;ctx.strokeStyle='#303b46';ctx.beginPath();ctx.moveTo(l,y(value));ctx.lineTo(l+w,y(value));ctx.stroke();ctx.fillText(value.toFixed(1),3,y(value)+3);}
  for(let s=0;s<=4;s++)ctx.fillText(s+'s',x(s)-4,height-6);
  const interval=measured.methods.director.transition_seconds;ctx.fillStyle='rgba(153,236,200,.07)';ctx.fillRect(x(interval[0]),t,x(interval[1])-x(interval[0]),h);
  for(const [key,method] of Object.entries(measured.methods)){
    ctx.strokeStyle=colors[key];ctx.lineWidth=key==='director'?2.7:1.7;ctx.beginPath();
    method.anchor_positions.forEach((p,i)=>{const px=x(i/measured.fps),py=y(p[0]);if(i)ctx.lineTo(px,py);else ctx.moveTo(px,py);});ctx.stroke();
  }
  if(Number.isFinite(video.currentTime)){ctx.strokeStyle='#f1f5f9';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x(video.currentTime),t);ctx.lineTo(x(video.currentTime),t+h);ctx.stroke();}
}
video.addEventListener('timeupdate',plot);window.addEventListener('resize',plot);
function fill(data){
  measured=data;
  $('gap').textContent=data.unaligned_gap_m.toFixed(3)+' m';
  $('bridge').textContent=Math.round(data.bridge_seconds*1000)+' ms';
  $('full-clip').textContent=data.source_seconds[1].toFixed(3)+' s';
  $('preserved').textContent=data.original_result_unchanged?'Unchanged':'Check failed';
  $('build-status').textContent=`Blender ${data.blender} · ${data.runtime} · Generated in GitHub Actions · Synthetic sequence fixture: ${data.fixture_status}`;
  $('build-source').href='https://github.com/raal1600/blender-asset-director/commit/'+data.commit;
  $('build-source').textContent='Source '+data.commit.slice(0,7);$('build-run').href=data.actions_run;
  for(const [key,title] of Object.entries(names)){
    const label=document.createElement('span'),swatch=document.createElement('i');swatch.style.background=colors[key];label.append(swatch,document.createTextNode(title));$('legend').append(label);
    const row=document.createElement('div');row.className='timeline-row';const name=document.createElement('span');name.textContent=title;const track=document.createElement('div');track.className='track';
    const overlap=key==='nla'||key==='aligned',bridge=key==='director';
    const phases=[[overlap?data.source_seconds[0]-data.bridge_seconds:data.source_seconds[0],'a','A']];
    if(overlap||bridge)phases.push([data.bridge_seconds,overlap?'overlap':'bridge',overlap?'Overlap':'Bridge']);
    phases.push([Math.max(.1,data.rendered_seconds-phases.reduce((s,p)=>s+p[0],0)),'b','B →']);
    phases.forEach(([seconds,kind,text])=>{const bar=document.createElement('span');bar.className='phase-'+kind;bar.style.width=String(seconds/data.rendered_seconds*100)+'%';bar.textContent=text;track.append(bar);});
    const duration=document.createElement('small');duration.textContent=(data.source_seconds.reduce((a,b)=>a+b,0)+(bridge?data.bridge_seconds:overlap?-data.bridge_seconds:0)).toFixed(2)+' s';duration.title='Full sequence duration, not the four-second viewing excerpt';row.append(name,track,duration);$('timelines').append(row);
  }plot();
}
fetch('./metrics.json').then(response=>{if(!response.ok)throw new Error('Metrics unavailable');return response.json();}).then(data=>{
  if(data.schema!=='asset-director.transition-showcase/1'||!data.synthetic||data.fixture_status!=='PASS')throw new Error('Unexpected evidence schema');fill(data);
}).catch(error=>{$('build-status').textContent='Build evidence could not be loaded. The video remains available; numerical results are not asserted.';console.error(error);});
