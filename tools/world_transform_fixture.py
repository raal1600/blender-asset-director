"""Real World batch-save jobs on a generated keyed-rig scene; no live data/UI."""
import copy
import json
import sys
from pathlib import Path
import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director import jobs, world_transform, world_transform_contract as contract
from asset_director.core import Library, DirectorError, atomic_json, file_hash
from asset_director.blender_ops import flatten


def run(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    checks = []

    def check(value, name):
        checks.append({'name': name, 'status': 'PASS' if value else 'FAIL'})
        assert value, name

    original = file_hash(source)
    try:
        bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
        scene = bpy.context.scene
        initial = world_transform.audit()
        check(len(initial['instances']) == 3 and not initial['unsupported'], 'observed two rigged instances and multi-root prop')
        options = {'version': contract.VERSION, 'transforms': []}
        for index, item in enumerate(initial['instances']):
            before = Matrix([item['matrix'][i:i + 4] for i in range(0, 16, 4)])
            after = Matrix.Translation((index + 1, -2, .5)) @ Matrix.Rotation(.4, 4, 'Z') @ Matrix.Scale(1.25, 4) @ before
            options['transforms'].append({'instance': item['instance'], 'expected_matrix': item['matrix'], 'matrix': flatten(after)})
        before = {o.name: flatten(o.matrix_world) for o in scene.objects}
        bad = copy.deepcopy(options); bad['transforms'][-1]['expected_matrix'][3] += 1
        try:
            world_transform.apply(bad)
            raise AssertionError('Stale last target executed')
        except DirectorError as exc:
            check(exc.code == 'WORLD_BASE_CHANGED' and before == {o.name: flatten(o.matrix_world) for o in scene.objects},
                  'stale last batch target refuses before changing any object')
        foreign = bpy.data.objects.new('Synthetic foreign child', None)
        scene.collection.objects.link(foreign)
        foreign.parent = scene.objects[initial['instances'][-1]['control']]
        try:
            world_transform.apply(options)
            raise AssertionError('Foreign hierarchy executed')
        except DirectorError as exc:
            check(exc.code == 'WORLD_IDENTITY_CHANGED', 'cross-owned child refuses the batch')
        bpy.data.objects.remove(foreign, do_unlink=True)
        baseline = world_transform.preserved_state({x['control'] for x in initial['instances']})
        with Library(output / 'library') as lib:
            prepared = jobs.prepare(lib, 'world-transform', input_file=str(source), options=options)
            check(jobs.prepare(lib, 'world-transform', input_file=str(source), options=options)['id'] == prepared['id'],
                  'identical immutable request has same job identity')
            result = jobs.run(lib, prepared['id'], bpy.app.binary_path, timeout=180)
            data = json.loads((lib.root / 'jobs' / prepared['id'] / 'result.json').read_text())['data']
            check(result['state'] == 'SUCCEEDED' and data['reopened'], 'real isolated worker saves and reopens the result')
            changed = lib.root / 'jobs' / prepared['id'] / 'result.blend'
            saved = file_hash(changed)
            check(jobs.run(lib, prepared['id'], bpy.app.binary_path)['outputs'] == result['outputs']
                  and file_hash(changed) == saved, 'idempotent retry reuses verified bytes without a second edit')
            bpy.ops.wm.open_mainfile(filepath=str(changed), load_ui=False, use_scripts=False)
            world_transform.verify(data)
            check(world_transform.preserved_state({x['control'] for x in initial['instances']}) == baseline,
                  'separate process reopen retains animation, hierarchy, helpers and unrelated state')
            for frame in (1, 5, 9):
                bpy.context.scene.frame_set(frame)
                check(all(world_transform.close_matrix(world_transform.observed(bpy.context.scene, x['instance'])[1]['matrix'], x['matrix'])
                          for x in options['transforms']), 'all instance placements survive frame ' + str(frame))
            # The original matrices are stale against the NEW result, not retried over it.
            rejected = jobs.prepare(lib, 'world-transform', input_file=str(changed), options=options)
            try:
                jobs.run(lib, rejected['id'], bpy.app.binary_path, timeout=180)
                raise AssertionError('Stale source matrices executed')
            except DirectorError as exc:
                failure, receipt = jobs.read_job(lib, rejected['id'])
                check(exc.code == 'WORLD_BASE_CHANGED' and failure['state'] == 'FAILED'
                      and (receipt.parent / 'worker.log').is_file() and not (receipt.parent / 'result.blend').exists(),
                      'failed attempt remains recorded with no published scene')
            check(file_hash(source) == original and file_hash(changed) == saved, 'original and successful result remain byte-identical after refusal')
        atomic_json(output / 'world_transform_report.json', {'status': 'PASS', 'checks': checks,
                    'blender': bpy.app.version_string, 'human_approval': 'NOT_GRANTED', 'native_gui': 'NOT_TESTED'})
        print('WORLD_TRANSFORM_PASS', len(checks))
    except BaseException as exc:
        atomic_json(output / 'failure.json', {'status': 'FAIL', 'checks': checks, 'error': str(exc)})
        raise


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    run(args[0], args[1])
