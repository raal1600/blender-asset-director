"""Actual Blender round-trip/refusal tests on a clearly synthetic humanoid.

No model execution is represented by this offline retarget contract fixture.
The compact synthetic model skeleton is never used for provider acceptance.
"""
from pathlib import Path
import json
import math
import sys
import bpy
from mathutils import Quaternion, Vector
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director import motion_bricks_retarget as ret, sequence_math as qm
from asset_director.core import DirectorError, atomic_json, digest

out = Path(sys.argv[sys.argv.index('--') + 1]); out.mkdir(parents=True, exist_ok=False)
bpy.ops.wm.read_factory_settings(use_empty=True)
arm = bpy.data.armatures.new('Synthetic humanoid contract geometry')
rig = bpy.data.objects.new('Explicitly mapped synthetic humanoid', arm)
bpy.context.scene.collection.objects.link(rig); bpy.context.view_layer.objects.active = rig; rig.select_set(True)
positions = {'pelvis': (0, 0, 1), 'spine': (0, 0, 1.12), 'spine1': (0, 0, 1.28), 'chest': (0, 0, 1.44)}
for side, sign in [('left', 1), ('right', -1)]:
    for role, pos in {'thigh': (.12, 0, 1), 'shin': (.12, 0, .55), 'foot': (.12, 0, .12),
                      'toe': (.12, -.17, .04), 'upper_arm': (.23, 0, 1.42),
                      'forearm': (.47, 0, 1.37), 'hand': (.7, 0, 1.32), 'hand_tip': (.8, 0, 1.3)}.items():
        positions[side+'_'+role] = (pos[0]*sign, *pos[1:])
roles = {role: 'observed_'+str(i) for i, role in enumerate(positions)}
bpy.ops.object.mode_set(mode='EDIT')
for role, name in roles.items():
    b = arm.edit_bones.new(name); b.head = positions[role]; b.tail = Vector(b.head) + Vector((0, 0, .04))
for chain in ret.CHAINS:
    for a, b in zip(chain, chain[1:]):
        arm.edit_bones[roles[b]].parent = arm.edit_bones[roles[a]]
bpy.ops.object.mode_set(mode='OBJECT'); bpy.context.view_layer.update()
parents = [-1,0,1,2,3,4,5,6,0,8,9,10,11,12,13,0,15,16,17,18,19,20,21,22,23,24,17,26,27,28,29,30,31,32]
neutral = [None]*34
for role, indices in ret.GROUPS.items():
    for i in indices: neutral[i] = list(ret.axes().inverted() @ (Vector(positions[role])-Vector(positions['pelvis'])))
for i, role in [(7,'left_toe'), (14,'right_toe'), (25,'left_hand_tip'), (33,'right_hand_tip')]:
    neutral[i] = list(ret.axes().inverted() @ (Vector(positions[role])-Vector(positions['pelvis'])))
skeleton = {'id':'g1skel34', 'joint_names':['synthetic_'+str(i) for i in range(34)], 'parents':parents, 'neutral_joints':neutral}
profile = ret.build_profile(rig, skeleton, roles, 0.)
rig[ret.PROPERTY] = json.dumps(profile); original = digest(profile)
checks = []; maximum_position = 0.; maximum_angle = 0.
for index in range(6):
    rig.location = (index*.23, -index*.17, index*.021); bpy.context.view_layer.update()
    assert digest(ret.load_profile(rig)) == original, 'Playback translation changed the mapping'
    for j, bone in enumerate(rig.pose.bones):
        bone.rotation_mode = 'QUATERNION'
        bone.rotation_quaternion = Quaternion(Vector((.7, .2, .3)).normalized(), .09*math.sin(index*.7+j*.2))
    bpy.context.view_layer.update()
    before = {b.name:b.matrix.copy() for b in rig.pose.bones}
    _, encoded = ret.encode_pose(rig, profile, world_origin=(0,0,0))
    ret.apply_rotations(rig, ret.decode_rotations(rig, profile, encoded))
    for name, matrix in before.items():
        current = rig.pose.bones[name].matrix
        maximum_position = max(maximum_position, (matrix.translation-current.translation).length)
        maximum_angle = max(maximum_angle, math.degrees(qm.norm(qm.qlog(qm.qmul(qm.inverse(list(matrix.to_quaternion())), list(current.to_quaternion()))))))
assert maximum_position < 1e-5 and maximum_angle < .05, (maximum_position, maximum_angle)
checks.extend(['translated XYZ playback preserves reviewed mapping', 'six nontrivial native pose round trips', 'orientation-preserving G1 serial-axis factorization'])
rig.scale = (1, 1, 1.1); bpy.context.view_layer.update()
try: ret.load_profile(rig)
except DirectorError as error: assert error.code == 'MOTION_BRICKS_RETARGET_SCALE'
else: raise AssertionError('Nonuniform changed rig accepted')
rig.scale = (1,1,1); bpy.context.view_layer.update()
wrong = dict(roles); wrong['left_thigh'],wrong['right_thigh'] = wrong['right_thigh'],wrong['left_thigh']
try: ret.build_profile(rig, skeleton, wrong, 0.)
except DirectorError as error: assert error.code in ('MOTION_BRICKS_RETARGET_TOPOLOGY','MOTION_BRICKS_RETARGET_GEOMETRY')
else: raise AssertionError('Name-matched but geometrically incorrect mapping accepted')
checks.extend(['changed rig scale rejected', 'wrong anatomical mapping rejected'])
# Imported display tails deliberately differ from child heads. Positional
# retargeting must solve the anatomical chain, not those display lengths.
from asset_director import motion_bricks_feet as feet
for bone in rig.pose.bones:
    bone.location=(0,0,0); bone.rotation_quaternion=Quaternion(); bone.scale=(1,1,1)
rig.location=(0,0,0); bpy.context.view_layer.update()
for side in feet.SIDES:
    foot=rig.pose.bones[roles[side+'_foot']]
    target=rig.matrix_world@foot.head+Vector((0,-.04,.05))
    feet.solve(rig,roles,side,target)
    assert (rig.matrix_world@foot.head-target).length<2e-5
try: feet.solve(rig,roles,'left',Vector((20,0,0)))
except DirectorError as error: assert error.code=='MOTION_BRICKS_FOOT_REACH'
else: raise AssertionError('Unreachable generated foot accepted')
checks.extend(['anatomical child-head IK ignores imported display tails', 'unreachable generated step rejected'])
clone=rig.copy(); clone.data=rig.data.copy(); bpy.context.scene.collection.objects.link(clone)
original_objects=len(bpy.data.objects)
try: feet.Soles(rig,clone,roles)
except DirectorError as error: assert error.code=='MOTION_BRICKS_SOLE_GEOMETRY'
else: raise AssertionError('Missing sole geometry accepted')
assert len(bpy.data.objects)==original_objects
mesh=bpy.data.meshes.new('Synthetic sole geometry'); vertices=[]
for side in feet.SIDES:
    p=Vector(positions[side+'_foot'])
    vertices.extend([p+Vector((x,y,-.1)) for x,y in [(-.04,-.04),(.04,-.04),(.04,.08),(-.04,.08)]])
mesh.from_pydata(vertices,[],[(0,1,2,3),(4,5,6,7)])
skin=bpy.data.objects.new(mesh.name,mesh); bpy.context.scene.collection.objects.link(skin)
for index,side in enumerate(feet.SIDES):
    group=skin.vertex_groups.new(name=roles[side+'_foot']); group.add(list(range(index*4,index*4+4)),1.,'REPLACE')
modifier=skin.modifiers.new('Synthetic real armature deformation','ARMATURE');modifier.object=rig
original_objects=len(bpy.data.objects)
soles=feet.Soles(rig,clone,roles)
assert all(math.isfinite(v) for v in soles.heights().values())
assert len(bpy.data.objects)==original_objects+1
soles.close(); assert len(bpy.data.objects)==original_objects
assert modifier.object==rig and len(mesh.vertices)==8
clone_data=clone.data;bpy.data.objects.remove(clone,do_unlink=True);bpy.data.armatures.remove(clone_data)
checks.extend(['missing sole geometry rejected without leaked objects', 'real evaluated skin sampling preserves original modifier and geometry'])
from asset_director import root_contact_preparation as preparation, action_layer as layer
source=bpy.data.actions.new('Synthetic native in-place source');ad=rig.animation_data_create();ad.action=source
spine=rig.pose.bones[roles['spine']]
for frame in (0.,12.):
    rig.location=(.02*frame,0,0);rig.keyframe_insert('location',frame=frame)
    spine.rotation_quaternion=Quaternion((1,0,0),.02*frame);spine.keyframe_insert('rotation_quaternion',frame=frame)
source_hash=digest(layer.channels(source));source_slot=ad.action_slot
options={'schema':'root-contact-preparation-v1','profile_sha256':original,'clips':[
    {'action':source.name,'source_sha256':source_hash,'name':'Prepared synthetic native travel',
     'placement_delta_m':[.3,0.],'contacts':[{'side':'left','start':0.,'end':12.,'mesh':skin.name,'vertex':0}]}]}
# Exercise preparation on a real managed timeline, including its strict native
# source identity, rather than only an unbound isolated Action.
audit=layer.audit();performer=next(p for p in audit['performers'] if p['name']==rig.name);take=next(t for t in performer['takes'] if t['action']==source.name)
layer.apply({'version':'action-layer-v1','audit_sha256':audit['sha256'],'frame_range':[1,13],
    'changes':[{'performer':rig.name,'mode':'timeline','clips':[{'id':'clip_native','take_id':take['id'],'start':1,'frames':13,'speed':1,'repeat_reviewed':False,'travel':None}]}]},'source-preparation-contract')
original_action=ad.action;original_slot=ad.action_slot;original_tracks=[layer.track_record(t) for t in ad.nla_tracks]
original_objects=len(bpy.data.objects);report=preparation.prepare(rig,options)
prepared=bpy.data.actions[report[0]['result']]
assert digest(layer.channels(source))==source_hash and ad.action==original_action and ad.action_slot==original_slot
assert [c for c in layer.channels(source) if c[0]!='location']==[c for c in layer.channels(prepared) if c[0]!='location']
assert len(bpy.data.objects)==original_objects
assert all(t.mute for t in ad.nla_tracks if any(s.action==prepared for s in t.strips))
assert len(prepared.get('bad_root_contact_preparation_v1'))>0
from asset_director import native_motion_basis,action_timeline
native_motion_basis.capture(rig);action_timeline.load(rig)
assert [layer.track_record(t) for t in ad.nla_tracks][:len(original_tracks)]==original_tracks
checks.append('root preparation preserves source curves, active Action, slots, timeline and skin')
import copy
invalid=copy.deepcopy(options);invalid['clips'][0]['name']='Must not be created';invalid['clips'][0]['contacts'][0]['vertex']=7
try: preparation.prepare(rig,invalid)
except DirectorError as error: assert error.code=='ROOT_CONTACT_VERTEX'
else: raise AssertionError('Opposite-foot vertex accepted')
assert 'Must not be created' not in bpy.data.actions and len(bpy.data.objects)==original_objects
checks.append('wrong-foot contact landmark refused without partial Action or orphan clone')
bpy.ops.wm.save_as_mainfile(filepath=str(out/'profile.blend'))
rig_name=rig.name
bpy.ops.wm.open_mainfile(filepath=str(out/'profile.blend'))
assert digest(ret.load_profile(bpy.data.objects[rig_name])) == original
checks.append('saved mapping reopens unchanged')
atomic_json(out/'RESULTS.json', {'status':'PASS', 'input_kind':'GENERATED', 'checks':checks,
    'max_position_rig_units':maximum_position, 'max_orientation_degrees':maximum_angle,
    'actual_provider_execution':'NOT_APPLICABLE_CONTRACT_FIXTURE'})
