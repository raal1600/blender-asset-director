"""No network or driver installation in portable tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/ci'))
from native_mesa import validate_destination, SHA256, URL

class MesaScopeTests(unittest.TestCase):
    def test_refuses_user_install_and_existing_driver(self):
        with TemporaryDirectory() as d:
            root=Path(d); outside=root/'blender.exe';outside.touch()
            with self.assertRaises(ValueError):validate_destination(outside,root)
            exe=root/'verified-blender/blender/blender.exe';exe.parent.mkdir(parents=True);exe.touch()
            self.assertEqual(validate_destination(exe,root),exe.parent.resolve())
            (exe.parent/'opengl32.dll').touch()
            with self.assertRaises(ValueError):validate_destination(exe,root)
    def test_dependency_is_immutable_not_latest(self):
        self.assertEqual(len(SHA256),64)
        self.assertIn('/25.3.3/',URL);self.assertNotIn('latest',URL)
