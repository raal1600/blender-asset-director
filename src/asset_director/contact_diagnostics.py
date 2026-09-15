"""Pure reduction of measured sole samples; no edits or automatic foot locking."""
import math
import copy
from .core import require, fields
from .motion_assets import finite, vector


def summarize(samples, options):
    require(isinstance(samples, list) and 1 <= len(samples) <= 257,
            'CONTACT_SAMPLES_REQUIRED', 'Need 1..257 measured sole samples')
    # Preserve the raw measurements and reject nonfinite/unsorted evidence.
    samples = copy.deepcopy(samples)
    finite(options['meters_per_unit'], 1e-6, 1e3)
    finite(options['ground_z'], -1e4, 1e4)
    finite(options['tolerance_m'], 1e-6, .1)
    finite(options['near_ground_m'], options['tolerance_m'], .5)
    finite(options['glide_speed_m_s'], 1e-6, 10)
    for sample in samples:
        fields(sample, {'frame', 'time', 'left', 'right'}, {'frame', 'time', 'left', 'right'})
        finite(sample['frame'], -100000, 100000); finite(sample['time'], -1e7, 1e7)
        for side in ('left', 'right'):
            fields(sample[side], {'minimum_z', 'centroid'}, {'minimum_z', 'centroid'})
            finite(sample[side]['minimum_z']); vector(sample[side]['centroid'], bound=1e6)
    require(all(a['frame'] < b['frame'] and a['time'] < b['time'] for a,b in zip(samples,samples[1:])),
            'INVALID_TIMING', 'Measured frames and times must both increase')
    meters = options['meters_per_unit']; floor = options['ground_z']
    tol = options['tolerance_m']; near = options['near_ground_m']
    groups = {'integer_frames': [], 'subframes': []}; previous = None
    for sample in samples:
        f = sample['frame']
        group = 'integer_frames' if abs(f-round(f)) < 1e-6 else 'subframes'
        groups[group].append(sample)
        for side in ('left', 'right'):
            foot = sample[side]; h = (foot['minimum_z']-floor)*meters
            speed = None
            if previous is not None:
                dt = sample['time']-previous['time']
                require(dt > 0,'INVALID_TIMING','Contact times must increase')
                old = previous[side]['centroid']
                speed = math.hypot(foot['centroid'][0]-old[0], foot['centroid'][1]-old[1])*meters/dt
            foot['minimum_clearance_m'] = h
            foot['horizontal_centroid_speed_m_s'] = speed
            foot['state'] = ('PENETRATING' if h < -tol else 'ABOVE_GROUND_UNCLASSIFIED' if h > near else
                             'UNKNOWN_INITIAL_SAMPLE' if speed is None else
                             'GLIDE_CANDIDATE' if speed > options['glide_speed_m_s'] else 'PLANT_CANDIDATE')
        previous = sample
    summaries = {}
    for name, seq in groups.items():
        values = [s[side]['minimum_clearance_m'] for s in seq for side in ('left','right')]
        summaries[name] = {'count': len(seq), 'minimum_clearance_m': min(values) if values else None,
                           'maximum_clearance_m': max(values) if values else None,
                           'max_penetration_m': max(0, -min(values)) if values else None,
                           'penetration_within_tolerance': min(values) >= -tol if values else None}
    per_foot = {side: {'minimum_clearance_m': min(s[side]['minimum_clearance_m'] for s in samples),
                       'maximum_clearance_m': max(s[side]['minimum_clearance_m'] for s in samples),
                       'maximum_horizontal_centroid_speed_m_s': max(
                           (s[side]['horizontal_centroid_speed_m_s'] for s in samples
                            if s[side]['horizontal_centroid_speed_m_s'] is not None), default=None)}
                for side in ('left', 'right')}
    return {'samples': samples, 'extrema': summaries, 'per_foot': per_foot, 'tolerance_m': tol,
            'status': 'SAMPLED_PENETRATION' if any(s[k]['state']=='PENETRATING' for s in samples for k in ('left','right')) else 'NO_SAMPLED_PENETRATION',
            'channels_changed': [], 'repair_applied': False, 'intentional_glide': 'REQUIRES_PERFORMANCE_EVIDENCE',
            'floating_vs_airborne': 'NOT_INFERRED', 'performance': 'PENDING',
            'scope': 'finite sole/centroid samples, not swept-volume, support pressure, heel/toe phase or continuous contact'}
