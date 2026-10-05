"""Provider configuration changes cannot reuse an old Action inspection/job.

Small fake files exercise cache identity only, never real inference acceptance.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from asset_director.core import Library, DirectorError
from asset_director import jobs, motion_bricks_provider as provider

class MotionBricksCacheTests(unittest.TestCase):
    def test_configuration_binary_and_model_changes_invalidate_prepared_job(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=False):
            root=Path(directory);settings=root/'provider.json';scene=root/'source.blend';scene.write_bytes(b'BLENDER-v500 cache-contract')
            binary=root/'fake.dll';binary.write_bytes(b'cache metadata, not executable')
            models=root/'models';models.mkdir();model=models/'pose.gguf';model.write_bytes(b'not a real model')
            config={'library':str(binary),'model_dir':str(models),'device':'cpu'}
            settings.write_text(json.dumps(config),encoding='utf-8');os.environ['ASSET_DIRECTOR_MOTION_BRICKS_CONFIG']=str(settings)
            with Library(root/'library') as lib:
                old=jobs.prepare(lib,'action-audit',str(scene),options={})
                self.assertEqual(jobs.prepare(lib,'action-audit',str(scene),options={})['id'],old['id'])
                for change in ('device','binary','model'):
                    if change=='device':config['device']='vulkan';settings.write_text(json.dumps(config),encoding='utf-8')
                    elif change=='binary':binary.write_bytes(b'different native binary metadata')
                    else:model.write_bytes(b'changed model content and size')
                    with self.assertRaises(DirectorError) as caught:jobs.read_job(lib,old['id'])
                    self.assertEqual(caught.exception.code,'STALE_MOTION_PROVIDER')
                    new=jobs.prepare(lib,'action-audit',str(scene),options={});self.assertNotEqual(new['id'],old['id']);old=new

    def test_invalid_optional_setup_has_identity_without_disabling_native_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'broken.json';path.write_text('broken',encoding='utf-8')
            with patch.dict(os.environ, {'ASSET_DIRECTOR_MOTION_BRICKS_CONFIG':str(path)}):
                first=provider.configuration_identity();path.write_text('also broken',encoding='utf-8')
                self.assertNotEqual(first,provider.configuration_identity())
