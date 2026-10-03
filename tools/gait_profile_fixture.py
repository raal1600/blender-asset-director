"""Real Blender automatic-pace fixture. Optional caller-owned copied input stays private.

Usage: blender -b --python gait_profile_fixture.py -- OUT [INPUT RIG TAKE]
Human motion/contact acceptance is deliberately NOT_TESTED.
"""
from pathlib import Path
import sys
import math
import json
sys.dont_write_bytecode = True
import bpy
from mathutils import Vector, Quaternion
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from asset_director import action_layer as layer, gait_sampling
from asset_director.core import atomic_json, file_hash, DirectorError

args = sys.argv[sys.argv.index('--') + 1:]
out = Path(args[0]); out.mkdir(parents=True, exist_ok=False)
checks = []


def check(ok, label):
    assert ok, label
    checks.append(label)


def generated():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene; scene.render.fps = 24; scene.frame_end = 250
    data = bpy.data.armatures.new('Synthetic support rig')
    rig = bpy.data.objects.new('SyntheticWalker', data); scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig; rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    root = data.edit_bones.new('Core'); root.head = (0, 0, 1.8); root.tail = (0, 0, 2)
    for side, x in [('A', -.2), ('B', .2)]:
        upper = data.edit_bones.new('Upper'+side); upper.head = (x, 0, 1.8); upper.tail = (x, 0, .9); upper.parent = root
        lower = data.edit_bones.new('Lower'+side); lower.head = upper.tail; lower.tail = (x, 0, 0); lower.parent = upper
        toe = data.edit_bones.new('Support'+side); toe.head = lower.tail; toe.tail = (x, -.1, 0); toe.parent = lower
    bpy.ops.object.mode_set(mode='OBJECT')
    for index in range(65):
        for side, phase in [('A', index/64%1), ('B', (index/64+.5)%1)]:
            y = .4-1.6*phase if phase<.5 else -.4+1.6*(phase-.5)
            z = .12 + (0 if phase<.5 else .16*math.sin(2*math.pi*(phase-.5)))
            distance = math.hypot(y, 1.8-z)
            bend = math.acos(distance/1.8)
            angle = math.atan2(y, 1.8-z)
            for name, value in [('Upper'+side, angle-bend), ('Lower'+side, 2*bend)]:
                bone = rig.pose.bones[name]; rest = bone.bone.matrix_local.to_quaternion()
                bone.rotation_mode = 'QUATERNION'
                bone.rotation_quaternion = rest.inverted() @ Quaternion((1,0,0), value) @ rest
                bone.keyframe_insert('rotation_quaternion', frame=1+index*24/64)
    rig.animation_data.action.name = 'Synthetic alternate supports'
    for curve in layer.ops.curves(rig.animation_data.action):
        for key in curve.keyframe_points: key.interpolation='LINEAR'
    # Small skinned geometry makes the actual native result visible in the viewer.
    for side, x in [('A', -.2), ('B', .2)]:
        bpy.ops.mesh.primitive_cube_add(size=.12, location=(x,0,0))
        skin=bpy.context.object; skin.name='Synthetic foot '+side
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        skin.parent=rig; group=skin.vertex_groups.new(name='Support'+side)
        group.add(list(range(len(skin.data.vertices))),1,'REPLACE')
        skin.modifiers.new('Native skin','ARMATURE').object=rig
    scene.frame_set(1)
    return rig.name, rig.animation_data.action.name


try:
    if len(args) > 1:
        original = Path(args[1]); source_hash = file_hash(original)
        bpy.ops.wm.open_mainfile(filepath=str(original), load_ui=False, use_scripts=False)
        rig_name, take_name = args[2:4]
    else:
        rig_name, take_name = generated()
        original = out/'source.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(original)); source_hash=file_hash(original)
    before=layer.preserved(set()); audit=layer.audit()
    check(layer.preserved(set())==before,'sampling leaves objects, bindings, source keys, skin and rest unchanged')
    check(layer.audit()==audit,'repeated inspection is deterministic')
    item=next(p for p in audit['performers'] if p['name']==rig_name)
    take=next(t for t in item['takes'] if t['action']==take_name); g=take['gait']
    atomic_json(out/'INSPECTION.json',audit)
    check(g['status']=='estimated','actual evaluated supports yield an automatic estimate')
    check(take['travel_blocker'] is None,'native take has no conflicting planar travel')
    rig=bpy.context.scene.objects[rig_name]
    pair=next((a,s) for a,s in layer.bindings(rig) if a.name==take_name)
    check(gait_sampling.inspect(rig,*pair,take,[0])['status']=='unavailable','sampling budget refuses rather than guessing')
    check(gait_sampling.inspect(rig,*pair,take|{'range':[0,121]},[100])['status']=='unavailable','oversized native cycles refuse undersampled automatic calibration')
    if len(args)==1:
        scene=bpy.context.scene;old_parent=rig.parent;old_unit=scene.unit_settings.scale_length
        parent=bpy.data.objects.new('Synthetic scale/rotation probe',None);scene.collection.objects.link(parent)
        parent.scale=(2,2,2);parent.rotation_euler.z=.6;rig.parent=parent;scene.unit_settings.scale_length=.25;bpy.context.view_layer.update()
        changed=gait_sampling.inspect(rig,*pair,take,[100])
        check(changed['status']=='estimated' and abs(changed['meters_per_cycle']-g['meters_per_cycle']*.5)<1e-4,
              'automatic pace respects actual parent scale and scene metre units')
        rotated=[g['direction'][0]*math.cos(.6)-g['direction'][1]*math.sin(.6),g['direction'][0]*math.sin(.6)+g['direction'][1]*math.cos(.6)]
        check(math.dist(rotated,changed['direction'])<1e-4,'automatic heading rotates with actual World placement')
        rig.parent=old_parent;scene.unit_settings.scale_length=old_unit;bpy.data.objects.remove(parent,do_unlink=True);bpy.context.view_layer.update()
        check(layer.audit()==audit,'temporary transform probe leaves original inspection identical')
    distance=5; direction=Vector(g['direction']);direction.normalize()
    span=take['range'][1]-take['range'][0]
    frames=math.ceil(distance/g['meters_per_cycle']*span-1e-9)+1
    clip={'id':'clip_gait_test','take_id':take['id'],'start':1,'frames':frames,'speed':1,
          'repeat_reviewed':False,'travel':{'delta_m':list(direction*distance),'meters_per_cycle':g['meters_per_cycle'],'gait_id':g['id']}}
    options={'version':'action-layer-v1','audit_sha256':audit['sha256'],'frame_range':[1,max(250,frames)],
             'changes':[{'performer':rig_name,'mode':'timeline','clips':[clip]}]}
    try:layer.apply(options,'unreviewed-gait')
    except DirectorError:check(layer.preserved(set())==before,'unreviewed repeat refused before mutation')
    else:raise AssertionError('unreviewed repeat accepted')
    # Generated fixtures may exercise the reviewed branch. Private inputs only
    # execute ONE cycle: no human loop review is manufactured for a real asset.
    planned_five_metre_frames=frames
    if len(args)>1:
        distance=g['meters_per_cycle'];frames=math.ceil(span-1e-9)+1
        clip['frames']=frames;clip['travel']['delta_m']=list(direction*distance)
    else:clip['repeat_reviewed']=True
    for patch in [{'gait_id':'0'*64},{'meters_per_cycle':5},{'delta_m':list(-direction*5)}]:
        invalid=clip|{'travel':clip['travel']|patch}
        try:layer.apply(options|{'changes':[{'performer':rig_name,'mode':'timeline','clips':[invalid]}]},'forged-gait')
        except DirectorError:check(layer.preserved(set())==before,'tampered calibration refused without mutation')
        else:raise AssertionError('forged profile accepted')
    report=layer.apply(options,'gait-fixture')
    target=out/'automatic-travel.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target));layer.verify_saved(report,target)
    check(report['reopened'],'separately saved automatic timeline reopens and preserves native sources')
    scene=bpy.context.scene; rig=scene.objects[rig_name]
    scene.frame_set(1);start=rig.matrix_world.translation.copy()
    native_end=1+distance/g['meters_per_cycle']*span
    scene.frame_set(math.floor(native_end),subframe=native_end%1);end=rig.matrix_world.translation.copy()
    check(abs((end-start).length*scene.unit_settings.scale_length-distance)<1e-4,'planned world metres achieved at the fractional native endpoint')
    scene.frame_set(frames);rounded=rig.matrix_world.translation.copy()
    check((rounded-end).length<1e-5,'rounded occupied tail holds rather than sliding after native motion stops')
    scene.frame_set(1);fresh=layer.audit();saved_take=next(t for p in fresh['performers'] if p['name']==rig_name for t in p['takes'] if t['action']==take_name)
    check(saved_take['gait']['id']==g['id'],'saved path retains its exact native gait calibration')
    # Verify actual sampled contact drift before/after, not only frame counts.
    traces={name:[] for name in g['landmarks']}; unit=scene.unit_settings.scale_length
    for i in range(65):
        f=1+span*i/64;scene.frame_set(math.floor(f),subframe=f%1)
        evaluated=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
        for name in traces:traces[name].append(list(evaluated.matrix_world@evaluated.pose.bones[name].head*unit))
    native=[]; corrected=[]
    for path in traces.values():
        floor=min(p[2] for p in path)
        for a,b in zip(path,path[1:]):
            raw=[(b[k]-a[k])*64 for k in range(2)]
            original_velocity=[raw[k]-direction[k]*g['meters_per_cycle'] for k in range(2)]
            if (a[2]+b[2])/2<floor+.04 and abs(b[2]-a[2])*64<max(.1,math.hypot(*original_velocity)*.3):
                native.append(math.hypot(*original_velocity));corrected.append(math.hypot(*raw))
    from statistics import median
    check(bool(native) and median(corrected)<median(native)*.4,'sampled low-support median drift reduced by more than 60 percent')
    check(file_hash(original)==source_hash,'input file bytes remain unchanged')
    atomic_json(out/'RESULTS.json',{'status':'PASS','checks':checks,'profile':g,'frames':frames,
                'planned_five_metre_frames':planned_five_metre_frames,'executed_distance_m':distance,
                'source_sha256':source_hash,'output_sha256':file_hash(target),'blender':bpy.app.version_string,
                'stance_drift_m_per_cycle':{'native':median(native),'with_travel':median(corrected)},
                'human_review':'NOT_TESTED','contact_solver':'NOT_IMPLEMENTED','input_kind':'PRIVATE_COPY' if len(args)>1 else 'GENERATED'})
    print(json.dumps({'status':'PASS','checks':len(checks),'frames':frames}))
except Exception as error:
    atomic_json(out/'RESULTS.json',{'status':'FAIL','checks':checks,'error':repr(error)});raise
