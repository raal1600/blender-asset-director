"""Isolated setup tests; no claim that the configured dummy paths are Blender."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from create_workbench_studio import create

class StagingTests(unittest.TestCase):
    def test_existing_studio_never_overwritten(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)/'Studio';root.mkdir();sentinel=root/'project.txt';sentinel.write_text('keep')
            with self.assertRaisesRegex(ValueError,'already exists'):create(root,sys.executable,sys.executable,sys.executable)
            self.assertEqual(sentinel.read_text(),'keep')
    def test_new_studio_has_isolated_receipts_and_no_production_readiness_claim(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)/'New Studio'
            result=create(root,sys.executable,sys.executable,sys.executable,source_commit='a'*40)
            self.assertEqual(result['status'],'CREATED');self.assertEqual(result['runtime_ready'],'NOT_VERIFIED')
            config=json.loads((root/'SystemRuntime/UserData/Launcher/config.json').read_text())
            self.assertEqual(Path(config['library']).resolve(), (root/'Database/AssetDirector').resolve())
            self.assertTrue((root/'Database/AssetDirector/catalog.sqlite').is_file())
            self.assertTrue((root/'SystemRuntime/Launcher/public/workbench.html').is_file())
            self.assertTrue((root/'SystemRuntime/Launcher/Start Workbench.ps1').is_file())
            self.assertEqual(list((root/'Database/Meshes').iterdir()),[])
            self.assertFalse(result['production_installed']);self.assertEqual(result['native_gui'],'NOT_TESTED')
    def test_invalid_executable_does_not_create_target(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)/'New Studio'
            with self.assertRaises(ValueError):create(root,'relative-blender',sys.executable,sys.executable)
            self.assertFalse(root.exists())
