"""Explicit local-use declarations, not inferred licenses or legal clearance.

Only new, bounded World intake can bind this declaration. Existing catalog
evidence is never upgraded by preparation. The exact declaration and file scope
are part of the catalog version; raw distribution/training/future files are not
authorized. No provider, download or commercial-license inference is involved.
"""
from datetime import datetime
from pathlib import PurePosixPath
import re
from .core import DirectorError, digest, fields, require

POLICY = 'local-project-use-v1'
SCOPE = 'existing-local-version-project-use-no-redistribution-or-training'


def validate(confirmation, request=None):
    keys = {'policy', 'confirmed', 'source_id', 'source_version', 'member', 'confirmed_at', 'project_id'}
    fields(confirmation, keys, keys)
    require(confirmation['policy'] == POLICY and confirmation['confirmed'] is True,
            'LOCAL_USE_CONFIRMATION_REQUIRED', 'Explicit local project-use confirmation is required')
    for key, pattern in [('source_id', r'src_[a-f0-9-]{36}'), ('source_version', r'[a-f0-9]{64}'),
                         ('project_id', r'prj_[a-f0-9-]{36}')]:
        require(isinstance(confirmation[key], str) and re.fullmatch(pattern, confirmation[key]),
                'LOCAL_USE_SCOPE_MISMATCH', 'Invalid local confirmation identity')
    member = confirmation['member']
    require(isinstance(member, str) and 0 < len(member) <= 2000 and
            not any(ord(c) < 32 for c in member) and not any(c in member for c in '\\:') and
            not member.startswith('/') and all(p not in {'', '.', '..'} for p in member.split('/')) and
            PurePosixPath(member).suffix.lower() in {'.blend', '.gltf', '.glb', '.fbx'},
            'LOCAL_USE_SCOPE_MISMATCH', 'Confirm one exact supported local member')
    stamp = confirmation['confirmed_at']
    require(isinstance(stamp, str) and len(stamp) <= 100, 'LOCAL_USE_CONFIRMATION_REQUIRED', 'Invalid confirmation time')
    try:
        require(datetime.fromisoformat(stamp.replace('Z', '+00:00')).tzinfo is not None,
                'LOCAL_USE_CONFIRMATION_REQUIRED', 'Use a timezone-aware confirmation time')
    except ValueError:
        raise DirectorError('LOCAL_USE_CONFIRMATION_REQUIRED', 'Invalid confirmation time') from None
    if request is not None:
        require((confirmation['source_id'], confirmation['source_version'], member) ==
                (request['id'], request['version'], request['file']),
                'LOCAL_USE_SCOPE_MISMATCH', 'Confirmation belongs to another package version or member')


def bind(asset, confirmation):
    validate(confirmation)
    require(asset.provider == 'local' and asset.kind == 'model' and asset.license_id == 'UNKNOWN' and
            asset.evidence == 'user_attested' and asset.price == 0 and asset.local_files and
            isinstance(asset.metadata.get('prepared_member'), str) and
            asset.metadata['prepared_member'].endswith('/' + confirmation['member']) and
            not asset.metadata.get('license_grant') and not asset.metadata.get('local_motion'),
            'LOCAL_USE_SCOPE_MISMATCH', 'Local confirmation only binds a newly prepared model')
    record = {'schema': 'asset-director.local-use/1', 'scope': SCOPE, 'confirmation': dict(confirmation),
              'asset_id': asset.id, 'files_sha256': digest(asset.local_files),
              'prepared_member': asset.metadata['prepared_member']}
    record['id'] = 'lc_' + digest(record)
    asset.metadata['local_use_confirmation'] = record


def asset_gate(asset, purpose='project_use'):
    reasons = []
    if purpose != 'project_use':
        reasons.append('RAW_REDISTRIBUTION_NOT_AUTHORIZED')
    try:
        record = asset.metadata.get('local_use_confirmation')
        keys = {'id', 'schema', 'scope', 'confirmation', 'asset_id', 'files_sha256', 'prepared_member'}
        fields(record, keys, keys)
        validate(record['confirmation'])
        require(isinstance(record['prepared_member'], str) and isinstance(asset.local_files, list) and
                1 <= len(asset.local_files) <= 4096 and all(isinstance(f, dict) and
                isinstance(f.get('path'), str) and isinstance(f.get('sha256'), str) and
                re.fullmatch(r'[a-f0-9]{64}', f['sha256']) and type(f.get('size')) is int and f['size'] >= 0
                for f in asset.local_files), 'LOCAL_USE_SCOPE_MISMATCH', 'Invalid local file scope')
        require(record['id'] == 'lc_' + digest({k: v for k, v in record.items() if k != 'id'}) and
                record['schema'] == 'asset-director.local-use/1' and record['scope'] == SCOPE and
                record['asset_id'] == asset.id and record['files_sha256'] == digest(asset.local_files) and
                record['prepared_member'] == asset.metadata.get('prepared_member') and
                record['prepared_member'].endswith('/' + record['confirmation']['member']) and
                record['prepared_member'] in {f['path'] for f in asset.local_files},
                'LOCAL_USE_SCOPE_MISMATCH', 'Local confirmation does not match this exact asset')
        require(asset.provider == 'local' and asset.kind == 'model' and asset.license_id == 'UNKNOWN' and
                asset.evidence == 'user_attested' and asset.price == 0 and asset.local_files and
                not asset.author and not asset.license_url and not asset.source_url and
                not asset.metadata.get('license_grant') and not asset.metadata.get('local_motion'),
                'LOCAL_USE_SCOPE_MISMATCH', 'Do not replace recorded rights with a local declaration')
    except DirectorError as error:
        reasons.append(error.code)
    except (KeyError, TypeError, ValueError):
        reasons.append('LOCAL_USE_SCOPE_MISMATCH')
    return {'eligible': not reasons, 'reasons': reasons, 'basis': 'USER_CONFIRMED_LOCAL_USE',
            'scope': SCOPE, 'license_status': 'NOT_RECORDED', 'attribution_required': True,
            'attribution_notice': 'User must follow the original terms, including required credits.',
            'raw_redistribution': 'DENIED', 'model_training': 'NOT_AUTHORIZED', 'future_files': 'NOT_AUTHORIZED',
            'third_party_rights': 'NOT_VERIFIED', 'commercial_clearance': 'NOT_A_LEGAL_CLEARANCE'}


def job_binding(asset):
    require(asset_gate(asset)['eligible'], 'BLOCKED_POLICY', 'Local source confirmation is missing or changed')
    return {'asset_id': asset.id, 'confirmation_id': asset.metadata['local_use_confirmation']['id'],
            'asset_version': digest({k: v for k, v in asset.to_dict().items() if k != 'checked_at'})}
