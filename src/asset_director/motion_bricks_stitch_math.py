"""Local seam residuals for real generated motion, confined to edge windows.

The model's interior is retained exactly. Residuals match source values and
body-angular velocities, without stretching or crossfading either native clip.
"""
from . import sequence_math as sm
from .core import require


def rotate(q, v):
    return sm.qmul(sm.qmul(q, [0., *v]), sm.inverse(q))[1:]


def boundary_estimate(values, seconds, side):
    """Cubic one-sided value/derivative at the common boundary (not at h).

    Four samples at distances h,2h,3h,4h on one side. Quaternion callers
    supply rotation logs in the same reference frame for both sides.
    """
    require(len(values)==4 and seconds>0 and side in ('left','right'),
            'MOTION_BRICKS_DERIVATIVE','Boundary derivatives require four timed samples on one side')
    value=[sum(w*v[i] for w,v in zip((4,-6,4,-1),values)) for i in range(len(values[0]))]
    sign=1 if side=='left' else -1
    derivative=[sign*sum(w*v[i] for w,v in zip((13/3,-19/2,7,-11/6),values))/seconds for i in range(len(values[0]))]
    return value,derivative


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


def smooth_rotations(samples, seconds, *, sigma_seconds=.04, maximum_degrees=15.):
    """Bounded local SO(3) filtering of generated samples before seam fitting.

    The 40 ms Gaussian kernel removes discrete prediction/IK velocity steps.
    This is deterministic processing, not inference or a change of playback
    time. Native samples and timing are never passed to this filter.
    """
    import math
    import copy
    require(len(samples)>2 and seconds>0, 'MOTION_BRICKS_FILTER', 'Generated smoothing needs timed samples')
    step=seconds/(len(samples)-1);radius=math.ceil(3*sigma_seconds/step)
    output=copy.deepcopy(samples);largest=0.;squares=[]
    for i,(_,pose) in enumerate(samples):
        for name,value in pose.items():
            reference=sm.unit(value['q']);total=0.;offset=[0.,0.,0.]
            for j in range(max(0,i-radius),min(len(samples),i+radius+1)):
                weight=math.exp(-.5*((j-i)*step/sigma_seconds)**2)
                delta=sm.qlog(sm.qmul(sm.inverse(reference),sm.unit(samples[j][1][name]['q'])))
                offset=sm.add(offset,sm.mul(delta,weight));total+=weight
            offset=sm.mul(offset,1/total);degrees=math.degrees(sm.norm(offset))
            largest=max(largest,degrees);squares.append(degrees*degrees)
            output[i][1][name]['q']=sm.unit(sm.qmul(reference,sm.qexp(offset)))
    require(largest<=maximum_degrees,'MOTION_BRICKS_EXCESSIVE_FILTER',
            'Generated motion needs more than 15 degrees of smoothing; choose another duration or boundary')
    return output,{'method':'generated-only-SO3-gaussian-v1','sigma_seconds':sigma_seconds,
                   'radius_seconds':radius*step,'max_change_deg':largest,
                   'rms_change_deg':math.sqrt(sum(squares)/len(squares)),
                   'limit_deg':maximum_degrees,'timing_changed':False}
