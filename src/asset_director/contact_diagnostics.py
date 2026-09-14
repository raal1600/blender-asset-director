"""Pure reduction of measured sole samples; no edits or automatic foot locking."""
import math
from .core import require


def summarize(samples, options):
    require(samples, 'CONTACT_SAMPLES_REQUIRED', 'No sole measurements')
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
    return {'samples': samples, 'extrema': summaries, 'tolerance_m': tol,
            'status': 'SAMPLED_PENETRATION' if any(s[k]['state']=='PENETRATING' for s in samples for k in ('left','right')) else 'NO_SAMPLED_PENETRATION',
            'channels_changed': [], 'repair_applied': False, 'intentional_glide': 'REQUIRES_PERFORMANCE_EVIDENCE',
            'floating_vs_airborne': 'NOT_INFERRED', 'performance': 'PENDING',
            'scope': 'finite sole/centroid samples, not swept-volume, support pressure, heel/toe phase or continuous contact'}
