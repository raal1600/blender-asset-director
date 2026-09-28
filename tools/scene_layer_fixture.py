"""Real native camera/light transactions on generated geometry. No render approval."""
from pathlib import Path
import sys
import bpy
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from asset_director import scene_layer, jobs, action_layer
from asset_director.core import Library, atomic_json, file_hash, load_json, DirectorError

source, out = map(Path, sys.argv[sys.argv.index('--')+1:])
assert source.name == 'source.blend' and load_json(source.parent/'RESULTS.json')['scope'] == 'REAL_GENERATED_NATIVE_ACTION'
out.mkdir(parents=True, exist_ok=False)
original = file_hash(source);checks = [];outputs = []


def check(value, label):
    assert value, label
    checks.append(label)


def execute(lib, op, source_file, options):
    job = jobs.prepare(lib, op, str(source_file), options=options)
    result = jobs.run(lib, job['id'], blender=bpy.app.binary_path, timeout=180)
    assert result['state'] == 'SUCCEEDED', result
    directory = lib.root/'jobs'/job['id']
    return directory, load_json(directory/'result.json')['data']


def save(lib, source_file, layer, operations):
    before = file_hash(source_file)
    directory, inspected = execute(lib, 'scene-layer-audit', source_file, {'layer': layer})
    check(not (directory/'result.blend').exists(), layer+' inspection is read-only')
    request = {'version': 'scene-layer-v1', 'layer': layer, 'audit_sha256': inspected['sha256'], 'operations': operations}
    directory, result = execute(lib, 'scene-layer-edit', source_file, request)
    check(result['reopened'] and result['request'] == request and result['visual_acceptance'] == 'NOT_EVALUATED', layer+' exact operation saved and independently reopened without approval')
    check(file_hash(source_file) == before, layer+' input checkpoint bytes preserved')
    filename = directory/'result.blend';outputs.append({'path': str(filename.relative_to(out)), 'sha256': file_hash(filename)})
    bpy.ops.wm.open_mainfile(filepath=str(filename), load_ui=False, use_scripts=False)
    return filename, result


try:
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    # This generated fixture tests source-scene lighting, not compositor/VSE
    # delivery. Configure its NEW baseline explicitly; never alter the input.
    bpy.context.scene.render.use_compositing = False
    bpy.context.scene.render.use_sequencer = False
    for name, energy in [('SyntheticLayerKey', 100), ('SyntheticLayerFill', 25)]:
        assert name not in bpy.data.objects
        data = bpy.data.lights.new(name, 'AREA');data.energy = energy
        obj = bpy.data.objects.new(name, data);bpy.context.scene.collection.objects.link(obj);obj.location = (2, -3, 5)
    world = bpy.data.worlds.new('SyntheticLayerWorld');world.use_nodes = True;bpy.context.scene.world = world
    baseline = out/'source.blend';bpy.ops.wm.save_as_mainfile(filepath=str(baseline));baseline_hash = file_hash(baseline)
    with Library(out/'library') as lib:
        wide, report = save(lib, baseline, 'shots', [{'operation': 'camera-fit', 'name': 'SyntheticWide', 'options':
            {'subjects': ['SyntheticSkin0', 'SyntheticSkin1', 'StaticProp'], 'frames': [1, 5, 9], 'direction': [1, -2, 1], 'lens_mm': 50}}])
        check(bpy.context.scene.camera.name == 'SyntheticWide' and report['operations'][0]['data']['camera'] == 'SyntheticWide', 'fitted camera keeps its requested observed identity')
        plan = {'mode': 'create', 'name': 'SyntheticClose', 'subjects': ['SyntheticSkin0'], 'lens_mm': 50,
            'keyframes': [{'frame': 1, 'aim': {'subject': 'SyntheticSkin0'}, 'direction': [1, -2, 1], 'fit': {'margin': .1}}]}
        close, report = save(lib, wide, 'shots', [{'operation': 'camera-plan', 'options': plan}])
        check({'SyntheticWide', 'SyntheticClose'} <= set(bpy.context.scene.objects.keys()), 'two real cameras view one unchanged world')
        camera = bpy.context.scene.objects['SyntheticClose'];old_object = camera.animation_data.action.name;old_lens = camera.data.animation_data.action.name
        old_keys = {name: action_layer.channels(bpy.data.actions[name]) for name in (old_object, old_lens)}
        plan = {k:v for k,v in plan.items() if k != 'name'} | {'mode': 'adapt', 'camera': 'SyntheticClose', 'lens_mm': 65}
        refined, report = save(lib, close, 'shots', [{'operation': 'camera-plan', 'options': plan}])
        camera = bpy.context.scene.objects['SyntheticClose']
        check(camera.data.lens == 65 and all(action_layer.channels(bpy.data.actions[name]) == value for name, value in old_keys.items()), 'camera refinement changes requested lens while retaining original camera/lens keys')
        check(any(t.mute and any(s.action.name == old_lens for s in t.strips) for t in camera.data.animation_data.nla_tracks), 'previous lens motion is preserved in a muted native track')
        lit, report = save(lib, refined, 'light', [
            {'operation': 'light-adjust', 'options': {'lights': [{'name': 'SyntheticLayerKey', 'energy': 200, 'color': [1, .8, .6]}]}},
            {'operation': 'world-adjust', 'options': {'strength': .2}},
            {'operation': 'look-adjust', 'options': {'exposure': .5}},
            {'operation': 'light-rig', 'options': {'subjects': ['SyntheticSkin0'], 'lights': [{'type': 'POINT', 'energy': 50, 'offset': [1, -1, 1], 'color': [1, 1, 1]}]}}])
        check(bpy.data.objects['SyntheticLayerKey'].data.energy == 200 and bpy.data.objects['SyntheticLayerFill'].data.energy == 25, 'only requested existing light power changes')
        check(abs(bpy.context.scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value-.2)<1e-6 and bpy.context.scene.view_settings.exposure == .5, 'world and look changes are native saved values')
        check(len(report['operations'][-1]['data']['created_lights']) == 1 and bpy.context.scene.camera.name == 'SyntheticClose', 'additive light creation keeps cameras and scene context')
        audit = scene_layer.audit('shots');before = action_layer.preserved(set())
        for patch, code in [({'audit_sha256': '0'*64}, 'LAYER_CHANGED'),
                            ({'operations': [{'operation': 'camera-fit', 'name': 'Outside', 'options': {'subjects': ['StaticProp'], 'frames': [99], 'direction': [1, -1, 1], 'lens_mm': 50}}]}, 'INVALID_TIMEBASE')]:
            request = {'version': 'scene-layer-v1', 'layer': 'shots', 'audit_sha256': audit['sha256'], 'operations': [{'operation': 'camera-plan', 'options': plan}]} | patch
            try:scene_layer.apply(request, 'synthetic-refusal')
            except DirectorError as error:check(error.code == code and action_layer.preserved(set()) == before, 'no mutation on '+code)
            else:raise AssertionError('Invalid camera edit executed')
        key = bpy.data.objects['SyntheticLayerKey'];duplicate = bpy.data.objects.new('SyntheticSharedLight', key.data);bpy.context.scene.collection.objects.link(duplicate)
        audit = scene_layer.audit('light');before = action_layer.preserved(set())
        try:scene_layer.apply({'version': 'scene-layer-v1', 'layer': 'light', 'audit_sha256': audit['sha256'], 'operations': [{'operation': 'light-adjust', 'options': {'lights': [{'name': key.name, 'energy': 1}]}}]}, 'synthetic-shared-refusal')
        except DirectorError as error:check(error.code == 'LAYER_UNSUPPORTED' and action_layer.preserved(set()) == before, 'shared light data refuses before changes')
        else:raise AssertionError('Shared light was changed')
    check(file_hash(source) == original and file_hash(baseline) == baseline_hash, 'all original source and baseline bytes preserved')
    atomic_json(out/'RESULTS.json', {'status': 'PASS', 'scope': 'REAL_GENERATED_SCENE_LAYERS', 'checks': checks, 'outputs': outputs,
        'blender': bpy.app.version_string, 'human_review': 'NOT_TESTED', 'rendered_lighting': 'NOT_TESTED'})
    print('SCENE_LAYER_NATIVE_PASS', len(checks))
except Exception as error:
    atomic_json(out/'RESULTS.json', {'status': 'FAIL', 'checks': checks, 'outputs': outputs, 'error': repr(error)})
    raise
