"""Portable contract for explicitly preparing an older saved World copy."""
import re
from .core import fields, require

VERSION = 'world-prepare-v1'
FIELDS = {'version', 'audit_sha256', 'groups'}


def validate(options):
    require(isinstance(options, dict), 'INVALID_OPTIONS', 'World preparation needs an object')
    fields(options, FIELDS)
    require(set(options) == FIELDS and options['version'] == VERSION,
            'INVALID_OPTIONS', 'Unsupported or incomplete World preparation request')
    require(isinstance(options['audit_sha256'], str)
            and re.fullmatch('[0-9a-f]{64}', options['audit_sha256']),
            'INVALID_OPTIONS', 'Use the exact current compatibility inspection')
    groups = options['groups']
    require(isinstance(groups, list) and 1 <= len(groups) <= 64,
            'RESOURCE_LIMIT', 'Prepare one to 64 explicitly observed import groups')
    seen = set()
    for group in groups:
        require(isinstance(group, dict) and set(group) == {'asset_id', 'import_job'},
                'INVALID_OPTIONS', 'An import group needs its exact asset and job identities')
        pair = tuple(group[k] for k in ('asset_id', 'import_job'))
        require(all(isinstance(v, str) and not any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in v)
                    and 1 <= len(v.encode('utf-8')) <= 200 for v in pair),
                'INVALID_OPTIONS', 'Invalid import-group identity')
        require(pair not in seen, 'INVALID_OPTIONS', 'Choose each import group only once')
        seen.add(pair)
    return options
