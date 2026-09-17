"""Actual local Git wiki publishing E2E plus refusal/preservation regressions."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/wiki'))
from build import build, digest, MANIFEST, render_links
from publish import assert_current, load_manifest, publish, select_source, sync, verify

REPOSITORY = 'raal1600/blender-asset-director'
BRANCH = 'feature/consolidated-updates-20260917'


def git(root, *args):
    return subprocess.check_output(['git', '-c', 'core.autocrlf=false', '-C', str(root), *args], stderr=subprocess.DEVNULL, text=True, encoding='utf-8').strip()


def initialize(root, branch='master'):
    git(root, 'init', '-q', '-b', branch)
    git(root, 'config', 'user.name', 'Synthetic wiki test')
    git(root, 'config', 'user.email', 'wiki-test@example.invalid')


class LiveWikiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='wiki-tests-')
        cls.root = Path(cls.temp.name)
        cls.built = cls.root/'built'
        cls.commit = git(ROOT, 'rev-parse', 'HEAD')
        cls.manifest = build(ROOT, cls.built, REPOSITORY, cls.commit, BRANCH)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory(prefix='wiki-test-')
        self.addCleanup(self.sandbox.cleanup)
        self.path = Path(self.sandbox.name)
        self.incoming = self.path/'incoming'
        shutil.copytree(self.built, self.incoming)
        self.wiki = self.path/'wiki'
        self.wiki.mkdir()
        (self.wiki/'Home.md').write_text('<!-- live-wiki-bootstrap -->\n', encoding='utf-8')

    def test_build_is_deterministic_and_inventories_are_real(self):
        other = self.path/'other'
        result = build(ROOT, other, REPOSITORY, self.commit, BRANCH)
        self.assertEqual(result, self.manifest)
        self.assertIn('job-prepare', (other/'CLI-Reference.md').read_text(encoding='utf-8'))
        self.assertIn('camera-plan', (other/'Job-Operations.md').read_text(encoding='utf-8'))
        self.assertIn('live-wiki.yml', (other/'Workflow-Reference.md').read_text(encoding='utf-8'))
        self.assertIn('cancellation_blocks', (other/'Evidence-Inventory.md').read_text(encoding='utf-8'))
        self.assertEqual(set(p.name for p in other.iterdir()), set(result['pages']) | {MANIFEST})
        verify(other, result)

    def test_clone_push_readback_and_second_run_noop(self):
        initialize(self.wiki)
        (self.wiki/'Manual-Notes.md').write_text('Preserve this manual page.\n', encoding='utf-8')
        git(self.wiki, 'add', '.')
        git(self.wiki, 'commit', '-qm', 'Initialize synthetic wiki')
        remote = self.path/'remote.git'
        git(self.path, 'clone', '--bare', str(self.wiki), str(remote))
        first = publish(self.incoming, str(remote), REPOSITORY)
        second = publish(self.incoming, str(remote), REPOSITORY)
        self.assertEqual(first['status'], 'PUBLISHED')
        self.assertEqual(second['status'], 'UNCHANGED')
        self.assertTrue(first['readback_verified'])
        self.assertEqual(first['wiki_commit'], second['wiki_commit'])
        self.assertEqual(git(remote, 'show', 'HEAD:Manual-Notes.md'), 'Preserve this manual page.')
        self.assertEqual(git(remote, 'rev-list', '--count', 'HEAD'), '2')

    def test_code_and_docs_changes_regenerate_then_publish(self):
        checkout = self.path/'checkout'
        shutil.copytree(ROOT, checkout, ignore=shutil.ignore_patterns('.git', '__pycache__', 'node_modules', 'evidence'))
        initialize(checkout, 'main')
        cli = checkout/'src/asset_director/cli.py'
        cli.write_text(cli.read_text(encoding='utf-8').replace('    q=s.add_parser("sequence-prepare")',
            '    s.add_parser("wiki-synthetic-command")\n    q=s.add_parser("sequence-prepare")', 1), encoding='utf-8')
        (checkout/'docs/WIKI_SYNTHETIC.md').write_text('# Synthetic new documentation\n', encoding='utf-8')
        (checkout/'.github/workflows/wiki-synthetic.yml').write_text('name: Synthetic workflow inventory\non: workflow_dispatch\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo synthetic\n', encoding='utf-8')
        git(checkout, 'add', '.')
        git(checkout, 'commit', '-qm', 'Synthetic source change')
        commit = git(checkout, 'rev-parse', 'HEAD')
        changed = self.path/'changed'
        build(checkout, changed, REPOSITORY, commit, 'main')
        self.assertIn('wiki-synthetic-command', (changed/'CLI-Reference.md').read_text(encoding='utf-8'))
        self.assertIn('WIKI_SYNTHETIC.md', (changed/'Source-Index.md').read_text(encoding='utf-8'))
        self.assertIn('wiki-synthetic.yml', (changed/'Workflow-Reference.md').read_text(encoding='utf-8'))
        initialize(self.wiki)
        git(self.wiki, 'add', '.')
        git(self.wiki, 'commit', '-qm', 'Synthetic wiki seed')
        remote = self.path/'remote.git'
        git(self.path, 'clone', '--bare', str(self.wiki), str(remote))
        publish(self.incoming, str(remote), REPOSITORY)
        result = publish(changed, str(remote), REPOSITORY)
        self.assertEqual(result['source_commit'], commit)
        self.assertIn('wiki-synthetic-command', git(remote, 'show', 'HEAD:CLI-Reference.md'))

    def test_manual_pages_survive_sync(self):
        (self.wiki/'Manual.md').write_text('preserve', encoding='utf-8')
        sync(self.incoming, self.wiki, REPOSITORY)
        self.assertEqual((self.wiki/'Manual.md').read_text(encoding='utf-8'), 'preserve')

    def test_modified_managed_page_fails_before_writes(self):
        sync(self.incoming, self.wiki, REPOSITORY)
        (self.wiki/'Architecture.md').write_text('important manual change', encoding='utf-8')
        before = {p.name: p.read_bytes() for p in self.wiki.iterdir()}
        with self.assertRaisesRegex(ValueError, 'edited'):
            sync(self.incoming, self.wiki, REPOSITORY)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.wiki.iterdir()})

    def test_unknown_existing_home_is_preserved(self):
        (self.wiki/'Home.md').write_text('Existing project documentation', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Unowned'):
            sync(self.incoming, self.wiki, REPOSITORY)
        self.assertEqual((self.wiki/'Home.md').read_text(encoding='utf-8'), 'Existing project documentation')

    def test_default_github_home_can_be_initialized(self):
        (self.wiki/'Home.md').write_text('Welcome to the blender-asset-director wiki!', encoding='utf-8')
        manifest, _ = sync(self.incoming, self.wiki, REPOSITORY)
        verify(self.wiki, manifest)

    def test_removed_owned_page_is_deleted_but_manual_page_survives(self):
        sync(self.incoming, self.wiki, REPOSITORY)
        (self.wiki/'Manual.md').write_text('keep', encoding='utf-8')
        data = load_manifest(self.incoming, REPOSITORY)
        del data['pages']['Architecture.md']
        (self.incoming/'Architecture.md').unlink()
        (self.incoming/MANIFEST).write_text(json.dumps(data), encoding='utf-8')
        sync(self.incoming, self.wiki, REPOSITORY)
        self.assertFalse((self.wiki/'Architecture.md').exists())
        self.assertTrue((self.wiki/'Manual.md').exists())

    def test_corrupt_generated_page_is_rejected(self):
        (self.incoming/'Home.md').write_text('corrupt', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'edited'):
            sync(self.incoming, self.wiki, REPOSITORY)

    def test_manifest_path_traversal_is_rejected(self):
        data = load_manifest(self.incoming, REPOSITORY)
        data['pages']['../outside.md'] = 'a'*64
        (self.incoming/MANIFEST).write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            sync(self.incoming, self.wiki, REPOSITORY)

    def test_unexpected_payload_is_rejected(self):
        (self.incoming/'private.sqlite').write_text('synthetic forbidden payload', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            sync(self.incoming, self.wiki, REPOSITORY)

    def test_repository_identity_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'identity'):
            sync(self.incoming, self.wiki, 'other/repository')

    @unittest.skipIf(os.name == 'nt', 'Symlink creation requires Windows privileges; exercised on Linux')
    def test_dangling_manifest_symlink_cannot_write_outside(self):
        outside = self.path/'must-not-be-created'
        (self.wiki/MANIFEST).symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            sync(self.incoming, self.wiki, REPOSITORY)
        self.assertFalse(outside.exists())

    def test_links_rewrite_and_examples_remain_unchanged(self):
        body = '[Guide](guide.md#start)\n```sh\n[not a link](absent.md)\n```\n'
        result = render_links(body, 'docs/source.md', {'docs/guide.md': 'Guide'}, ROOT,
                              'https://github.com/test/test', self.commit)
        self.assertIn('[Guide](Guide#start)', result)
        self.assertIn('[not a link](absent.md)', result)

    def test_broken_source_links_fail(self):
        with self.assertRaisesRegex(ValueError, 'Broken'):
            render_links('[missing](does-not-exist.md)', 'docs/source.md', {}, ROOT,
                         'https://github.com/test/test', self.commit)

    def test_escape_links_fail(self):
        with self.assertRaisesRegex(ValueError, 'escapes'):
            render_links('[bad](../../outside.md)', 'wiki/Home.md', {}, ROOT,
                         'https://github.com/test/test', self.commit)

    def test_build_refuses_nonempty_destination(self):
        with self.assertRaisesRegex(ValueError, 'fresh empty'):
            build(ROOT, self.wiki, REPOSITORY, self.commit, BRANCH)

    def test_default_branch_promotion_and_stale_source_refusal(self):
        source = self.path/'source'
        source.mkdir()
        initialize(source, 'main')
        (source/'README.md').write_text('synthetic main without live wiki', encoding='utf-8')
        git(source, 'add', '.')
        git(source, 'commit', '-qm', 'Initial main')
        git(source, 'checkout', '-qb', BRANCH)
        git(source, 'commit', '--allow-empty', '-qm', 'Initial development')
        remote = self.path/'source.git'
        git(self.path, 'clone', '--bare', str(source), str(remote))
        git(source, 'remote', 'add', 'origin', str(remote))
        self.assertEqual(select_source(source, 'main', BRANCH), BRANCH)
        manifest = {'source_branch': BRANCH, 'source_commit': git(source, 'rev-parse', 'HEAD')}
        assert_current(source, manifest, 'main', BRANCH)
        git(source, 'commit', '--allow-empty', '-qm', 'New development revision')
        git(source, 'push', 'origin', BRANCH)
        with self.assertRaisesRegex(ValueError, 'moved'):
            assert_current(source, manifest, 'main', BRANCH)
        git(source, 'checkout', 'main')
        (source/'wiki').mkdir()
        (source/'wiki/config.json').write_text('{}', encoding='utf-8')
        git(source, 'add', '.')
        git(source, 'commit', '-qm', 'Adopt live wiki on main')
        git(source, 'push', 'origin', 'main')
        self.assertEqual(select_source(source, 'main', BRANCH), 'main')
        with self.assertRaisesRegex(ValueError, 'branch changed'):
            assert_current(source, manifest, 'main', BRANCH)
