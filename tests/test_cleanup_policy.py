"""Safety tests for one-time cleanup; no network requests or repository writes."""
import copy
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'tools' / 'cleanup_merged_branches.py'
spec = importlib.util.spec_from_file_location('cleanup_merged_branches', PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SHA = 'a' * 40


class CleanupPolicyTests(unittest.TestCase):
    def test_matching_inventory_and_ancestor_required(self):
        kwargs = dict(protected=False, ancestor=True, open_pr=False)
        self.assertEqual(m.decision('feature/old', SHA, SHA, **kwargs), 'eligible')
        for change in ({'protected': True}, {'ancestor': False}, {'open_pr': True}):
            self.assertNotEqual(m.decision('feature/old', SHA, SHA, **(kwargs | change)), 'eligible')
        self.assertNotEqual(m.decision('feature/old', 'b'*40, SHA, **kwargs), 'eligible')
        self.assertNotEqual(m.decision('main', SHA, SHA, **kwargs), 'eligible')

    def test_integration_requires_matching_merged_pr(self):
        kwargs = dict(protected=False, ancestor=True, open_pr=False)
        self.assertNotEqual(m.decision('chore/integrate', SHA, None, **kwargs), 'eligible')
        self.assertEqual(m.decision('chore/integrate', SHA, None, merged_pr=True, **kwargs), 'eligible')

    def test_exact_main_success_not_an_older_or_pr_run(self):
        good = dict(id=1, name='CI', head_sha=SHA, head_branch='main', event='push', status='completed', conclusion='success')
        self.assertTrue(m.gates_passed([good], ['CI'], SHA))
        for change in ({'head_sha': 'b'*40}, {'head_branch': 'feature/test'}, {'event': 'pull_request'},
                       {'status': 'in_progress'}, {'conclusion': 'skipped'}, {'conclusion': 'failure'}):
            self.assertFalse(m.gates_passed([good | change], ['CI'], SHA))
        self.assertFalse(m.gates_passed([good], ['CI', 'Pages'], SHA))
        self.assertFalse(m.gates_passed([good, good | {'id': 2, 'conclusion': 'failure'}], ['CI'], SHA))
        self.assertFalse(m.gates_passed([], ['CI'], SHA))

    def test_transaction_only_deletes_named_refs_under_explicit_leases(self):
        command = m.deletion_command([{'name':'feature/old', 'sha':SHA}])
        self.assertIn('--atomic', command)
        self.assertIn('--force-with-lease=refs/heads/feature/old:'+SHA, command)
        self.assertEqual(command[-1], ':refs/heads/feature/old')
        self.assertNotIn('--force', command)
        for bad in ([], [{'name':'main','sha':SHA}], [{'name':'feature/old','sha':'short'}]):
            with self.assertRaises(ValueError): m.deletion_command(bad)

    def test_manifest_cannot_select_main_or_a_different_repository(self):
        valid = {'schema':'asset-director.branch-cleanup/1','repository':'owner/repo',
                 'branches':[{'name':'feature/old','sha':SHA}], 'integration_branch':'chore/integrate', 'required_workflows':['CI']}
        m.validate_manifest(valid, 'owner/repo')
        with self.assertRaises(ValueError): m.validate_manifest(valid, 'other/repo')
        for name in ('main', '../main', '-delete', 'x//y', 'feature/old'):
            bad = copy.deepcopy(valid); bad['integration_branch'] = name
            with self.assertRaises(ValueError): m.validate_manifest(bad, 'owner/repo')
        bad = copy.deepcopy(valid); bad['required_workflows'] = []
        with self.assertRaises(ValueError): m.validate_manifest(bad, 'owner/repo')


if __name__ == '__main__': unittest.main()
