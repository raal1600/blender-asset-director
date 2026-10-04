"""Real Blender save/reopen/edit regression for source-bound pace calibration.

Only generated limbs are used. No contact, naturalness or human approval claim.
Run: blender -b --factory-startup --python native_calibration_fixture.py -- OUT
"""
from pathlib import Path
import sys
import math
import json
sys.dont_write_bytecode = True
import bpy
from mathutils import Quaternion, Matrix
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from asset_director import action_layer as layer, native_motion_basis as basis
from asset_director.action_timeline_contract import timing
from asset_director.core import atomic_json, file_hash, DirectorError

out = Path(sys.argv[sys.argv.index('--') + 1])
assert not out.exists(), 'Evidence is new-only'
out.mkdir(parents=True)
checks = []


def check(ok, label):
    assert ok, label
    checks.append(label)


def generated():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 24
    scene.frame_end = 250
    data = bpy.data.armatures.new('Generated calibration limbs')
    rig = bpy.data.objects.new('CalibrationSubject', data)
    scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    root = data.edit_bones.new('Core')
    root.head, root.tail = (0, 0, 1.8), (0, 0, 2)
    for side, x in [('A', -.2), ('B', .2)]:
        upper = data.edit_bones.new('Upper' + side)
        upper.head, upper.tail, upper.parent = (x, 0, 1.8), (x, 0, .9), root
        lower = data.edit_bones.new('Lower' + side)
        lower.head, lower.tail, lower.parent = upper.tail, (x, 0, 0), upper
        toe = data.edit_bones.new('Support' + side)
        toe.head, toe.tail, toe.parent = lower.tail, (x, -.1, 0), lower
    bpy.ops.object.mode_set(mode='OBJECT')
    for index in range(65):
        for side, phase in [('A', index / 64 % 1), ('B', (index / 64 + .5) % 1)]:
            y = .4 - 1.6 * phase if phase < .5 else -.4 + 1.6 * (phase - .5)
            z = .12 + (0 if phase < .5 else .16 * math.sin(2 * math.pi * (phase - .5)))
            bend = math.acos(math.hypot(y, 1.8 - z) / 1.8)
            angle = math.atan2(y, 1.8 - z)
            for name, value in [('Upper' + side, angle - bend), ('Lower' + side, 2 * bend)]:
                bone = rig.pose.bones[name]
                rest = bone.bone.matrix_local.to_quaternion()
                bone.rotation_mode = 'QUATERNION'
                bone.rotation_quaternion = rest.inverted() @ Quaternion((1, 0, 0), value) @ rest
                bone.keyframe_insert('rotation_quaternion', frame=1 + index * 24 / 64)
    first = rig.animation_data.action
    first.name = 'Generated cycle A'
    for curve in layer.ops.curves(first):
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'
    second = first.copy()
    second.name = 'Generated cycle B'
    slot = next(iter(getattr(second, 'slots', [])), None)
    track = layer.add_strip(rig, second, slot, 'Retained second native take', 1, [1, 25], 1)
    track.mute = True
    # Nontrivial static space exposes decomposition/cancellation drift that an
    # identity-origin fixture misses. It is not a production-time preset.
    parent = bpy.data.objects.new('Generated placement', None)
    scene.collection.objects.link(parent)
    parent.location = (13.713, -8.257, 0)
    parent.scale = (.94578755,) * 3
    parent.rotation_euler.z = .6149
    rig.parent = parent
    scene.frame_set(90)
    return rig


def inspected():
    audit = layer.audit()
    return audit, next(p for p in audit['performers'] if p['name'] == 'CalibrationSubject')


def validate_static_change(rig, mutate, restore, label):
    mutate()
    bpy.context.view_layer.update()
    try:
        basis.capture(rig)
    except DirectorError:
        check(True, label)
    else:
        raise AssertionError(label)
    finally:
        restore()
        bpy.context.view_layer.update()


try:
    rig = generated()
    source = out / 'source.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    source_hash = file_hash(source)
    audit, performer = inspected()
    a, b = [next(t for t in performer['takes'] if t['action'] == name)
            for name in ['Generated cycle A', 'Generated cycle B']]
    g = a['gait']
    check(g['status'] == 'estimated', 'Generated native supports have a measured pace')
    clip_a = {'id': 'clip_first', 'take_id': a['id'], 'start': 1, 'frames': 25,
              'speed': 1, 'repeat_reviewed': False,
              'travel': {'delta_m': [v * g['meters_per_cycle'] for v in g['direction']],
                         'meters_per_cycle': g['meters_per_cycle'], 'gait_id': g['id']}}
    clip_b = {'id': 'clip_second', 'take_id': b['id'], 'start': 32, 'frames': 25,
              'speed': 1, 'repeat_reviewed': False,
              'travel': {'delta_m': [v * g['meters_per_cycle'] for v in g['direction']],
                         'meters_per_cycle': g['meters_per_cycle']},
              'transition': {'frames': 6, 'match_phase': False}}
    options = {'version': 'action-layer-v1', 'audit_sha256': audit['sha256'],
               'frame_range': [1, 250], 'changes': [{'performer': rig.name, 'mode': 'timeline', 'clips': [clip_a, clip_b]}]}
    report = layer.apply(options, 'native-calibration-first')
    first = out / 'connected.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(first))
    layer.verify_saved(report, first)
    first_hash = file_hash(first)
    profiles = []
    for frame in [1, 40, 90, 250]:
        bpy.context.scene.frame_set(frame)
        fresh, p = inspected()
        current = next(t for t in p['takes'] if t['id'] == a['id'])
        profiles.append(current['gait'])
        check(current['gait'] == g, f'Saved native calibration is exact at frame {frame}')
        for c in p['timeline']['clips']:
            timing(c, next(t for t in p['takes'] if t['id'] == c['take_id']))
    check('native_basis' in report['changes'][0]['timeline'], 'Saved timeline retains verified native defaults')
    # Edit B again: A is bytewise unchanged and fresh calibration remains valid.
    edited_b = {**clip_b, 'frames': 37, 'repeat_reviewed': True,
                'travel': {**clip_b['travel'], 'delta_m': [v * 1.5 for v in clip_b['travel']['delta_m']]}}
    second_options = {**options, 'audit_sha256': fresh['sha256'],
                      'changes': [{'performer': 'CalibrationSubject', 'mode': 'timeline', 'clips': [clip_a, edited_b]}]}
    second_report = layer.apply(second_options, 'native-calibration-edit')
    second = out / 'edited.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(second))
    layer.verify_saved(second_report, second)
    check(second_report['changes'][0]['timeline']['clips'][0] == clip_a,
          'Editing a following clip preserves the first clip exactly')
    check(file_hash(first) == first_hash and file_hash(source) == source_hash,
          'Both original input and prior saved checkpoint remain bytewise unchanged')
    rig = bpy.context.scene.objects['CalibrationSubject']
    scene = bpy.context.scene
    unit = scene.unit_settings.scale_length
    validate_static_change(rig, lambda: setattr(scene.unit_settings, 'scale_length', unit * 2),
                           lambda: setattr(scene.unit_settings, 'scale_length', unit), 'Changed units invalidate saved native basis')
    x = rig.parent.location.x
    validate_static_change(rig, lambda: setattr(rig.parent.location, 'x', x + .1),
                           lambda: setattr(rig.parent.location, 'x', x), 'Changed static parent placement invalidates saved native basis')
    support = rig.pose.bones['SupportA']
    scale = support.scale.x
    validate_static_change(rig, lambda: setattr(support.scale, 'x', scale + .01),
                           lambda: setattr(support.scale, 'x', scale), 'Changed unkeyed native pose invalidates saved native basis')
    action = bpy.data.actions['Generated cycle A']
    key = layer.ops.curves(action)[0].keyframe_points[0]
    value = key.co.y
    validate_static_change(rig, lambda: setattr(key.co, 'y', value + .01),
                           lambda: setattr(key.co, 'y', value), 'Changed exact native keys invalidate saved native basis')
    original_data = rig.data
    changed_data = original_data.copy()
    changed_data.transform(Matrix.Translation((0, 0, .01)))
    validate_static_change(rig, lambda: setattr(rig, 'data', changed_data),
                           lambda: setattr(rig, 'data', original_data), 'Changed native rest geometry invalidates saved native basis')
    bpy.data.armatures.remove(changed_data)
    bone = rig.data.bones['LowerA']
    for field, replacement in [('inherit_scale', 'NONE'), ('use_inherit_rotation', False),
                               ('use_local_location', False), ('use_relative_parent', True)]:
        value = getattr(bone, field)
        assert value != replacement, f'Generated fixture needs a changed {field}'
        validate_static_change(rig, lambda f=field, v=replacement: setattr(bone, f, v),
                               lambda f=field, v=value: setattr(bone, f, v),
                               f'Changed bone {field} invalidates saved native basis')
    pose_position = rig.data.pose_position
    validate_static_change(rig, lambda: setattr(rig.data, 'pose_position', 'REST'),
                           lambda: setattr(rig.data, 'pose_position', pose_position),
                           'Changed armature pose position invalidates saved native basis')
    # Bone.use_connect is observed read-only; its actual editing surface is
    # EditBone. Exercise it on a disposable data copy, then restore exact data.
    original_data = rig.data
    connected_data = original_data.copy()
    rig.data = connected_data
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    connected_data.edit_bones['LowerA'].use_connect = True
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.data = original_data
    validate_static_change(rig, lambda: setattr(rig, 'data', connected_data),
                           lambda: setattr(rig, 'data', original_data),
                           'Changed bone connected-parent behavior invalidates saved native basis')
    bpy.data.armatures.remove(connected_data)
    # The supported 256-bone ceiling also needs a bounded but sufficient saved
    # metadata budget. Long names and nontrivial unkeyed defaults expose the old
    # 200000-character ceiling without adding animation sampling work.
    large_rig = generated()
    bpy.context.view_layer.objects.active = large_rig
    large_rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for index in range(256 - len(large_rig.data.edit_bones)):
        bone = large_rig.data.edit_bones.new(f'Generated metadata support {index:03d} ' + 'long_name_' * 3)
        bone.head = (index * .0314159, .271828, 1.23456)
        bone.tail = (index * .0314159 + .21234, .57391, 1.85439)
        bone.use_deform = False
    bpy.ops.object.mode_set(mode='OBJECT')
    for bone in large_rig.pose.bones:
        if not bone.bone.use_deform:
            bone.location = (1.1234567, 2.2345678, 3.3456789)
            bone.rotation_euler = (.1234567, .2345678, .3456789)
            bone.scale = (1.0123456, 1.0234567, 1.0345678)
    large_audit, large_p = inspected()
    large_take = next(t for t in large_p['takes'] if t['action'] == 'Generated cycle A')
    large_gait = large_take['gait']
    check(large_gait['status'] == 'estimated' and len(large_rig.data.bones) == 256,
          'Maximum supported rig retains bounded support sampling')
    large_clip = {**clip_a, 'take_id': large_take['id'], 'travel': {
        'delta_m': [v * large_gait['meters_per_cycle'] for v in large_gait['direction']],
        'meters_per_cycle': large_gait['meters_per_cycle'], 'gait_id': large_gait['id']}}
    large_report = layer.apply({**options, 'audit_sha256': large_audit['sha256'],
                               'changes': [{'performer': large_rig.name, 'mode': 'timeline', 'clips': [large_clip]}]},
                              'maximum-native-metadata')
    raw = large_rig.get('bad_action_timeline_v1')
    metadata_bytes = len(raw.encode('utf-8'))
    check(200000 < metadata_bytes <= basis.MAX_TIMELINE_JSON_BYTES,
          '256-bone exact baseline fits explicit 2 MiB metadata limit, not old 200000 limit')
    maximum = out / 'maximum-rig.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(maximum))
    layer.verify_saved(large_report, maximum)
    large_rig = bpy.context.scene.objects['CalibrationSubject']
    original_metadata = large_rig['bad_action_timeline_v1']
    try:
        large_rig['bad_action_timeline_v1'] = json.dumps({'unused': 'é' * (basis.MAX_TIMELINE_JSON_BYTES // 2)}, ensure_ascii=False)
        try:
            basis.capture(large_rig)
        except DirectorError as error:
            check('oversized' in str(error), 'Metadata guard counts UTF-8 bytes before parsing')
        else:
            raise AssertionError('Oversized native metadata accepted')
    finally:
        large_rig['bad_action_timeline_v1'] = original_metadata
    result = {'status': 'PASS', 'checks': checks, 'blender': bpy.app.version_string,
              'profile': g, 'source_sha256': source_hash, 'first_sha256': first_hash,
              'second_sha256': file_hash(second), 'human_review': 'NOT_TESTED', 'inputs': 'GENERATED',
              'maximum_rig_metadata_bytes': metadata_bytes}
except Exception as error:
    result = {'status': 'FAIL', 'checks': checks, 'error': repr(error)}
    atomic_json(out / 'RESULTS.json', result)
    raise
atomic_json(out / 'RESULTS.json', result)
print({'status': result['status'], 'checks': len(checks)})
