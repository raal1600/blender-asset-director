"""Actual deformed-mesh regression for controller/ornament leakage in clay.

Synthetic control hierarchy, not the user's motion. Uses no live MCP or user
project. The output images are structural evidence, not dance acceptance.
Run in isolated background Blender: -- OUTPUT_DIRECTORY BACKEND_LIBRARY.
"""
from pathlib import Path
import json
import math
import shutil
import sys
import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]
from asset_director import blender_ops as ops, jobs, motion_assets as ma
from asset_director.core import Library, atomic_json, file_hash, load_json, DirectorError
from asset_director.motion_body import build_profile
from asset_director.proxy_geometry import check_attachments
from headless_fixture import humanoid


def main(out, library):
    assert bpy.app.background
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=True)
    checks = []
    def passed(name, **details): checks.append({'name': name, 'status': 'PASS', **details})
    with Library(library) as lib:
        terms = lib.root/'licenses/proxy-visual-synthetic.txt'
        terms.write_text('Synthetic proxy_visual_fixture.py data; CC0; not human capture.')
        rights = {'license_id': 'CC0-1.0', 'license_url': 'https://creativecommons.org/publicdomain/zero/1.0/',
                  'evidence': [{'path': terms.relative_to(lib.root).as_posix(), 'sha256': file_hash(terms), 'size': terms.stat().st_size}],
                  'commercial': 'allowed', 'adaptation': 'allowed', 'raw_redistribution': 'allowed', 'attribution': 'Synthetic CI fixture'}
        def run(operation, source=None, options=None):
            job = jobs.prepare(lib, operation, str(source) if source else None, options=options)
            jobs.run(lib, job['id'], bpy.app.binary_path, 180)
            directory = lib.root/'jobs'/job['id']
            return directory/'result.blend', load_json(directory/'result.json')['data'], job

        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene; scene.render.fps = 24
        source, old_skin = humanoid('UnrelatedTestRig')
        bpy.data.objects.remove(old_skin, do_unlink=True)
        bpy.context.view_layer.objects.active = source
        bpy.ops.object.mode_set(mode='EDIT')
        source.data.edit_bones['root'].head = (0, 0, -.316)
        source.data.edit_bones['root'].tail = (4, 3, 8)
        helper = source.data.edit_bones.new('HelperPivot')
        helper.head = (.17, .06, 1.35); helper.tail = (2, .06, 1.35)
        helper.parent = source.data.edit_bones['spine']
        source.data.edit_bones['head'].parent = helper
        for base in ('spine', 'head', 'upperarm_l'):
            ornament = source.data.edit_bones.new('Decorative_' + base)
            ornament.head = source.data.edit_bones[base].head + Vector((0, 0, .1))
            ornament.tail = ornament.head + Vector((7, 2, 4))
            ornament.parent = source.data.edit_bones[base]
        for name in ('thigh_l', 'calf_l', 'thigh_r', 'calf_r', 'hand_l', 'foot_r', 'head'):
            bone = source.data.edit_bones[name]
            bone.tail = bone.head + Vector((.27, .05, .08))
        bpy.ops.object.mode_set(mode='OBJECT')
        roles = {r: r for r in ops.rig_report(source)['roles']}
        renames = {b.name: f'ControlNode_{i:03}' for i, b in enumerate(source.data.bones)}
        for old, new in renames.items(): source.data.bones[old].name = new
        roles = {r: renames[n] for r, n in roles.items()}
        helpers = {renames['HelperPivot'], *[renames['Decorative_'+n] for n in ('spine','head','upperarm_l')]}
        for pb in source.pose.bones: pb.rotation_mode = 'QUATERNION'
        for frame in range(1, 26):
            fraction = (frame-1)/24
            hips = source.pose.bones[roles['hips']]
            hips.location = (.48*fraction, 0, 0); hips.keyframe_insert('location', frame=frame)
            for role, angle in (('spine', .2), ('thigh_l', .5), ('thigh_r', -.3), ('forearm_l', 1.1)):
                pb = source.pose.bones[roles[role]]
                pb.rotation_quaternion = Vector((1,0,0)).rotation_difference(Vector((1, angle*math.sin(fraction*math.pi), 0)).normalized())
                pb.keyframe_insert('rotation_quaternion', frame=frame)
            helper_pose = source.pose.bones[renames['HelperPivot']]
            helper_pose.rotation_quaternion = Quaternion((0, 1, 0), .7*math.sin(fraction*math.pi))
            helper_pose.keyframe_insert('rotation_quaternion', frame=frame)
        action = source.animation_data.action
        for curve in ops.curves(action, source.animation_data.action_slot):
            for k in curve.keyframe_points: k.interpolation = 'LINEAR'
        scene.frame_start = 1; scene.frame_end = 25; scene.frame_set(1)
        action_name, source_name = action.name, source.name
        original = out/'synthetic-import-style-source.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(original)); original_hash = file_hash(original)
        _, _, export_job = run('motion-export', original, {
            'target_object': source_name, 'action': action_name, 'start': 1, 'end': 25, 'sample_fps': 24,
            'meters_per_unit': 1, 'source_to_canonical': [1,0,0,0,1,0,0,0,1], 'roles': roles,
            'source': {'provider': 'local', 'source_id': 'synthetic-controller-leak',
                       'source_url': 'https://github.com/raal1600/blender-asset-director',
                       'capture_method': 'generated', 'capture_evidence': 'Synthetic regression, not a human performance'},
            'rights': rights, 'semantics': {'title': 'Synthetic moving hips with stationary root', 'labels': ['synthetic'],
                                          'description': 'Controller/ornament geometry regression, not dance'}, 'project_use': 'commercial'})
        mid = ma.collect(lib, export_job['id'])['motion_id']; record, samples = ma.load(lib, mid, samples=True)
        passed('export rig with decorative tails and unnamed intermediate helpers')
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add(location=(9,4,0)); bpy.context.object.name = 'ProtectedFixtureProp'
        staging = out/'staging.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(staging)); staging_hash = file_hash(staging)
        for variant, scales in [('source_shaped', {}), ('short_legs', {
                'thigh_l': .8, 'calf_l': .8, 'thigh_r': .8, 'calf_r': .8,
                'upperarm_l': 1.15, 'forearm_l': 1.15, 'upperarm_r': 1.15, 'forearm_r': 1.15})]:
            proxy_file, proxy, _ = run('clay-proxy', staging, {'motion_id': mid, 'project_use': 'commercial', 'length_scales': scales})
            graph = proxy['proxy_geometry']['graph']
            excluded = set(graph['excluded_bones'])
            assert roles['root'] in excluded and helpers <= excluded
            assert not graph['terminal_display_tails_used']
            assert all(s['start_bone'] not in excluded and s['end_bone'] not in excluded for s in graph['segments'])
            profile = build_profile(record['skeleton'], proxy['skeleton'])
            assert abs(profile['chain_ratios']['leg_l'] - (.8 if scales else 1)) < 1e-5
            assert abs(profile['chain_ratios']['arm_l'] - (1.15 if scales else 1)) < 1e-5
            bpy.ops.wm.open_mainfile(filepath=str(proxy_file), load_ui=False, use_scripts=False)
            target = bpy.data.objects[proxy['armature']]; skin = bpy.data.objects[proxy['mesh']]
            assert all(n in target.data.bones for n in excluded), 'Helpers were deleted from the rig'
            assert not excluded & {g.name for g in skin.vertex_groups}
            surface = bmesh.new()
            try:
                surface.from_mesh(skin.data)
                assert all(edge.is_manifold for edge in surface.edges), 'Open capsule surface'
                assert surface.calc_volume(signed=True) > 0, 'Capsule normals face inward'
            finally:
                surface.free()
            assert {b['name'] for b in proxy['rig']['bones']} == set(renames.values())
            root_start = target.pose.bones[roles['root']].head.copy()
            origin = list(target.pose.bones[roles['hips']].head)
            options = {'motion_id': mid, 'project_use': 'commercial', 'target_object': target.name,
                       'target_fps': 30, 'target_meters_per_unit': 1,
                       'mapping': profile['mapping'], 'alignment': {n: [v for row in Matrix.Identity(4) for v in row] for n in profile['mapping'].values()},
                       'expected_source_fingerprint': record['skeleton']['source_fingerprint'],
                       'expected_target_fingerprint': proxy['rig']['fingerprint'],
                       'pose_space': {'rotation': [1,0,0,0,1,0,0,0,1], 'translation_bone': roles['hips'],
                                      'translation_scale': 1, 'translation_scale_xyz': profile['suggested_translation_scale_xyz'],
                                      'target_origin': origin}}
            transferred, report, _ = run('motion-retarget', proxy_file, options)
            assert report['proxy_attachment_check']['status'] == 'PASS'
            bpy.ops.wm.open_mainfile(filepath=str(transferred), load_ui=False, use_scripts=False)
            target = bpy.data.objects[proxy['armature']]; skin = bpy.data.objects[proxy['mesh']]
            qa = check_attachments(target, [1+i*30/24 for i in range(25)])
            bpy.context.scene.frame_set(31)
            assert (target.pose.bones[roles['root']].head-root_start).length < 1e-6
            assert (target.pose.bones[roles['hips']].head-Vector(origin)).length > .3
            assert all(tuple(b.scale) == (1.,1.,1.) for b in target.pose.bones)
            assert 'ProtectedFixtureProp' in bpy.data.objects
            passed(variant + ': evaluated mesh follows anatomy, not root/helpers', **qa,
                   leg_ratio=profile['chain_ratios']['leg_l'], arm_ratio=profile['chain_ratios']['arm_l'])
            if not scales:
                vertex_id = proxy['proxy_geometry']['attachments'][0]['indices'][0]
                skin.data.vertices[vertex_id].co.x += .25; skin.data.update()
                try:
                    check_attachments(target, [31]); raise AssertionError('Displaced skin was falsely accepted')
                except DirectorError as exc:
                    assert exc.code == 'PROXY_ATTACHMENT_FAILED', exc.code
                passed('negative control: detached evaluated mesh fails despite valid rig')
                skin.vertex_groups.new(name=roles['root']).add([0], 1, 'REPLACE')
                try:
                    check_attachments(target, [31]); raise AssertionError('Root-weighted geometry was accepted')
                except DirectorError as exc:
                    assert exc.code == 'PROXY_WEIGHT_INVALID', exc.code
                passed('negative control: nonanatomical skin weights are refused')
            else:
                camera, _, _ = run('camera-fit', transferred, {'subjects': [proxy['mesh']], 'frames': [1,16,31],
                                   'lens_mm': 50, 'direction': [.3,-1,.15], 'margin': .15})
                lit, _, _ = run('light-rig', camera, {'subjects': [proxy['mesh']],
                                'lights': [{'type': 'AREA', 'energy': 200, 'offset': [1,-2,2], 'color': [1,1,1], 'size_ratio': 2}]})
                _, preview, preview_job = run('preview', lit, {'frames': [1,16], 'width': 480, 'height': 480, 'samples': 8})
                assert preview['production_settings_restored']
                directory = lib.root/'jobs'/preview_job['id']
                pngs = sorted(directory.glob('*.png')); assert len(pngs) == 2, list(directory.iterdir())
                for label, image in zip(('proxy-rest.png','proxy-pose.png'), pngs): shutil.copyfile(image, out/label)
                passed('rest and articulated midpoint CPU mesh previews; render settings restored', frames=[1,16])
        assert file_hash(original) == original_hash and file_hash(staging) == staging_hash
        passed('source and staging preserved; old timing/scale implementation unchanged')
        atomic_json(out/'proxy_visual_report.json', {'status': 'PASS', 'blender_version': bpy.app.version_string,
                    'checks': checks, 'notice': 'Synthetic mesh attachment evidence only; real-source and continuous visual acceptance still required'})
        print(json.dumps({'status':'PASS','checks':len(checks)}))


if __name__ == '__main__': main(*sys.argv[sys.argv.index('--')+1:])
