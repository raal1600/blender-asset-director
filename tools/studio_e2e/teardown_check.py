"""Observe a real pending native preview, then drain only its installed test backend."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import time
import traceback

from support import ROOT, Studio
from evidence import Evidence, digest, read, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--blender', required=True)
    args = parser.parse_args()
    output = Path(args.evidence).resolve()
    if output.exists():
        raise RuntimeError('Use a new synthetic evidence directory')
    evidence = Evidence(output, 'synthetic-resource-check', 'pending-native-shutdown',
                        human_review='NOT_TESTED', native_gui='NOT_TESTED',
                        worktree_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)))
    studio = Studio(output, args.blender, evidence)
    try:
        studio.install()
        project = studio.api('projects/create', {'name': 'Synthetic shutdown probe'})
        studio.api('workbench/create', {'projectId': project['id'], 'revision': project['revision'],
                                       'name': 'Pending preview'})
        project = studio.api('project?projectId='+project['id'])['project']
        scene = project['workbench']['scenes'][0]
        original = Path(project['directory'])/'Scenes/SyntheticSource.blend'
        shutil.copyfile(studio.source, original)
        studio.api('workbench/import', {'projectId': project['id'], 'sceneId': scene['id'],
                    'revision': project['revision'], 'sourceScene': 'Scenes/SyntheticSource.blend'})
        project = studio.api('project?projectId='+project['id'])['project']
        scene = project['workbench']['scenes'][0]
        checkpoint = next(c for c in scene['checkpoints'] if c['id'] == scene['candidate'])
        manifest = Path(project['directory'])/'project.json'
        source_hash, manifest_hash = digest(original), digest(manifest)
        request = dict(projectId=project['id'], sceneId=scene['id'], revision=project['revision'],
                       request={'kind': 'checkpoint', 'id': checkpoint['id']})
        with evidence.checkpoint('pending_native_drain') as check:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(studio.api, 'workbench/viewer-prepare', request)
                preview_root = studio.root/'SystemRuntime/UserData/ViewerPreviews'
                deadline, job_file = time.monotonic()+30, None
                while time.monotonic() < deadline:
                    for candidate in preview_root.glob('view_*/library/jobs/j_*/job.json'):
                        if read(candidate)['state'] == 'RUNNING':
                            job_file = candidate
                            break
                    if job_file:
                        break
                    if pending.done():
                        pending.result()
                        raise RuntimeError('Preview finished before observing its native writer; no timing claim')
                    time.sleep(.02)
                assert job_file is not None, 'Native preview never reached observed RUNNING state'
                assert studio.api('lifecycle')['busy'] is True
                assert not pending.done()
                started = time.monotonic()
                studio.close()
                result = pending.result(timeout=10)
                assert studio.server.poll() == 0, 'Owned backend did not stop normally'
                assert result['nativeJob'] == job_file.parent.name
                native_result = read(job_file.parent/'result.json')
                assert read(job_file)['state'] == 'SUCCEEDED'
                assert native_result['status'] == 'OK'
                write(output/'native-preview-result.json', native_result)
                check.update(job=result['nativeJob'], preview=result['previewId'],
                             drain_seconds=round(time.monotonic()-started, 3),
                             backend_exit=studio.server.returncode, forced_termination=False)
        with evidence.checkpoint('originals_and_evidence_preserved'):
            assert digest(original) == source_hash == digest(studio.source)
            assert digest(manifest) == manifest_hash
            assert digest(Path(project['directory'])/checkpoint['path']) == checkpoint['sha256']
            assert (job_file.parent/'worker.log').is_file()
            write(output/'preservation.json', {'source': source_hash, 'manifest': manifest_hash,
                  'checkpoint': checkpoint['sha256'], 'review': 'UNAPPROVED_CANDIDATE'})
        evidence.finish(['installed_checkout', 'catalog_initialized', 'launcher_authenticated',
                         'pending_native_drain', 'originals_and_evidence_preserved'])
    except Exception as error:
        evidence.fail(error)
        (output/'failure.log').write_text(evidence.redact(traceback.format_exc()), encoding='utf-8')
        print(evidence.redact(str(error)))
        return 1
    finally:
        studio.close()
    print(json.dumps({'status': 'PASS', 'checks': 5, 'native_gui': 'NOT_TESTED'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
