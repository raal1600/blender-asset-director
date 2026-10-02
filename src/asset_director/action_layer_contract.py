"""Portable saved-scene Action commands. No source acquisition or retargeting."""
import re
from .core import fields, require
from .motion_timing import number

VERSION = 'action-layer-v1'
FIELDS = {'version', 'audit_sha256', 'changes', 'frame_range'}


def validate(value):
    fields(value, FIELDS, {'version', 'audit_sha256', 'changes'})
    require(value['version'] == VERSION and isinstance(value['audit_sha256'], str)
            and re.fullmatch(r'[0-9a-f]{64}', value['audit_sha256']), 'INVALID_ACTION', 'Inspect the exact saved Action state first')
    changes = value['changes']
    require(isinstance(changes, list) and 1 <= len(changes) <= 32, 'RESOURCE_LIMIT', 'Choose one to 32 observed performers')
    seen = set()
    for change in changes:
        fields(change, {'performer', 'mode', 'take_id', 'start', 'speed', 'frame', 'clips'}, {'performer', 'mode'})
        name = change['performer']
        require(isinstance(name, str) and 0 < len(name) <= 255 and name not in seen,
                'INVALID_ACTION', 'Choose distinct observed performers')
        seen.add(name)
        if change['mode'] == 'timeline':
            from .action_timeline_contract import validate as validate_timeline
            validate_timeline(change)
        elif change['mode'] == 'clip':
            require(set(change) == {'performer', 'mode', 'take_id', 'start', 'speed'}
                    and isinstance(change['take_id'], str) and re.fullmatch(r'take_[0-9a-f]{64}', change['take_id']),
                    'INVALID_ACTION', 'Choose an observed native take; no guessed action or slot')
            require(type(change['start']) is int and -100000 <= change['start'] <= 100000
                    and number(change['speed'], .1, 4), 'INVALID_TIMING', 'Use an explicit start and playback speed from 0.1 to 4')
        else:
            require(change['mode'] == 'hold' and set(change) == {'performer', 'mode', 'frame'},
                    'INVALID_ACTION', 'Choose native motion or hold an observed pose')
            require(type(change['frame']) is int and -100000 <= change['frame'] <= 100000,
                    'INVALID_TIMING', 'Choose an explicit integer pose frame')
    require(not any(c['mode'] == 'timeline' for c in changes) or all(c['mode'] == 'timeline' for c in changes),
            'INVALID_TIMELINE', 'Save timeline changes separately from legacy clip/hold changes')
    if 'frame_range' in value:
        interval = value['frame_range']
        require(isinstance(interval, list) and len(interval) == 2 and all(type(f) is int for f in interval)
                and -100000 <= interval[0] <= interval[1] <= 100000 and interval[1] - interval[0] <= 3600,
                'INVALID_TIMING', 'Scene playback range must be bounded to 3600 intervals')
    return value
