"""Small, animation-name-independent pose/velocity matching helpers. No model."""
import math
from . import sequence_math as sm
from .core import require


def source_frame(start, end, elapsed, phase=0., endpoint=False):
    span = end-start
    value = (elapsed+phase*span) % span
    # Retain the real final pose at an exact cycle end, rather than frame zero.
    if endpoint and elapsed > 0 and min(value, span-value) < 1e-7:
        value = span
    return start+value


def pose_cost(a, b):
    require(a.keys() == b.keys(), 'STITCH_CHANNEL_REVIEW', 'Clips do not cover the same transform owners')
    return sum(sm.norm(sm.qlog(sm.qmul(sm.inverse(sm.unit(a[n]['q'])), sm.unit(b[n]['q']))))**2
               + sm.norm(sm.sub(a[n]['location'], b[n]['location']))**2 for n in a) / max(1, len(a))


def closed(a, b):
    # This is a numerical cycle-closure guard, never loop approval.
    return a.keys() == b.keys() and all(
        sm.norm(sm.sub(a[n]['location'], b[n]['location'])) < 1e-4
        and sm.norm(sm.qlog(sm.qmul(sm.inverse(sm.unit(a[n]['q'])), sm.unit(b[n]['q'])))) < math.radians(3)
        and sm.norm(sm.sub(a[n]['scale'], b[n]['scale'])) < 1e-4 for n in a)


def match_cost(ap, a, b, bn, dt, duration):
    cost = pose_cost(a, b)
    for name in a:
        va = sm.mul(sm.sub(a[name]['location'], ap[name]['location']), 1/dt)
        vb = sm.mul(sm.sub(bn[name]['location'], b[name]['location']), 1/dt)
        wa = sm.angular_velocity(ap[name]['q'], a[name]['q'], dt)
        wb = sm.angular_velocity(b[name]['q'], bn[name]['q'], dt)
        cost += (sm.norm(sm.sub(va, vb))**2 + sm.norm(sm.sub(wa, wb))**2) * (duration*.5)**2 / len(a)
    return cost


def tangents(a, b, ap, bn, dt):
    """Native endpoint derivatives, in scene-frame time and body angular space."""
    result = []
    for before, after in ((ap, a), (b, bn)):
        result.append({name: {
            'location': sm.mul(sm.sub(after[name]['location'], before[name]['location']), 1/dt),
            'angular': sm.angular_velocity(before[name]['q'], after[name]['q'], dt),
            'scale': sm.mul(sm.sub(after[name]['scale'], before[name]['scale']), 1/dt)} for name in a})
    return result


def smooth_keys(curve, endpoint_slopes=None, interval=None, *, continuous=False):
    """Cubic Hermite segments; explicit slopes avoid Blender auto-handle overshoot.

    Interior central differences approximate the densely sampled trajectory.
    Endpoint slopes come from native motion, never the first baked secant.
    Source curves are never passed here.
    """
    keys = [k for k in curve.keyframe_points if interval is None or interval[0]-1e-5 <= k.co[0] <= interval[1]+1e-5]
    if len(keys) < 2:
        return
    clamped=None
    if continuous:
        from .motion_bricks_spline import clamped_key_slopes
        clamped=clamped_key_slopes([k.co[0] for k in keys],[k.co[1] for k in keys],endpoint_slopes)
    for i, key in enumerate(keys):
        previous, following = keys[max(0, i-1)], keys[min(len(keys)-1, i+1)]
        slope = (following.co[1]-previous.co[1])/(following.co[0]-previous.co[0])
        if endpoint_slopes is not None and i in (0, len(keys)-1):
            slope = endpoint_slopes[0 if i == 0 else 1]
        if clamped is not None:slope=clamped[i]
        left = (key.co[0]-previous.co[0])/3 if i else (following.co[0]-key.co[0])/3
        right = (following.co[0]-key.co[0])/3 if i < len(keys)-1 else left
        key.interpolation = 'BEZIER'
        key.handle_left_type = key.handle_right_type = 'FREE'
        key.handle_left = (key.co[0]-left, key.co[1]-slope*left)
        key.handle_right = (key.co[0]+right, key.co[1]+slope*right)


def bridge(a, b, ap, bn, dt, duration, u):
    result = {}
    for name in a:
        va = sm.mul(sm.sub(a[name]['location'], ap[name]['location']), 1/dt)
        vb = sm.mul(sm.sub(bn[name]['location'], b[name]['location']), 1/dt)
        wa = sm.angular_velocity(ap[name]['q'], a[name]['q'], dt)
        wb = sm.angular_velocity(b[name]['q'], bn[name]['q'], dt)
        sa = sm.mul(sm.sub(a[name]['scale'], ap[name]['scale']), 1/dt)
        sb = sm.mul(sm.sub(bn[name]['scale'], b[name]['scale']), 1/dt)
        result[name] = {
            'location': sm.hermite(a[name]['location'], b[name]['location'], va, vb, duration, u),
            'q': sm.rotation_bridge(a[name]['q'], b[name]['q'], wa, wb, duration, u),
            'scale': sm.hermite(a[name]['scale'], b[name]['scale'], sa, sb, duration, u)}
        require(all(math.isfinite(x) for values in result[name].values() for x in values),
                'STITCH_INVALID_POSE', 'Connection produced a non-finite pose')
        require(all(v > 0 for v in result[name]['scale']), 'STITCH_SCALE_REVIEW',
                'This connection crosses a singular scale; use an intermediate clip or Blender')
    return result


def segments(start, end, elapsed, phase):
    """At most three native NLA pieces, preserving phase-shifted cycle duration."""
    span = end-start
    if phase <= 1e-10:
        return [(start, start+min(span, elapsed), max(1., elapsed/span))]
    first = min(elapsed, (1-phase)*span)
    pieces = [(start+phase*span, start+phase*span+first, 1.)]
    remaining = elapsed-first
    full = math.floor((remaining+1e-8)/span)
    if full:
        pieces.append((start, end, float(full)))
    tail = remaining-full*span
    if tail > 1e-7:
        pieces.append((start, start+tail, 1.))
    return pieces
