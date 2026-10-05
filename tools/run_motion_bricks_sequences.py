"""Run real MotionBricks sequence fixtures and fresh Blender reopen checks.

The manifest points to locally authorized assets. No network acquisition or
upload. Every case runs in a separate bounded Blender process with measured
resources. Contacts and visual quality require separate reviewed evidence.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from transition_resources import measured_run

ROOT = Path(__file__).resolve().parents[1]

def main():
    if not __debug__:
        raise RuntimeError("Optimized Python disables acceptance assertions")
    environment=dict(os.environ, PYTHONIOENCODING="utf-8");environment.pop("PYTHONOPTIMIZE",None)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--blender', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', action='append', help='Explicit case names; default all manifest cases')
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    if not 5 <= args.timeout <= 900:
        parser.error('Per-process timeout must be 5..900 seconds')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    assert manifest['schema'] == 'motion-bricks-sequence-fixture-v1'
    names = [case['name'] for case in manifest['cases']]
    assert 1 <= len(names) <= 16 and len(names) == len(set(names))
    assert all(re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', name) for name in names)
    selected = args.case or names
    assert selected and len(selected) == len(set(selected)) and set(selected) <= set(names)
    args.output.mkdir(parents=True, exist_ok=False)
    identity = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, timeout=10)
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, capture_output=True, text=True, timeout=10)
    report = {'status': 'FAIL', 'scope': 'REAL_PROVIDER_CONTINUITY_TIMING_PRESERVATION_AND_REOPEN',
              'contact_quality': 'NOT VERIFIED', 'visual_quality': 'NOT VERIFIED', 'client_journey': 'NOT TESTED BY THIS RUNNER',
              'commit': identity.stdout.strip() if identity.returncode == 0 else None,
              'tracked_source_dirty': bool(dirty.stdout.strip()) if dirty.returncode == 0 else None, 'cases': []}
    command = [str(args.blender.resolve()), '--background', '--factory-startup', '--disable-autoexec',
               '--threads', '2', '--python-exit-code', '1', '--python', str(ROOT/'tools/motion_bricks_sequence_fixture.py'), '--']
    try:
        for name in selected:
            folder = args.output/name
            measured = measured_run(command + ['--manifest', str(args.manifest.resolve()), '--case', name,
                                               '--output', str(folder.resolve())],
                                    args.output/(name+'.log'), cwd=ROOT, env=environment, timeout=args.timeout)
            (args.output/(name+'-resources.json')).write_text(json.dumps(measured, indent=2)+'\n', encoding='utf-8')
            case = {'name': name, 'status': 'FAIL', 'generate_exit_code': measured['exit_code'],
                    'generate_process_release': measured['observed_process_release']}
            report['cases'].append(case)
            if measured['exit_code'] == 0 and measured['observed_process_release'] == 'PASS':
                result = json.loads((folder/'RESULTS.json').read_text(encoding='utf-8'))
                if result['status'] == 'PASS':
                    if result.get('expected_refusal'):
                        case.update(status='PASS', refusal=result['code'])
                    else:
                        reopened = measured_run(command+['--verify',str((folder/'RESULTS.json').resolve())],
                                                args.output/(name+'-reopen.log'), cwd=ROOT, env=environment, timeout=args.timeout)
                        (args.output/(name+'-reopen-resources.json')).write_text(json.dumps(reopened,indent=2)+'\n',encoding='utf-8')
                        case.update(reopen_exit_code=reopened['exit_code'],reopen_process_release=reopened['observed_process_release'])
                        if reopened['exit_code'] == 0 and reopened['observed_process_release'] == 'PASS':
                            verified=json.loads((folder/'fresh-process.json').read_text(encoding='utf-8'))
                            assert verified['status']=='PASS'
                            case.update(status='PASS',source_sha256=result['result_sha256'])
            print(json.dumps(case),flush=True)
        report['status']='PASS' if all(case['status']=='PASS' for case in report['cases']) else 'FAIL'
    finally:
        (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return 0 if report['status']=='PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
