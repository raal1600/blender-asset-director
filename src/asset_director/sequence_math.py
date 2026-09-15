"""Small dependency-free exact-endpoint bridge math; no neural runtime.

A quintic Hermite bridge matches endpoint values and velocities with zero
coordinate acceleration. Quaternion tangents use the SO(3) right Jacobian.
This is an offline endpoint bridge inspired by inertial transition literature,
not a port or claim of equivalence to a proprietary inertialization node.
"""
import math
from .core import require


def add(a, b): return [x + y for x, y in zip(a, b)]
def sub(a, b): return [x - y for x, y in zip(a, b)]
def mul(a, s): return [x * s for x in a]
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def norm(a): return math.sqrt(dot(a, a))
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def unit(q):
    n = norm(q)
    require(math.isfinite(n) and n > 1e-12, 'INVALID_SEQUENCE_POSE', 'Degenerate quaternion')
    return mul(q, 1/n)


def qmul(a, b):
    w, x, y, z = a; v, i, j, k = b
    return [w*v-x*i-y*j-z*k, w*i+x*v+y*k-z*j,
            w*j-x*k+y*v+z*i, w*k+x*j-y*i+z*v]


def inverse(q): return [q[0], -q[1], -q[2], -q[3]]


def qlog(q):
    q = unit(q)
    if q[0] < 0: q = mul(q, -1)
    s = norm(q[1:])
    if s < 1e-10: return mul(q[1:], 2)
    return mul(q[1:], 2*math.atan2(s, max(0, q[0]))/s)


def qexp(v):
    angle = norm(v)
    if angle < 1e-10: return unit([1, *mul(v, .5)])
    return [math.cos(angle/2), *mul(v, math.sin(angle/2)/angle)]


def right_jacobian_inverse(v, omega):
    angle = norm(v)
    c = 1/12 + angle*angle/720 if angle < 1e-4 else 1/(angle*angle)-1/(2*angle*math.tan(angle/2))
    return add(add(omega, mul(cross(v, omega), .5)), mul(cross(v, cross(v, omega)), c))


def hermite(a, b, va, vb, duration, u):
    require(duration > 0 and 0 <= u <= 1, 'INVALID_SEQUENCE_TIME', 'Invalid bridge time')
    result = []
    for x, y, v, w in zip(a, b, va, vb):
        d = y-x; v *= duration; w *= duration
        result.append(x+v*u+(10*d-6*v-4*w)*u**3+(-15*d+8*v+7*w)*u**4+(6*d-3*v-3*w)*u**5)
    return result


def rotation_bridge(a, b, wa, wb, duration, u):
    a, b = unit(a), unit(b)
    if dot(a, b) < 0: b = mul(b, -1)
    delta = qlog(qmul(inverse(a), b))
    # Near-pi shortest-path selection is ambiguous. Require a different join or
    # an explicitly designed intermediate pose instead of inventing a spin.
    require(norm(delta) < math.pi-.005, 'BRIDGE_ROTATION_REVIEW', 'Near-180-degree pose mismatch needs a reviewed intermediate pose')
    tangent = right_jacobian_inverse(delta, wb)
    v = hermite([0, 0, 0], delta, wa, tangent, duration, u)
    return unit(qmul(a, qexp(v)))


def angular_velocity(q, next_q, seconds):
    return mul(qlog(qmul(inverse(unit(q)), unit(next_q))), 1/seconds)


def grid(start, end, step, limit):
    require(all(type(v) in (int, float) and math.isfinite(v) for v in (start, end, step))
            and end > start and step > 0, 'INVALID_SEQUENCE_TIME', 'Invalid sample interval')
    count = math.floor((end-start)/step)
    require(count+2 <= limit+1, 'RESOURCE_LIMIT', 'Sampling exceeds explicit budget')
    eps = max(math.ulp(float(end))*8, 1e-10)
    result = [start+i*step for i in range(count+1) if start+i*step < end-eps] + [end]
    require(len(result) <= limit, 'RESOURCE_LIMIT', 'Sampling exceeds explicit budget')
    return result
