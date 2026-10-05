"""Lightweight metadata commands keep exact provenance and strict CLI parsing."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from asset_director import cli, core, jobs, settings

ROOT = Path(__file__).resolve().parents[1]


class WorkbenchCLICase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {
            'BAD_CONFIG': str(self.root / 'no-config.json'),
            'BAD_LIBRARY': str(self.root / 'library'),
            'PYTHONPATH': str(ROOT / 'src'), 'PYTHONDONTWRITEBYTECODE': '1',
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def run_cli(self, *args):
        result = subprocess.run([sys.executable, '-B', '-m', 'asset_director', *args],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return json.loads(result.stdout)

    def test_capabilities_match_job_identity_without_creating_library(self):
        result = self.run_cli('--library', str(self.root / 'absent'), 'workbench-capabilities')
        self.assertEqual(result, cli.workbench_capabilities())
        self.assertEqual(result['implementation'], jobs.implementation_hash())
        self.assertEqual(result['limits'], {'frames_per_shot': 360, 'frames_per_film': 3600, 'render_seconds': 900})
        self.assertTrue(result['explicit_save_handoff'] and result['gpu_render'])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_transition_capabilities_disclose_native_and_unaccepted_candidate(self):
        with patch.dict(os.environ, {'ASSET_DIRECTOR_MOTION_BRICKS_CONFIG':''}):
            providers = cli.workbench_capabilities()['transition_providers']
        self.assertEqual(providers[0], {'provider':'native', 'mode':'deterministic', 'available':True, 'implementation':'native-stitch-c1-v2'})
        self.assertEqual(providers[1]['provider'], 'motion-bricks.cpp')
        self.assertFalse(providers[1]['accepted_transition'])
        self.assertEqual(providers[1]['state'], 'NOT_CONFIGURED')
        with patch.dict(os.environ, {'ASSET_DIRECTOR_MOTION_BRICKS_CONFIG':str(self.root/'missing-config.json')}):
            result = cli.workbench_capabilities()
        self.assertTrue(result['transition_providers'][0]['available'])
        self.assertEqual(result['transition_providers'][1]['state'], 'CONFIGURATION_ERROR')
        self.assertTrue(result['action_save_cancellation'])

    def test_capabilities_do_not_open_or_modify_existing_catalog(self):
        library = self.root / 'library'
        library.mkdir()
        db = library / 'catalog.sqlite'
        db.write_bytes(b'synthetic unreadable catalog must not be opened')
        before = db.read_bytes()
        self.run_cli('--library=' + str(library), 'workbench-capabilities')
        self.assertEqual(db.read_bytes(), before)
        self.assertEqual(list(library.iterdir()), [db])

    def test_capabilities_default_and_skill_entrypoint_agree(self):
        expected = self.run_cli('workbench-capabilities')
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'skills/blender-asset-director/scripts/director.py'),
                                 'workbench-capabilities'], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), expected)
        self.assertFalse((self.root / 'library').exists())

    def test_lightweight_commands_do_not_load_network_or_job_modules(self):
        project = self.root / 'project.json'
        project.write_text('{"owner":"asset-director-launcher","workbench":{"catalogPins":[]}}')
        for args in [['workbench-capabilities'], ['workbench-verify', '--project', str(project)]]:
            code = ('import sys; from asset_director.cli import main; '
                    'result=main(sys.argv[1:]); '
                    'assert not any(n in sys.modules for n in '
                    "['asset_director.providers','asset_director.acquire','asset_director.jobs','ssl']); "
                    'raise SystemExit(result)')
            result = subprocess.run([sys.executable, '-B', '-c', code, *args],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_lightweight_and_full_parsers_accept_identical_arguments(self):
        commands = [
            ['workbench-capabilities'], ['workbench-verify', '--project', 'p.json'],
            ['workbench-preview', '--request', 'r.json', '--blender', 'blender', '--embedded'],
            ['workbench-intake', '--request', 'r.json', '--evidence', 'e.json', '--blender', 'blender'],
            ['workbench-catalog', '--kinds', 'model', 'pack', '--verify', '--limit', '9'],
        ]
        with patch.object(settings, 'blender_path', return_value=None):
            for prefix in [[], ['--library', 'explicit library'], ['--library=explicit']]:
                for command in commands:
                    args = prefix + command
                    self.assertTrue(cli._workbench_only(args))
                    self.assertEqual(vars(cli.parser(workbench_only=True).parse_args(args)),
                                     vars(cli.parser().parse_args(args)))

    def test_malformed_arguments_still_refused(self):
        commands = [
            ['workbench-capabilities', '--unknown'], ['workbench-capabilities', 'extra'],
            ['workbench-capabilities', '--library', 'late'], ['workbench-verify'],
            ['workbench-catalog', '--limit', 'no'], ['workbench-catalog', '--kind', 'unknown'],
        ]
        with patch.object(settings, 'blender_path', return_value=None), contextlib.redirect_stderr(io.StringIO()):
            for args in commands:
                for lightweight in [False, True]:
                    with self.subTest(args=args, lightweight=lightweight), self.assertRaises(SystemExit) as error:
                        cli.parser(workbench_only=lightweight).parse_args(args)
                    self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.root / 'library').exists())

    def test_full_commands_and_library_named_like_command_use_full_parser(self):
        for args in [[], ['--help'], ['providers'], ['--library', 'workbench-capabilities', 'providers'],
                     ['--library=workbench-capabilities', 'providers'], ['--lib', 'p', 'workbench-verify']]:
            self.assertFalse(cli._workbench_only(args))
        self.assertIn('local', self.run_cli('providers'))

    def test_runtime_identity_is_legacy_content_hash_not_metadata_cache(self):
        modules = self.root / 'modules'
        modules.mkdir()
        first = modules / 'core.py'
        first.write_bytes(b'first')
        second = modules / 'worker.py'
        second.write_bytes(b'alpha')
        with patch.object(core, '__file__', str(first)):
            expected = core.digest({p.name: core.file_hash(p) for p in sorted(modules.glob('*.py'))})
            self.assertEqual(core.implementation_hash(), expected)
            self.assertEqual(jobs.implementation_hash(), expected)
            old_stat = second.stat()
            second.write_bytes(b'bravo')
            os.utime(second, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
            self.assertNotEqual(core.implementation_hash(), expected)
            changed = core.implementation_hash()
            second.unlink()
            self.assertNotEqual(core.implementation_hash(), changed)


if __name__ == '__main__':
    unittest.main()
