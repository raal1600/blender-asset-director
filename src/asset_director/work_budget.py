"""Explicit long-take budgets. Legacy callers keep the short-take default.

This bounds generated keys/evaluations, not merely an artistic duration. All
requested limits are themselves capped; approval is bound by the transfer plan.
"""
import math
from .core import fields, require

FIELDS = {'max_duration_seconds', 'max_samples', 'max_bone_samples', 'max_created_keys'}
HARD = {'max_duration_seconds': 120, 'max_samples': 7201,
        'max_bone_samples': 500000, 'max_created_keys': 3500000}
DEFAULT = {'max_duration_seconds': 120, 'max_samples': 361,
           'max_bone_samples': 92416, 'max_created_keys': 646912}


def validate(value):
    if value is None:
        return dict(DEFAULT)
    fields(value, FIELDS, FIELDS)
    for key, cap in HARD.items():
        v = value[key]
        require(type(v) in ((int, float) if key == 'max_duration_seconds' else (int,))
                and math.isfinite(v) and 1 <= v <= cap,
                'RESOURCE_LIMIT', 'Invalid bounded work budget: ' + key)
    require(value['max_samples'] >= 2, 'RESOURCE_LIMIT', 'Need at least two samples')
    return dict(value)


def account(value, duration, samples, bones):
    limit = validate(value)
    require(type(bones) is int and 1 <= bones <= 256, 'RESOURCE_LIMIT', 'Invalid mapped bone count')
    require(math.isfinite(duration) and 0 < duration <= limit['max_duration_seconds']
            and 2 <= samples <= limit['max_samples'], 'RESOURCE_LIMIT',
            'Take exceeds reviewed duration/sample budget; do not crop or change FPS')
    measured = {'duration_seconds': duration, 'samples': samples,
                'bone_samples': samples * bones, 'created_keys_upper_bound': samples * bones * 7}
    require(measured['bone_samples'] <= limit['max_bone_samples']
            and measured['created_keys_upper_bound'] <= limit['max_created_keys'],
            'RESOURCE_LIMIT', 'Take exceeds reviewed mapped-pose/key budget')
    return {'limits': limit, 'estimated': measured,
            'explicit_long_take_budget': value is not None,
            'grounding_budget': 'separate 2881 checkpoints and 50M full-mesh evaluations; no implicit increase'}
