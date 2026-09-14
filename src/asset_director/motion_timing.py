"""Portable timing contracts: seconds, frame coordinates and playback speed differ."""
import math
from .core import fields, require


def number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def bake_samples(start, end, source_fps, target_fps):
    require(number(start, -10000, 10000) and number(end, -10000, 10000) and end > start,
            'INVALID_TIMING', 'Source frame range must be finite and increasing')
    require(number(source_fps, 1, 240) and number(target_fps, 1, 120),
            'INVALID_TIMING', 'Unsupported source/target frame rate')
    span = (end-start) * target_fps / source_fps
    require(span <= 360, 'RESOURCE_LIMIT', 'At most 360 output-frame intervals')
    if abs(span-round(span)) < 1e-8:
        span = float(round(span))
    # Preserve the true endpoint; rounding duration used to truncate or stretch it.
    result = [(float(i+1), start+i*source_fps/target_fps) for i in range(math.floor(span)+1)]
    if abs(span-round(span)) < 1e-8:
        result[-1] = (float(round(span)+1), end)
    else:
        result.append((1+span, end))
    require(2 <= len(result) <= 361, 'RESOURCE_LIMIT', 'Invalid bounded bake sample count')
    return result


def validate_assembly(options):
    fields(options, {'target_object', 'clips', 'fps', 'controller_speed', 'direction', 'terrain_object', 'travel_frames'})
    clips = options.get('clips')
    require(isinstance(clips, list) and 1 <= len(clips) <= 4, 'INVALID_SEQUENCE', 'Specify one to four clips')
    if 'fps' in options:
        require(number(options['fps'], 1, 120), 'INVALID_TIMING', 'Invalid sequence FPS')
    for clip in clips:
        fields(clip, {'action', 'slot', 'start', 'source_fps', 'playback_speed', 'blend_in', 'repeat'}, {'action', 'start'})
        require(isinstance(clip['action'], str) and clip['action'].strip(), 'INVALID_SEQUENCE', 'Name the baked action')
        require(type(clip['start']) is int and 1 <= clip['start'] <= 360,
                'INVALID_TIMING', 'Clip start must be an integer in 1..360')
        require(number(clip.get('playback_speed', 1), .1, 4), 'INVALID_TIMING', 'playback_speed must be 0.1..4; 1 is original speed')
        require(number(clip.get('blend_in', 0), 0, 180), 'INVALID_TIMING', 'Invalid blend-in duration')
        require(type(clip.get('repeat', 1)) is int and 1 <= clip.get('repeat', 1) <= 8,
                'INVALID_SEQUENCE', 'Repeat must be 1..8 whole cycles')
        if 'source_fps' in clip:
            require(number(clip['source_fps'], 1, 240), 'INVALID_TIMING', 'Invalid source FPS')


def strip_scale(source_fps, target_fps, playback_speed=1):
    require(number(source_fps, 1, 240) and number(target_fps, 1, 120) and number(playback_speed, .1, 4),
            'INVALID_TIMING', 'Invalid rate or playback speed')
    return target_fps / (source_fps * playback_speed)


def retained_range(strips):
    """Only retain integer frames actually covered by an evaluated strip."""
    require(strips and all(number(s['start'], 1, 361) and number(s['end'], 1, 361)
                          and s['end'] > s['start'] for s in strips),
            'RESOURCE_LIMIT', 'Sequence exceeds its 361-frame bound or has an invalid strip')
    first = math.ceil(min(s['start'] for s in strips))
    last = math.floor(max(s['end'] for s in strips))
    require(last > first, 'INVALID_TIMING', 'Need at least two retained integer frames')
    require(all(any(s['start'] <= f <= s['end'] for s in strips) for f in range(first, last+1)),
            'SEQUENCE_GAP_REVIEW', 'An uncovered integer frame would expose the rest pose; resolve the gap explicitly')
    return first, last


def horizontal_span(samples):
    """Hips can travel under a stationary root; check both, including out-and-back."""
    return max((max(s[role][axis] for s in samples)-min(s[role][axis] for s in samples)
                for role in ('root', 'hips') if all(role in s for s in samples) for axis in (0, 1)), default=0)


def capture_times(duration_seconds, sample_fps, max_samples=10000):
    """Bounded canonical seconds, including the exact endpoint only once.

    A floating product such as (31/30)*30 can lie just above an integer.
    ceil(product) followed by an appended endpoint would then duplicate the
    final timestamp. Discard only ULP-near endpoint grid values and append the
    supplied duration, without rounding the capture's duration or changing FPS.
    """
    require(number(duration_seconds, 1e-7, 600) and number(sample_fps, 1, 240),
            'INVALID_TIMING', 'Invalid canonical duration or sampling rate')
    require(type(max_samples) is int and 2 <= max_samples <= 10000,
            'RESOURCE_LIMIT', 'Canonical sample bound must be 2..10000')
    intervals = math.floor(duration_seconds * sample_fps)
    require(intervals <= max_samples, 'RESOURCE_LIMIT', 'Export sample budget exceeded')
    tolerance = 8 * max(math.ulp(float(duration_seconds)), math.ulp(1.0 / sample_fps))
    times = [i / sample_fps for i in range(intervals + 1)
             if i / sample_fps < duration_seconds - tolerance]
    times.append(float(duration_seconds))
    require(2 <= len(times) <= max_samples and times[0] == 0.0
            and all(a < b for a, b in zip(times, times[1:])),
            'RESOURCE_LIMIT', 'Invalid bounded canonical sample count')
    return times
