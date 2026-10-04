"""Export generated saved turns for independent native/Three.js geometry checks."""
from pathlib import Path
import math
import sys
import bpy
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from asset_director.core import atomic_json, file_hash, load_json
from asset_director.viewer_export import export

args = sys.argv[sys.argv.index('--') + 1:]
generated, out = map(Path, args)
receipt = load_json(generated / 'RESULTS.json')
assert receipt['status'] == 'PASS' and receipt['input_kind'] == 'GENERATED'
source = generated / 'heading.blend'
identity = file_hash(source)
out.mkdir(parents=True, exist_ok=False)
try:
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    # This disposable background fixture is the preview worker; never save its
    # preview-only marker back into the original generated checkpoint.
    scene['asset_director_preview_only'] = True
    assert scene.render.fps == 24
    samples = []
    for value in (1, 25, 28, 30, 32, 34, 37, 38, 44, 50, 62):
        scene.frame_set(math.floor(value), subframe=value % 1)
        bpy.context.view_layer.update()
        mesh = scene.objects['Synthetic skin'].evaluated_get(bpy.context.evaluated_depsgraph_get())
        samples.append({'frame': value, 'points': [list(mesh.matrix_world @ vertex.co) for vertex in mesh.data.vertices]})
    scene.frame_set(1)
    exported = export(out / 'heading.glb', {'takes': [], 'checkpoint': True, 'preview_profile': 'action-playback-v1'})
    assert exported['playback']['start'] == 1 and exported['playback']['end'] >= 62
    assert file_hash(source) == identity
    atomic_json(out / 'RESULTS.json', {'status': 'PASS', 'input_kind': 'GENERATED', 'samples': samples,
                'source_sha256': identity, 'mesh': 'Synthetic skin', 'fps': 24,
                'checks': ['real saved heading export', 'source bytes unchanged'],
                'human_review': 'NOT_TESTED'})
except Exception as error:
    atomic_json(out / 'RESULTS.json', {'status': 'FAIL', 'error': str(error)})
    raise
