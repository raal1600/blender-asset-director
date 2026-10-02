"""Real generated rigs: travel, sequencing, preservation, reopen and refusal."""
from pathlib import Path
import sys
import math
import json
sys.dont_write_bytecode = True
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director import action_layer as layer, action_timeline as timeline
from asset_director.core import atomic_json, file_hash, DirectorError

out = Path(sys.argv[sys.argv.index('--') + 1]);out.mkdir(parents=True, exist_ok=False)
checks = []


def check(ok, label):
    assert ok, label
    checks.append(label)


def save_result(options, name):
    report = layer.apply(options, name)
    target = out / (name + '.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    layer.verify_saved(report, target)
    atomic_json(out / (name + '.json'), report)
    return target, report


def centroid(name):
    obj = bpy.data.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get())
    return sum((obj.matrix_world @ v.co for v in obj.data.vertices), Vector()) / len(obj.data.vertices)


try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene;scene.frame_start=1;scene.frame_end=250;scene.render.fps=24
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.1
    for index in range(2):
        parent=bpy.data.objects.new('World placement '+str(index),None);scene.collection.objects.link(parent)
        parent['bad_placement_control']=1;parent['bad_placement_instance']='instance_fixture_'+str(index)
        parent.rotation_euler.z=.4;parent.scale=(2,2,2);parent.location.x=index*20
        arm=bpy.data.armatures.new('Rig data '+str(index));rig=bpy.data.objects.new('TimelineRig'+str(index),arm);scene.collection.objects.link(rig);rig.parent=parent
        bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
        bone=arm.edit_bones.new('NativeJoint');bone.head=(0,0,0);bone.tail=(0,0,10)
        bpy.ops.object.mode_set(mode='OBJECT');rig.select_set(False)
        bpy.ops.mesh.primitive_cube_add(size=4,location=(0,0,6));skin=bpy.context.object;skin.name='TimelineSkin'+str(index);skin.parent=rig
        group=skin.vertex_groups.new(name='NativeJoint');group.add(list(range(8)),1,'REPLACE');skin.modifiers.new('Skin','ARMATURE').object=rig
        pb=rig.pose.bones['NativeJoint'];pb.rotation_mode='XYZ'
        for frame,angle in [(1,0),(7,.2),(13,0),(19,-.2),(25,0)]:
            pb.rotation_euler.x=angle;pb.keyframe_insert('rotation_euler',frame=frame)
        rig.animation_data.action.name='Synthetic in-place cycle '+str(index)
        for curve in layer.ops.curves(rig.animation_data.action):
            for key in curve.keyframe_points:key.interpolation='LINEAR'
    scene.frame_set(1);bpy.context.view_layer.update()
    source=out/'source.blend';bpy.ops.wm.save_as_mainfile(filepath=str(source));source_hash=file_hash(source)
    initial=layer.audit();original_keys={a.name:layer.channels(a) for a in bpy.data.actions}
    one=next(p for p in initial['performers'] if p['name']=='TimelineRig0');take=one['takes'][0]
    check(take['travel_blocker'] is None,'native in-place rotation cycle eligible without guessed bone semantics')
    c={'id':'clip_first','take_id':take['id'],'start':1,'frames':49,'speed':1,'repeat_reviewed':True,'travel':{'delta_m':[0,-5],'meters_per_cycle':2.5}}
    options={'version':'action-layer-v1','audit_sha256':initial['sha256'],'frame_range':[1,250],'changes':[{'performer':one['name'],'mode':'timeline','clips':[c,c|{'id':'clip_second','start':50,'frames':25,'travel':{'delta_m':[2.5,0],'meters_per_cycle':2.5}}]}]}
    before=layer.preserved(set())
    for patch in [c|{'repeat_reviewed':False},c|{'frames':50},c|{'take_id':'take_'+'0'*64}]:
        try:layer.apply(options|{'changes':[{'performer':one['name'],'mode':'timeline','clips':[patch]}]},'refuse')
        except DirectorError:check(layer.preserved(set())==before,'invalid sequence refused before scene mutation')
        else:raise AssertionError('invalid clip accepted')
    other_before=[]
    for f in [1,7,49,50,74,250]:scene.frame_set(f);other_before.append(list(centroid('TimelineSkin1')))
    scene.frame_set(1)
    result,report=save_result(options,'timeline-first')
    check(report['reopened'] and report['performance_acceptance']=='NOT_EVALUATED','actual reopened result verifies without human approval')
    rig=bpy.data.objects['TimelineRig0'];samples=[]
    for f in [1,7,25,49,50,62,74,250]:
        scene=bpy.context.scene;scene.frame_set(f);bpy.context.view_layer.update()
        samples.append({'frame':f,'origin_m':[v*.1 for v in rig.matrix_world.translation],'skin':list(centroid('TimelineSkin0'))})
    positions={s['frame']:Vector(s['origin_m']) for s in samples}
    check((positions[49]-positions[1]-Vector((0,-5,0))).length<1e-5,'backward path travels exactly five world metres through scaled rotated parent')
    check((positions[74]-positions[49]-Vector((2.5,0,0))).length<1e-5,'next clip starts from prior endpoint and travels right independently of facing')
    check((positions[50]-positions[49]).length<1e-6 and (positions[250]-positions[74]).length<1e-6,'inclusive occupancy has no endpoint jump; final position holds')
    check(abs(Vector(samples[1]['skin']).z-Vector(samples[0]['skin']).z)>.01,'native skin actually deforms, not merely a translated static mesh')
    for i,f in enumerate([1,7,49,50,74,250]):scene.frame_set(f);check((centroid('TimelineSkin1')-Vector(other_before[i])).length<1e-5,'other character preserved at frame '+str(f))
    check(all(layer.channels(bpy.data.actions[name])==keys for name,keys in original_keys.items()),'all original native source channels remain unchanged')
    control=rig.parent;control.location.x+=1;bpy.context.view_layer.update()
    try:timeline.load(rig)
    except DirectorError:check(True,'changed World placement invalidates saved world-space path context')
    else:raise AssertionError('changed path coordinates were accepted')
    control.location.x-=1;bpy.context.view_layer.update()
    scene.frame_set(1);inspection=layer.audit();saved_hash=file_hash(result)
    edited=options|{'audit_sha256':inspection['sha256'],'changes':[{'performer':one['name'],'mode':'timeline','clips':[c|{'travel':{'delta_m':[-5,0],'meters_per_cycle':2.5}}]}]}
    revision,revised=save_result(edited,'timeline-revised')
    check(file_hash(result)==saved_hash and file_hash(source)==source_hash,'revision retains original and previous timeline bytes')
    current=layer.audit();clear=options|{'audit_sha256':current['sha256'],'changes':[{'performer':one['name'],'mode':'timeline','clips':[]}]}
    _,cleared=save_result(clear,'timeline-cleared');check(cleared['action_audit']['performers'][0]['name'] is not None,'empty timeline saves without reviving muted performance')
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
    rig=bpy.data.objects['TimelineRig0'];pb=rig.pose.bones['NativeJoint']
    for f,x in [(1,0),(13,10),(25,0)]:pb.location.x=x;pb.keyframe_insert('location',frame=f)
    blocked=layer.audit();p=next(p for p in blocked['performers'] if p['name']==rig.name)
    check(bool(p['takes'][0]['travel_blocker']),'out-and-back root motion is not misclassified as in-place')
    bpy.ops.wm.open_mainfile(filepath=str(result),load_ui=False,use_scripts=False)
    bpy.context.scene['asset_director_preview_only']=True
    from asset_director.viewer_export import export
    exported=export(out/'timeline.glb',{'takes':[],'checkpoint':True,'preview_profile':'action-playback-v1'})
    check(exported['playback']['start']==1 and exported['playback']['end']==250,'real combined timeline GLB exports its complete saved playback range')
    atomic_json(out/'RESULTS.json',{'status':'PASS','scope':'GENERATED_ACTION_TIMELINE','checks':checks,'samples':samples,'source_sha256':source_hash,'blender':bpy.app.version_string,'human_review':'NOT_TESTED'})
    print(json.dumps({'status':'PASS','checks':len(checks)}))
except Exception as error:
    atomic_json(out/'RESULTS.json',{'status':'FAIL','checks':checks,'error':repr(error)});raise
