"""Immutable clip-result intake and explicit sequence approval (portable Python).

Completed historical retargets are DATA, not jobs to rerun under newer code. Their
record/output hashes and current license dependencies are rechecked. New plans and
execution retain the normal current-implementation stale-job gates.
"""
from pathlib import Path
from .core import require, digest, load_json, file_hash, within
from . import sequence_contract as contract, license_policy as lp


def ref(lib, path):
    path = Path(path)
    return {'path': path.relative_to(lib.root).as_posix(), 'sha256': file_hash(path), 'size': path.stat().st_size}


def completed(lib, jid, operations):
    contract.job_id(jid)
    path = within(lib.root, 'jobs/'+jid+'/job.json')
    require(path.is_file(), 'SEQUENCE_CLIP_MISSING', 'Completed clip job not found in this library')
    job = load_json(path); spec = job['specification']
    require(job.get('id') == jid == 'j_'+digest(spec)[:24]
            and Path(job['library']).resolve() == lib.root
            and job.get('state') == 'SUCCEEDED' and spec['operation'] in operations,
            'SEQUENCE_CLIP_INVALID', 'Need an immutable successful result of the supported operation')
    outputs = job['outputs']
    for f in outputs: lib.verify_file(f)
    result_path = path.parent/'result.json'
    require(any(f['path'] == result_path.relative_to(lib.root).as_posix() for f in outputs),
            'SEQUENCE_CLIP_INVALID', 'Successful job does not bind its result receipt')
    result = load_json(result_path)
    require(result.get('status') == 'OK' and result.get('job_id') == jid,
            'SEQUENCE_CLIP_INVALID', 'Result receipt/job mismatch')
    deps = [ref(lib, path), ref(lib, result_path)]
    grants = spec.get('license_grants', [])
    require(lp.dependencies(lib, grants) == spec.get('license_files', []),
            'LICENSE_EVIDENCE_CHANGED', 'Historical result license evidence changed or was revoked')
    return job, result['data'], path.parent, deps, grants


def clip(lib, jid):
    job, data, directory, deps, grants = completed(lib, jid, {'retarget'})
    spec = job['specification']; review = spec['options'].get('transfer_binding')
    require(review and data.get('qa_roles') and data.get('slot'),
            'SEQUENCE_ROLE_REVIEW_REQUIRED', 'Use a reviewed retarget with recorded QA roles and action slot')
    pjob, proposal, _, pdeps, _ = completed(lib, review['plan_job_id'], {'transfer-plan'})
    require(proposal.get('id') == review['plan_id'] == 'tp_'+digest({k:v for k,v in proposal.items() if k!='id'})
            and data['qa_roles'] == proposal['target_roles']
            and {k:v for k,v in spec['options'].items() if k != 'transfer_binding'} == proposal['retarget_options'],
            'STALE_SEQUENCE_CLIP', 'Transfer result lost its exact reviewed semantic context')
    from .transfer_review import validate_review
    validate_review(review)
    blend = directory/'result.blend'
    f = ref(lib, blend)
    require(f in job['outputs'], 'SEQUENCE_CLIP_INVALID', 'Clip blend is not a verified output')
    # Descriptor binds content/owner/slot/job, never the generic Mixamo label alone.
    value = {'job_id': jid, 'file': f, 'action': data['action'], 'slot': data['slot'],
             'owner': data['target'], 'target_fingerprint': data['target_fingerprint'],
             'roles': data['qa_roles'], 'world': proposal['target_world'],
             'meters_per_unit': proposal['units']['target_meters_per_unit'],
             'anchor': spec['options']['pose_space']['translation_bone'],
             'fps': data['fps'], 'range': data['frame_range'], 'duration_seconds': data['duration_seconds'],
             'motion_source_asset_id': spec['asset_id'], 'license_grants': grants,
             'character_provenance': proposal['target_character']}
    return value, deps+pdeps+[f], grants


def proposal(lib, review):
    contract.validate_review(review)
    from .jobs import read_job
    job, path = read_job(lib, review['plan_job_id'])
    require(job['state'] == 'SUCCEEDED' and job['specification']['operation'] == 'sequence-plan',
            'SEQUENCE_PLAN_NOT_READY', 'Need a successful read-only sequence plan')
    for f in job['outputs']: lib.verify_file(f)
    p = load_json(path.parent/'result.json')['data']
    require(p.get('schema') == contract.SCHEMA and p.get('status') == 'REVIEW_REQUIRED'
            and p.get('id') == review['plan_id'] == 'sq_'+digest({k:v for k,v in p.items() if k!='id'}),
            'STALE_SEQUENCE_BINDING', 'Sequence proposal identity changed')
    return p, job, path


def prepare(lib, review):
    _, job, _ = proposal(lib, review)
    from .jobs import prepare as job_prepare
    return job_prepare(lib, 'sequence-execute', job['specification']['inputs'][0]['path'],
                       options={'sequence_binding': review})


def dependencies(lib, operation, options, input_file):
    files = []; grants = set()
    if operation == 'sequence-plan':
        for item in options['clips']:
            _, deps, scope = clip(lib, item['job_id']); files += deps; grants.update(scope)
    elif operation == 'sequence-execute':
        _, job, path = proposal(lib, options['sequence_binding'])
        require(Path(input_file).resolve() == Path(job['specification']['inputs'][0]['path']).resolve(),
                'STALE_SEQUENCE_BINDING', 'Sequence review is bound to the exact target file')
        files += job['specification']['source_files'] + [ref(lib, path.parent/'result.json')]
        grants.update(job['specification']['license_grants'])
    else:
        job, data, directory, deps, scope = completed(lib, options['sequence_job_id'], {'sequence-execute'})
        files += deps + [ref(lib, directory/'sequence.json')]
        grants.update(scope)
    unique = {f['path']:f for f in files}
    return [unique[k] for k in sorted(unique)], sorted(grants)
