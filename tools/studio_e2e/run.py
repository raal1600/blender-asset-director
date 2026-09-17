"""Run real installed-studio journeys against generated, disposable inputs only."""
import argparse
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/ci'))
from contracts import SCENARIOS, checkpoints
from evidence import Evidence
from support import Studio
import journeys

NOT_TESTED = [
    'authenticated Codex/model calls and autonomous agent decisions',
    'native desktop EXE focus/tray and live Blender add-on MCP',
    'private/licensed inputs and installed-studio retargeting',
    'human visual/temporal/artistic acceptance',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', required=True)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--scenario', choices=SCENARIOS, default='full')
    args = parser.parse_args()
    evidence = Evidence(args.evidence, 'studio', args.scenario, platform=sys.platform,
                        not_tested=NOT_TESTED,
                        source_use_answers='Synthetic MCP client; generated inputs only')
    try:
        if not __debug__:
            raise RuntimeError('Optimized Python disables test assertions; refuse to run')
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory(prefix='synthetic-studio-e2e-') as temporary:
            s = Studio(temporary, args.blender, evidence)
            try:
                s.install()
                with sync_playwright() as pw:
                    try:
                        s.open_browser(pw)
                        for stage in SCENARIOS[args.scenario][1:]:
                            getattr(journeys, stage)(s)
                        s.preserve()
                        assert not s.errors, s.errors
                        s.page.screenshot(path=str(evidence.directory/'studio.png'))
                    except Exception:
                        if s.page:
                            try:
                                s.page.screenshot(path=str(evidence.directory/'failure.png'))
                            except Exception:
                                pass  # Diagnostics cannot replace the original failure.
                        raise
                    finally:
                        s.close()
            finally:
                # Export on success AND failure, even after a partial setup.
                try:
                    s.export_jobs()
                finally:
                    s.close()
        evidence.finish(checkpoints(args.scenario))
    except Exception as error:
        evidence.fail(error)
        print(evidence.redact(str(error)), file=sys.stderr)
        return 1
    print((evidence.directory/'report.json').read_text(encoding='utf-8'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
