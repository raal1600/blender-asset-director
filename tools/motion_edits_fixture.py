"""Actual generated Blender source trims/replacement/explicit heading preview.

No licensed inputs, user scene, render, inferred anatomy or artistic approval.
"""
from pathlib import Path
import math
import sys
import bpy
from mathutils import Vector, Quaternion, Euler
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from asset_director import action_layer as layer, action_timeline as timeline, motion_heading
from asset_director.core import atomic_json, file_hash, DirectorError

out = Path(sys.argv[sys.argv.index('--')+1]); out.mkdir(parents=True, exist_ok=False)
checks = []


def check(ok, label):
    assert ok, label
    checks.append(label)


def frame(value):
    bpy.context.scene.frame_set(math.floor(value), subframe=value % 1)
    bpy.context.view_layer.update()


def quat_distance(a, b):
    return min((a-b).magnitude, (a+b).magnitude)


try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene; scene.frame_end = 100; scene.unit_settings.scale_length = .5
    parent = bpy.data.objects.new('Static World placement', None); scene.collection.objects.link(parent)
    parent.rotation_euler.z = .4; parent.scale = (2., 2., 2.)
    parent['bad_placement_control'] = 1
    data = bpy.data.armatures.new('Synthetic native rig data')
    obj = bpy.data.objects.new('Synthetic native performer', data); scene.collection.objects.link(obj)
    obj.parent = parent; obj.rotation_euler.z = .3; obj.delta_rotation_euler.z = .2
    bpy.context.view_layer.objects.active = obj; obj.select_set(True); bpy.ops.object.mode_set(mode='EDIT')
    bone = data.edit_bones.new('ObservedJoint'); bone.tail = (0., 0., 1.)
    bpy.ops.object.mode_set(mode='OBJECT'); joint = obj.pose.bones['ObservedJoint']; joint.rotation_mode = 'XYZ'
    for index in range(2):
        action = bpy.data.actions.new('Native source '+str(index)); obj.animation_data_create().action = action
        for i in range(25):
            joint.rotation_euler = (0., 0., 0.)
            joint.rotation_euler[index] = .3*math.sin(2*math.pi*i/24)
            joint.keyframe_insert('rotation_euler', frame=i+1)
        for curve in layer.ops.curves(action):
            for key in curve.keyframe_points:
                key.interpolation = 'LINEAR'
        slot = getattr(obj.animation_data, 'action_slot', None)
        layer.add_strip(obj, action, slot, 'Original source '+str(index), 1, [1, 25], 1).mute = True
    frame(1)
    bpy.ops.mesh.primitive_cube_add(size=.2, location=(0., 0., .5))
    skin = bpy.context.object; skin.name = 'Synthetic skin'; skin.parent = obj
    skin.vertex_groups.new(name='ObservedJoint').add(list(range(8)), 1., 'REPLACE')
    skin.modifiers.new('Native skin', 'ARMATURE').object = obj
    original = out/'original.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(original)); original_hash = file_hash(original)
    audit = layer.audit(); performer = next(p for p in audit['performers'] if p['name'] == obj.name)
    takes = sorted(performer['takes'], key=lambda t: t['action']); a, b = takes
    check(all(t['heading_blocker'] is None for t in takes), 'observed native heading eligibility uses no animation names or bone roles')
    native_hashes = {action.name: layer.digest(layer.channels(action)) for action in bpy.data.actions}
    first = {'id': 'clip_first', 'take_id': a['id'], 'start': 1, 'frames': 25, 'speed': 1.,
             'repeat_reviewed': False, 'travel': {'delta_m': [0., -1.], 'meters_per_cycle': 1.}}
    second = first | {'id': 'clip_second', 'take_id': b['id'], 'start': 38, 'heading_deg': 90.,
                      'travel': {'delta_m': [-1., 0.], 'meters_per_cycle': 1.},
                      'transition': {'frames': 12, 'match_phase': False, 'mode': 'turn'}}
    request = {'version': 'action-layer-v1', 'audit_sha256': audit['sha256'], 'frame_range': [1, 100],
               'changes': [{'performer': obj.name, 'mode': 'timeline', 'clips': [first, second]}]}
    result = layer.apply(request, 'synthetic-heading')
    saved = out/'heading.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(saved)); layer.verify_saved(result, saved)
    check(result['reopened'], 'heading and generated turn saved and reopened independently')
    obj = bpy.data.objects['Synthetic native performer']; joint = obj.pose.bones['ObservedJoint']
    positions, rotations = {}, {}
    for value in (1, 25, 28.25, 31.5, 34.75, 38, 44, 50, 62):
        frame(value); positions[value] = obj.matrix_world.translation.copy()*.5
        rotations[value] = obj.matrix_world.to_quaternion()
    base_q = Quaternion((0, 0, 1), .9)
    check(quat_distance(rotations[25], base_q) < 1e-5 and
          quat_distance(rotations[31.5], Quaternion((0, 0, 1), math.pi/4) @ base_q) < 1e-5 and
          quat_distance(rotations[38], Quaternion((0, 0, 1), math.pi/2) @ base_q) < 1e-5,
          'explicit body heading turns only in its added interval with rotated scaled World parent and preserved base delta')
    check((positions[28.25]-positions[34.75]).length < 1e-5, 'turn path has a visible stationary middle interval, not diagonal continuation')
    check((positions[62]-positions[38]-Vector((-1., 0., 0.))).length < 1e-5,
          'incoming clip retains exact requested travel after its separate turn')
    for value in (38, 44, 50, 62):
        frame(value)
        expected = .3*math.sin(2*math.pi*(value-38)/24)
        check(abs(joint.rotation_euler.x) < 1e-5 and abs(joint.rotation_euler.y-expected) < 1e-5,
              'incoming native source B replaces A exactly at saved frame '+str(value))
    check(all(layer.digest(layer.channels(bpy.data.actions[name])) == signature for name, signature in native_hashes.items()),
          'all original source Action channels remain byte-identical in value')
    frame(1); fresh = layer.audit()
    check(next(p for p in fresh['performers'] if p['name'] == obj.name)['timeline']['error'] is None,
          'saved source defaults and timeline remain editable after heading playback')
    previous_hash = file_hash(saved)
    # Trim and split retain the exact native source positions at discrete frames.
    trimmed = first | {'travel': None, 'source_range': [7., 19.], 'frames': 13}
    split_a = trimmed | {'source_range': [7., 12.], 'frames': 6}
    split_b = trimmed | {'id': 'clip_split', 'source_range': [13., 19.], 'start': 7, 'frames': 7}
    revised = layer.apply(request | {'audit_sha256': fresh['sha256'], 'changes': [
        {'performer': obj.name, 'mode': 'timeline', 'clips': [split_a, split_b]}]}, 'synthetic-trim-split')
    revision = out/'trim-split.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(revision)); layer.verify_saved(revised, revision)
    obj = bpy.data.objects['Synthetic native performer']; joint = obj.pose.bones['ObservedJoint']
    for value in (1, 6, 7, 13):
        frame(value); expected = .3*math.sin(2*math.pi*(value+5)/24)
        check(abs(joint.rotation_euler.x-expected) < 1e-5 and abs(joint.rotation_euler.y) < 1e-5,
              'split source range preserves discrete native sample at frame '+str(value))
    check(file_hash(saved) == previous_hash and file_hash(original) == original_hash,
          'previous checkpoint and original scene bytes remain untouched')
    frame(1); fresh = layer.audit(); empty = layer.apply(request | {'audit_sha256': fresh['sha256'],
        'changes': [{'performer': obj.name, 'mode': 'timeline', 'clips': []}]}, 'synthetic-empty')
    empty_path = out/'empty.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(empty_path)); layer.verify_saved(empty, empty_path)
    check(empty['reopened'], 'empty edited timeline saves and reopens without resurrecting old sources')
    for mode in ('QUATERNION', 'ZYX'):
        bpy.ops.wm.open_mainfile(filepath=str(original), load_ui=False, use_scripts=False)
        obj = bpy.data.objects['Synthetic native performer']; parent = obj.parent
        parent.rotation_euler = (.25, .1, .4)
        base = Euler((.2, .3, .4)).to_quaternion(); delta = Euler((.1, -.2, .15)).to_quaternion()
        obj.rotation_mode = mode
        if mode == 'QUATERNION':
            obj.rotation_quaternion = base; obj.delta_rotation_quaternion = delta
        else:
            obj.rotation_euler = base.to_euler(mode); obj.delta_rotation_euler = delta.to_euler(mode)
        frame(1); neutral = obj.matrix_world.to_quaternion(); audit = layer.audit()
        performer = next(p for p in audit['performers'] if p['name'] == obj.name)
        take = performer['takes'][0]
        clip = first | {'take_id': take['id'], 'heading_deg': 75., 'travel': None}
        edited = layer.apply(request | {'audit_sha256': audit['sha256'], 'changes': [
            {'performer': obj.name, 'mode': 'timeline', 'clips': [clip]}]}, 'synthetic-heading-'+mode)
        target = out/('heading-'+mode+'.blend'); bpy.ops.wm.save_as_mainfile(filepath=str(target)); layer.verify_saved(edited, target)
        obj = bpy.data.objects['Synthetic native performer']; frame(13)
        check(quat_distance(obj.matrix_world.to_quaternion(), Quaternion((0, 0, 1), math.radians(75)) @ neutral) < 2e-5,
              mode+' heading preserves mixed native base orientation and mode without moving World placement')
    bpy.ops.wm.open_mainfile(filepath=str(original), load_ui=False, use_scripts=False)
    obj = bpy.data.objects['Synthetic native performer']; obj.rotation_mode = 'AXIS_ANGLE'
    frame(1); audit = layer.audit(); performer = next(p for p in audit['performers'] if p['name'] == obj.name)
    check(all('axis-angle' in t['heading_blocker'] for t in performer['takes']),
          'native object axis-angle heading is explicitly unsupported without changing its rotation owner')
    bpy.ops.wm.open_mainfile(filepath=str(original), load_ui=False, use_scripts=False)
    obj = bpy.data.objects['Synthetic native performer']; obj.parent.scale = (1., 2., 1.)
    frame(1); audit = layer.audit(); performer = next(p for p in audit['performers'] if p['name'] == obj.name)
    take = performer['takes'][0]
    check('uniformly scaled' in take['heading_blocker'], 'nonuniform parent heading limitation is exposed before Save')
    before_refusal = layer.preserved(set())
    try:
        layer.apply(request | {'audit_sha256': audit['sha256'], 'changes': [
            {'performer': obj.name, 'mode': 'timeline', 'clips': [first | {'take_id': take['id'], 'heading_deg': 45., 'travel': None}]}]}, 'synthetic-refused-heading')
    except DirectorError:
        check(layer.preserved(set()) == before_refusal, 'unsupported heading refuses without source or scene mutation')
    else:
        raise AssertionError('Nonuniform parent heading unexpectedly accepted')
    bpy.ops.wm.open_mainfile(filepath=str(saved), load_ui=False, use_scripts=False)
    obj = bpy.data.objects['Synthetic native performer']; obj.pose.bones['ObservedJoint'].scale.z += .2
    frame(1); audit = layer.audit(); before_refusal = layer.preserved(set())
    try:
        layer.apply(request | {'audit_sha256': audit['sha256']}, 'synthetic-stale-native-default')
    except DirectorError:
        check(layer.preserved(set()) == before_refusal, 'changed unkeyed native defaults refuse instead of silently redefining saved heading or pace')
    else:
        raise AssertionError('Changed native defaults unexpectedly accepted')
    # Blender permits duplicate NLA track labels and truncates them at 63 bytes.
    # Real UUID clip IDs previously removed the distinguishing job suffix.
    bpy.ops.wm.open_mainfile(filepath=str(original), load_ui=False, use_scripts=False)
    obj = bpy.data.objects['Synthetic native performer']
    for track in obj.animation_data.nla_tracks:
        track.name = 'Legacy duplicate native label'
    check(len({t.name for t in obj.animation_data.nla_tracks}) == 1,
          'generated legacy fixture retains genuinely duplicate native track labels')
    frame(1); audit = layer.audit(); performer = next(p for p in audit['performers'] if p['name'] == obj.name)
    a, b = sorted(performer['takes'], key=lambda t: t['action'])
    long_first = first | {'id': 'clip_11111111-1111-4111-8111-111111111111', 'take_id': a['id']}
    long_second = second | {'id': 'clip_22222222-2222-4222-8222-222222222222', 'take_id': b['id']}
    prior_outputs = {}
    for index, incoming in enumerate((long_second, long_second | {'frames': 37, 'repeat_reviewed': True,
            'travel': {'delta_m': [-1.5, 0.], 'meters_per_cycle': 1.}},
            long_second | {'frames': 19, 'travel': None, 'source_range': [3., 21.]})):
        obj.animation_data.nla_tracks.active = obj.animation_data.nla_tracks[0]
        frame(1); audit = layer.audit()
        before_tracks = [layer.track_record(t) for t in obj.animation_data.nla_tracks]
        edited = layer.apply(request | {'audit_sha256': audit['sha256'], 'changes': [
            {'performer': obj.name, 'mode': 'timeline', 'clips': [long_first, incoming]}]}, 'j_'+str(index+1)*24)
        target = out/('long-id-revision-'+str(index)+'.blend')
        bpy.ops.wm.save_as_mainfile(filepath=str(target)); layer.verify_saved(edited, target)
        obj = bpy.data.objects['Synthetic native performer']
        after_tracks = [layer.track_record(t) for t in obj.animation_data.nla_tracks]
        check(after_tracks[:len(before_tracks)] == [dict(t, mute=True) for t in before_tracks],
              'revision '+str(index)+' preserves every ordered prior native track even with duplicate labels')
        new_names = [t['name'] for t in after_tracks[len(before_tracks):]]
        check(len(set(new_names)) == len(new_names) and not set(new_names).intersection(t['name'] for t in before_tracks)
              and all(len(n.encode('utf-8')) <= 63 for n in new_names),
              'revision '+str(index)+' generated labels remain bounded and distinct with full UUID clip IDs')
        check(all(file_hash(path) == signature for path, signature in prior_outputs.items()),
              'revision '+str(index)+' leaves all earlier saved outputs intact')
        prior_outputs[target] = file_hash(target)
    prior_track = obj.animation_data.nla_tracks[0]
    prior_track.strips[0].frame_start += 1
    try:
        layer.verify_previous_tracks(obj, edited['changes'][0]['previous_tracks'])
    except DirectorError:
        check(True, 'exact ordered verification still rejects a real change in a retained duplicate-label track')
    else:
        raise AssertionError('Modified old native strip incorrectly accepted')
    atomic_json(out/'RESULTS.json', {'status': 'PASS', 'checks': checks, 'input_kind': 'GENERATED',
                                   'blender': bpy.app.version_string, 'human_review': 'NOT_TESTED',
                                   'foot_locking': 'NOT_IMPLEMENTED', 'original_sha256': original_hash})
    print({'status': 'PASS', 'checks': len(checks)})
except Exception as error:
    atomic_json(out/'RESULTS.json', {'status': 'FAIL', 'checks': checks, 'error': repr(error)})
    raise
