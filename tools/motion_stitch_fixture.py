"""Generated-only actual Blender connection, phase, preservation and GLB checks."""
from pathlib import Path
import sys
import math
import json
sys.dont_write_bytecode = True
import bpy
from mathutils import Vector, Quaternion
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from asset_director import action_layer as layer, action_timeline as timeline
from asset_director.core import atomic_json, file_hash, DirectorError

out = Path(sys.argv[sys.argv.index('--')+1]); out.mkdir(parents=True, exist_ok=False)
checks = []


def check(ok, label):
    assert ok, label
    checks.append(label)


def frame(f):
    bpy.context.scene.frame_set(math.floor(f), subframe=f%1)
    bpy.context.view_layer.update()


def centroid(name):
    obj=bpy.context.scene.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=obj.to_mesh()
    try:return sum((obj.matrix_world @ v.co for v in mesh.vertices),Vector())/len(mesh.vertices)
    finally:obj.to_mesh_clear()


def rotation_case(mode, rigged):
    """Native rotation formats and stationary non-character motion, no mappings."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;scene.frame_end=80
    if rigged:
        data=bpy.data.armatures.new('Synthetic rig data');obj=bpy.data.objects.new('ObservedOwner',data);scene.collection.objects.link(obj)
        bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
        bone=data.edit_bones.new('UnclassifiedJoint');bone.tail=(0,0,1);bpy.ops.object.mode_set(mode='OBJECT')
        owner=obj.pose.bones['UnclassifiedJoint']
    else:
        bpy.ops.mesh.primitive_cube_add();obj=bpy.context.object;obj.name='ObservedOwner';owner=obj
    owner.rotation_mode=mode
    for index in range(2):
        action=bpy.data.actions.new('Observed format '+str(index));obj.animation_data_create().action=action
        for i in range(25):
            q=Quaternion((1,0,0) if index==0 else (0,1,0), .01*i+.3*index)
            if mode=='QUATERNION':owner.rotation_quaternion=q;prop='rotation_quaternion'
            elif mode=='AXIS_ANGLE':axis,angle=q.to_axis_angle();owner.rotation_axis_angle=(angle,*axis);prop='rotation_axis_angle'
            else:owner.rotation_euler=q.to_euler(mode);prop='rotation_euler'
            owner.keyframe_insert(prop,frame=1+i)
        slot=getattr(obj.animation_data,'action_slot',None)
        track=layer.add_strip(obj,action,slot,'Retained '+str(index),1,[1,25],1);track.mute=True
    frame(1);audit=layer.audit();p=next(p for p in audit['performers'] if p['name']==obj.name)
    a,b=sorted(p['takes'],key=lambda t:t['action'])
    ca={'id':'clip_format_a','take_id':a['id'],'start':1,'frames':25,'speed':1,'repeat_reviewed':False,'travel':None}
    cb=ca|{'id':'clip_format_b','take_id':b['id'],'start':32,'transition':{'frames':6,'match_phase':True}}
    request={'version':'action-layer-v1','audit_sha256':audit['sha256'],'frame_range':[1,80],
             'changes':[{'performer':obj.name,'mode':'timeline','clips':[ca,cb]}]}
    report=layer.apply(request,'synthetic-'+mode);result=out/(mode+('-rig' if rigged else '-object')+'.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(result));layer.verify_saved(report,result)
    check(report['reopened'] and report['changes'][0]['timeline']['connections'][0]['phase']==0,
          mode+' '+('rig' if rigged else 'object')+' connection reopens without unreviewed phase shift')
    owner=bpy.context.scene.objects['ObservedOwner'];owner=owner.pose.bones['UnclassifiedJoint'] if rigged else owner
    check(owner.rotation_mode==mode,'connection retains '+mode+' rotation ownership')


def incompatibility_cases(source):
    from asset_director import motion_stitch
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
    obj=bpy.context.scene.objects['TestPerformer0'];action,slot=list(layer.bindings(obj))[1]
    action_copy=action.copy();ad=obj.animation_data;ad.action=action_copy
    if slot is not None:ad.action_slot=action_copy.slots[0]
    obj.pose.bones['ArbitraryJoint'].keyframe_insert('scale',frame=1)
    obj.pose.bones['ArbitraryJoint'].keyframe_insert('scale',frame=25)
    frame(1);audit=layer.audit();p=next(p for p in audit['performers'] if p['name']==obj.name)
    a=next(t for t in p['takes'] if t['action']=='Observed 0 0');b=next(t for t in p['takes'] if t['action']==action_copy.name)
    check(a['stitch_channels']!=b['stitch_channels'],'mismatched native channel ownership is observable before Save')
    ca={'id':'clip_bad_a','take_id':a['id'],'start':1,'frames':25,'speed':1,'repeat_reviewed':False,'travel':None}
    cb=ca|{'id':'clip_bad_b','take_id':b['id'],'start':32,'transition':{'frames':6,'match_phase':False}}
    before=layer.preserved(set())
    try:layer.apply({'version':'action-layer-v1','audit_sha256':audit['sha256'],'frame_range':[1,80],
                     'changes':[{'performer':obj.name,'mode':'timeline','clips':[ca,cb]}]},'synthetic-bad-channels')
    except DirectorError as error:check('different channels' in str(error) and layer.preserved(set())==before,'different channels refuse without lasting scene mutation')
    else:raise AssertionError('different channels accepted')
    curve=list(layer.ops.curves(action_copy))[0];modifier=curve.modifiers.new('NOISE')
    check(motion_stitch.reason(obj,action_copy,getattr(ad,'action_slot',None)) is not None,'procedural channels request Blender review')
    curve.modifiers.remove(modifier)
    obj.location.x=0;obj.keyframe_insert('location',index=0,frame=1);obj.location.x=1;obj.keyframe_insert('location',index=0,frame=25)
    check('native planar travel' in timeline.travel_reason(obj,action_copy,getattr(ad,'action_slot',None)),'native root travel cannot acquire a second movement owner')


try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene; scene.render.fps=24; scene.frame_end=80
    scene.unit_settings.scale_length=.5
    for index in range(2):
        parent=bpy.data.objects.new('Placement '+str(index),None);scene.collection.objects.link(parent)
        parent['bad_placement_control']=1;parent['bad_placement_instance']='synthetic_stitch_'+str(index)
        parent.location.x=index*4;parent.rotation_euler.z=.4;parent.scale=(2,2,2)
        data=bpy.data.armatures.new('Data '+str(index));rig=bpy.data.objects.new('TestPerformer'+str(index),data);scene.collection.objects.link(rig);rig.parent=parent
        bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
        bone=data.edit_bones.new('ArbitraryJoint');bone.head=(0,0,0);bone.tail=(0,0,1)
        bpy.ops.object.mode_set(mode='OBJECT');rig.select_set(False)
        pb=rig.pose.bones['ArbitraryJoint'];pb.rotation_mode='XYZ'
        for take_index in range(2):
            action=bpy.data.actions.new('Observed '+str(index)+' '+str(take_index));rig.animation_data_create().action=action
            for i in range(97):
                pb.rotation_euler.x=.4*math.sin(2*math.pi*i/96+take_index*math.pi/2)
                pb.keyframe_insert('rotation_euler',frame=1+i/4)
            for curve in layer.ops.curves(action):
                for key in curve.keyframe_points:key.interpolation='LINEAR'
            slot=getattr(rig.animation_data,'action_slot',None)
            retained=layer.add_strip(rig,action,slot,'Retained '+str(take_index),1,[1,25],1);retained.mute=True
        rig.animation_data.action=rig.animation_data.nla_tracks[0].strips[0].action
        if hasattr(rig.animation_data,'action_slot'):rig.animation_data.action_slot=rig.animation_data.nla_tracks[0].strips[0].action_slot
        bpy.ops.mesh.primitive_cube_add(size=.3,location=(0,0,.6));skin=bpy.context.object;skin.name='VisibleSkin'+str(index);skin.parent=rig
        group=skin.vertex_groups.new(name='ArbitraryJoint');group.add(list(range(8)),1,'REPLACE');skin.modifiers.new('Skin','ARMATURE').object=rig
    # The same saved transition is also exercised through the application's
    # normal shot-render flow. These generated presentation assets are retained
    # in the source checkpoint, not injected into an unrelated rendering demo.
    camera_data=bpy.data.cameras.new('Synthetic transition camera')
    camera=bpy.data.objects.new(camera_data.name,camera_data);scene.collection.objects.link(camera)
    camera.location=(5,-8,5)
    camera.rotation_euler=(Vector((1,-1,1))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera_data.type='ORTHO';camera_data.ortho_scale=7;scene.camera=camera
    light_data=bpy.data.lights.new('Synthetic transition key','AREA');light_data.energy=700;light_data.size=5
    light=bpy.data.objects.new(light_data.name,light_data);scene.collection.objects.link(light)
    light.location=(1,-4,6);light.rotation_euler=(Vector((1,-1,1))-light.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1
    scene.render.use_compositing=False;scene.render.use_sequencer=False
    scene.render.resolution_x=320;scene.render.resolution_y=240;scene.render.resolution_percentage=100
    frame(1)
    source=out/'source.blend';bpy.ops.wm.save_as_mainfile(filepath=str(source));original=file_hash(source)
    before=layer.preserved(set());inspection=layer.audit()
    check(layer.preserved(set())==before,'read-only compatibility inspection preserves original scene')
    p=next(p for p in inspection['performers'] if p['name']=='TestPerformer0');a,b=sorted(p['takes'],key=lambda t:t['action'])
    check(a['stitch_blocker'] is None and b['stitch_blocker'] is None,'eligible by observed channels, not animation names')
    def clip(t,id,start,delta):
        return {'id':id,'take_id':t['id'],'start':start,'frames':25,'speed':1,'repeat_reviewed':True,
                'travel':{'delta_m':delta,'meters_per_cycle':1}}
    ca=clip(a,'clip_alpha',1,[0,-1]);cb=clip(b,'clip_beta',32,[1,0])|{'transition':{'frames':6,'match_phase':True}}
    options={'version':'action-layer-v1','audit_sha256':inspection['sha256'],'frame_range':[1,80],
             'changes':[{'performer':p['name'],'mode':'timeline','clips':[ca,cb]}]}
    for bad in [cb|{'start':31},cb|{'travel':{'delta_m':[0,1],'meters_per_cycle':1}}]:
        try:layer.apply(options|{'changes':[{'performer':p['name'],'mode':'timeline','clips':[ca,bad]}]},'invalid')
        except DirectorError:check(layer.preserved(set())==before,'invalid timing or reversal refused before lasting mutation')
        else:raise AssertionError('unsafe join accepted')
    report=layer.apply(options,'synthetic-stitch')
    result=out/'stitched.blend';bpy.ops.wm.save_as_mainfile(filepath=str(result));layer.verify_saved(report,result)
    join=report['changes'][0]['timeline']['connections'][0]
    check(report['reopened'],'separate result reopened and independently verified')
    check(.65<join['matched_phase']<.85 and join['match_cost_after']<join['match_cost_before']*.1,'phase match uses pose and velocity instead of selecting the opposite swing')
    check(abs(join['phase']-(join['matched_phase']+7/24)%1)<1e-6,'incoming cycle advances through the connection instead of restarting at the same matched pose')
    check(join['contact_acceptance']=='NOT_EVALUATED','numerical join does not manufacture contact or human approval')
    rig=bpy.context.scene.objects['TestPerformer0'];samples=[]
    for f in [1,7,24,25,25.25,26,27,28,28.5,29,30,31,31.75,32,33,44,56,80]:
        frame(f);samples.append({'frame':f,'world_m':[v*.5 for v in rig.matrix_world.translation],
                                'skin':list(centroid('VisibleSkin0')),
                                'angle':float(rig.pose.bones['ArbitraryJoint'].rotation_euler.x)})
    positions={r['frame']:Vector(r['world_m']) for r in samples}
    check(next(r['angle'] for r in samples if r['frame']==28.5)>.25
          and next(r['angle'] for r in samples if r['frame']==32)>.35,
          'compatible synthetic swing continues through the bridge rather than freezing or reversing its phase')
    check((positions[25]-positions[1]-Vector((0,-1,0))).length<1e-5,'first native clip retains its exact world travel')
    check((positions[32]-positions[25]-Vector((7/48,-7/48,0))).length<1e-5,'connection carries its explicitly planned world displacement')
    check((positions[56]-positions[32]-Vector((1,0,0))).length<1e-5,'incoming clip retains its own full duration and distance')
    check((positions[80]-positions[56]).length<1e-6,'final pose and path hold without restarting the source')
    check(file_hash(source)==original,'source bytes remain unchanged')
    saved=file_hash(result);frame(1);fresh=layer.audit()
    edited=options|{'audit_sha256':fresh['sha256'],'changes':[{'performer':p['name'],'mode':'timeline','clips':[ca,cb|{'start':36,'transition':{'frames':10,'match_phase':False}}]}]}
    revised=layer.apply(edited,'synthetic-stitch-revision');revision=out/'revised.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(revision));layer.verify_saved(revised,revision)
    check(file_hash(result)==saved and revised['changes'][0]['timeline']['connections'][0]['phase']==0,'revision preserves previous output and permits explicit original phase')
    bpy.ops.wm.open_mainfile(filepath=str(result),load_ui=False,use_scripts=False)
    bpy.context.scene['asset_director_preview_only']=True
    from asset_director.viewer_export import export
    exported=export(out/'stitched.glb',{'takes':[],'checkpoint':True,'preview_profile':'action-playback-v1'})
    check(exported['playback']['start']==1 and exported['playback']['end']==80,'actual combined-scene GLB includes transitions')
    incompatibility_cases(source)
    for mode,rigged in [('QUATERNION',True),('AXIS_ANGLE',True),('XYZ',False)]:rotation_case(mode,rigged)
    atomic_json(out/'RESULTS.json',{'status':'PASS','input_kind':'GENERATED','checks':checks,'samples':samples,
                'source_sha256':original,'result_sha256':saved,'join':join,'blender':bpy.app.version_string,
                'human_review':'NOT_TESTED','foot_locking':'NOT_IMPLEMENTED'})
    print(json.dumps({'status':'PASS','checks':len(checks)}))
except Exception as error:
    atomic_json(out/'RESULTS.json',{'status':'FAIL','checks':checks,'error':repr(error)});raise
