"""Run an explicit subsystem's real Blender fixtures; preserve failure evidence.

Fixture processes are isolated from one another. Failure never prevents the
remaining fixtures from running, and missing reports cannot turn into a pass.
"""
import argparse
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from contracts import BLENDER_SUITES, BLENDER_VERSIONS
from evidence import Evidence, ROOT, read


def validate_fixture(text, expected, directory):
    if expected.startswith('@'):
        marker = expected[1:]
        if not any((line == marker or line.startswith(marker + ' ')) for line in text.splitlines()):
            raise ValueError('Real Blender regression did not emit ' + marker)
    else:
        path = directory/expected
        if not path.is_file() or read(path).get('status') != 'PASS':
            raise ValueError('Missing or failed real Blender report: ' + expected)


def validate_version(banner, expected):
    # The publisher appends LTS to supported long-term release banners.
    if not re.fullmatch(r'Blender ' + re.escape(expected) + r'(?: LTS)?', banner):
        raise ValueError('Executable version differs from matrix: ' + banner)


def run_process(args, env, log, timeout):
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run([str(arg) for arg in args], cwd=ROOT, env=env,
                                stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{log.name}: Blender/subprocess exited {result.returncode}')
    return log.read_text(encoding='utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=BLENDER_SUITES, required=True)
    parser.add_argument('--blender', required=True)
    parser.add_argument('--version', choices=BLENDER_VERSIONS, required=True)
    parser.add_argument('--evidence', required=True)
    args = parser.parse_args()
    evidence = Evidence(args.evidence, 'blender', args.suite, platform=sys.platform,
                        blender_version=args.version,
                        not_tested=['installed app/browser path', 'private inputs', 'artistic acceptance'])
    fixtures = BLENDER_SUITES[args.suite]
    try:
        if not __debug__:
            raise RuntimeError('Optimized Python disables test assertions; refuse to run')
        env = dict(os.environ, PYTHONPATH=str(ROOT/'src'), PYTHONIOENCODING='utf-8')
        env.pop('PYTHONOPTIMIZE', None)
        version = subprocess.check_output([args.blender, '--version'], text=True, encoding='utf-8').splitlines()[0]
        validate_version(version, args.version)
        evidence.report['blender_banner'] = version
        with tempfile.TemporaryDirectory(prefix='synthetic-blender-suite-') as temporary:
            root = Path(temporary)
            library = root/'library'
            env['BAD_CONFIG'] = str(root/'runtime.json')
            run_process([sys.executable, '-m', 'asset_director', '--library', library, 'backend-install'],
                        env, evidence.directory/'backend-install.log', 240)
            failures = []
            for name, script, expected, with_library, extra in fixtures:
                output = root/name
                # Several fixtures intentionally require a new, nonexistent output path.
                destination = evidence.directory/'fixtures'/name
                destination.mkdir(parents=True)
                try:
                    with evidence.checkpoint(name):
                        command = [args.blender, '--background', '--factory-startup', '--disable-autoexec',
                                   '--threads', '2', '--python-exit-code', '11', '--python', ROOT/'tools'/script]
                        if not expected.startswith('@'):
                            command += ['--', output]
                            if with_library:
                                command += [library]
                            command += list(extra)
                        text = run_process(command, env, destination/'process.log', 1200)
                        validate_fixture(text, expected, output)
                        if not expected.startswith('@'):
                            shutil.copy2(output/expected, destination/expected)
                        if name == 'workbench-film':
                            movie=output/'synthetic-film.mp4'
                            if not movie.is_file() or movie.stat().st_size>8*1024*1024:
                                raise RuntimeError('Missing or oversized synthetic film evidence')
                            shutil.copy2(movie,destination/movie.name)
                        if name == 'proxy-visual':
                            previews = list(output.glob('proxy-*.png'))
                            if not previews:
                                raise RuntimeError('Proxy fixture omitted its expected previews')
                            for preview in previews:
                                shutil.copy2(preview, destination/preview.name)
                except Exception as exc:
                    failures.append(str(exc))
                finally:
                    # Copy only named diagnostics, never raw Blender/FBX assets.
                    for report in output.glob('*.json'):
                        if report.name == expected or report.stem.endswith(('_progress', '_failure')):
                            shutil.copy2(report, destination/report.name)
                    for log in output.rglob('worker.log'):
                        target = destination/'workers'/log.parent.name/'worker.log'
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(log, target)
            for log in library.glob('jobs/*/worker.log'):
                target = evidence.directory/'workers'/log.parent.name/'worker.log'
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(log, target)
            if failures:
                raise RuntimeError('; '.join(failures))
        evidence.finish(row[0] for row in fixtures)
        return 0
    except Exception as exc:
        evidence.fail(exc)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
