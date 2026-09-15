"""Physical numerical budget for non-anchor local translation, not a cleanup.

The approved unit conversion and fixed uniform world scale determine local units.
A centimetre FBX must not face a hundred-times tighter physical epsilon than a
metre FBX. Original channels are never edited to satisfy this check.
"""
import math
from .core import require

TOLERANCE_M = 1e-5  # 10 micrometres per component, same as the old metre check.


def precision(meters_per_unit, world_scale=1.0):
    require(type(meters_per_unit) in (int, float) and math.isfinite(meters_per_unit)
            and 1e-6 <= meters_per_unit <= 1e3,
            'INVALID_POSE_TRANSFER', 'Declare bounded metres per source scene unit')
    require(type(world_scale) in (int, float) and math.isfinite(world_scale) and world_scale > 0,
            'INVALID_POSE_TRANSFER', 'A positive fixed uniform object scale is required')
    factor = meters_per_unit * world_scale
    require(math.isfinite(factor) and factor > 0, 'INVALID_POSE_TRANSFER', 'Invalid local-to-metre factor')
    return {'tolerance_m_per_component': TOLERANCE_M,
            'meters_per_local_unit': factor, 'tolerance_local_units': TOLERANCE_M/factor,
            'basis': 'reviewed source units times fixed uniform world scale; not a caller-selected tolerance'}


def check_span(values, policy, label='non-anchor channel'):
    require(values and all(type(v) in (int, float) and math.isfinite(v) for v in values),
            'INVALID_MOTION', 'Nonfinite or empty translation samples')
    span = max(values)-min(values)
    physical = span*policy['meters_per_local_unit']
    require(physical <= policy['tolerance_m_per_component'], 'NON_ANCHOR_TRANSLATION',
            f'{label}: non-anchor translation span {physical:.9g} m exceeds '
            f'{policy["tolerance_m_per_component"]:.9g} m; only the reviewed source anchor may translate')
    return physical
