"""Regression coverage for failures found by actual cross-platform CI."""
from contextlib import contextmanager
from pathlib import Path
import json
import os
import tempfile
import unittest
from asset_director.acquire import gltf_dependencies


@contextmanager
def working_directory(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class CanonicalDependencyPaths(unittest.TestCase):
    def test_relative_package_root_uses_canonical_base(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "models").mkdir()
            (root / "textures").mkdir()
            (root / "textures" / "color.png").write_bytes(b"fixture")
            (root / "models" / "model.gltf").write_text(json.dumps({"images": [{"uri": "../textures/color.png"}]}), encoding="utf-8")
            with working_directory(root):
                self.assertEqual(gltf_dependencies(Path("models/model.gltf"), Path(".")), ["textures/color.png"])
