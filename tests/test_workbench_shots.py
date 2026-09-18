"""Portable shot preview contracts. Actual camera renders are tested by Blender fixtures."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from asset_director import jobs, preview_camera
from asset_director.core import DirectorError, Library


class ShotPreviewTests(unittest.TestCase):
    def test_names_and_incompatible_staging_are_rejected_before_execution(self):
        preview_camera.validate({})
        preview_camera.validate({"camera": "Camera A"})
        for name in (None, True, 1, "", "a" * 256, "Camera\nB", "Camera\0"):
            with self.subTest(name=name), self.assertRaises(DirectorError):
                preview_camera.validate({"camera": name})
        with self.assertRaises(DirectorError):
            preview_camera.validate({"camera": "Camera A", "stage": True})

    def test_exact_camera_changes_job_identity_legacy_options_remain_valid(self):
        with TemporaryDirectory() as root, Library(Path(root) / 'library') as lib:
            source = Path(root) / 'source.blend'
            source.write_bytes(b'BLENDER-v420 SYNTHETIC UNIT FIXTURE ONLY')
            options = {"frames": [1], "width": 64, "height": 64, "samples": 1}
            old = jobs.prepare(lib, 'preview', str(source), options=options)
            a = jobs.prepare(lib, 'preview', str(source), options={**options, "camera": "A"})
            b = jobs.prepare(lib, 'preview', str(source), options={**options, "camera": "B"})
            self.assertEqual(len({old['id'], a['id'], b['id']}), 3)
            self.assertNotIn('camera', old['specification']['options'])
            self.assertEqual(a, jobs.prepare(lib, 'preview', str(source), options={**options, "camera": "A"}))

    def test_no_arbitrary_command_surface_in_preview(self):
        with TemporaryDirectory() as root, Library(Path(root) / 'library') as lib:
            source = Path(root) / 'source.blend'
            source.write_bytes(b'BLENDER SYNTHETIC')
            with self.assertRaises(DirectorError):
                jobs.prepare(lib, 'preview', str(source), options={'camera': 'A', 'script': 'x'})
