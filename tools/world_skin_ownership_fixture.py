"""Generated cross-owned skin regression; never opens or changes user scenes."""
import json
import sys
from pathlib import Path
import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director import world_placement, world_transform, world_prepare
from asset_director.blender_ops import flatten
from asset_director.core import DirectorError, atomic_json, file_hash


def run(generated, output):
    generated, output = Path(generated).resolve(), Path(output).resolve()
    assert json.loads((generated / 'world_layers_report.json').read_text())['status'] == 'PASS'
    output.mkdir(parents=True, exist_ok=False)
    source = generated / 'placed.blend'
    original = file_hash(source)
    report = {'scope': 'REAL_GENERATED_WORLD_SKIN_OWNERSHIP', 'checks': [],
              'human_review': 'NOT_TESTED', 'native_desktop': 'NOT_TESTED'}

    def check(value, name):
        report['checks'].append({'name': name, 'status': 'PASS' if value else 'FAIL'})
        assert value, name

    def points(obj):
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return [evaluated.matrix_world @ vertex.co for vertex in evaluated.data.vertices]

    try:
        bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
        scene = bpy.context.scene
        check(len(world_transform.audit()['instances']) == 3, 'ordinary same-group skin remains independently placeable')
        skin = scene.objects['SyntheticSkin0']
        # A rig can drive saved geometry in another scene without itself being
        # linked into that scene. Inspect all saved objects, not only scene members.
        extra_scene = bpy.data.scenes.new('Synthetic external skin scene')
        external_skin = skin.copy(); external_skin.parent = None
        extra_scene.collection.objects.link(external_skin)
        external_audit = world_transform.audit()
        check(len(external_audit['instances']) == 2 and len(external_audit['unsupported']) == 1,
              'incoming skin dependency in another saved scene also refuses independent placement')
        bpy.data.objects.remove(external_skin, do_unlink=True)
        bpy.data.scenes.remove(extra_scene)
        foreign = scene.objects['SyntheticRig1']
        skin.modifiers['Skin'].object = foreign
        scene.frame_set(5)
        bpy.context.view_layer.update()
        fixture = output / 'cross-owned-skin.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(fixture))
        fixture_hash = file_hash(fixture)
        control = world_placement.ancestor_control(skin)
        matrix = flatten(control.matrix_world)
        delta = Matrix.Translation((2, 0, 0)) @ Matrix.Rotation(.5, 4, 'Z')
        before_points = points(skin)
        request = {'version': 'world-transform-v1', 'transforms': [
            {'instance': control[world_placement.INSTANCE], 'expected_matrix': matrix,
             'matrix': flatten(delta @ control.matrix_world)}]}
        try:
            world_transform.apply(request)
            actual = points(skin)
            report['unsafe_probe'] = {'accepted': True,
                'max_vertex_placement_error': max((new - delta @ old).length for old, new in zip(before_points, actual))}
        except DirectorError as exc:
            report['unsafe_probe'] = {'accepted': False, 'code': exc.code}
        check(not report['unsafe_probe']['accepted'], 'cross-owned armature modifier refuses before World placement')
        check(flatten(control.matrix_world) == matrix, 'refused transform keeps the exact prior placement')
        audit = world_transform.audit()
        check(len(audit['instances']) == 1 and len(audit['unsupported']) == 2,
              'both dependent mesh group and externally used rig group are unsupported; independent prop stays usable')
        selected = sorted(o.name for o in bpy.context.selected_objects)
        try:
            world_placement.select_instances([skin])
            raise AssertionError('Native whole-asset selection accepted a cross-owned rig')
        except DirectorError as exc:
            check(exc.code == 'WORLD_PLACEMENT_UNSUPPORTED' and selected == sorted(o.name for o in bpy.context.selected_objects),
                  'native selection also refuses without changing the selection')
        prop = audit['instances'][0]
        batch = {'version': 'world-transform-v1', 'transforms': [
            {'instance': prop['instance'], 'expected_matrix': prop['matrix'],
             'matrix': flatten(Matrix.Translation((1, 0, 0)) @ Matrix([prop['matrix'][i:i+4] for i in range(0, 16, 4)]))},
            request['transforms'][0]]}
        before = {o.name: flatten(o.matrix_world) for o in scene.objects}
        try:
            world_transform.apply(batch)
            raise AssertionError('Mixed batch accepted a cross-owned rig')
        except DirectorError as exc:
            check(exc.code == 'WORLD_PLACEMENT_UNSUPPORTED' and before == {o.name: flatten(o.matrix_world) for o in scene.objects},
                  'later unsupported group refuses the whole batch before earlier valid prop changes')
        bpy.ops.wm.open_mainfile(filepath=str(generated / 'baseline-failure.blend'), load_ui=False, use_scripts=False)
        scene = bpy.context.scene
        scene.objects['SyntheticSkin0'].modifiers['Skin'].object = scene.objects['SyntheticRig1']
        before_names = sorted(o.name for o in scene.objects)
        compatibility = world_prepare.audit()
        check(sum(g['status'] == 'UNSUPPORTED' for g in compatibility['groups']) == 2,
              'read-only compatibility rejects outgoing and incoming cross-group skin dependencies')
        prepared = world_placement.prepare(scene, only_job=scene.objects['SyntheticRig0']['bad_job'])
        check(not prepared['prepared'] and len(prepared['unsupported']) == 1 and before_names == sorted(o.name for o in scene.objects),
              'task preparation refuses before creating a placement container')
        check(file_hash(source) == original and file_hash(fixture) == fixture_hash,
              'generated original and failure-input file remain byte-identical')
        report['status'] = 'PASS'
    except BaseException as exc:
        report.update(status='FAIL', error=str(exc))
        raise
    finally:
        report['source'] = {'path': str(source), 'sha256': original}
        atomic_json(output / 'RESULTS.json', report)
        print('WORLD_SKIN_OWNERSHIP', report['status'], len(report['checks']))


if __name__ == '__main__':
    run(*sys.argv[sys.argv.index('--') + 1:])
