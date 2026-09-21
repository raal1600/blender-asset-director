"""Reviewed local package preparation; reuse intake and isolated Blender inspection.

No provider download, original write, license invention or project approval.
"""
from pathlib import Path
from .core import Asset, atomic_json, fields, file_hash, load_json, require, rights, within
from .acquire import MAX_DOWNLOAD
from .asset_preview import prepare
from .intake import intake
from .workbench_catalog import describe


def validate_evidence(evidence):
    fields(evidence, {'title', 'kind', 'source_url', 'license_id', 'license_url', 'author', 'price', 'tags', 'attested'},
           {'title', 'kind', 'source_url', 'license_id', 'license_url', 'author', 'price', 'attested'})
    require(evidence['kind'] == 'model' and evidence['attested'] is True and type(evidence['price']) in {int, float}
            and evidence['price'] == 0, 'RIGHTS_REQUIRED', 'Confirm the actual zero-cost source and retained rights')
    for key in ('title', 'source_url', 'license_id', 'license_url', 'author'):
        value = evidence[key]
        require(isinstance(value, str) and 0 < len(value.strip()) <= 2000 and not any(ord(c) < 32 for c in value),
                'RIGHTS_REQUIRED', 'Provide the actual ' + key)
    # No network request is made. References are recorded evidence, not trusted instructions.
    from urllib.parse import urlsplit
    for key in ('source_url', 'license_url'):
        url = urlsplit(evidence[key])
        require(url.scheme == 'https' and url.hostname and not url.username and not url.password,
                'RIGHTS_REQUIRED', 'Use an HTTPS source/terms reference without credentials')
    require(isinstance(evidence.get('tags', []), list) and len(evidence.get('tags', [])) <= 16 and
            all(isinstance(t, str) and len(t) <= 100 for t in evidence.get('tags', [])), 'INVALID_SCHEMA', 'Invalid tags')
    asset = Asset('local', 'policy-check', evidence['title'], 'model', evidence['source_url'],
                  evidence['license_id'], evidence['license_url'], evidence['author'], 0, True,
                  ['.blend'], evidence.get('tags', []), 'user_attested')
    require(rights(asset)['eligible'], 'BLOCKED_POLICY', 'These rights need the existing specialist review; no automatic relicensing')


def run(lib, request_file, evidence_file, blender):
    request_file = Path(request_file).resolve()
    request = load_json(request_file)
    evidence = load_json(Path(evidence_file))
    validate_evidence(evidence)
    require(request.get('source_kind') == 'source' and Path(request['file']).suffix.lower() in {'.blend', '.gltf', '.glb', '.fbx'},
            'FORMAT_UNSUPPORTED', 'Guided preparation supports registered World model packages; motion and conversion need review')
    require(sum(f['size'] for f in request['files']) <= MAX_DOWNLOAD, 'RESOURCE_LIMIT', 'Preparation is bounded to 500 MiB')
    receipt = request_file.parent / 'intake-receipt.json'
    result = {'schema': 1, 'state': 'PREPARING', 'source_id': request['id'], 'source_version': request['version'],
              'source_file': request['file'], 'production_use_approved': False, 'scene_imported': False}
    atomic_json(receipt, result)
    try:
        # A real Blender read of a separate verified copy checks package-local
        # dependencies. Script execution remains disabled by the native runner.
        inspection = prepare(request_file, blender)
        result['inspection_job'] = inspection['job_id']
        result['observed_objects'] = len(inspection['data']['objects'])
        # Intake the byte-identical package snapshot, NOT PREVIEW_COPY.blend.
        # Relative dependencies and the original package identity are retained.
        package = request_file.parent / 'library/incoming/package'
        taken = intake(lib, str(package), str(evidence_file), preserve_existing=True, prepared_member=request['file'])
        asset = describe(lib, lib.get(taken['asset_id']), verify=True)
        require(asset['policy']['eligible'], 'BLOCKED_POLICY', 'Existing catalog evidence was preserved and still blocks use')
        suffix = '/' + request['file']
        members = [f for f in asset['models'] if f.endswith(suffix)]
        require(len(members) == 1, 'SOURCE_NOT_IN_ASSET', 'Prepared member does not resolve uniquely')
        for record in request['files']:
            source = within(Path(request['root']), record['path'])
            require(source.stat().st_size == record['size'] and file_hash(source) == record['sha256'],
                    'STALE_SOURCE', 'Original changed during preparation; no scene import was authorized')
        result.update(state='READY', asset_id=asset['id'], asset_version=asset['version'], file=members[0],
                      intake_status=taken['status'], dependency_check='PACKAGE_LOCAL', asset=asset)
        atomic_json(receipt, result)
        return result
    except Exception as error:
        result.update(state='FAILED', code=getattr(error, 'code', type(error).__name__), message=str(error))
        atomic_json(receipt, result)
        raise
