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
