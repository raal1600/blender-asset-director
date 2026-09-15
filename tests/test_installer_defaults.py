"""Offline pin/argument regressions; real public downloads are a separate CI step."""
from pathlib import Path
import contextlib
import hashlib
import importlib.util
import io
import json
import re
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PIN = json.loads((ROOT / 'published-release.json').read_text(encoding='utf-8'))
spec = importlib.util.spec_from_file_location('default_bootstrap', ROOT / 'install.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


class InstallerDefaultTests(unittest.TestCase):
    def test_published_pin_has_explicit_release_identity(self):
        self.assertEqual(PIN['schema'], 'asset-director.published-release/1')
        self.assertRegex(PIN['version'], r'^\d+\.\d+\.\d+$')
        self.assertRegex(PIN['source_commit'], r'^[0-9a-f]{40}$')

    def test_python_default_matches_published_release_not_development(self):
        self.assertEqual(boot.DEFAULT_VERSION, PIN['version'])

    def test_shell_default_matches_published_release(self):
        text = (ROOT / 'install.sh').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'^version=([^\s]+)$', text, re.M), [PIN['version']])

    def test_powershell_default_matches_published_release(self):
        text = (ROOT / 'install.ps1').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r"\$Version\s*=\s*'([^']+)'", text), [PIN['version']])

    def test_readme_advertises_the_same_published_release(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('## Current published preview: v' + PIN['version'], readme)
        self.assertIn('Development source: `main`', readme)

    def exercise_online_selection(self, argv, version):
        """Use a tiny inert package; no network, installed files or Blender."""
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('_release.json', json.dumps({'version': version, 'commit': 'a' * 40}))
            archive.writestr('tools/install_skill.py', '# Inert unit fixture; never executed.\n')
        package = data.getvalue()
        name = f'blender-asset-director-{version}.zip'
        checksum = (hashlib.sha256(package).hexdigest() + '  ' + name + '\n').encode()
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(boot, 'fetch', side_effect=[checksum, package]) as fetch, \
                patch.object(boot, 'run_installer') as install, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(boot.main(['--dest', str(Path(tmp) / 'skill')] + argv), 0)
            base = f'https://github.com/{boot.REPOSITORY}/releases/download/v{version}/'
            self.assertEqual([call.args[0] for call in fetch.call_args_list],
                             [base + 'SHA256SUMS.txt', base + name])
            install.assert_called_once()
            self.assertEqual(install.call_args.args[1].version, version)

    def test_omitted_version_selects_published_download_urls(self):
        self.exercise_online_selection([], PIN['version'])

    def test_explicit_version_overrides_default(self):
        self.exercise_online_selection(['--version', '9.8.7-preview.1'], '9.8.7-preview.1')

    def test_invalid_version_does_not_download_or_install(self):
        for version in ['main', '../../main', 'v0.5.0', '0.5.0/other']:
            with self.subTest(version=version), patch.object(boot, 'fetch') as fetch, \
                    patch.object(boot, 'run_installer') as install, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(boot.main(['--version', version]), 2)
                fetch.assert_not_called()
                install.assert_not_called()

    def test_failed_published_download_never_falls_back_to_main(self):
        with patch.object(boot, 'fetch', side_effect=ValueError('fixture download failure')) as fetch, \
                patch.object(boot, 'run_installer') as install, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(boot.main([]), 2)
            fetch.assert_called_once()
            self.assertIn('/releases/download/v' + PIN['version'] + '/', fetch.call_args.args[0])
            install.assert_not_called()


if __name__ == '__main__':
    unittest.main()
