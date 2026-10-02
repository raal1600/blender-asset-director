"""Bounded, explicit native clips and planar travel. No inferred gait speed."""
import math
import re
from .core import fields, require
from .motion_timing import number

VERSION = 'action-timeline-v1'


def validate(change):
    fields(change, {'performer', 'mode', 'clips'}, {'performer', 'mode', 'clips'})
    clips = change['clips']
    require(change['mode'] == 'timeline' and isinstance(clips, list) and len(clips) <= 64,
            'INVALID_TIMELINE', 'Use at most 64 clips per performer')
    seen, end = set(), -100001
    for clip in clips:
        fields(clip, {'id', 'take_id', 'start', 'frames', 'speed', 'repeat_reviewed', 'travel'},
               {'id', 'take_id', 'start', 'frames', 'speed', 'repeat_reviewed', 'travel'})
        require(isinstance(clip['id'], str) and re.fullmatch(r'clip_[a-zA-Z0-9_-]{1,64}', clip['id'])
                and clip['id'] not in seen, 'INVALID_TIMELINE', 'Clips need distinct stable identities')
        seen.add(clip['id'])
        require(isinstance(clip['take_id'], str) and re.fullmatch(r'take_[0-9a-f]{64}', clip['take_id']),
                'INVALID_TIMELINE', 'Choose an observed native take')
        require(type(clip['start']) is int and -100000 <= clip['start'] <= 100000
                and type(clip['frames']) is int and 2 <= clip['frames'] <= 3601
                and number(clip['speed'], .1, 4) and type(clip['repeat_reviewed']) is bool,
                'INVALID_TIMING', 'Use bounded integer frames and speed from 0.1 to 4')
        require(clip['start'] > end, 'TIMELINE_OVERLAP', 'Clips on one performer cannot overlap; move or shorten the clip')
        end = clip['start'] + clip['frames'] - 1
        require(end <= 100000, 'INVALID_TIMING', 'Clip exceeds the frame limit')
        travel = clip['travel']
        if travel is not None:
            fields(travel, {'delta_m', 'meters_per_cycle'}, {'delta_m', 'meters_per_cycle'})
            require(isinstance(travel['delta_m'], list) and len(travel['delta_m']) == 2
                    and all(number(v, -10000, 10000) for v in travel['delta_m'])
                    and 0 < math.hypot(*travel['delta_m']) <= 10000
                    and number(travel['meters_per_cycle'], .001, 1000),
                    'INVALID_TRAVEL', 'Set a planar distance in metres and an explicit travel pace per cycle')
    if clips:
        require(end - clips[0]['start'] <= 3600, 'RESOURCE_LIMIT', 'Timeline exceeds 3600 intervals')
    return change


def timing(clip, take):
    """Integer occupancy, fractional native sampling, visible repeat/trim."""
    span = take['range'][1] - take['range'][0]
    require(number(span, 1e-6, 100000), 'INVALID_TIMING', 'Take has no usable duration')
    cycles = (clip['frames'] - 1) * clip['speed'] / span
    travel = clip['travel']
    if travel:
        cycles = math.hypot(*travel['delta_m']) / travel['meters_per_cycle']
        expected = math.ceil(cycles * span / clip['speed'] - 1e-9) + 1
        require(clip['frames'] == expected, 'INVALID_TRAVEL', 'Distance, pace and occupied frames disagree')
    require(.001 <= cycles <= 100, 'RESOURCE_LIMIT', 'Keep each clip within 100 cycles')
    # Integer presentation rounding is endpoint hold, never an implicit loop.
    if not travel and 1 < cycles <= 1 + clip['speed'] / span + 1e-9:
        cycles = 1.0
    require(cycles <= 1 + 1e-9 or clip['repeat_reviewed'], 'LOOP_REVIEW_REQUIRED',
            'Review this take as a repeatable cycle before repeating it')
    return {'cycles': cycles, 'end': clip['start'] + clip['frames'] - 1,
            'native_end': clip['start'] + cycles * span / clip['speed']}
