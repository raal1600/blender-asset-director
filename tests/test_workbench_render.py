"""Portable contract/failure tests. Synthetic native receipts are NOT Blender evidence.

The encoder case, when tools are installed, actually runs FFmpeg and FFprobe on
small generated PNGs. Real Blender coverage lives in workbench_film_fixture.py.
"""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import shutil
import struct
import unittest
import uuid
import zlib
from asset_director import film, jobs, render_sequence as contract, task_workspace
from asset_director.core import Library, DirectorError, atomic_json, file_hash


def png(width=32, height=32, value=90):
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff)
    raw = (b'\0' + bytes([value, 80, 120]) * width) * height
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def synthetic_success(lib, job, data, frames=None):
    """Exercise evidence parser with labelled fake worker responses, not an executor."""
    directory = lib.root / 'jobs' / job['id']
    atomic_json(directory / 'result.json', {'job_id': job['id'], 'status': 'OK', 'data': data, 'synthetic_unit_fixture': True})
    for name, content in (frames or {}).items():
        (directory / name).write_bytes(content)
    job['state'] = 'SUCCEEDED'
    job['outputs'] = [{'path': f.relative_to(lib.root).as_posix(), 'size': f.stat().st_size, 'sha256': file_hash(f)} for f in directory.iterdir() if f.name != 'job.json']
    atomic_json(directory / 'job.json', job)
    return job


class RenderContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lib = Library(self.root / 'library')
        self.addCleanup(self.lib.db.close)
        self.project_id = 'prj_' + str(uuid.uuid4())
        self.scene_id = 'sc_' + str(uuid.uuid4())
        self.project = self.root / 'project'
        (self.project / 'Scenes').mkdir(parents=True)
        atomic_json(self.project / 'project.json', {'owner': 'asset-director-launcher', 'id': self.project_id})
        self.source = self.project / 'Scenes' / 'synthetic.blend'
        self.source.write_bytes(b'BLENDER-v420SYNTHETIC UNIT TEST ONLY')
        ready = jobs.prepare(self.lib, 'render-readiness', str(self.source))
        self.audit = {'kind': 'RENDER_READINESS', 'blockers': [], 'cameras': ['Camera.042'], 'camera': 'Camera.042',
                      'frame_range': [1, 24], 'fps': {'numerator': 24, 'denominator': 1}, 'dependencies': []}
        self.ready = synthetic_success(self.lib, ready, self.audit)
        self.options = {'readiness_job': ready['id'], 'camera': 'Camera.042', 'start': 1, 'end': 3, 'width': 32, 'height': 32, 'samples': 1}

    def refusal(self, function, code):
        with self.assertRaises(DirectorError) as raised:
            function()
        self.assertEqual(raised.exception.code, code)

    def rendered(self, **changes):
        options = {**self.options, **changes}
        job = jobs.prepare(self.lib, 'render-frames', str(self.source), options=options)
        count = options['end'] - options['start'] + 1
        data = {'kind': 'RENDERED_FRAME_SEQUENCE', 'delivery_master': False, 'frame_count': count,
                'frames': [{'file': 'frame_%06d.png' % i, 'frame': options['start'] + i - 1} for i in range(1, count + 1)],
                'width': options['width'], 'height': options['height'], 'fps': self.audit['fps'], 'source_sha256': file_hash(self.source)}
        return synthetic_success(self.lib, job, data, {f['file']: png(options['width'], options['height'], 50 + i * 10) for i, f in enumerate(data['frames'])})

    def plan(self, job_id):
        return {'schema': 1, 'id': 'cut_' + str(uuid.uuid4()), 'project_id': self.project_id,
                'clips': [{'scene_id': self.scene_id, 'job_id': job_id, 'checkpoint_sha256': file_hash(self.source)}]}

    def test_explicit_render_contract_and_idempotent_preparation(self):
        self.assertEqual(contract.validate(self.options), 3)
        job = jobs.prepare(self.lib, 'render-frames', str(self.source), options=self.options)
        self.assertEqual(job, jobs.prepare(self.lib, 'render-frames', str(self.source), options=self.options))
        self.assertEqual(len(job['specification']['source_files']), 1)
        self.assertEqual(job['specification']['source_files'][0]['path'], self.ready['outputs'][0]['path'])
        self.assertEqual(self.source.read_bytes(), b'BLENDER-v420SYNTHETIC UNIT TEST ONLY')

    def test_rejects_invented_settings_or_script_surface(self):
        for key in self.options:
            with self.subTest(key=key):
                value = deepcopy(self.options); del value[key]
                self.refusal(lambda: contract.validate(value), 'INVALID_SCHEMA')
        self.refusal(lambda: contract.validate({**self.options, 'script': 'anything'}), 'INVALID_SCHEMA')

    def test_gpu_selection_is_observed_and_bound_to_job_identity(self):
        gpu = {'backend': 'OPTIX', 'id': 'synthetic-gpu'}
        self.refusal(lambda: jobs.prepare(self.lib, 'render-frames', str(self.source),
                     options={**self.options, 'render_device': gpu}), 'RENDER_DEVICE_UNAVAILABLE')
        self.audit['render_devices'] = [{**gpu, 'name': 'Synthetic GPU'}]
        synthetic_success(self.lib, self.ready, self.audit)
        cpu = jobs.prepare(self.lib, 'render-frames', str(self.source), options=self.options)
        options = {**self.options, 'render_device': gpu}
        native = jobs.prepare(self.lib, 'render-frames', str(self.source), options=options)
        self.assertNotEqual(cpu['id'], native['id'])
        self.assertEqual(native['specification']['options']['render_device'], gpu)
        self.assertEqual(native, jobs.prepare(self.lib, 'render-frames', str(self.source), options=options))
        self.refusal(lambda: jobs.prepare(self.lib, 'render-frames', str(self.source),
                     options={**options, 'end': 360, 'width': 1920, 'height': 1080, 'samples': 128}), 'RESOURCE_LIMIT')
        self.assertEqual(self.source.read_bytes(), b'BLENDER-v420SYNTHETIC UNIT TEST ONLY')

    def test_rejects_boolean_noninteger_and_unbounded_values(self):
        for key in ['start', 'end', 'width', 'height', 'samples']:
            for value in [True, '32', 1.5]:
                with self.subTest(key=key, value=value):
                    self.refusal(lambda: contract.validate({**self.options, key: value}), 'INVALID_SCHEMA')
        for patch in [{'end': 361}, {'start': -100001}, {'width': 641}, {'samples': 0}, {'height': 1082}, {'width': 1920, 'height': 1080, 'end': 360, 'samples': 128}]:
            self.refusal(lambda: contract.validate({**self.options, **patch}), 'RESOURCE_LIMIT')

    def test_requires_saved_blender_input_and_no_asset_id(self):
        self.refusal(lambda: jobs.prepare(self.lib, 'render-readiness'), 'TARGET_REQUIRED')
        self.refusal(lambda: jobs.prepare(self.lib, 'render-frames', str(self.source), 'not-an-asset', self.options), 'TARGET_REQUIRED')
        obj = self.project / 'Scenes' / 'source.obj'; obj.write_text('o test')
        self.refusal(lambda: jobs.prepare(self.lib, 'render-readiness', str(obj)), 'TARGET_REQUIRED')

    def test_camera_and_range_must_be_observed(self):
        self.refusal(lambda: jobs.prepare(self.lib, 'render-frames', str(self.source), options={**self.options, 'camera': 'invented'}), 'CAMERA_REQUIRED')
        self.refusal(lambda: jobs.prepare(self.lib, 'render-frames', str(self.source), options={**self.options, 'end': 25}), 'INVALID_RANGE')

    def test_readiness_must_be_successful_same_input_and_not_tampered(self):
        other = self.project / 'Scenes' / 'other.blend'; other.write_bytes(b'BLENDER other bytes')
        self.refusal(lambda: contract.prepare(self.lib, self.options, str(other)), 'STALE_READINESS')
        report = self.lib.root / 'jobs' / self.ready['id'] / 'result.json'
        report.write_text('{}')
        self.refusal(lambda: contract.prepare(self.lib, self.options, str(self.source)), 'STALE_INPUT')

    def test_blockers_are_not_ignored(self):
        self.audit['blockers'] = ['Cache review required']
        synthetic_success(self.lib, self.ready, self.audit)
        self.refusal(lambda: contract.prepare(self.lib, self.options, str(self.source)), 'RENDER_BLOCKED')

    def test_external_dependency_drift_invalidates_render_job(self):
        texture = self.root / 'texture.png'; texture.write_bytes(png())
        self.audit['dependencies'] = [{'path': str(texture), 'sha256': file_hash(texture), 'size': texture.stat().st_size}]
        synthetic_success(self.lib, self.ready, self.audit)
        job = jobs.prepare(self.lib, 'render-frames', str(self.source), options=self.options)
        texture.write_bytes(png(value=77))
        self.refusal(lambda: jobs.read_job(self.lib, job['id']), 'STALE_RENDER_DEPENDENCIES')

    def test_frame_sequence_identity_and_corruption(self):
        job = self.rendered()
        checked = film.rendered_sequence(self.lib, job['id'])
        self.assertEqual(len(checked['frames']), 3)
        checked['frames'][1][0].write_bytes(b'corrupt PNG')
        self.refusal(lambda: film.rendered_sequence(self.lib, job['id']), 'STALE_INPUT')

    def test_preview_or_readiness_is_not_a_rendered_film(self):
        self.refusal(lambda: film.rendered_sequence(self.lib, self.ready['id']), 'RENDER_REQUIRED')

    def test_plan_identifiers_scope_and_limits(self):
        plan = self.plan('j_' + 'a' * 24)
        film.validate_plan(plan)
        for patch in [{'id': '../../overwrite'}, {'project_id': None}, {'clips': []}, {'clips': plan['clips'] * 33}, {'script': 'anything'}]:
            with self.subTest(patch=patch):
                with self.assertRaises(DirectorError): film.validate_plan({**plan, **patch})

    def test_missing_encoder_is_not_automatically_installed(self):
        self.refusal(lambda: film.assemble(self.lib, self.plan(self.rendered()['id']), self.project, '/missing/ffmpeg', '/missing/ffprobe'), 'ENCODER_NOT_CONFIGURED')

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'Actual encoder integration requires installed FFmpeg/FFprobe')
    def test_real_encoder_from_synthetic_frames_and_no_output_overwrite(self):
        job = self.rendered(); plan = self.plan(job['id'])
        result = film.assemble(self.lib, plan, self.project, shutil.which('ffmpeg'), shutil.which('ffprobe'))
        self.assertEqual(result['state'], 'SUCCEEDED'); self.assertEqual(result['frames'], 3)
        self.assertEqual(result['audio'], 'NONE'); self.assertEqual(result['human_acceptance'], 'PENDING')
        self.assertEqual(result['codec'], 'h264'); self.assertEqual(result['measured']['nb_read_frames'], '3')
        self.assertTrue((self.project / 'Deliverables' / plan['id'] / 'film.mp4').is_file())
        self.refusal(lambda: film.assemble(self.lib, plan, self.project, shutil.which('ffmpeg'), shutil.which('ffprobe')), 'OUTPUT_EXISTS')
        wrong = deepcopy(plan); wrong['id'] = 'cut_' + str(uuid.uuid4()); wrong['clips'][0]['checkpoint_sha256'] = 'f' * 64
        self.refusal(lambda: film.assemble(self.lib, wrong, self.project, shutil.which('ffmpeg'), shutil.which('ffprobe')), 'STALE_FILM_PLAN')

    def task(self):
        identity = 'task_' + str(uuid.uuid4())
        return {'schema': 1, 'id': identity, 'projectId': self.project_id, 'sceneId': self.scene_id,
                'stage': 'world', 'projectDirectory': str(self.project), 'library': str(self.lib.root),
                'input': {'path': 'Scenes/synthetic.blend', 'sha256': file_hash(self.source)},
                'workingScene': 'Scenes/working.blend', 'checkpointScene': 'Scenes/checkpoint.blend',
                'returnFile': 'Docs/Workbench/' + identity + '-return.json', 'targets': [], 'camera': None,
                'frame': None, 'action': 'workbench-edit', 'state': 'RUNNING', 'startedAt': 'synthetic', 'selectedSources': []}

    def test_task_manifest_validation_without_importing_bpy(self):
        self.assertEqual(task_workspace.validate(self.task()), self.project.resolve())
        self.assertEqual(task_workspace.validate({**self.task(), 'frameRange': [1, 4]}), self.project.resolve())
        for patch in [{'stage': 'arbitrary-script'}, {'workingScene': '../escape.blend'}, {'checkpointScene': 'Scenes/synthetic.blend'},
                      {'returnFile': 'project.json'}, {'projectId': 'prj_' + str(uuid.uuid4())}, {'targets': [5]}, {'camera': '\0'}, {'frame': True}, {'frameRange': [2, 1]}, {'frameRange': [1, True]}, {'frameRange': [1, 361]}]:
            with self.subTest(patch=patch):
                with self.assertRaises(DirectorError): task_workspace.validate({**self.task(), **patch})

    def test_task_refuses_changed_original(self):
        task = self.task(); self.source.write_bytes(b'BLENDER CHANGED')
        self.refusal(lambda: task_workspace.validate(task), 'STALE_INPUT')
