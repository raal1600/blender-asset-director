"""Real isolated older-World preparation; generated inputs, never live projects."""
import copy
import json
import shutil
import sys
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director import jobs, world_prepare, world_placement, world_transform
from asset_director.core import Library, DirectorError, atomic_json, file_hash, digest


def run(generated, output):
    generated, output = Path(generated).resolve(), Path(output).resolve()
    assert json.loads((generated / 'world_layers_report.json').read_text())['status'] == 'PASS'
    source = generated / 'baseline-failure.blend'
    original = file_hash(source)
    output.mkdir(parents=True, exist_ok=False)
    checks = []

    def check(value, name):
        checks.append({'name': name, 'status': 'PASS' if value else 'FAIL'})
        assert value, name

    def load():bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)

    def options(audit, groups=None):
        return {'version': 'world-prepare-v1', 'audit_sha256': audit['sha256'],
                'groups': groups or [{k: g[k] for k in ('asset_id', 'import_job')} for g in audit['groups']]}

    def skin_points():
        scene = bpy.context.scene
        result = {}
        frame, subframe = scene.frame_current, scene.frame_subframe
        try:
            for f in (1, 5, 9):
                scene.frame_set(f)
                graph = bpy.context.evaluated_depsgraph_get()
                for name in ('SyntheticSkin0', 'SyntheticSkin1'):
                    obj = scene.objects[name].evaluated_get(graph)
                    result[name + ':' + str(f)] = list(sum((obj.matrix_world @ v.co for v in obj.data.vertices), Vector()) / len(obj.data.vertices))
        finally:scene.frame_set(frame, subframe=subframe)
        return result

    try:
        load(); inspected = world_prepare.audit(); baseline = digest(inspected)
        check(len(inspected['groups']) == 3 and all(g['status'] == 'PREPARABLE' for g in inspected['groups']),
              'read-only inspection observes three explicit older import groups')
        check(world_transform.audit()['instances'] == [] and digest(world_prepare.audit()) == baseline,
              'inspection does not add controls, alter ownership or save the original')
        before_motion = skin_points()
        bad = options(inspected); bad['groups'][-1]['import_job'] = 'j_' + 'f' * 24
        try:
            world_prepare.apply(bad); raise AssertionError('Unknown last target ran')
        except DirectorError as exc:
            check(exc.code == 'WORLD_PLACEMENT_UNSUPPORTED' and digest(world_prepare.audit()) == baseline,
                  'unknown final target refuses before any earlier target changes')
        constraint = bpy.data.objects['SyntheticRig1'].constraints.new('COPY_LOCATION')
        changed = world_prepare.audit()
        check(sum(g['status'] == 'UNSUPPORTED' for g in changed['groups']) == 1,
              'constrained hierarchy is reported unsupported, not guessed into a group')
        try:
            world_prepare.apply(options(changed)); raise AssertionError('Unsupported final group ran')
        except DirectorError as exc:
            check(exc.code == 'WORLD_PLACEMENT_UNSUPPORTED' and not world_transform.audit()['instances'],
                  'mixed supported/unsupported request is all-or-nothing before mutation')
        bpy.data.objects['SyntheticRig1'].constraints.remove(constraint)
        check(digest(world_prepare.audit()) == baseline, 'disposable refusal probe restores exact baseline')
        # Two groups can share an import-job tag; selecting one must not prepare both.
        bpy.data.objects['StaticProp']['bad_job'] = inspected['groups'][0]['import_job']
        bpy.data.objects['StaticPropTwin']['bad_job'] = inspected['groups'][0]['import_job']
        shared = world_prepare.audit(); chosen = shared['groups'][0]
        partial = world_prepare.apply(options(shared, [{k: chosen[k] for k in ('asset_id', 'import_job')}]))
        check(len(partial['created']) == 1 and len(world_transform.audit()['instances']) == 1
              and len(world_transform.audit()['unprepared']) > 0,
              'selection binds asset and job together, leaving unselected groups untouched')
        load(); check(skin_points() == before_motion, 'native keyed motion remains available in the original')
        with Library(output / 'library') as lib:
            inspected_job = jobs.prepare(lib, 'world-prepare-audit', input_file=str(source))
            inspected_result = jobs.run(lib, inspected_job['id'], bpy.app.binary_path, timeout=180)
            inspected = json.loads((lib.root / 'jobs' / inspected_job['id'] / 'result.json').read_text())['data']
            check(inspected_result['state'] == 'SUCCEEDED' and not any(x['path'].endswith('.blend') for x in inspected_result['outputs']),
                  'real compatibility worker emits evidence without a changed Blender file')
            request = options(inspected)
            prepared = jobs.prepare(lib, 'world-prepare', input_file=str(source), options=request)
            check(jobs.prepare(lib, 'world-prepare', input_file=str(source), options=request)['id'] == prepared['id'],
                  'exact request binds one immutable native job identity')
            result = jobs.run(lib, prepared['id'], bpy.app.binary_path, timeout=180)
            folder = lib.root / 'jobs' / prepared['id']
            data = json.loads((folder / 'result.json').read_text())['data']
            changed = folder / 'result.blend'; saved = file_hash(changed)
            check(result['state'] == 'SUCCEEDED' and data['reopened'] and len(data['created']) == 3
                  and data['publication'] == 'SEPARATE_CANDIDATE_ONLY' and data['visual_acceptance'] == 'NOT_EVALUATED',
                  'real worker saves/reopens verified separate preparation, never human approval')
            check(jobs.run(lib, prepared['id'], bpy.app.binary_path)['outputs'] == result['outputs']
                  and file_hash(changed) == saved, 'idempotent retry preserves exact existing result bytes')
            bpy.ops.wm.open_mainfile(filepath=str(changed), load_ui=False, use_scripts=False)
            world_prepare.verify(data)
            after_motion = skin_points()
            check(all(max(abs(a - b) for a, b in zip(before_motion[name], value)) < 1e-5
                      for name, value in after_motion.items())
                  and before_motion['SyntheticSkin0:1'] != before_motion['SyntheticSkin0:5'],
                  'both evaluated skinned performers preserve actual motion at start/middle/end')
            from asset_director.viewer_export import export
            preview_copy = output / 'preview-copy.blend'
            shutil.copyfile(changed, preview_copy)
            bpy.ops.wm.open_mainfile(filepath=str(preview_copy), load_ui=False, use_scripts=False)
            bpy.context.scene['asset_director_preview_only'] = True
            preview = export(output / 'prepared-world.glb', {'takes': [], 'checkpoint': True, 'preview_profile': 'world-static-v1'})
            check(len(preview['placement']['instances']) == 3 and not preview['placement']['unprepared'],
                  'actual static World GLB exposes all three independently prepared instances')
            stale = jobs.prepare(lib, 'world-prepare', input_file=str(changed), options=request)
            try:
                jobs.run(lib, stale['id'], bpy.app.binary_path, timeout=180)
                raise AssertionError('Stale inspection executed')
            except DirectorError as exc:
                failed, receipt = jobs.read_job(lib, stale['id'])
                check(exc.code == 'WORLD_BASE_CHANGED' and failed['state'] == 'FAILED'
                      and (receipt.parent / 'worker.log').is_file() and not (receipt.parent / 'result.blend').exists(),
                      'stale job fails with retained evidence and no scene publication')
            check(file_hash(source) == original and file_hash(changed) == saved,
                  'original failure scene and successful candidate remain byte-identical')
            atomic_json(output / 'RESULTS.json', {'status': 'PASS', 'scope': 'REAL_GENERATED_WORLD_PREPARATION',
                        'checks': checks, 'blender': bpy.app.version_string, 'source': {'path': str(source), 'sha256': original},
                        'job': prepared['id'], 'candidate': {'path': str(changed), 'sha256': saved},
                        'human_review': 'NOT_TESTED', 'native_desktop': 'NOT_TESTED', 'launcher': 'NOT_TESTED'})
            print('WORLD_PREPARE_PASS', len(checks))
    except BaseException as exc:
        atomic_json(output / 'failure.json', {'status': 'FAIL', 'checks': checks, 'error': str(exc)})
        raise


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    run(args[0], args[1])
