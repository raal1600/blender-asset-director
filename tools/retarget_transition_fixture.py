"""Real pinned retarget bake -> native transition -> saved Blender regression.

Generated CC0 fixture. No arbitrary cross-rig names are accepted as transition
compatibility: reviewed mapping is applied first and both takes belong to the
same renamed/resized destination performer before native transition planning.
"""
from pathlib import Path
import json
import math
import sys
import bpy
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
sys.dont_write_bytecode=True
from asset_director import blender_ops as ops,action_layer as layer,sequence_math as sm
from asset_director.backend import verify,COMMIT
from asset_director.core import Library,atomic_json,digest,file_hash,DirectorError
from headless_fixture import humanoid

out,library=sys.argv[sys.argv.index('--')+1:];out=Path(out);out.mkdir(parents=True,exist_ok=False)
result={'status':'FAIL','input_kind':'GENERATED_CC0','backend_revision':COMMIT,'results':[]}


def frame(f):
    bpy.context.scene.frame_set(math.floor(f),subframe=f-math.floor(f));bpy.context.view_layer.update()


def observe(obj,f):
    frame(f);rig=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());world=rig.matrix_world
    return {'frame':f,'root':list(world.translation),
            'joints':{p.name:{'p':list(world@p.head),'q':list((world@p.matrix).to_quaternion())} for p in rig.pose.bones}}


def visible_skin(target, old_skin):
    old_skin.hide_render=True
    material=bpy.data.materials.new('Retargeted reference teal');material.diffuse_color=(.035,.45,.35,1);material.use_nodes=True
    material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.035,.45,.35,1)
    def segment(name,center,direction,dimensions,bone):
        bpy.ops.mesh.primitive_cube_add(size=1,location=center);mesh=bpy.context.object;mesh.name=name
        mesh.rotation_euler=direction.to_track_quat('Y','Z').to_euler();mesh.dimensions=dimensions
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);mesh.parent=target
        mesh.vertex_groups.new(name=bone).add(list(range(8)),1,'REPLACE');mesh.modifiers.new('Verified native skin','ARMATURE').object=target;mesh.data.materials.append(material)
    for bone in target.data.bones:
        if bone.name.endswith(':root'):continue
        direction=bone.tail_local-bone.head_local;center=(bone.tail_local+bone.head_local)*.5
        dimensions=(.14,direction.length,.24 if ':foot_' in bone.name else .14)
        if bone.name.endswith(':head'):dimensions=(.24,direction.length,.24)
        segment('Visible '+bone.name,center,direction,dimensions,bone.name)
    segment('Visible pelvis',Vector((0,0,1.2)),Vector((1,0,0)),(.20,.54,.18),'verified:hips')
    segment('Visible shoulders',Vector((0,0,1.8)),Vector((1,0,0)),(.18,.60,.16),'verified:spine')


try:
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.render.fps=24
    source,skin=humanoid('Reviewed capture source')
    target,target_skin=humanoid('Retargeted transition performer','verified:',1.2);target.location=(3,0,0);visible_skin(target,target_skin)
    mapping={p.name:'verified:'+p.name for p in source.pose.bones}
    alignment={name:[v for row in Matrix.Identity(4) for v in row] for name in mapping.values()}
    source_hashes={};retarget_reports=[]
    with Library(library) as lib:
        backend=verify(lib)
        for index in range(2):
            action=bpy.data.actions.new('Authored source '+str(index));source.animation_data_create().action=action
            for f in range(1,25):
                for name,phase in [('thigh_l',0),('thigh_r',math.pi),('upperarm_l',math.pi),('upperarm_r',0)]:
                    bone=source.pose.bones[name];bone.rotation_mode='XYZ';bone.rotation_euler.x=(.20+.08*index)*math.sin((f-1)/23*2*math.pi+phase+.8*index)
                    bone.keyframe_insert('rotation_euler',frame=f)
            for c in ops.curves(action):
                for key in c.keyframe_points:key.interpolation='LINEAR'
            source_hashes[action.name]=digest(layer.channels(action))
            retained=layer.add_strip(source,action,getattr(source.animation_data,'action_slot',None),'Retained source '+str(index),1,[1,24],1);retained.mute=True
            baked=ops.retarget(source,target,action,None,{'source_fps':24,'target_fps':30,'mapping':mapping,'alignment':alignment},backend,'transition-retarget-'+str(index))
            new=target.animation_data.action;slot=getattr(target.animation_data,'action_slot',None)
            layer.add_strip(target,new,slot,'Reviewed retarget '+str(index),1,baked['frame_range'],1).mute=True
            assert baked['mapping']==mapping and baked['target_fingerprint']==ops.rig_report(target)['fingerprint']
            retarget_reports.append(baked)
    source.hide_render=True;skin.hide_render=True
    frame(1);before_rest=ops.rig_report(target)['fingerprint'];audit=layer.audit();p=next(p for p in audit['performers'] if p['name']==target.name)
    takes=sorted(p['takes'],key=lambda t:t['action']);assert len(takes)==2 and all(t['stitch_blocker'] is None for t in takes),takes
    channels={a.name:digest(layer.channels(a)) for a in bpy.data.actions}
    span=takes[0]['range'][1]-takes[0]['range'][0];occupied=math.ceil(span)+1
    ca={'id':'clip_retarget_a','take_id':takes[0]['id'],'start':1,'frames':occupied,'speed':1.,'repeat_reviewed':False,'travel':None}
    cb=ca|{'id':'clip_retarget_b','take_id':takes[1]['id'],'start':occupied+7,'transition':{'frames':6,'match_phase':False}}
    request={'version':'action-layer-v1','audit_sha256':audit['sha256'],'frame_range':[1,80],
             'changes':[{'performer':target.name,'mode':'timeline','clips':[ca,cb]}]}
    # A take from the foreign source rig must be refused even when its names
    # resemble the target mapping. Binding identity, not names, is the authority.
    source_take=next(p for p in audit['performers'] if p['name']==source.name)['takes'][0]
    before=layer.preserved(set())
    try:layer.apply(request|{'changes':[{'performer':target.name,'mode':'timeline','clips':[ca|{'take_id':source_take['id']}]}]},'cross-rig-refuse')
    except DirectorError as error:assert error.code=='ACTION_BINDING_CHANGED' and layer.preserved(set())==before
    else:raise AssertionError('Foreign rig Action accepted without retargeting')
    # Lightweight visible subject, retained rendering state for optional checker.
    bpy.ops.mesh.primitive_plane_add(size=20)
    bpy.ops.object.camera_add(location=(6,-6,4));scene=bpy.context.scene;scene.camera=bpy.context.object;scene.camera.data.type='ORTHO';scene.camera.data.ortho_scale=4
    scene.camera.rotation_euler=(Vector((3,0,1.1))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.light_add(type='AREA',location=(4,-3,6));bpy.context.object.data.energy=700;bpy.context.object.data.size=5
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=2
    frame(1);request['audit_sha256']=layer.audit()['sha256']
    source_file=out/'source.blend';bpy.ops.wm.save_as_mainfile(filepath=str(source_file));source_digest=file_hash(source_file)
    report=layer.apply(request,'retarget-native-transition');target=bpy.data.objects['Retargeted transition performer']
    stamps=[1+span,cb['start']];boundaries=[]
    for f in stamps:
        h=1/64;rows={i:observe(target,f+i*h) for i in (-3,-2,-1,0,1,2,3)};max_angle=0;max_position=0;max_orientation=0
        for name,center in rows[0]['joints'].items():
            logs={i:sm.qlog(sm.qmul(sm.inverse(center['q']),rows[i]['joints'][name]['q'])) for i in (-3,-2,-1,1,2,3)}
            derivatives=[[sign*(4*a-b)*30/(2*h) for a,b in zip(logs[sign],logs[sign*2])] for sign in (-1,1)]
            max_angle=max(max_angle,math.degrees(math.dist(*derivatives)))
            positions=[[3*a-3*b+c for a,b,c in zip(rows[sign]['joints'][name]['p'],rows[sign*2]['joints'][name]['p'],rows[sign*3]['joints'][name]['p'])] for sign in (-1,1)]
            angles=[[3*a-3*b+c for a,b,c in zip(logs[sign],logs[sign*2],logs[sign*3])] for sign in (-1,1)]
            max_position=max(max_position,math.dist(*positions));max_orientation=max(max_orientation,math.degrees(math.dist(*angles)))
        boundaries.append({'frame':f,'position_m':max_position,'orientation_deg':max_orientation,'angular_velocity_deg_s':max_angle,'linear_velocity_m_s':0.})
    height=ops.rig_report(target)['anatomical_height'];thresholds={'position_m':.001*height,'orientation_deg':1.,'angular_velocity_deg_s':5.,'linear_velocity_m_s':.05*height}
    if not all(b[k]<=thresholds[k] for b in boundaries for k in thresholds):
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'failed-result.blend'))
        atomic_json(out/'failed-samples.json',{'boundaries':boundaries,'samples':[observe(target,f) for f in (36.9,36.99,37.,37.01,37.1)]})
    assert all(b[k]<=thresholds[k] for b in boundaries for k in thresholds),boundaries
    assert ops.rig_report(target)['fingerprint']==before_rest
    assert all(digest(layer.channels(bpy.data.actions[n]))==v for n,v in channels.items())
    samples=[observe(target,f) for f in sorted({x+d for x in stamps for d in (-1,-.25,0,.25,1)})]
    accepted=out/'result.blend';acceptance=out/'acceptance-report.json';atomic_json(acceptance,report)
    bpy.ops.wm.save_as_mainfile(filepath=str(accepted));layer.verify_saved(report,accepted)
    assert file_hash(source_file)==source_digest
    result.update(status='PASS',checks=['real pinned upstream matrix retarget to renamed scaled rig','explicit reviewed mapping and rest fingerprint',
        'foreign-rig binding rejected','retargeted Actions stitched by native provider','fractional native endpoint and 24-to-30 FPS conversion',
        'source and retarget Action preservation','all-joint boundary continuity','saved .blend reopens'],retarget=retarget_reports,
        results=[{'status':'PASS','result':str(accepted),'result_sha256':file_hash(accepted),'acceptance_report':str(acceptance),'rig':'Retargeted transition performer',
                  'character_height_m':height,'fps':30,'stitch_timestamps':stamps,'source_channel_hashes':channels,'samples':samples,
                  'metrics':{'boundaries':boundaries},'thresholds':thresholds}])
finally:atomic_json(out/'RESULTS.json',result)
