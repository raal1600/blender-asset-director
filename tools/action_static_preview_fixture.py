"""Real exported static Action cases. Synthetic source only, no human approval."""
from pathlib import Path
import sys
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director import action_layer
from asset_director.core import atomic_json, file_hash, load_json
from asset_director.viewer_export import export
from asset_director.action_preview import playback, assert_static_scene
from asset_director.core import DirectorError

source, out = map(Path, sys.argv[sys.argv.index('--') + 1:])
assert source.name == 'source.blend' and load_json(source.parent / 'RESULTS.json')['scope'] == 'REAL_GENERATED_NATIVE_ACTION'
out.mkdir(parents=True, exist_ok=False)
original = file_hash(source)
cases = []
refusals = []


def record(name):
    scene = bpy.context.scene
    bpy.ops.wm.save_as_mainfile(filepath=str(out / (name + '.blend')))
    scene['asset_director_preview_only'] = True
    frame = scene.frame_current
    state = action_layer.preserved(set())
    flags = {o.name: o.hide_render for o in scene.objects}
    samples = []
    for sample in sorted({scene.frame_start, (scene.frame_start + scene.frame_end) // 2, scene.frame_end}):
        scene.frame_set(sample)
        deps = bpy.context.evaluated_depsgraph_get()
        positions = {}
        for original_obj in scene.objects:
            if original_obj.name not in {'SyntheticSkin0', 'SyntheticSkin1', 'StaticProp', 'NeverAnimatedCube'}:
                continue
            obj = original_obj.evaluated_get(deps)
            point = sum((obj.matrix_world @ v.co for v in obj.data.vertices), Vector()) / len(obj.data.vertices)
            positions[obj.name] = [point.x, point.z, -point.y]
        samples.append({'frame': sample, 'positions': positions})
    scene.frame_set(frame)
    result = export(out / (name + '.glb'), {'takes': [], 'checkpoint': True, 'preview_profile': 'action-playback-v1'})
    assert action_layer.preserved(set()) == state and flags == {o.name: o.hide_render for o in scene.objects}
    assert result['playback']['start'] == scene.frame_start and result['playback']['end'] == scene.frame_end
    for sample in samples[1:]:
        for obj, position in sample['positions'].items():
            assert (Vector(position) - Vector(samples[0]['positions'][obj])).length < 1e-5
    cases.append({'name': name, 'playback': result['playback'], 'samples': samples,
                  'model': {'path': name + '.glb', 'sha256': file_hash(out / (name + '.glb'))}})


try:
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    audit = action_layer.audit()
    action_layer.apply({'version': 'action-layer-v1', 'audit_sha256': audit['sha256'],
                        'changes': [{'performer': p['name'], 'mode': 'hold', 'frame': 5}
                                    for p in audit['performers']]}, 'synthetic-static-preview')
    record('all-performers-held')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(location=(2, 0, 1))
    bpy.context.object.name = 'NeverAnimatedCube'
    bpy.context.scene.frame_start = 11
    bpy.context.scene.frame_end = 19
    bpy.context.scene.render.fps = 24
    bpy.context.scene.frame_set(11)
    record('never-animated')
    bpy.context.scene.frame_end = 11
    bpy.context.scene.frame_set(11)
    record('single-frame')
    bpy.context.object.modifiers.new('Synthetic procedural refusal', 'WAVE')
    try: assert_static_scene(bpy.context.scene)
    except DirectorError as error:
        assert error.code == 'VIEWER_EXPORT_FAILED'; refusals.append('procedural motion is not a verified still')
    else: raise AssertionError('Wave modifier was treated as static')
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    try: playback(out / 'never-animated.glb', bpy.context.scene)
    except DirectorError as error:
        assert error.code == 'VIEWER_EXPORT_FAILED'; refusals.append('missing clip from animated source is refused')
    else: raise AssertionError('Missing animation was treated as static')
    assert file_hash(source) == original
    atomic_json(out / 'RESULTS.json', {'status': 'PASS', 'scope': 'GENERATED_STATIC_ACTION_PREVIEW',
                'cases': cases, 'refusals': refusals, 'original_sha256': original, 'native_source_unchanged': True,
                'glb_evaluated_comparison': 'PENDING_BROWSER', 'human_review': 'NOT_TESTED'})
    print('ACTION_STATIC_PREVIEW_NATIVE_PASS')
except Exception as error:
    atomic_json(out / 'FAILURE.json', {'status': 'FAIL', 'cases': cases, 'error': repr(error)})
    raise
