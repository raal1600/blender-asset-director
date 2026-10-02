"""Resource/environment tests for the fixture; not replacements for real E2E."""
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools/studio_e2e'))
from support import Studio, disposable_studio, verify_catalog


class FixtureResourceTests(unittest.TestCase):
    def test_unfinished_shutdown_preserves_backend_instead_of_force_killing(self):
        studio = Studio.__new__(Studio)
        studio.mcp = studio.browser = None
        studio.server = Mock()
        studio.server.poll.return_value = None
        studio.session = {'token': 'not-a-real-session'}
        studio.api = Mock(return_value={'busy': True, 'reasons': ['synthetic writer']})
        with patch('support.time.monotonic', side_effect=[0, 226]):
            with self.assertRaisesRegex(TimeoutError, 'test files retained'):
                studio.close()
        studio.server.terminate.assert_not_called()
        studio.server.kill.assert_not_called()
        studio.api.assert_called_once_with('lifecycle')

    def test_generated_root_removed_only_after_success(self):
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as parent:
                directory = Path(parent)/'synthetic-studio-e2e-test'
                directory.mkdir()
                marker = directory/'synthetic-evidence.txt'
                marker.write_text('retained failure evidence', encoding='utf-8')
                evidence = SimpleNamespace(report={})
                with patch('support.tempfile.mkdtemp', return_value=str(directory)), \
                        patch('support.tempfile.gettempdir', return_value=parent):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
                            with disposable_studio(evidence):
                                raise RuntimeError('synthetic failure')
                        self.assertEqual(marker.read_text(encoding='utf-8'), 'retained failure evidence')
                        self.assertEqual(evidence.report['retained_test_root'], str(directory.resolve()))
                    else:
                        with disposable_studio(evidence):
                            self.assertTrue(marker.exists())
                        self.assertFalse(directory.exists())
                        self.assertNotIn('retained_test_root', evidence.report)

    def test_close_drains_owned_backend_before_temporary_directory_cleanup(self):
        studio = Studio.__new__(Studio)
        studio.mcp = None
        studio.browser = Mock()
        studio.page = Mock()
        studio.server = Mock()
        studio.server.poll.return_value = None
        studio.session = {'origin': 'synthetic', 'token': 'not-a-real-session'}
        studio.api = Mock(side_effect=[
            {'busy': True, 'reasons': ['1 launcher operation(s) in progress']},
            {'busy': False, 'reasons': []}, {'message': 'Launcher stopped'},
        ])
        with patch('support.time.sleep'):
            studio.close()
        self.assertEqual([c.args for c in studio.api.call_args_list],
                         [('lifecycle',), ('lifecycle',), ('stop', {})])
        studio.server.terminate.assert_not_called()
        studio.server.kill.assert_not_called()
        studio.server.wait.assert_called_once()

    def test_catalog_connection_closed_on_success_and_assertion_failure(self):
        for initialized in (False, True):
            with self.subTest(initialized=initialized), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/'catalog.sqlite'
                connection = sqlite3.connect(path)
                if initialized:
                    connection.execute('CREATE TABLE synthetic_check (id INTEGER)')
                    connection.commit()
                try:
                    with patch('support.sqlite3.connect', return_value=connection):
                        if initialized:
                            verify_catalog(path)
                        else:
                            with self.assertRaises(AssertionError):
                                verify_catalog(path)
                    # Keep a strong reference so GC cannot hide a leaked handle.
                    with self.assertRaises(sqlite3.ProgrammingError):
                        connection.execute('SELECT 1')
                finally:
                    connection.close()
                path.unlink()  # Also exercises Windows deletion with no open handle.

    def test_missing_catalog_is_not_silently_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'absent.sqlite'
            with self.assertRaises(AssertionError):
                verify_catalog(path)
            self.assertFalse(path.exists())

    def test_windows_allocator_setting_is_local_to_fixture_children(self):
        for platform in ('win32', 'linux'):
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as tmp:
                evidence = SimpleNamespace(report={})
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop('TBB_MALLOC_DISABLE_REPLACEMENT', None)
                    with patch('support.sys.platform', platform):
                        studio = Studio(tmp, sys.executable, evidence)
                    self.assertNotIn('TBB_MALLOC_DISABLE_REPLACEMENT', os.environ)
                    if platform == 'win32':
                        self.assertEqual(studio.env['TBB_MALLOC_DISABLE_REPLACEMENT'], '1')
                    else:
                        self.assertNotIn('TBB_MALLOC_DISABLE_REPLACEMENT', studio.env)

    def test_harness_worker_environment_policy_is_not_relaxed(self):
        from asset_director.jobs import child_environment
        with patch.dict(os.environ, {'TBB_MALLOC_DISABLE_REPLACEMENT': '1'}):
            self.assertNotIn('TBB_MALLOC_DISABLE_REPLACEMENT', child_environment())
