"""Independent acceptance inventory for the mandatory Windows GUI journey."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent/'ci'))
from contracts import SCHEMA
from evidence import read
from verify_evidence import validate_artifacts

DESKTOP_CHECKS = ('native_host_loaded', 'second_launch_reused', 'blender_task_focused',
                  'active_close_preserved', 'native_edit_checkpoint', 'unrelated_unsaved_preserved',
                  'idle_exit_stopped_server', 'restart_resumed')
ARTIFACTS = {'native-desktop.png', 'native-blender.png', 'native-checkpoint.json', 'native-events.json',
             'native-task-exit.png', 'native-exit-options.png', 'empty-task-status.json'}


def verify(root, commit):
    import re
    if not re.fullmatch('[a-f0-9]{40}', commit):raise ValueError('Exact source commit required')
    report=read(Path(root)/'report.json')
    if (report.get('schema'), report.get('kind'), report.get('partition'), report.get('platform'),
        report.get('status'), report.get('commit')) != (SCHEMA,'desktop','native-roundtrip','win32','PASS',commit):
        raise ValueError('Wrong, failed or stale native desktop evidence')
    checks=report.get('checks',[])
    if [c.get('id') for c in checks]!=list(DESKTOP_CHECKS) or any(c.get('status')!='PASS' for c in checks):
        raise ValueError('Native desktop checkpoints missing or failed')
    if not ARTIFACTS.issubset(report.get('artifacts',{})):raise ValueError('Native evidence attachments missing')
    validate_artifacts(root, report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--commit',required=True)
    args=parser.parse_args();verify(args.root,args.commit);print('NATIVE_DESKTOP_EVIDENCE_VERIFIED '+args.commit)
