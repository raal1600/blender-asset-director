"""Reject incomplete/mixed-commit evidence; never infer acceptance from file presence."""
import argparse
import json
from pathlib import Path
import re

from contracts import NEEDED_JOBS, SCHEMA, SCENARIOS, BLENDER_SUITES, partitions
from evidence import digest


def validate_needs(needs):
    if not isinstance(needs, dict) or set(needs) != NEEDED_JOBS:
        raise ValueError('Acceptance dependency inventory is missing or changed')
    if any(not isinstance(value, dict) for value in needs.values()):
        raise ValueError('Malformed dependency result')
    failed = {key: value.get('result') for key, value in needs.items() if value.get('result') != 'success'}
    if failed:
        raise ValueError('Dependencies did not succeed: ' + json.dumps(failed))


def validate_reports(reports, commit):
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Expected an exact 40-character source commit')
    expected = partitions()
    observed = set()
    for report in reports:
        if not isinstance(report, dict):
            raise ValueError('Evidence is not a report object')
        if report.get('schema') != SCHEMA or report.get('status') != 'PASS' or report.get('commit') != commit:
            raise ValueError('Failed, malformed or mixed-commit evidence')
        discriminator = report.get('blender_version') if report.get('kind') == 'blender' else report.get('platform')
        key = (report.get('kind'), report.get('partition'), discriminator)
        if key not in expected or key in observed:
            raise ValueError('Unexpected or duplicate evidence partition: ' + repr(key))
        observed.add(key)
        checks = report.get('checks')
        if not isinstance(checks, list) or any(not isinstance(c, dict) for c in checks) or [c.get('id') for c in checks] != list(expected[key]):
            raise ValueError('Required checkpoints absent or reordered: ' + repr(key))
        if any(c.get('status') != 'PASS' for c in checks):
            raise ValueError('Failed or skipped checkpoint: ' + repr(key))
    if observed != set(expected):
        raise ValueError('Missing evidence partitions: ' + repr(sorted(set(expected) - observed)))
    return len(observed)



def validate_artifacts(directory, report):
    directory = Path(directory).resolve()
    artifacts = report.get('artifacts')
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError('Missing artifact hash inventory')
    required = set()
    if report['kind'] == 'studio':
        required.add('studio.png')
        stages = SCENARIOS[report['partition']]
        if 'execution' in stages:
            required.add('synthetic-preview.png')
        if 'production' in stages:
            required.update(('production-preview.png', 'production-scene.json', 'workbench-shot-revision.png'))
    elif report['kind'] == 'installation':
        required.add('bootstrap.log')
    elif report['kind'] == 'blender':
        for name, script, expected, library, extra in BLENDER_SUITES[report['partition']]:
            required.add('fixtures/' + name + '/process.log')
            if not expected.startswith('@'):
                required.add('fixtures/' + name + '/' + expected)
    if not required.issubset(artifacts):
        raise ValueError('Required journey attachments missing: ' + repr(sorted(required - artifacts.keys())))
    for name, checksum in artifacts.items():
        if not isinstance(name, str) or not isinstance(checksum, str) or not re.fullmatch(r'[a-f0-9]{64}', checksum):
            raise ValueError('Malformed artifact hash entry')
        path = directory/name
        if Path(name).is_absolute() or '\\' in name or not path.resolve().is_relative_to(directory):
            raise ValueError('Unsafe evidence path')
        if path.is_symlink() or not path.is_file() or digest(path) != checksum:
            raise ValueError('Missing or changed evidence attachment: ' + name)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    # Runner report files are at the root of each artifact. Nested reports are
    # subprocess evidence, not independent acceptance partitions.
    paths = sorted(args.root.glob('*/report.json'))
    reports = [json.loads(path.read_text(encoding='utf-8')) for path in paths]
    count = validate_reports(reports, args.commit)
    for path, report in zip(paths, reports):
        validate_artifacts(path.parent, report)
    print(json.dumps({'status': 'PASS', 'commit': args.commit, 'partitions': count}))


if __name__ == '__main__':
    main()
