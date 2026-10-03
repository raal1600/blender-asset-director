"""Portable conservative stance-velocity estimate, not a contact/IK solver.

Input: two geometrically observed low, independent skeletal landmarks sampled
over a complete native cycle in world metres. Names never classify the gait.
No input is a human loop, contact, or performance approval.
"""
import math
from statistics import median

VERSION = 'stance-pace-v1'


def unavailable(reason):
    return {'version': VERSION, 'status': 'unavailable', 'reason': reason}


def estimate(traces, height):
    if not math.isfinite(height) or height < .01 or len(traces) != 2:
        return unavailable('Automatic pace needs two unambiguous low support landmarks on an upright rig.')
    names = sorted(traces)
    paths = [traces[name] for name in names]
    count = len(paths[0])
    if count < 33 or count > 129 or any(len(p) != count for p in paths):
        return unavailable('Insufficient bounded gait samples.')
    if any(len(p) != 3 or not all(math.isfinite(x) for x in p) for path in paths for p in path):
        return unavailable('Invalid gait samples.')
    seam = max(math.dist(path[0], path[-1]) for path in paths)
    if seam > height * .025:
        return unavailable('The support landmarks do not close into a repeatable cycle; inspect the take in Blender.')
    velocities, masks = [], []
    for path in paths:
        low = min(p[2] for p in path)
        lift = max(p[2] for p in path) - low
        if not height * .008 <= lift <= height * .3:
            return unavailable('No clear alternating lift and stance; automatic walking pace is not reliable for this take.')
        mask, samples = [], []
        for a, b in zip(path, path[1:]):
            v = [(a[k] - b[k]) * (count - 1) for k in range(3)]
            speed = math.hypot(*v[:2])
            contact = ((a[2] + b[2]) / 2 <= low + height * .025
                       and abs(v[2]) <= max(height * .06, speed * .3)
                       and speed > height * .05)
            mask.append(contact)
            if contact: samples.append(v[:2])
        if len(samples) < (count - 1) * .18:
            return unavailable('Too little stable stance to estimate travel without guessing.')
        velocities.append(samples); masks.append(mask)
    union = sum(a or b for a, b in zip(*masks)) / (count - 1)
    exclusive = sum(a != b for a, b in zip(*masks)) / (count - 1)
    if union < .55 or exclusive < .25:
        return unavailable('Support is not a clear alternating grounded gait; use the native take or Blender.')
    means = [[median(v[k] for v in samples) for k in range(2)] for samples in velocities]
    samples = velocities[0] + velocities[1]
    vector = [median(v[k] for v in samples) for k in range(2)]
    pace = math.hypot(*vector)
    if not max(.001, height * .08) <= pace <= min(1000, height * 4):
        return unavailable('Observed support motion has no plausible walking pace.')
    residual = median(math.dist(v, vector) for v in samples) / pace
    if residual > .3 or any(math.dist(v, vector) / pace > .3 for v in means):
        return unavailable('The support velocities disagree; automatic travel would risk visible foot sliding.')
    return {'version': VERSION, 'status': 'estimated', 'meters_per_cycle': round(pace, 7),
            'direction': [round(v / pace, 9) for v in vector], 'landmarks': names,
            'samples_per_cycle': count, 'stance_coverage': round(union, 4),
            'stance_residual_ratio': round(residual, 4), 'seam_error_m': round(seam, 7),
            'reason': 'Estimated from alternating low support motion; review feet and loop joins. No foot locking or terrain adaptation.'}
