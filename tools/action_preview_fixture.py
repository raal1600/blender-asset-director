"""Generate combined Action GLB and evaluated native sample evidence. No user assets."""
from pathlib import Path
import sys
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director.core import atomic_json, file_hash, load_json
from asset_director import action_layer
from asset_director.viewer_export import export

source, out = map(Path, sys.argv[sys.argv.index('--') + 1:])
assert source.name == 'source.blend' and load_json(source.parent / 'RESULTS.json')['scope'] == 'REAL_GENERATED_NATIVE_ACTION'
out.mkdir(parents=True, exist_ok=False)
before = file_hash(source)
try:
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    scene = bpy.context.scene;scene['asset_director_preview_only'] = True
    saved_frame = scene.frame_current;flags = {o.name:o.hide_render for o in scene.objects}
    state = action_layer.preserved(set());samples = []
    for frame in [scene.frame_start, (scene.frame_start + scene.frame_end) // 2, scene.frame_end]:
        scene.frame_set(frame);deps = bpy.context.evaluated_depsgraph_get();positions = {}
        for name in ['SyntheticSkin0','SyntheticSkin1','StaticProp']:
            obj = scene.objects[name].evaluated_get(deps)
            point = sum((obj.matrix_world @ v.co for v in obj.data.vertices), Vector()) / len(obj.data.vertices)
            positions[name] = [point.x, point.z, -point.y]  # Blender Z-up -> glTF Y-up
        samples.append({'frame': frame, 'positions': positions})
    scene.frame_set(saved_frame)
    result = export(out / 'action.glb', {'takes': [], 'checkpoint': True, 'preview_profile': 'action-playback-v1'})
    assert result['playback']['start'] == scene.frame_start and result['playback']['end'] == scene.frame_end
    assert action_layer.preserved(set()) == state and flags == {o.name:o.hide_render for o in scene.objects}
    assert file_hash(source) == before
    atomic_json(out / 'RESULTS.json', {'status':'PASS','scope':'GENERATED_COMBINED_ACTION_PREVIEW','playback':result['playback'],
        'samples':samples,'model':{'path':'action.glb','sha256':file_hash(out/'action.glb')},'original_sha256':before,
        'native_source_unchanged':True,'glb_evaluated_comparison':'PENDING_BROWSER','human_review':'NOT_TESTED'})
    print('ACTION_PREVIEW_NATIVE_PASS')
except Exception as error:
    atomic_json(out / 'FAILURE.json', {'status':'FAIL','error':repr(error)})
    raise
