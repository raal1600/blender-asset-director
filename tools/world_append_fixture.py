"""Exact installed-journey collection import regression on generated source only."""
import json
import runpy
import shutil
import sys
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director import jobs
from asset_director.core import Asset, Library, atomic_json, file_hash


def run(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    checks = []
    try:
        with Library(output / 'library') as lib:
            source = lib.root / 'incoming/synthetic/fixture.blend'
            original_args = sys.argv
            try:
                sys.argv = ['scene.py', '--', str(source)]
                runpy.run_path(str(ROOT / 'tools/studio_e2e/scene.py'), run_name='__main__')
            finally:
                sys.argv = original_args
            original = file_hash(source)
            asset = Asset('local', 'synthetic-append-placement', 'Generated collection', 'model',
                          'https://example.invalid/generated', license_id='CC0-1.0',
                          license_url='https://example.invalid/synthetic-license', price=0,
                          formats=['.blend'], evidence='user_attested',
                          local_files=[{'path': source.relative_to(lib.root).as_posix(), 'sha256': original,
                                        'size': source.stat().st_size}])
            lib.put(asset)
            # Native collection append does not eagerly evaluate the view layer,
            # unlike glTF import; test both first and repeated source instances.
            previous = output / 'seed.blend'
            shutil.copyfile(source, previous)
            instance_ids = set()
            for index in range(2):
                prepared = jobs.prepare(lib, 'import', str(previous), asset.id,
                                        {'file': asset.local_files[0]['path'], 'selection': ['Synthetic_E2E_Set'],
                                         'placement': 'world-v1'})
                result = jobs.run(lib, prepared['id'], bpy.app.binary_path, timeout=120)
                folder = lib.root / 'jobs' / result['id']
                data = json.loads((folder / 'result.json').read_text())['data']
                assert len(data['world_placement']['prepared']) == 1 and not data['world_placement']['unsupported']
                item = data['world_placement']['prepared'][0]
                assert item['instance'] not in instance_ids
                instance_ids.add(item['instance'])
                previous = folder / 'result.blend'
                bpy.ops.wm.open_mainfile(filepath=str(previous), load_ui=False, use_scripts=False)
                observed = [o for o in bpy.context.scene.objects if o.get('bad_job') == result['id']]
                meshes = [o for o in observed if o.type == 'MESH']
                assert len(meshes) == 1
                for frame, x in [(1, -.25), (12, .25)]:
                    bpy.context.scene.frame_set(frame)
                    assert abs(meshes[0].matrix_world.translation.x - x) < 1e-5
                checks.append({'name': 'append instance ' + str(index + 1) + ' preserves keyed world transform after reopen', 'status': 'PASS'})
            assert file_hash(source) == original
            checks.append({'name': 'original source bytes retained', 'status': 'PASS'})
        atomic_json(output / 'world_append_report.json', {'status': 'PASS', 'checks': checks,
                    'blender': bpy.app.version_string, 'human_approval': 'NOT_GRANTED'})
        print('WORLD_APPEND_PASS', len(checks))
    except BaseException as exc:
        atomic_json(output / 'failure.json', {'status': 'FAIL', 'checks': checks, 'error': str(exc)})
        raise


if __name__ == '__main__':
    run(sys.argv[sys.argv.index('--') + 1])
