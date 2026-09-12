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


class PublicAddressFailover(unittest.TestCase):
    def test_unreachable_first_address_tries_next_validated_address(self):
        from unittest.mock import patch
        import time
        from asset_director.acquire import connect_public
        sentinel = object()
        with patch("asset_director.acquire.socket.create_connection", side_effect=[TimeoutError(), sentinel]) as connect:
            result = connect_public(["1.1.1.1", "8.8.8.8"], 20, time.monotonic() + 30)
        self.assertIs(result, sentinel)
        self.assertEqual([call.args[0] for call in connect.call_args_list], [("1.1.1.1", 443), ("8.8.8.8", 443)])
        self.assertLessEqual(connect.call_args_list[0].args[1], 15)

    def test_all_addresses_unreachable_is_explicit_failure(self):
        from unittest.mock import patch
        import time
        from asset_director.acquire import connect_public
        from asset_director.core import DirectorError
        with patch("asset_director.acquire.socket.create_connection", side_effect=OSError()):
            with self.assertRaises(DirectorError) as error:
                connect_public(["1.1.1.1", "8.8.8.8"], 20, time.monotonic() + 30)
        self.assertEqual(error.exception.code, "CONNECTION_FAILED")

    def test_private_fallback_is_rejected_before_connecting(self):
        from unittest.mock import patch
        import time
        from asset_director.acquire import connect_public
        from asset_director.core import DirectorError
        with patch("asset_director.acquire.socket.create_connection") as connect:
            with self.assertRaises(DirectorError):
                connect_public(["1.1.1.1", "127.0.0.1"], 20, time.monotonic() + 30)
            connect.assert_not_called()
