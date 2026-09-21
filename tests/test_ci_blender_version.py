"""Validate version-banner parsing without claiming to execute Blender."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools/ci'))
from run_blender_suite import validate_version


class BlenderVersionTests(unittest.TestCase):
    def test_exact_regular_and_lts_versions_accepted(self):
        for version in ('4.5.3', '5.0.0', '5.2.1'):
            validate_version('Blender ' + version, version)
            validate_version('Blender ' + version + ' LTS', version)

    def test_other_patch_and_minor_versions_rejected(self):
        for banner in ('Blender 5.2.0 LTS', 'Blender 5.0.0', 'Blender 5.2.10 LTS'):
            with self.subTest(banner=banner), self.assertRaises(ValueError):
                validate_version(banner, '5.2.1')

    def test_prerelease_or_unknown_banner_rejected(self):
        for banner in ('', 'Blender 5.2.1 Alpha', 'Blender 5.2.1 LTS altered', '5.2.1'):
            with self.subTest(banner=banner), self.assertRaises(ValueError):
                validate_version(banner, '5.2.1')
