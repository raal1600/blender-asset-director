"""Local seam residuals for real generated motion, confined to edge windows.

The model's interior is retained exactly. Residuals match source values and
body-angular velocities, without stretching or crossfading either native clip.
"""
from . import sequence_math as sm
from .core import require


def rotate(q, v):
    return sm.qmul(sm.qmul(q, [0., *v]), sm.inverse(q))[1:]


def rotation_residual(generated, native, generated_velocity, native_velocity):
    """Return log residual and its derivative for q_generated * exp(residual)."""
    error = sm.qlog(sm.qmul(sm.inverse(sm.unit(generated)), sm.unit(native)))
    transported = rotate(sm.inverse(sm.qexp(error)), generated_velocity)
    tangent = sm.right_jacobian_inverse(error, sm.sub(native_velocity, transported))
    return error, tangent


def edge_residual(value, tangent, time, duration, window, side):
    require(0 < window <= duration / 2 and 0 <= time <= duration and side in (0, 1),
            'MOTION_BRICKS_SEAM_WINDOW', 'Residual windows must fit inside the generated interval')
    zero = [0.] * len(value)
    if side == 0:
        return sm.hermite(value, zero, tangent, zero, window, time/window) if time < window else zero
    return sm.hermite(zero, value, zero, tangent, window, (time-duration+window)/window) if time > duration-window else zero


def correct_rotation(generated, residuals, time, duration, window):
    result = sm.unit(generated)
    for side, (value, tangent) in enumerate(residuals):
        result = sm.qmul(result, sm.qexp(edge_residual(value, tangent, time, duration, window, side)))
    return sm.unit(result)


def ground_clearance(value, reference_height):
    """Suppress small model floor-height noise, with C2 release into a lift.

    This is a disclosed geometric cleanup heuristic, not a contact annotation.
    The reference is the reviewed pelvis/ground height in metres.
    """
    import math
    require(all(type(v) in (float,int) and math.isfinite(v) for v in (value,reference_height)) and reference_height>0,
            'MOTION_BRICKS_GROUND', 'Ground clearance requires finite metres and positive reference height')
    low,high=.02*reference_height,.05*reference_height
    if value<=low:return 0.
    if value>=high:return value
    u=(value-low)/(high-low)
    return value*u*u*u*(10+u*(-15+6*u))
