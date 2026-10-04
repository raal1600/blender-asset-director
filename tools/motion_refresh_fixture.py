"""New generated-only fixture of one intentionally obsolete saved pace identity.

The malformed identity is test input, not an edited acceptance receipt. No user
file, historic job or approval is loaded. The healthy generated file is retained.
Usage: blender -b --factory-startup --python motion_refresh_fixture.py -- OUT
"""
from pathlib import Path
import ast
import json
import math
import sys
sys.dont_write_bytecode = True
import bpy
from mathutils import Quaternion
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from asset_director import action_layer as layer, action_timeline
from asset_director.core import atomic_json, file_hash

out = Path(sys.argv[sys.argv.index('--') + 1])
out.mkdir(parents=True, exist_ok=False)
checks = []
try:
    # Reuse only the explicit generated geometry builder, never that script's
    # caller-input branch, module setup or historical result-writing workflow.
    builder_path = Path(__file__).with_name('gait_profile_fixture.py')
    tree = ast.parse(builder_path.read_text(encoding='utf-8'), filename=str(builder_path))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'generated']
    assert len(functions) == 1
    scope = {'bpy': bpy, 'math': math, 'Quaternion': Quaternion, 'layer': layer}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(builder_path), 'exec'), scope)
    rig_name, take_name = scope['generated']()
    rig = bpy.context.scene.objects[rig_name]
    first_action = rig.animation_data.action
    second_action = first_action.copy()
    second_action.name = 'Synthetic following cycle'
    slot = next(iter(getattr(second_action, 'slots', [])), None)
    track = layer.add_strip(rig, second_action, slot, 'Retained synthetic following take', 1, [1, 25], 1)
    track.mute = True
    base = out / 'native-input.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(base))
    original_hash = file_hash(base)
    audit = layer.audit()
    performer = next(p for p in audit['performers'] if p['name'] == rig_name)
    takes = [next(t for t in performer['takes'] if t['action'] == name)
             for name in [take_name, second_action.name]]
    assert all(t['gait']['status'] == 'estimated' for t in takes)
    clips = []
    for index, take in enumerate(takes):
        g = take['gait']
        clip = {'id': ['clip_legacy_first', 'clip_following'][index], 'take_id': take['id'],
                'start': [1, 20][index], 'frames': 13, 'speed': 1, 'repeat_reviewed': False,
                'travel': {'delta_m': [v * g['meters_per_cycle'] * .5 for v in g['direction']],
                           'meters_per_cycle': g['meters_per_cycle'], 'gait_id': g['id']}}
        if index:
            clip['transition'] = {'frames': 6, 'match_phase': False}
        clips.append(clip)
    result = layer.apply({'version': 'action-layer-v1', 'audit_sha256': audit['sha256'],
                          'frame_range': [1, 250], 'changes': [{'performer': rig_name,
                          'mode': 'timeline', 'clips': clips}]}, 'generated-refresh-baseline')
    healthy = out / 'healthy-generated.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(healthy))
    layer.verify_saved(result, healthy)
    healthy_hash = file_hash(healthy)
    checks.append('Two generated native clips execute, save and reopen with valid measured pace')
    rig = bpy.context.scene.objects[rig_name]
    metadata = json.loads(rig[action_timeline.PROPERTY])
    metadata['clips'][0]['travel']['gait_id'] = '0' * 64
    rig[action_timeline.PROPERTY] = json.dumps(metadata)
    source = out / 'source.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    fresh = layer.audit()
    inspected = next(p for p in fresh['performers'] if p['name'] == rig_name)
    assert not inspected['timeline']['error']
    assert inspected['timeline']['clips'][0]['travel']['gait_id'] == '0' * 64
    assert all(t['gait']['status'] == 'estimated' and t['gait']['id'] != '0' * 64 for t in inspected['takes'])
    assert file_hash(base) == original_hash and file_hash(healthy) == healthy_hash
    checks.append('Only a newly generated copy has the deliberate old profile; baseline files remain intact')
    report = {'status': 'PASS', 'input_kind': 'GENERATED', 'checks': checks,
              'fixture_purpose': 'INTENTIONALLY_STALE_SYNTHETIC_PACE',
              'rig': rig_name, 'clips': metadata['clips'], 'takes': inspected['takes'],
              'source_sha256': file_hash(source), 'healthy_sha256': healthy_hash,
              'builder_sha256': file_hash(builder_path), 'blender': bpy.app.version_string,
              'human_review': 'NOT_TESTED', 'production_data': 'NOT_USED'}
except Exception as error:
    atomic_json(out / 'RESULTS.json', {'status': 'FAIL', 'checks': checks, 'error': repr(error)})
    raise
atomic_json(out / 'RESULTS.json', report)
print(json.dumps({'status': report['status'], 'checks': len(checks)}))
