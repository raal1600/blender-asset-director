"""Installer/configuration tests: no live desktop, provider requests or credentials."""
from pathlib import Path
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director import settings
from asset_director.core import DirectorError
from asset_director.cli import main as cli
spec = importlib.util.spec_from_file_location('release_bootstrap', ROOT / 'install.py')
boot = importlib.util.module_from_spec(spec); spec.loader.exec_module(boot)


class SettingsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name).resolve()
        self.env = patch.dict(os.environ, {'BAD_CONFIG': str(self.root / 'settings.json'),
                    'CODEX_HOME': str(self.root / 'codex'), 'BAD_LIBRARY': '', 'BAD_BLENDER': ''})
        self.env.start()
    def tearDown(self):
        self.env.stop(); self.tmp.cleanup()
    def configure(self, **kw):
        return settings.configure(library=str(self.root / 'CGI library'), skill_path=str(self.root / 'skill'), **kw)
    def test_config_saved_outside_skill(self):
        with patch.object(settings, 'blender_candidates', return_value=[]):
            result = self.configure()
        self.assertTrue(Path(result['settings_file']).is_file())
        self.assertFalse((self.root / 'skill').exists())
        self.assertTrue((self.root / 'CGI library' / 'catalog.sqlite').exists())
        self.assertEqual(settings.library_path(), str(self.root / 'CGI library'))
    def test_config_preserves_explicit_blender(self):
        exe = self.root / 'Blender custom.exe'; exe.write_text('fixture, not executable')
        self.configure(blender=str(exe))
        settings.configure(library=str(self.root / 'next library'))
        self.assertEqual(settings.blender_path(), str(exe))
    def test_missing_explicit_blender_rejected(self):
        with self.assertRaises(DirectorError): self.configure(blender=str(self.root / 'missing'))
        self.assertFalse(settings.config_path().exists())
    def test_skill_and_library_must_be_separate(self):
        for lib, skill in [(self.root, self.root / 's'), (self.root / 's' / 'l', self.root / 's')]:
            with self.assertRaises(DirectorError): settings.configure(library=str(lib), skill_path=str(skill))
    def test_env_overrides_saved_paths(self):
        self.configure()
        with patch.dict(os.environ, {'BAD_LIBRARY': str(self.root / 'override')}):
            self.assertEqual(settings.library_path(), str(self.root / 'override'))
            self.assertEqual(settings.library_path(str(self.root / 'explicit')), str(self.root / 'explicit'))
    def test_selected_missing_blender_not_silently_replaced(self):
        exe = self.root / 'exe'; exe.touch(); self.configure(blender=str(exe)); exe.unlink()
        with patch.object(settings, 'blender_candidates', return_value=['replacement']):
            self.assertEqual(settings.blender_path(), str(exe))
            self.assertEqual(settings.health()['blender']['status'], 'NOT_FOUND')
    def test_unknown_settings_rejected(self):
        settings.config_path().write_text('{"schema_version":1,"owner":"someone-else"}')
        with self.assertRaises(DirectorError): settings.read_settings()
    def test_settings_reject_secret_fields(self):
        settings.config_path().write_text('{"schema_version":1,"owner":"blender-asset-director","api_key":"test"}')
        with self.assertRaises(DirectorError): settings.read_settings()
    def test_health_never_claims_mcp_connected(self):
        self.configure()
        h = settings.health()
        self.assertEqual(h['codex']['connection'], 'NOT_TESTED')
        self.assertEqual(h['network_requests'], 0)
        self.assertEqual(h['model_calls'], 0)
    def test_codex_settings_read_only_redacted(self):
        home = self.root / 'codex'; home.mkdir()
        text = 'model="unchanged"\n[mcp_servers.blender]\ncommand="uvx"\nargs=["blender-mcp"]\n[mcp_servers.blender.env]\nSECRET="TEST_SECRET_NEVER_ECHO"\n'
        f = home / 'config.toml'; f.write_text(text)
        before = f.read_bytes(); result = settings.codex_status()
        self.assertEqual(result['blender_mcp'], 'CONFIGURED_LIVE_TEST_PENDING')
        self.assertNotIn('TEST_SECRET_NEVER_ECHO', json.dumps(result))
        self.assertEqual(before, f.read_bytes())
    def test_disabled_mcp_not_counted(self):
        home = self.root / 'codex'; home.mkdir()
        (home / 'config.toml').write_text('[mcp_servers.blender]\nenabled=false\ncommand="blender"')
        self.assertEqual(settings.codex_status()['blender_mcp'], 'NOT_DETECTED_IN_USER_CONFIG')
    def test_overlay_alone_not_blender_connection(self):
        home = self.root / 'codex'; home.mkdir()
        (home / 'config.toml').write_text('[mcp_servers.blender_overlay]\ncommand="overlay"')
        self.assertEqual(settings.codex_status()['blender_mcp'], 'NOT_DETECTED_IN_USER_CONFIG')
    def test_invalid_host_config_is_not_rewritten(self):
        home = self.root / 'codex'; home.mkdir()
        f = home / 'config.toml'; f.write_text('broken[Toml')
        self.assertEqual(settings.codex_status()['blender_mcp'], 'CONFIG_UNREADABLE_OR_INVALID')
        self.assertEqual(f.read_text(), 'broken[Toml')
    def test_doctor_uses_saved_paths_without_extra_flags(self):
        self.configure()
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli(['doctor']), 0)
        self.assertEqual(json.loads(out.getvalue())['library'], str(self.root / 'CGI library'))
    def test_job_missing_blender_actionable(self):
        # The missing-Blender branch must be tested independently of the host machine.
        # Some real users run the installer with Blender's bundled Python, where Blender
        # is necessarily discoverable. Mock discovery before configure() so no detected
        # executable is persisted into the temporary runtime settings.
        with patch.object(settings, 'blender_candidates', return_value=[]):
            self.configure()
            self.assertIsNone(settings.blender_path())
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli(['job-run', 'j_'+'0'*24]), 2)
        self.assertEqual(json.loads(out.getvalue())['code'], 'BLENDER_NOT_FOUND')
    def test_cli_rejects_invalid_config_without_traceback(self):
        settings.config_path().write_text('{"schema_version":9,"owner":"blender-asset-director"}')
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli(['doctor']), 2)
        self.assertNotIn('Traceback', out.getvalue())


class BootstrapCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def archive(self, entries):
        path = self.root / 'release.zip'
        with zipfile.ZipFile(path, 'w') as z:
            for name, content in entries:
                if isinstance(name, str):
                    info = zipfile.ZipInfo('raw-fixture')
                    info.filename = name
                    info.orig_filename = name
                    name = info
                z.writestr(name, content)
        return path, hashlib.sha256(path.read_bytes()).hexdigest()
    def test_valid_archive(self):
        p, sha = self.archive([('tools/install_skill.py', '# trusted fixture')])
        boot.extract(p, self.root / 'out', sha)
        self.assertTrue((self.root / 'out' / 'tools' / 'install_skill.py').is_file())
    def test_bad_checksum_writes_nothing(self):
        p, _ = self.archive([('x.py', 'pass')])
        with self.assertRaises(ValueError): boot.extract(p, self.root / 'out', '0'*64)
        self.assertFalse((self.root / 'out').exists())
    def test_missing_checksum(self):
        p, _ = self.archive([('x.py', 'pass')])
        with self.assertRaises(ValueError): boot.extract(p, self.root / 'out', '')
    def test_unsafe_archive_names(self):
        for name in ['../outside', '/absolute', 'a/../../outside', 'C:/outside', 'a\\b', 'dir/CON.txt', 'trailing. /x', 'x\ny']:
            with self.subTest(name=name):
                p, sha = self.archive([(name, 'test')])
                with self.assertRaises(ValueError): boot.extract(p, self.root / 'out', sha)
        self.assertFalse((self.root / 'out').exists())
    def test_duplicate_case_collision(self):
        p, sha = self.archive([('Readme', '1'), ('README', '2')])
        with self.assertRaises(ValueError): boot.extract(p, self.root / 'out', sha)
    def test_file_directory_collision(self):
        p, sha = self.archive([('dir', '1'), ('dir/file.py', '2')])
        with self.assertRaises(ValueError): boot.extract(p, self.root / 'out', sha)
    def test_symlink_archive_rejected(self):
        info = zipfile.ZipInfo('link'); info.external_attr = (stat.S_IFLNK | 0o777) << 16
        p, sha = self.archive([(info, '/outside')])
        with self.assertRaises(ValueError): boot.extract(p, self.root / 'out', sha)
    def test_checksum_file_exact_match(self):
        self.assertEqual(boot.checksum_for('a'*64+'  package.zip\n', 'package.zip'), 'a'*64)
    def test_checksum_file_ambiguous(self):
        with self.assertRaises(ValueError): boot.checksum_for(('a'*64+'  package.zip\n')*2, 'package.zip')
    def test_checksum_file_wrong_name(self):
        with self.assertRaises(ValueError): boot.checksum_for('a'*64+'  wrong.zip\n', 'package.zip')
    def test_redirect_policy(self):
        for url in ['http://github.com/file', 'https://evil.example/x', 'https://github.com.evil.example/x', 'https://user:pass@github.com/x']:
            with self.assertRaises(ValueError): boot.check_url(url)
        boot.check_url('https://release-assets.githubusercontent.com/file')
    def test_invalid_release_ref(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(boot.main(['--version', '../main']), 2)
    def test_offline_requires_hash(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(boot.main(['--archive', 'test.zip']), 2)
    def test_version_mismatch_before_execution(self):
        p, sha = self.archive([('_release.json', json.dumps({'version':'99.0.0','commit':'0'*40}))])
        with patch.object(boot, 'run_installer') as run, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(boot.main(['--archive', str(p), '--sha256', sha]), 2)
            run.assert_not_called()

if __name__ == '__main__': unittest.main()
