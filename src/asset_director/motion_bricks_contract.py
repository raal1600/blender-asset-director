"""Portable, versioned restrictions for the pinned offline G1 adapter.

No clip labels, rig-name heuristics, contact truth or physical guarantees live
here. Evaluated inputs and reviewed calibration supply those separate facts.
"""
import math
from .core import require
from . import sequence_math as qm

DOMAIN_VERSION = 'motion-bricks.upright-grounded.v1'
INPUT_SCHEMA = 'asset-director.transition-input.v1'
MODEL_FPS = 30
CONTEXT_FRAMES = 4
OUTPUT_LENGTHS = tuple(range(24, 65, 4))
RETIME_LIMITS = (.85, 1.15)
SAMPLING_MODES = ('argmax', 'gumbel-temperature-1')
# Motion comparisons must ignore filenames, metadata and quaternion sign.
# Below these bounds a candidate is a near duplicate, not useful diversity.
DUPLICATE_LIMITS = {'root_rms_height': 1e-4, 'rotation_rms_degrees': .1}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def duration_plan(seconds):
    require(finite(seconds) and seconds > 0, 'MOTION_BRICKS_DURATION',
            'Choose a positive generated duration; native intervals stay unchanged')
    available = [(n, (n-7)/MODEL_FPS) for n in OUTPUT_LENGTHS]
    valid = [(n, native) for n, native in available
             if RETIME_LIMITS[0]-1e-12 <= seconds/native <= RETIME_LIMITS[1]+1e-12]
    require(valid, 'MOTION_BRICKS_DURATION',
            'Generated duration must fit N=24,28,...,64 at 30 FPS, with bridge-only '
            'retiming 0.85–1.15 (total supported range 0.481667–2.185 seconds)')
    n, native = min(valid, key=lambda item: (abs(item[1]-seconds), item[0]))
    return {'model_frames': n, 'model_fps': MODEL_FPS, 'bridge_indices': [3, n-4],
            'native_duration_seconds': native, 'requested_duration_seconds': seconds,
            'generated_retime_ratio': seconds/native, 'retime_limits': list(RETIME_LIMITS),
            'native_clips_retimed': False}


def context_schedule(interval, source_fps, side, *, elapsed=None):
    """Exact source-frame timestamps, including the selected physical boundary.

    source_fps is the source-frame rate per playback second. No extrapolation,
    looping, nearest-frame substitution or context beyond the selected interval.
    A shortened occupancy is itself an explicit selected endpoint (elapsed).
    """
    require(isinstance(interval, (list, tuple)) and len(interval) == 2
            and all(finite(v) for v in interval) and interval[1] > interval[0]
            and finite(source_fps) and source_fps > 0 and side in ('source', 'target'),
            'MOTION_BRICKS_CONTEXT', 'Provide an increasing native interval and its source FPS')
    length = interval[1]-interval[0]
    if elapsed is None:
        elapsed = length
    require(finite(elapsed) and 0 < elapsed <= length+1e-7, 'MOTION_BRICKS_CONTEXT',
            'Generated transitions require a selected single native interval; split reviewed repeats explicitly')
    offsets = [(i-3 if side == 'source' else i)/MODEL_FPS for i in range(CONTEXT_FRAMES)]
    edge = interval[0]+elapsed if side == 'source' else interval[0]
    frames = [edge+t*source_fps for t in offsets]
    require(frames[0] >= interval[0]-1e-7 and frames[-1] <= interval[0]+elapsed+1e-7,
            'MOTION_BRICKS_CONTEXT',
            'Selected interval lacks four context frames at 30 FPS (0.1 seconds). '
            'Select an explicit longer interval; unavailable frames are never fabricated')
    return {'side': side, 'selected_interval': list(interval), 'selected_end': interval[0]+elapsed,
            'source_fps': source_fps, 'source_frames': frames,
            'seconds_from_stitch': offsets, 'context_horizon_seconds': .1}


def sampling_settings(mode, seed):
    require(mode in SAMPLING_MODES and type(seed) is int and 0 <= seed < 2**32,
            'MOTION_BRICKS_SAMPLING', 'Choose diagnostic argmax or Gumbel temperature 1 with a uint32 seed')
    return {'mode': mode, 'seed': seed, 'argmax': mode == 'argmax',
            'temperature': None if mode == 'argmax' else 1,
            'seed_affects_output': mode != 'argmax', 'duration_selection': 'fixed-mask'}


def motion_difference(first, second, height_m):
    """Compare sampled motion in the same frame/timebase, never metadata.

    Different durations are reported as incomparable here. A/B playback retains
    actual physical time; it must not warp candidates to make metrics agree.
    """
    require(finite(height_m) and height_m > 0, 'MOTION_BRICKS_REFERENCE_HEIGHT',
            'Use a fixed reviewed character height for motion comparisons')
    if len(first['roots']) != len(second['roots']):
        return {'status': 'DIFFERENT_DURATIONS', 'near_duplicate': False}
    require(len(first['roots']) >= 9 and len(first['roots']) == len(first['local_xyzw'])
            and len(second['roots']) == len(second['local_xyzw']),
            'MOTION_BRICKS_COMPARISON', 'Compare complete motion arrays in a common timebase')
    roots = [math.dist(a,b)/height_m for a,b in zip(first['roots'][4:-4], second['roots'][4:-4])]
    angles = []
    for a,b in zip(first['local_xyzw'][4:-4],second['local_xyzw'][4:-4]):
        require(len(a) == len(b) and a, 'MOTION_BRICKS_COMPARISON', 'Comparison skeletons differ')
        for q,r in zip(a,b):
            angles.append(math.degrees(qm.norm(qm.qlog(qm.qmul(
                qm.inverse(qm.unit([q[3],*q[:3]])),qm.unit([r[3],*r[:3]]))))))
    rms = lambda v: math.sqrt(sum(x*x for x in v)/len(v))
    root, angle = rms(roots), rms(angles)
    require(math.isfinite(root) and math.isfinite(angle), 'MOTION_BRICKS_COMPARISON', 'Nonfinite candidate motion')
    return {'status': 'COMPARED_INTERIOR', 'root_rms_height': root,
            'rotation_rms_degrees': angle, 'root_max_m': max(roots)*height_m,
            'rotation_max_degrees': max(angles), 'thresholds': dict(DUPLICATE_LIMITS),
            'near_duplicate': root <= DUPLICATE_LIMITS['root_rms_height']
                and angle <= DUPLICATE_LIMITS['rotation_rms_degrees']}
