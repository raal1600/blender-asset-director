"""Test-only interruption of the exact Blender child created by a generated fixture.

The production jobs.run code owns the real Popen. This fixture captures that
handle and stops it during startup; it does not edit job state or kill by name.
"""
import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from asset_director import cli, jobs
from asset_director.core import atomic_json, file_hash


def main(root, library, job_id, blender):
    root, library, blender = Path(root).resolve(), Path(library).resolve(), Path(blender).resolve()
    marker = json.loads((root / 'TEST_FIXTURE.json').read_text())
    assert marker == {'kind': 'synthetic-world-recovery', 'library': str(library), 'job_id': job_id}
    assert library.is_relative_to(root) and blender.is_file()
    job_path = library / 'jobs' / job_id / 'job.json'
    job = json.loads(job_path.read_text())
    assert job['id'] == job_id and job['state'] == 'PLANNED' and job['specification']['operation'] == 'world-transform'
    assert all(Path(item['path']).resolve().is_relative_to(root) for item in job['specification']['inputs'])
    destination = root / 'INTERRUPTION.json'
    assert not destination.exists(), 'One new interruption evidence directory per attempt'
    real_popen, timer = jobs.subprocess.Popen, None
    evidence = {'kind': 'TEST_ONLY_OWNED_CHILD_STARTUP_INTERRUPTION', 'job_id': job_id,
                'blender': str(blender), 'worker_sha256': file_hash(ROOT / 'src/asset_director/worker.py'),
                'stopped': False, 'human_approval': 'NOT_GRANTED'}

    def spawn_owned(args, **kwargs):
        nonlocal timer
        assert Path(args[0]).resolve() == blender and Path(args[-1]).resolve() == job_path
        assert Path(kwargs['cwd']).resolve() == job_path.parent and '--background' in args and '--disable-autoexec' in args
        child = real_popen(args, **kwargs)
        evidence['pid'] = child.pid

        def interrupt():
            try:
                if child.poll() is None:
                    # The retained process handle belongs to this exact startup,
                    # not a PID lookup that could target an unrelated window.
                    child.kill()
                    child.wait(timeout=10)
                    evidence['stopped'] = True
                evidence['returncode'] = child.returncode
            except BaseException as exc:
                evidence['error'] = type(exc).__name__ + ': ' + str(exc)
            finally:
                atomic_json(destination, evidence)

        timer = threading.Timer(.1, interrupt)
        timer.start()
        return child

    jobs.subprocess.Popen = spawn_owned
    try:
        return cli.main(['--library', str(library), 'job-run', job_id, '--blender', str(blender), '--timeout', '180'])
    finally:
        jobs.subprocess.Popen = real_popen
        if timer:timer.join(timeout=15)


if __name__ == '__main__':
    raise SystemExit(main(*sys.argv[1:]))
