"""Real Blender fixture: three animated scenes -> frozen checkpoints -> silent film.

Synthetic geometry, real Blender saves/audits/CPU rendering, real FFmpeg encode
and decode. Headless task setup does NOT certify a native window, selected UI
workspace, human edits, authenticated Codex, private input rights or artistry.
"""
from pathlib import Path
import json
import shutil
import sys
import uuid
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director import film, jobs, task_workspace
from asset_director.core import Library, DirectorError, atomic_json, file_hash

OUT = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
CHECKS = []


def check(ok, name, **details):
    if not ok:
        raise AssertionError(name + ': ' + json.dumps(details, default=str))
    CHECKS.append({'check': name, **details})


def rejection(fn, expected, name):
    try:
        fn()
    except DirectorError as exc:
        check(exc.code == expected, name, code=exc.code, expected=expected)
        return
    raise AssertionError(name + ': expected refusal ' + expected)


def create_scene(filename, number):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 1
    scene.render.fps, scene.render.fps_base = 24, 1.0
    scene.frame_start, scene.frame_end = 1, 4
    scene.render.resolution_x = scene.render.resolution_y = 64
    scene.render.resolution_percentage = 100
    scene.render.use_compositing = scene.render.use_sequencer = False
    bpy.ops.mesh.primitive_cube_add(size=1)
    subject = bpy.context.object; subject.name = 'Synthetic performer ' + str(number)
    for frame, x in [(1, -.4), (4, .4)]:
        subject.location = (x, 0, .5)
        subject.keyframe_insert(data_path='location', frame=frame)
    bpy.ops.mesh.primitive_plane_add(size=8)
    plane = bpy.context.object; plane.name = 'Synthetic floor'
    camera_data = bpy.data.cameras.new('Synthetic camera ' + str(number))
    camera = bpy.data.objects.new(camera_data.name, camera_data); scene.collection.objects.link(camera)
    camera.location = (2.5 + number * .1, -4, 2)
    camera.rotation_euler = (Vector((0, 0, .5)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = camera
    light_data = bpy.data.lights.new('Synthetic key', 'AREA'); light_data.energy = 400; light_data.size = 4
    light = bpy.data.objects.new('Synthetic key', light_data); scene.collection.objects.link(light)
    light.location = (0, -2, 4)
    light.rotation_euler = (Vector((0, 0, .5)) - light.location).to_track_quat('-Z', 'Y').to_euler()
    scene.world = bpy.data.worlds.new('Synthetic world'); scene.world.use_nodes = True
    background = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
    background.inputs['Strength'].default_value = .2
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(filename), check_existing=False)
    return subject.name, camera.name


def main():
    encoder, probe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    check(bool(encoder and probe), 'real_encoder_executables_present')
    project_id = 'prj_' + str(uuid.uuid4())
    project = OUT / 'project'; (project / 'Scenes').mkdir(parents=True)
    atomic_json(project / 'project.json', {'id': project_id, 'owner': 'asset-director-launcher'})
    clips = []
    with Library(OUT / 'library') as lib:
        for number in range(1, 4):
            scene_id, task_id = 'sc_' + str(uuid.uuid4()), 'task_' + str(uuid.uuid4())
            source = project / 'Scenes' / ('source-' + str(number) + '.blend')
            subject, camera = create_scene(source, number)
            source_hash = file_hash(source)
            task = {'schema': 1, 'id': task_id, 'projectId': project_id, 'sceneId': scene_id, 'stage': 'shots',
                    'projectDirectory': str(project), 'library': str(lib.root), 'input': {'path': source.relative_to(project).as_posix(), 'sha256': source_hash},
                    'workingScene': 'Scenes/edit-' + str(number) + '.blend', 'checkpointScene': 'Scenes/checkpoint-' + str(number) + '.blend',
                    'returnFile': 'Docs/Workbench/' + task_id + '-return.json', 'targets': [camera], 'camera': camera,
                    'frame': 1, 'action': 'workbench-edit', 'state': 'RUNNING', 'startedAt': 'synthetic-fixture', 'selectedSources': []}
            initialized = task_workspace.initialize(task)
            check(not initialized['gui_configured'], 'headless_does_not_claim_gui', scene=number)
            check(bpy.context.scene.camera.name == camera, 'exact_camera_selected', scene=number)
            check(bpy.context.view_layer.objects.active.name == camera, 'exact_target_selected', scene=number)
            bpy.data.objects[camera].data.lens = 45 + number
            returned = task_workspace.checkpoint(task, initialized)
            checkpoint = project / returned['path']
            check(Path(bpy.data.filepath).resolve() == (project / task['workingScene']).resolve(), 'checkpoint_is_copy_not_live_file', scene=number)
            check(file_hash(source) == source_hash, 'original_preserved', scene=number)
            check(returned['human_acceptance'] == 'PENDING' and returned['audit']['camera'] == camera, 'observed_checkpoint_not_autoapproved', scene=number)
            rejection(lambda: task_workspace.checkpoint(task, initialized), 'CHECKPOINT_EXISTS', 'checkpoint_never_overwritten')
            ready = jobs.prepare(lib, 'render-readiness', str(checkpoint))
            ready = jobs.run(lib, ready['id'], bpy.app.binary_path, timeout=180)
            readiness = json.loads((lib.root / 'jobs' / ready['id'] / 'result.json').read_text())['data']
            check(not readiness['blockers'], 'real_saved_scene_ready', scene=number, blockers=readiness['blockers'])
            options = {'readiness_job': ready['id'], 'camera': camera, 'start': 1, 'end': 4, 'width': 64, 'height': 64, 'samples': 1}
            shot = jobs.prepare(lib, 'render-frames', str(checkpoint), options=options)
            shot = jobs.run(lib, shot['id'], bpy.app.binary_path, timeout=180)
            sequence = film.rendered_sequence(lib, shot['id'])
            check(len(sequence['frames']) == 4, 'complete_real_cpu_sequence', scene=number)
            check(len({frame[1]['sha256'] for frame in sequence['frames']}) > 1, 'animation_changes_rendered_frames', scene=number)
            check(file_hash(checkpoint) == returned['sha256'], 'render_preserves_frozen_checkpoint', scene=number)
            check(jobs.run(lib, shot['id'], bpy.app.binary_path, timeout=180)['id'] == shot['id'], 'idempotent_verified_render_replay', scene=number)
            clips.append({'scene_id': scene_id, 'job_id': shot['id'], 'checkpoint_sha256': returned['sha256']})
        plan = {'schema': 1, 'id': 'cut_' + str(uuid.uuid4()), 'project_id': project_id, 'clips': clips}
        result = film.assemble(lib, plan, project, encoder, probe)
        check(result['state'] == 'SUCCEEDED' and result['frames'] == 12 and len(result['sources']) == 3, 'three_scene_film_encoded_and_decoded')
        check(result['audio'] == 'NONE' and result['human_acceptance'] == 'PENDING', 'technical_success_not_artistic_approval')
        check(result['fps'] == {'numerator': 24, 'denominator': 1} and result['dimensions'] == [64, 64], 'exact_delivery_timebase')
        # Retain only the generated movie, not the fixture's .blend files or catalog.
        movie = project / 'Deliverables' / plan['id'] / result['file']
        shutil.copyfile(movie, OUT / 'synthetic-film.mp4')
        check(file_hash(OUT / 'synthetic-film.mp4') == result['sha256'], 'retained_film_matches_verified_output')
        rejection(lambda: film.assemble(lib, plan, project, encoder, probe), 'OUTPUT_EXISTS', 'film_does_not_overwrite')
        bad = dict(plan, id='cut_' + str(uuid.uuid4()), clips=[dict(clips[0], checkpoint_sha256='f' * 64)])
        rejection(lambda: film.assemble(lib, bad, project, encoder, probe), 'STALE_FILM_PLAN', 'wrong_checkpoint_refused')
        frame = film.rendered_sequence(lib, clips[0]['job_id'])['frames'][0][0]
        frame.write_bytes(b'DELIBERATELY CORRUPTED SYNTHETIC FRAME')
        rejection(lambda: film.rendered_sequence(lib, clips[0]['job_id']), 'STALE_INPUT', 'tampered_render_refused')
    atomic_json(OUT / 'workbench_film_report.json', {'status': 'PASS', 'checks': CHECKS, 'blender': bpy.app.version_string,
        'not_tested': ['native GUI/window focus', 'authenticated Codex', 'private assets', 'creative quality', 'audio', 'full live task bridge']})


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        atomic_json(OUT / 'workbench_film_failure.json', {'status': 'FAIL', 'checks': CHECKS, 'error': str(exc)})
        raise
