"""Synthetic runner observability must retain failure and avoid broad log publication."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('embedded_browser_suite', Path(__file__).resolve().parents[1] / 'tools/embedded_viewer_suite.py')
SUITE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUITE)


class BrowserEvidenceTests(unittest.TestCase):
    def test_failure_surfaces_only_existing_verdict_and_still_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'synthetic').mkdir()
            (root / 'synthetic/RESULTS.json').write_text(json.dumps({
                'status': 'FAIL', 'checks': ['Reached native worker'], 'error': 'Expected assertion',
                'errors': [], 'session': {'token': 'not-for-output'}, 'saved': ['private-file']}))
            capture = io.StringIO()
            with patch.object(SUITE.subprocess, 'run', return_value=subprocess.CompletedProcess(['test'], 7)), contextlib.redirect_stderr(capture), self.assertRaises(subprocess.CalledProcessError) as error:
                SUITE.reported_browser(['test'], root, 'synthetic', 300)
            self.assertEqual(error.exception.returncode, 7)
            result = json.loads(capture.getvalue())
            self.assertEqual(result['result']['error'], 'Expected assertion')
            self.assertEqual(set(result['result']), {'status', 'checks', 'error', 'errors'})
            self.assertNotIn('not-for-output', capture.getvalue())
            self.assertNotIn('private-file', capture.getvalue())

    def test_missing_report_is_not_a_pass_and_success_has_no_failure_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); capture = io.StringIO()
            with patch.object(SUITE.subprocess, 'run', return_value=subprocess.CompletedProcess(['test'], 1)), contextlib.redirect_stderr(capture), self.assertRaises(subprocess.CalledProcessError):
                SUITE.reported_browser(['test'], root, 'missing', 300)
            self.assertIn('failed before a readable result', capture.getvalue())
            capture = io.StringIO()
            with patch.object(SUITE.subprocess, 'run', return_value=subprocess.CompletedProcess(['test'], 0)), contextlib.redirect_stderr(capture):
                SUITE.reported_browser(['test'], root, 'pass', 300)
            self.assertEqual(capture.getvalue(), '')


if __name__ == '__main__':unittest.main()
