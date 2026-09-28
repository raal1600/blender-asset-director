"""Real camera projection and motion evidence from generated geometry only."""
from pathlib import Path
import sys
from uuid import uuid4
import bpy
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director.core import atomic_json, file_hash, DirectorError
from asset_director import shot_view, action_layer
from asset_director.viewer_export import export

out = Path(sys.argv[sys.argv.index('--') + 1]);out.mkdir(parents=True, exist_ok=False)
report = {'scope': 'REAL_GENERATED_SHOT_CAMERA', 'checks': [], 'cases': [], 'human_review': 'NOT_TESTED'}


def check(value, label):
    assert value, label
    report['checks'].append(label)


try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene;scene.frame_start = 1;scene.frame_end = 9
    scene.render.fps = 30;scene.render.fps_base = 1.001
    scene.render.resolution_x = 640;scene.render.resolution_y = 360
    scene.render.pixel_aspect_x = 1.2;scene.render.pixel_aspect_y = .9
    bpy.ops.mesh.primitive_cube_add(size=.5)
    subject = bpy.context.object;subject.name = 'SyntheticShotSubject'
    for frame, x in [(1, -1), (5, 0), (9, 1)]:
        subject.location.x = x;subject.keyframe_insert('location', frame=frame)
    for name, projection in [('SyntheticPerspective', 'PERSP'), ('SyntheticOrtho', 'ORTHO')]:
        data = bpy.data.cameras.new(name);obj = bpy.data.objects.new(name, data);scene.collection.objects.link(obj)
        data.type = projection;data.lens = 45;data.ortho_scale = 5;data.shift_x = .12;data.shift_y = -.07
        data.sensor_fit = 'VERTICAL';data.sensor_height = 24
        obj.location = (2, -5, 2);obj.rotation_euler = (-obj.location).to_track_quat('-Z', 'Y').to_euler()
        if projection == 'PERSP':
            for frame, offset, lens in [(1, 0, 45), (9, .6, 65)]:
                obj.location.x = 2 + offset;obj.keyframe_insert('location', frame=frame)
                data.lens = lens;data.keyframe_insert('lens', frame=frame)
    scene.camera = scene.objects['SyntheticOrtho'];scene.frame_set(4, subframe=.25)
    source = out/'source.blend';bpy.ops.wm.save_as_mainfile(filepath=str(source));original = file_hash(source)
    for label, camera, first, last, profile in [
        ('perspective', 'SyntheticPerspective', 2, 9, 'shot-framing-v1'),
        ('orthographic', 'SyntheticOrtho', 3, 7, 'look-inspection-v1'),
        ('single-frame', 'SyntheticPerspective', 5, 5, 'shot-framing-v1'),
        ('camera-only', 'SyntheticPerspective', 2, 8, 'shot-framing-v1')]:
        bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
        scene = bpy.context.scene;case_source = source
        if label == 'camera-only':
            scene.objects['SyntheticShotSubject'].animation_data_clear();case_source = out/'camera-only.blend'
            bpy.ops.wm.save_as_mainfile(filepath=str(case_source))
        scene['asset_director_preview_only'] = True
        before = action_layer.preserved(set());old_frame = (scene.frame_current, scene.frame_subframe)
        shot = {'version': 'shot-view-v1', 'id': 'shot_'+str(uuid4()), 'revision': 1, 'name': label,
                'camera': camera, 'start': first, 'end': last}
        sampled = shot_view.inspect(shot);native = []
        for sample in sampled['samples']:
            scene.frame_set(sample['frame']);deps = bpy.context.evaluated_depsgraph_get()
            mesh = scene.objects['SyntheticShotSubject'].evaluated_get(deps)
            point = sum((mesh.matrix_world @ v.co for v in mesh.data.vertices), Vector()) / len(mesh.data.vertices)
            expected = world_to_camera_view(scene, scene.objects[camera].evaluated_get(deps), point)
            matrix = lambda value: Matrix([value[i:i+4] for i in range(0, 16, 4)])
            clip = matrix(sample['projection_matrix']) @ matrix(sample['matrix_world']).inverted() @ point.to_4d()
            assert max(abs(clip[i]/clip.w-(expected[i]*2-1)) for i in range(2)) < 1e-5
            native.append({'frame': sample['frame'], 'position': [point.x, point.z, -point.y], 'ndc': [expected.x*2-1, expected.y*2-1]})
        scene.frame_set(old_frame[0], subframe=old_frame[1])
        result = export(out/(label+'.glb'), {'takes': [], 'checkpoint': True, 'preview_profile': profile, 'shot_view': shot})
        check(result['shot_view'] == sampled, label+' camera samples survive complete native export')
        check(before == action_layer.preserved(set()) and (scene.frame_current, scene.frame_subframe) == old_frame and
              scene.camera.name == 'SyntheticOrtho', label+' preserves source motion, current frame and active camera')
        report['cases'].append({'label': label, 'source': case_source.name, 'source_sha256': file_hash(case_source),
            'model': label+'.glb', 'model_sha256': file_hash(out/(label+'.glb')), 'profile': profile,
            'shotView': sampled, 'playback': result['playback'], 'timebase': result['timebase'], 'samples': native})
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False);scene = bpy.context.scene
    scene['asset_director_preview_only'] = True
    for patch in [{'camera': 'Missing camera'}, {'start': 0}, {'end': 10}, {'end': 500}]:
        try:shot_view.inspect(shot | patch)
        except DirectorError:report['checks'].append('Refused invalid shot '+str(patch))
        else:raise AssertionError('Invalid shot accepted')
    scene.objects[shot['camera']].data.type = 'PANO'
    try:shot_view.inspect(shot)
    except DirectorError:report['checks'].append('Panorama refuses instead of perspective approximation')
    else:raise AssertionError('Panorama silently approximated')
    check(file_hash(source) == original, 'Original source bytes preserved through all previews and refusals')
    report.update(status='PASS', blender=bpy.app.version_string)
except Exception as error:
    report.update(status='FAIL', error=repr(error));raise
finally:
    atomic_json(out/'RESULTS.json', report)
    print({'status': report.get('status'), 'checks': len(report['checks']), 'error': report.get('error')})
