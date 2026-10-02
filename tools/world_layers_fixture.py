"""Real saved/reopened rig placement and static World export regression.

Generated inputs only; no desktop control, user scenes or creative approval.
"""
import json
import struct
import sys
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director import world_placement as placement, blender_ops as ops
from asset_director.core import atomic_json, file_hash, digest
from asset_director.viewer_export import export
from asset_director.world_preview import frozen_meshes

out = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
out.mkdir(parents=True, exist_ok=False)
checks = []

def check(value, name):
    checks.append({'name': name, 'status': 'PASS' if value else 'FAIL'})
    assert value, name

def key_state():
    return {a.name: digest([[c.data_path, c.array_index, [list(k.co) for k in c.keyframe_points]]
                            for c in ops.curves(a)]) for a in bpy.data.actions}

def point(name):
    obj = bpy.data.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get())
    # glTF may reorder vertices; compare the evaluated centroid, not index zero.
    return sum((obj.matrix_world @ v.co for v in obj.data.vertices), Vector()) / len(obj.data.vertices)

def gltf(file):
    raw = file.read_bytes()
    size, kind = struct.unpack_from('<II', raw, 12)
    assert raw[:4] == b'glTF' and kind == 0x4e4f534a
    return json.loads(raw[20:20+size])

try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end, scene.render.fps = 1, 9, 24
    for index in range(2):
        arm = bpy.data.armatures.new('SyntheticRigData' + str(index))
        rig = bpy.data.objects.new('SyntheticRig' + str(index), arm)
        scene.collection.objects.link(rig)
        bpy.ops.object.select_all(action='DESELECT')
        rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode='EDIT')
        bone = arm.edit_bones.new('Joint')
        bone.head, bone.tail = (0, 0, 0), (0, 0, 1)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.mesh.primitive_cube_add(size=.4, location=(0, 0, .5))
        skin = bpy.context.object
        skin.name = 'SyntheticSkin' + str(index)
        skin.parent = rig
        group = skin.vertex_groups.new(name='Joint')
        group.add(list(range(8)), 1, 'REPLACE')
        skin.modifiers.new('Skin', 'ARMATURE').object = rig
        for frame, x in [(1, 0), (5, .5), (9, 0)]:
            rig.location = (0, 0, 0)
            rig.keyframe_insert('location', frame=frame)
            rig.rotation_euler.z = .2 if frame == 5 else 0
            rig.keyframe_insert('rotation_euler', frame=frame)
            rig.pose.bones['Joint'].location.x = x
            rig.pose.bones['Joint'].keyframe_insert('location', frame=frame)
        for obj in (rig, skin):
            obj['bad_asset'] = 'a_' + '1' * 24
            obj['bad_job'] = 'j_' + str(index + 1) * 24
    bpy.ops.mesh.primitive_cube_add(size=.2, location=(0, 3, 0))
    prop = bpy.context.object
    prop.name = 'StaticProp'
    prop['bad_asset'], prop['bad_job'] = 'a_' + '2' * 24, 'j_' + '3' * 24
    twin = prop.copy();twin.name='StaticPropTwin';scene.collection.objects.link(twin);twin.location.x=1
    # Multiple independent roots, sharing mesh data but not object transforms.
    bpy.ops.mesh.primitive_cube_add(size=.1, location=(8, 0, 0))
    widget = bpy.context.object
    widget.name = 'ObservedWidget'
    bpy.data.objects['SyntheticRig0'].pose.bones['Joint'].custom_shape = widget
    bpy.ops.mesh.primitive_cube_add(size=.1, location=(9, 0, 0))
    bpy.context.object.name = 'ObservedWidget.001'
    scene.frame_set(1)
    # Preserve a genuinely failing baseline before any preparation.
    bpy.data.objects['SyntheticRig0'].location = (2, 3, 4)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'baseline-failure.blend'))
    original = file_hash(out / 'baseline-failure.blend')
    bpy.ops.wm.open_mainfile(filepath=str(out / 'baseline-failure.blend'), load_ui=False, use_scripts=False)
    check(bpy.data.objects['SyntheticRig0'].location.length < 1e-6, 'reproduced keyed placement reset on reopen')
    scene = bpy.context.scene
    keys = key_state()
    # Unsupported ownership/constraints must refuse before adding any control.
    rig = bpy.data.objects['SyntheticRig0']
    foreign = bpy.data.objects.new('UnownedChild', None)
    scene.collection.objects.link(foreign); foreign.parent = rig
    refused = placement.prepare(scene, only_job=rig['bad_job'])
    check(not refused['prepared'] and len(refused['unsupported']) == 1 and not rig.parent,
          'cross-owned child refuses without mutation')
    bpy.data.objects.remove(foreign, do_unlink=True)
    constraint = rig.constraints.new('LIMIT_LOCATION')
    refused = placement.prepare(scene, only_job=rig['bad_job'])
    check(not refused['prepared'] and not rig.parent, 'constrained rig refuses without mutation')
    rig.constraints.remove(constraint)
    extra_scene = bpy.data.scenes.new('Shared ownership refusal')
    extra_scene.collection.objects.link(rig)
    refused = placement.prepare(scene, only_job=rig['bad_job'])
    check(not refused['prepared'] and not rig.parent, 'shared scene ownership refuses without mutation')
    bpy.data.scenes.remove(extra_scene)
    before = {o.name: ops.flatten(o.matrix_world) for o in scene.objects}
    report = placement.prepare(scene)
    check(len(report['prepared']) == 3 and not report['unsupported'], 'prepare two independent copies and static asset')
    check(all(ops.flatten(bpy.data.objects[n].matrix_world) == value for n, value in before.items()), 'preparation preserves original transforms')
    check(placement.prepare(scene) == report, 'repeated preparation is idempotent')
    check(bpy.data.objects['StaticProp'].data == bpy.data.objects['StaticPropTwin'].data
          and placement.ancestor_control(bpy.data.objects['StaticProp']) == placement.ancestor_control(bpy.data.objects['StaticPropTwin']),
          'multi-root static asset retains shared mesh data under one control')
    controls = [placement.ancestor_control(bpy.data.objects['SyntheticRig' + str(i)]) for i in range(2)]
    check(controls[0] != controls[1] and controls[0][placement.INSTANCE] != controls[1][placement.INSTANCE], 'same source asset has distinct placement instances')
    selected = placement.select_instances([bpy.data.objects['SyntheticSkin0'], bpy.data.objects['SyntheticRig0']])
    check(selected == {controls[0]}, 'parent plus child resolves to one whole-asset control')
    placement.install_tools({}, report)
    assert bpy.ops.asset_director.world_select(control=controls[1].name) == {'FINISHED'}
    check(set(bpy.context.selected_objects) == {controls[1]}, 'actual whole-asset selector operator registers and selects the control')
    instance = controls[0][placement.INSTANCE]
    controls[0][placement.INSTANCE] = 'changed-identity'
    refused = placement.prepare(scene, only_job=controls[0]['bad_job'])
    check(not refused['prepared'] and len(refused['unsupported']) == 1, 'broken instance binding refuses')
    controls[0][placement.INSTANCE] = instance
    controls[0].location = (2, 3, 4)
    controls[0].rotation_euler.z = .3
    controls[0].scale = (1.2, 1.2, 1.2)
    controls[1].location = (-3, -2, 1)
    placement.ancestor_control(bpy.data.objects['StaticProp']).location.x = 5
    scene.frame_set(5)
    bpy.context.view_layer.update()
    positions = {n: list(point(n)) for n in ('SyntheticSkin0', 'SyntheticSkin1', 'StaticProp')}
    placement.hide_widgets(scene)
    check(bpy.data.objects['ObservedWidget'].hide_get() and not bpy.data.objects['ObservedWidget'].hide_render, 'World hides widget locally without changing render visibility')
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'placed.blend'))
    placed_hash = file_hash(out / 'placed.blend')
    bpy.ops.wm.open_mainfile(filepath=str(out / 'placed.blend'), load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    check(all((point(n) - Vector(v)).length < 1e-5 for n, v in positions.items()), 'saved/reopened evaluated skin and static positions match')
    check(key_state() == keys, 'native animation channels preserved exactly')
    placement.restore_widgets(scene)
    check(not bpy.data.objects['ObservedWidget'].hide_get(), 'Action restores original widget visibility')
    samples = []
    for frame in (1, 5, 9):
        scene.frame_set(frame)
        samples.append(list(point('SyntheticSkin0')))
        check((bpy.data.objects['SyntheticRig0'].matrix_world.translation - Vector((2, 3, 4))).length < 1e-5,
              'placement persists through frame ' + str(frame))
    check((Vector(samples[0]) - Vector(samples[1])).length > .1, 'native skin deformation still plays')
    scene.frame_set(5)
    frozen_position = point('SyntheticSkin0').copy()
    scene['asset_director_preview_only'] = True
    before_names = {o.name for o in bpy.data.objects}
    before_meshes = {m.name for m in bpy.data.meshes}
    before_flags = {o.name: o.hide_render for o in scene.objects}
    try:
        with frozen_meshes(True):
            raise RuntimeError('Deliberate derivative interruption')
    except RuntimeError as exc:
        check(str(exc) == 'Deliberate derivative interruption', 'deliberate interrupted export exercised')
    check(before_names == {o.name for o in bpy.data.objects} and before_meshes == {m.name for m in bpy.data.meshes}
          and before_flags == {o.name: o.hide_render for o in scene.objects} and key_state() == keys,
          'interrupted derivative restores objects, meshes, flags and actions')
    exported = export(out / 'world.glb', {'takes': [], 'checkpoint': True, 'preview_profile': 'world-static-v1'})
    doc = gltf(out / 'world.glb')
    mapped = {item['source']: item['node'] for item in exported['static_objects']}
    check(not doc.get('animations') and exported['reference_frame'] == 5, 'World derivative is static at its recorded frame')
    meshes = {n.get('name') for n in doc['nodes'] if 'mesh' in n}
    check('ObservedWidget' not in mapped and {mapped[n] for n in ('SyntheticSkin0', 'SyntheticSkin1', 'StaticProp', 'ObservedWidget.001')} <= meshes,
          'World excludes only referenced helper and retains real/similarly-named meshes')
    check(not bpy.data.objects['ObservedWidget'].hide_render and key_state() == keys, 'export restores widget flags and preserves source animation')
    export(out / 'action.glb', {'takes': [], 'checkpoint': True, 'preview_profile': 'inspection-v1'})
    check(bool(gltf(out / 'action.glb').get('animations')), 'Action derivative retains actual animation')
    check(file_hash(out / 'baseline-failure.blend') == original and file_hash(out / 'placed.blend') == placed_hash, 'original failure and saved checkpoint bytes preserved')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(out / 'world.glb'))
    actual = point(mapped['SyntheticSkin0'])
    atomic_json(out / 'static-comparison.json', {'expected': list(frozen_position), 'actual': list(actual)})
    check((actual - frozen_position).length < 1e-4, 'static GLB skin placement matches evaluated Blender frame')
    atomic_json(out / 'world_layers_report.json', {'status': 'PASS', 'checks': checks, 'blender': bpy.app.version_string,
                'human_approval': 'NOT_GRANTED', 'native_gui': 'NOT_TESTED'})
    print('WORLD_LAYERS_PASS', len(checks))
except BaseException as exc:
    atomic_json(out / 'failure.json', {'status': 'FAIL', 'checks': checks, 'error': str(exc)})
    raise
