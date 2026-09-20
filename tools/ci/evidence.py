"""Small fail-closed report writer for real CI journeys; stdlib only."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

from contracts import SCHEMA

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def source_commit():
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    expected = os.environ.get('GITHUB_SHA')
    if expected and expected != sha:
        raise RuntimeError('Checkout does not match the workflow commit')
    return sha


class Evidence:
    def __init__(self, directory, kind, partition, **metadata):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.secrets = []
        self.report = dict(schema=SCHEMA, kind=kind, partition=partition, status='FAIL',
                           checks=[], started_at=datetime.now(timezone.utc).isoformat(),
                           run_id=os.environ.get('GITHUB_RUN_ID', 'LOCAL'), **metadata)
        self.save()  # Persist FAIL even when Git or setup subsequently fails.
        self.report['commit'] = source_commit()
        self.save()

    def redact(self, text):
        for secret in self.secrets:
            if secret:
                text = text.replace(secret, '[REDACTED]')
        return text

    def save(self):
        text = self.redact(json.dumps(self.report, indent=2))
        (self.directory / 'report.json').write_text(text + '\n', encoding='utf-8')
        failed = sum(c['status'] != 'PASS' for c in self.report['checks'])
        incomplete = self.report['status'] != 'PASS' and not failed
        suite = ET.Element('testsuite', name=self.report['kind'] + ':' + self.report['partition'],
                           tests=str(len(self.report['checks']) + int(incomplete)),
                           failures=str(failed + int(incomplete)))
        for check in self.report['checks']:
            case = ET.SubElement(suite, 'testcase', name=check['id'], time=str(check.get('seconds', 0)))
            if check['status'] != 'PASS':
                ET.SubElement(case, 'failure', message=self.redact(check.get('error', 'Incomplete checkpoint')))
        if incomplete:
            case = ET.SubElement(suite, 'testcase', name='runner_completion')
            ET.SubElement(case, 'failure', message=self.redact(self.report.get('error', 'Run incomplete')))
        ET.ElementTree(suite).write(self.directory / 'junit.xml', encoding='utf-8', xml_declaration=True)

    @contextmanager
    def checkpoint(self, name):
        if any(c['id'] == name for c in self.report['checks']):
            raise ValueError('Duplicate checkpoint: ' + name)
        check = {'id': name, 'status': 'FAIL'}
        self.report['checks'].append(check)
        self.save()
        started = time.monotonic()
        try:
            yield check
        except Exception as exc:
            check['error'] = self.redact(str(exc))[-5000:]
            raise
        else:
            check['status'] = 'PASS'
        finally:
            check['seconds'] = round(time.monotonic() - started, 3)
            self.save()

    def finish(self, expected):
        checks = self.report['checks']
        ids = [c['id'] for c in checks]
        if ids != list(expected) or not checks or any(c['status'] != 'PASS' for c in checks):
            raise RuntimeError('Missing, failed or out-of-order checkpoints: ' + repr(ids))
        self.report['artifacts'] = {
            path.relative_to(self.directory).as_posix(): digest(path)
            for path in sorted(self.directory.rglob('*'))
            if path.is_file() and path.name not in ('report.json', 'junit.xml')
        }
        if not self.report['artifacts']:
            raise RuntimeError('No execution artifacts were retained')
        self.report['status'] = 'PASS'
        self.save()

    def fail(self, error):
        self.report['status'] = 'FAIL'
        self.report['error'] = self.redact(str(error))[-5000:]
        self.save()
