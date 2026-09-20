"""Portable tests of the CI gate, not substitutes for real journey execution."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/ci'))
from contracts import BLENDER_SUITES, NEEDED_JOBS, SCHEMA, SCENARIOS, checkpoints, partitions
from evidence import Evidence, digest, read, write
from run_blender_suite import validate_fixture
from verify_evidence import validate_artifacts, validate_needs, validate_reports

SHA = 'a' * 40


def report_fixtures():
    """Synthetic metadata to test the gate parser, never published as E2E results."""
    reports = []
    for (kind, partition, discriminator), expected in partitions().items():
        report = dict(schema=SCHEMA, kind=kind, partition=partition, status='PASS', commit=SHA,
                      checks=[{'id': name, 'status': 'PASS'} for name in expected])
        report['blender_version' if kind == 'blender' else 'platform'] = discriminator
        reports.append(report)
    return reports


class CoverageContractTests(unittest.TestCase):
    def test_exact_partitions_and_original_fixture_inventory(self):
        self.assertEqual(len(partitions()), 23)
        fixtures = [row for suite in BLENDER_SUITES.values() for row in suite]
        self.assertEqual(len(fixtures), 22)
        self.assertEqual(len({row[0] for row in fixtures}), 22)
        self.assertIn('asset-preview', {row[0] for row in fixtures})
        self.assertIn('import-visibility', {row[0] for row in fixtures})
        for _, script, _, _, _ in fixtures:
            self.assertTrue((ROOT/'tools'/script).is_file())
        self.assertEqual(set(BLENDER_SUITES), {'authoring', 'motion', 'continuity'})

    def test_every_named_studio_journey_reaches_installed_runtime_and_audit(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                checks = checkpoints(scenario)
                self.assertIn('installed_checkout', checks)
                self.assertIn('scene_audited', checks)
                self.assertEqual(len(checks), len(set(checks)))
        self.assertTrue(set(checkpoints('production')).issubset(checkpoints('full')))
        self.assertTrue(set(checkpoints('recovery')).issubset(checkpoints('full')))


class AcceptanceGateTests(unittest.TestCase):
    def test_complete_exact_commit_inventory_is_accepted(self):
        self.assertEqual(validate_reports(report_fixtures(), SHA), 23)

    def test_missing_partition_rejected(self):
        with self.assertRaises(ValueError):
            validate_reports(report_fixtures()[:-1], SHA)

    def test_duplicate_partition_rejected(self):
        reports = report_fixtures()
        reports[-1] = copy.deepcopy(reports[0])
        with self.assertRaises(ValueError):
            validate_reports(reports, SHA)

    def test_short_and_mixed_commit_rejected(self):
        with self.assertRaises(ValueError):
            validate_reports(report_fixtures(), SHA[:7])
        reports = report_fixtures()
        reports[0]['commit'] = 'b' * 40
        with self.assertRaises(ValueError):
            validate_reports(reports, SHA)

    def test_failed_skipped_or_missing_check_rejected(self):
        for mutation in ('status', 'empty', 'skipped', 'reorder', 'malformed'):
            reports = report_fixtures()
            if mutation == 'status':
                reports[0]['status'] = 'FAIL'
            elif mutation == 'empty':
                reports[0]['checks'] = []
            elif mutation == 'skipped':
                reports[0]['checks'][0]['status'] = 'SKIPPED'
            elif mutation == 'reorder':
                reports[0]['checks'].reverse()
            else:
                reports[0]['checks'][0] = 'not a checkpoint'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_reports(reports, SHA)

    def test_unknown_schema_and_partition_rejected(self):
        for key in ('schema', 'partition'):
            reports = report_fixtures()
            reports[0][key] = 'unknown'
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_reports(reports, SHA)

    def test_all_dependency_results_must_be_success(self):
        needs = {key: {'result': 'success'} for key in NEEDED_JOBS}
        validate_needs(needs)
        for status in ('failure', 'cancelled', 'skipped', None):
            invalid = copy.deepcopy(needs)
            invalid['studio']['result'] = status
            with self.subTest(status=status), self.assertRaises(ValueError):
                validate_needs(invalid)
        del needs['studio']
        with self.assertRaises(ValueError):
            validate_needs(needs)

    def test_missing_or_tampered_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root/'bootstrap.log'
            log.write_text('unit-test metadata fixture')
            report = {'kind': 'installation', 'artifacts': {'bootstrap.log': digest(log)}}
            validate_artifacts(root, report)
            log.write_text('changed')
            with self.assertRaises(ValueError):
                validate_artifacts(root, report)
            log.unlink()
            with self.assertRaises(ValueError):
                validate_artifacts(root, report)

    def test_required_scene_artifacts_cannot_be_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root/'arbitrary.log'
            log.write_text('unit-test metadata fixture')
            report = {'kind': 'studio', 'partition': 'production', 'artifacts': {'arbitrary.log': digest(log)}}
            with self.assertRaises(ValueError):
                validate_artifacts(root, report)

    def test_path_traversal_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'evidence'
            root.mkdir()
            log = root/'bootstrap.log'
            log.write_text('unit-test metadata fixture')
            outside = root.parent/'outside.log'
            outside.write_text('do not export')
            report = {'kind': 'installation', 'artifacts': {'bootstrap.log': digest(log), '../outside.log': digest(outside)}}
            with self.assertRaises(ValueError):
                validate_artifacts(root, report)
            # Symlink support differs on Windows; traversal above is always tested.
            try:
                (root/'linked.log').symlink_to(outside)
            except OSError:
                return
            report['artifacts'] = {'bootstrap.log': digest(log), 'linked.log': digest(outside)}
            with self.assertRaises(ValueError):
                validate_artifacts(root, report)


class EvidenceWriterTests(unittest.TestCase):
    def test_writer_starts_failed_and_cannot_finish_without_execution_evidence(self):
        with tempfile.TemporaryDirectory() as tmp, patch('evidence.source_commit', return_value=SHA):
            evidence = Evidence(tmp, 'unit-fixture', 'metadata-only')
            self.assertEqual(read(Path(tmp)/'report.json')['status'], 'FAIL')
            with self.assertRaises(RuntimeError):
                evidence.finish(('real-step',))
            self.assertEqual(ET.parse(Path(tmp)/'junit.xml').getroot().get('failures'), '1')

    def test_checkpoint_and_attachments_required_before_pass(self):
        with tempfile.TemporaryDirectory() as tmp, patch('evidence.source_commit', return_value=SHA):
            evidence = Evidence(tmp, 'unit-fixture', 'metadata-only')
            with evidence.checkpoint('parser-fixture'):
                pass
            with self.assertRaises(RuntimeError):
                evidence.finish(('parser-fixture',))
            (Path(tmp)/'unit-fixture.txt').write_text('not an E2E artifact')
            evidence.finish(('parser-fixture',))
            self.assertEqual(read(Path(tmp)/'report.json')['status'], 'PASS')
            self.assertEqual(ET.parse(Path(tmp)/'junit.xml').getroot().get('failures'), '0')

    def test_failed_checkpoint_and_secret_remain_failed_and_redacted(self):
        with tempfile.TemporaryDirectory() as tmp, patch('evidence.source_commit', return_value=SHA):
            evidence = Evidence(tmp, 'unit-fixture', 'metadata-only')
            evidence.secrets.append('unit-test-token')
            with self.assertRaisesRegex(RuntimeError, 'unit-test-token'):
                with evidence.checkpoint('negative-parser-fixture'):
                    raise RuntimeError('unit-test-token must never be exported')
            for name in ('report.json', 'junit.xml'):
                text = (Path(tmp)/name).read_text()
                self.assertNotIn('unit-test-token', text)
                self.assertIn('REDACTED', text)
            with self.assertRaises(RuntimeError):
                evidence.finish(('negative-parser-fixture',))

    def test_setup_failure_is_visible_in_junit(self):
        with tempfile.TemporaryDirectory() as tmp, patch('evidence.source_commit', return_value=SHA):
            evidence = Evidence(tmp, 'unit-fixture', 'metadata-only')
            evidence.fail('setup did not execute')
            root = ET.parse(Path(tmp)/'junit.xml').getroot()
            self.assertEqual(root.get('failures'), '1')
            self.assertIn('setup did not execute', (Path(tmp)/'junit.xml').read_text())


class BlenderReportParserTests(unittest.TestCase):
    def test_missing_failed_and_success_report_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                validate_fixture('', 'look_report.json', root)
            write(root/'look_report.json', {'status': 'FAIL'})
            with self.assertRaises(ValueError):
                validate_fixture('', 'look_report.json', root)
            write(root/'look_report.json', {'status': 'PASS'})
            validate_fixture('', 'look_report.json', root)

    def test_markers_require_exact_token_not_zero_exit_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            for text in ('', 'PASS_suffix', 'some PASS'):
                with self.subTest(text=text), self.assertRaises(ValueError):
                    validate_fixture(text, '@PASS', Path(tmp))
            validate_fixture('other\nPASS\n', '@PASS', Path(tmp))
            validate_fixture("PASS {'measured': 1}", '@PASS', Path(tmp))
