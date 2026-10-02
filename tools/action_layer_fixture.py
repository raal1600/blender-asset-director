"""Generated two-performer Action regression. No user files or visual approval."""
from pathlib import Path
import sys
import json
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director import action_layer as action, blender_ops as ops, jobs
from asset_director.core import Library, atomic_json, file_hash, load_json, DirectorError

source, out = map(Path, sys.argv[sys.argv.index('--') + 1:])
assert source.name == 'placed.blend' and load_json(source.parent / 'world_layers_report.json')['status'] == 'PASS'
out.mkdir(parents=True, exist_ok=False)
checks = []
original = file_hash(source)


def check(value, label):
    assert value, label
    checks.append(label)


def run(lib, op, file, options):
    prepared = jobs.prepare(lib, op, str(file), options=options)
    finished = jobs.run(lib, prepared['id'], blender=bpy.app.binary_path, timeout=180)
    assert finished['state'] == 'SUCCEEDED', finished
    return lib.root / 'jobs' / prepared['id'] / 'result.blend', load_json(lib.root / 'jobs' / prepared['id'] / 'result.json')['data']


def point(name):
    obj = bpy.data.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get())
    return sum((obj.matrix_world @ v.co for v in obj.data.vertices), Vector()) / len(obj.data.vertices)


try:
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    rig = bpy.data.objects['SyntheticRig0'];native = rig.animation_data.action;slot = rig.animation_data.action_slot
    alternate = native.copy();alternate.name = 'Synthetic Alternate'
    track = action.add_strip(rig, alternate, alternate.slots[0], 'Bundled alternative', 1, [1, 9], 1);track.mute = True
    # Shared action remains separately bound to its actual performer; no bone-name inference.
    loose = native.copy();loose.name = 'Unbound lookalike';loose.use_fake_user = True
    prop = bpy.data.objects['StaticProp']
    for frame, offset in [(1, 0), (5, 1), (9, 0)]:
        prop.location.z = offset;prop.keyframe_insert('location', frame=frame)
    bpy.context.scene.frame_set(5)
    baseline = out / 'source.blend';bpy.ops.wm.save_as_mainfile(filepath=str(baseline))
    bpy.ops.wm.open_mainfile(filepath=str(baseline), load_ui=False, use_scripts=False)
    initial = action.audit();snapshot = action.preserved(set());hash_before = file_hash(baseline)
    check(any(x['action'] == 'Unbound lookalike' for x in initial['unassigned']), 'unbound lookalike stays outside native take choices')
    by_name = {p['name']: p for p in initial['performers']}
    check(len(by_name['SyntheticRig0']['takes']) == 2 and len(by_name['SyntheticRig1']['takes']) == 1, 'takes belong to their actual performer')
    take = next(t for t in by_name['SyntheticRig0']['takes'] if t['action'] == 'Synthetic Alternate')
    foreign = by_name['SyntheticRig1']['takes'][0]
    prop_take = by_name['StaticProp']['takes'][0]
    options = {'version': action.contract.VERSION, 'audit_sha256': initial['sha256'], 'frame_range': [1, 12],
               'changes': [{'performer': 'SyntheticRig0', 'mode': 'clip', 'take_id': take['id'], 'start': 3, 'speed': 2},
                           {'performer': 'StaticProp', 'mode': 'clip', 'take_id': prop_take['id'], 'start': 3, 'speed': 2}]}
    for patch, code in [({'audit_sha256': '0' * 64}, 'ACTION_CHANGED'),
                        ({'changes': options['changes'] + [{'performer': 'SyntheticRig1', 'mode': 'clip', 'take_id': take['id'], 'start': 1, 'speed': 1}]}, 'ACTION_BINDING_CHANGED')]:
        try:action.apply(options | patch, 'synthetic-refusal')
        except DirectorError as error:check(error.code == code and action.preserved(set()) == snapshot, 'prevalidation preserves full scene on ' + code)
        else:raise AssertionError('Invalid request executed')
    constrained = bpy.data.objects['SyntheticRig1'];constraint = constrained.constraints.new('LIMIT_LOCATION')
    constrained_audit = action.audit();snapshot_constrained = action.preserved(set())
    try:action.apply({'version': action.contract.VERSION, 'audit_sha256': constrained_audit['sha256'],
                     'changes': [{'performer': constrained.name, 'mode': 'hold', 'frame': 5}]}, 'synthetic-constraint-refusal')
    except DirectorError as error:check(error.code == 'ACTION_UNSUPPORTED' and action.preserved(set()) == snapshot_constrained, 'constrained performer refuses before mutation')
    else:raise AssertionError('Constraint was silently overridden')
    constrained.constraints.remove(constraint)
    with Library(out / 'library') as lib:
        edited, report = run(lib, 'action-edit', baseline, options)
        check(report['reopened'] and report['performance_acceptance'] == 'NOT_EVALUATED', 'real worker verifies reopened output without performance approval')
        bpy.ops.wm.open_mainfile(filepath=str(edited), load_ui=False, use_scripts=False)
        item = report['changes'][0]['track']['strips'][0]
        check(item['start'] == 3 and item['end'] == 7 and item['scale'] == .5 and item['repeat'] == 1, 'full take retimed without changing native FPS or keys')
        points = []
        for frame in [3, 5, 7]:bpy.context.scene.frame_set(frame);points.append(point('SyntheticSkin0'))
        check((points[1] - points[0]).length > .1, 'retimed rig actually deforms its skin over time')
        prop_points = []
        for frame in [3, 5, 7]:bpy.context.scene.frame_set(frame);prop_points.append(point('StaticProp'))
        check((prop_points[1] - prop_points[0]).length > .5, 'same batch retimes actual object motion independently')
        check(bpy.data.objects['SyntheticRig1'].animation_data.action.name == foreign['action'], 'other performer native action remains assigned')
        bpy.context.scene.frame_set(3);other_held = point('SyntheticSkin1').copy()
        bpy.context.scene.frame_set(5);held_point = point('SyntheticSkin0').copy();inspection = action.audit()
        bpy.ops.wm.save_as_mainfile(filepath=str(out / 'hold-input.blend'))
        held, held_report = run(lib, 'action-edit', out / 'hold-input.blend', {'version': action.contract.VERSION,
             'audit_sha256': inspection['sha256'], 'changes': [{'performer': 'SyntheticRig0', 'mode': 'hold', 'frame': 5},
                                                            {'performer': 'SyntheticRig1', 'mode': 'hold', 'frame': 3}]})
        bpy.ops.wm.open_mainfile(filepath=str(held), load_ui=False, use_scripts=False)
        for frame in [1, 5, 12]:
            bpy.context.scene.frame_set(frame)
            check((point('SyntheticSkin0') - held_point).length < 1e-5, 'held pose remains static at frame ' + str(frame))
            check((point('SyntheticSkin1') - other_held).length < 1e-5, 'second performer holds its different sampled pose at frame ' + str(frame))
        check(held_report['reopened'] and any(t['action'] == 'Synthetic Alternate' for p in held_report['action_audit']['performers'] if p['name'] == 'SyntheticRig0' for t in p['takes']), 'held pose retains original native motion choices')
    check(file_hash(source) == original and file_hash(baseline) == hash_before, 'all original source/checkpoint bytes preserved')
    atomic_json(out / 'RESULTS.json', {'status': 'PASS', 'checks': checks, 'blender': bpy.app.version_string,
                                     'scope': 'REAL_GENERATED_NATIVE_ACTION', 'human_review': 'NOT_TESTED'})
    print(json.dumps({'status': 'PASS', 'checks': len(checks)}))
except Exception as error:
    atomic_json(out / 'RESULTS.json', {'status': 'FAIL', 'checks': checks, 'error': repr(error)})
    raise
