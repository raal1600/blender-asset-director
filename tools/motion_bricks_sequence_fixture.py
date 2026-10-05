"""Real provider/native-rig sequence regression from an explicit local manifest.

Requires actual Blender and the pinned MotionBricks model. No licensed assets
are redistributed. The input file is immutable; new fixture timelines and FPS
copies are created in a disposable worker. PASS covers continuity, clocks,
source preservation and persistence, not unauthored contacts or visual approval.
"""
import argparse
if not __debug__:raise RuntimeError("Optimized Python disables acceptance assertions")
import bpy,sys,os,json,math,traceback,time
from pathlib import Path
from mathutils import Vector
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'src'));sys.dont_write_bytecode=True
from asset_director import action_layer as layer,blender_ops as ops,native_motion_basis as basis,motion_bricks_retarget as ret,sequence_math as qm
from asset_director.core import atomic_json,digest,file_hash,DirectorError
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--manifest',type=Path);p.add_argument('--case');p.add_argument('--output',type=Path);p.add_argument('--verify',type=Path)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
def sample(obj,f):
 bpy.context.scene.frame_set(math.floor(f),subframe=f%1);bpy.context.view_layer.update();e=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
 return {p.name:{'p':list((e.matrix_world@p.matrix).translation),'q':list((e.matrix_world@p.matrix).to_quaternion())} for p in e.pose.bones}
def seam_metrics(obj,edge,fps):
 pelvis=ret.load_profile(obj)['roles']['pelvis'];h=fps/(24*64);left=[sample(obj,edge-j*h) for j in (1,2,3)];right=[sample(obj,edge+j*h) for j in (1,2,3)];rows=[]
 for n in obj.pose.bones.keys():
  l=[Vector(s[n]['p']) for s in left];r=[Vector(s[n]['p']) for s in right];lp=3*l[0]-3*l[1]+l[2];rp=3*r[0]-3*r[1]+r[2];lv=(2.5*l[0]-4*l[1]+1.5*l[2])*fps/h;rv=(-2.5*r[0]+4*r[1]-1.5*r[2])*fps/h
  lq=[s[n]['q'] for s in left];rq=[s[n]['q'] for s in right];z=[Vector(qm.qlog(qm.qmul(qm.inverse(lq[0]),q))) for q in lq+rq];ql=3*z[0]-3*z[1]+z[2];qr=3*z[3]-3*z[4]+z[5];wl=(2.5*z[0]-4*z[1]+1.5*z[2])*fps/h;wr=(-2.5*z[3]+4*z[4]-1.5*z[5])*fps/h
  rows.append({'bone':n,'position_m':(lp-rp).length,'orientation_deg':math.degrees((ql-qr).length),'root_velocity_m_s':(lv-rv).length,'angular_velocity_deg_s':math.degrees((wl-wr).length)})
 return {'frame':edge,**{k:(next(v[k] for v in rows if v['bone']==pelvis) if k=='root_velocity_m_s' else max(v[k] for v in rows)) for k in limits},'bones':rows}
if a.verify:
 row=json.loads(a.verify.read_text(encoding='utf-8'));assert row['status']=='PASS' and not row.get('expected_refusal')
 source=Path(row['result']);assert file_hash(source)==row['result_sha256']
 bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);rig=bpy.data.objects[row['rig']]
 from asset_director.action_timeline import load
 assert load(rig) and not rig.animation_data.action
 maximum_position=0.;maximum_angle=0.
 for expected in row['samples']:
  actual=sample(rig,expected['frame']);assert actual.keys()==expected['joints'].keys()
  for name,pose in expected['joints'].items():
   maximum_position=max(maximum_position,math.dist(actual[name]['p'],pose['p']))
   maximum_angle=max(maximum_angle,math.degrees(qm.norm(qm.qlog(qm.qmul(qm.inverse(pose['q']),actual[name]['q'])))))
 assert maximum_position<1e-5 and maximum_angle<.05,(maximum_position,maximum_angle)
 assert all(digest(layer.channels(bpy.data.actions[n]))==h for n,h in row['original_source_channels'].items())
 assert file_hash(source)==row['result_sha256']
 atomic_json(a.verify.parent/'fresh-process.json',{'status':'PASS','source_sha256':row['result_sha256'],'max_position_m':maximum_position,'max_orientation_deg':maximum_angle,'samples':len(row['samples'])})
 raise SystemExit(0)
assert a.manifest and a.case and a.output,'Provide --manifest, --case and a new --output directory'
manifest=json.loads(a.manifest.read_text(encoding='utf-8-sig'));assert manifest['schema']=='motion-bricks-sequence-fixture-v1'
source=Path(manifest['blend']).resolve();config=Path(manifest['provider_config']).resolve();assert source.is_file() and config.is_file()
os.environ['ASSET_DIRECTOR_MOTION_BRICKS_CONFIG']=str(config)
assert 0<manifest['height_m']<=100 and 1<=manifest['source_fps']<=120
H=manifest['height_m'];limits={'position_m':.001*H,'orientation_deg':1.,'root_velocity_m_s':.05*H,'angular_velocity_deg_s':5.}
assert 1<=len(manifest['cases'])<=16 and len({c['name'] for c in manifest['cases']})==len(manifest['cases'])
cases=[c for c in manifest['cases'] if c['name']==a.case];assert len(cases)==1
case=cases[0];assert 2<=len(case['clips'])<=4 and 1<=case['fps']<=120 and isinstance(case['fps'],int)
assert isinstance(case['extra'],int) and 2<=case['extra']<=120
assert len(case.get('source_fps',case['clips']))==len(case['clips'])
assert all(isinstance(v,(int,float)) and 1<=v<=120 for v in case.get('source_fps',[manifest['source_fps']]))
assert not case.get('expected') or isinstance(case['expected'],str) and len(case['expected'])>0
assert 'offset' not in case or len(case['offset'])==2 and all(isinstance(v,(int,float)) and math.isfinite(v) and abs(v)<=100 for v in case['offset'])
assert not a.output.exists(),'Preserve earlier evidence; use a fresh output directory'
a.output.mkdir(parents=True);out=a.output;results=[];chosen=a.case
for case in cases:
 folder=out;row={'case':case,'status':'FAIL','thresholds':limits,'character_height_m':H,'contact_quality':'NOT VERIFIED: this runner has no authored stance masks','visual_quality':'NOT VERIFIED','derivatives':'Second-order one-sided at same timestamp; h=1/1536 second at all FPS'};results.append(row)
 try:
  bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);scene=bpy.context.scene;rig=bpy.data.objects[manifest['rig']];scene.frame_set(1);baseline=basis.capture(rig);original={a.name:digest(layer.channels(a)) for a in bpy.data.actions};profile=ret.load_profile(rig)
  for track in rig.animation_data.nla_tracks:track.mute=True
  rig.animation_data.action=None;basis.restore(rig,baseline)
  if 'bad_action_timeline_v1' in rig:del rig['bad_action_timeline_v1']
  scene.render.fps=case['fps'];scene.render.fps_base=1.;bpy.context.view_layer.update()
  selected=[]
  for i,name in enumerate(case['clips']):
   action=bpy.data.actions[name];bound_slots=[slot for bound,slot in layer.bindings(rig) if bound==action];assert len(bound_slots)==1,'Select an unambiguous rig/Action/slot binding';slot=bound_slots[0];source_fps=case.get('source_fps',[manifest['source_fps']]*len(case['clips']))[i];offset=case.get('offset') if i==1 else None
   if offset:
    parent=rig.parent.matrix_world@rig.matrix_parent_inverse if rig.parent else rig.matrix_parent_inverse;offset=list(parent.to_3x3().inverted()@Vector((*offset,0.)))
   if source_fps!=manifest['source_fps'] or offset:
    action=action.copy();action.name='Acceptance '+case['name']+' '+str(i)
    if slot is not None:slot=next(s for s in action.slots if s.identifier==slot.identifier)
    for fc in ops.curves(action,slot):
     for k in fc.keyframe_points:
      for attr in ('co','handle_left','handle_right'):getattr(k,attr).x*=source_fps/manifest['source_fps']
      if offset and fc.data_path=='location' and fc.array_index<3:
       for attr in ('co','handle_left','handle_right'):getattr(k,attr).y+=offset[fc.array_index]
     fc.update()
    track=rig.animation_data.nla_tracks.new();track.name='Acceptance FPS/source offset '+str(i);strip=track.strips.new(action.name,0,action)
    if slot is not None:strip.action_slot=slot
    track.mute=True
   selected.append((action.name,source_fps))
  scene.frame_set(1);basis.restore(rig,baseline);bpy.context.view_layer.update();audit=layer.audit();performer=next(p for p in audit['performers'] if p['name']==manifest['rig']);clips=[];start=1
  for i,(name,source_fps) in enumerate(selected):
   take=next(t for t in performer['takes'] if t['action']==name);speed=source_fps/case['fps'];frames=math.ceil((take['range'][1]-take['range'][0])/speed)+1
   c={'id':'clip_'+str(i),'take_id':take['id'],'start':start,'frames':frames,'speed':speed,'repeat_reviewed':False,'travel':None}
   if i:c['transition']={'frames':case['extra'],'mode':'generated','match_phase':False,'seed':1234,'profile_sha256':digest(profile)}
   if i and case.get('heading'):c['heading_deg']=case['heading']
   clips.append(c);start+=frames+case['extra']
  options={'version':'action-layer-v1','audit_sha256':audit['sha256'],'frame_range':[1,clips[-1]['start']+clips[-1]['frames']-1],'changes':[{'performer':manifest['rig'],'mode':'timeline','clips':clips}]};atomic_json(folder/'options.json',options)
  report=layer.apply(options,case['name'],execution={'directory':folder,'progress':lambda event:print(json.dumps({'seconds':time.monotonic(),'progress':event}),flush=True)});atomic_json(folder/'report.json',report)
  assert not case.get('expected'),'Expected incompatible input rejection'
  path=folder/'result.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path));layer.verify_saved(report,path);scene=bpy.context.scene;rig=bpy.data.objects[manifest['rig']];timeline=json.loads(rig['bad_action_timeline_v1']);assert len(timeline['connections'])==len(clips)-1
  metrics=[seam_metrics(rig,edge,case['fps']) for join in timeline['connections'] for edge in (join['start'],join['end'])];failures=[(s['frame'],k,s[k],limit) for s in metrics for k,limit in limits.items() if s[k]>limit]
  preserved=all(digest(layer.channels(bpy.data.actions[n]))==value for n,value in original.items());assert preserved
  row.update(status='FAIL' if failures else 'PASS',failures=failures,boundaries=metrics,source_actions_preserved=preserved,rig=rig.name,original_source_channels=original,result=str(path),result_sha256=file_hash(path),native_time_normalization=[sf/case['fps'] for _,sf in selected],providers=[j['provider'] for j in timeline['connections']],samples=[{'frame':f,'joints':sample(rig,f)} for f in range(1,scene.frame_end+1)])
 except Exception as e:
  code=getattr(e,'code',None);row.update(error=str(e),code=code,traceback=traceback.format_exc())
  if case.get('expected') and isinstance(e,DirectorError) and case['expected']==code:row['status']='PASS';row['expected_refusal']=True
 atomic_json(folder/'RESULTS.json',row);atomic_json(out/'SUMMARY.json',{'status':'PASS' if all(v['status']=='PASS' for v in results) else 'FAIL','source_sha256':file_hash(source),'source_scope':'Local manifest fixture; asset license and acquisition are the caller responsibility','manifest_sha256':file_hash(a.manifest),'scope':'CONTINUITY_TIMING_PRESERVATION_ONLY','results':results});print('CASE',case['name'],row['status'],row.get('code'),row.get('failures'),flush=True)
assert all(v['status']=='PASS' for v in results),'Expanded scenario failures retained'
