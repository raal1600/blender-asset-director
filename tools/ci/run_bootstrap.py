"""Run the real installer lifecycle and retain exact-commit acceptance evidence."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from contracts import BOOTSTRAP_CHECKS
from evidence import Evidence, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell', choices=('sh', 'pwsh', 'powershell'), required=True)
    parser.add_argument('--evidence', required=True)
    args = parser.parse_args()
    evidence = Evidence(args.evidence, 'installation', args.shell, platform=sys.platform,
                        not_tested=['live Blender MCP', 'published HTTPS installer selection'])
    try:
        if not __debug__:
            raise RuntimeError('Optimized Python disables test assertions; refuse to run')
        log = evidence.directory/'bootstrap.log'
        with log.open('w', encoding='utf-8') as stream:
            result = subprocess.run([sys.executable, 'tools/bootstrap_smoke.py', '--shell', args.shell],
                                    cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=800)
        text = log.read_text(encoding='utf-8')
        if result.returncode:
            raise RuntimeError('Real bootstrap failed; inspect bootstrap.log')
        reports = [json.loads(line) for line in text.splitlines() if line.startswith('{') and '"shell"' in line]
        if len(reports) != 1 or reports[0].get('status') != 'PASS' or reports[0].get('shell') != args.shell:
            raise RuntimeError('Real bootstrap did not return its expected lifecycle report')
        if reports[0].get('checks') != list(BOOTSTRAP_CHECKS):
            raise RuntimeError('Bootstrap lifecycle coverage changed or is incomplete')
        for name in reports[0]['checks']:
            with evidence.checkpoint(name):
                pass  # Each assertion was executed by the real subprocess above.
        evidence.finish(BOOTSTRAP_CHECKS)
        return 0
    except Exception as exc:
        evidence.fail(exc)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
