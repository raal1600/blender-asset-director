"""Resource/environment tests for the fixture; not replacements for real E2E."""
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools/studio_e2e'))
from support import Studio, verify_catalog


class FixtureResourceTests(unittest.TestCase):
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
