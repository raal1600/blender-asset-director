"""Portable identity of one saved named-shot inspection, not a camera edit."""
import re
from .core import fields, require

PROFILES = {'shot-framing-v1', 'look-inspection-v1'}


def validate(value):
    keys = {'version', 'id', 'revision', 'name', 'camera', 'start', 'end'}
    fields(value, keys, keys)
    require(value['version'] == 'shot-view-v1' and isinstance(value['id'], str)
            and re.fullmatch(r'shot_[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', value['id'])
            and type(value['revision']) is int and value['revision'] >= 1,
            'INVALID_PREVIEW', 'Invalid saved shot identity')
    for key, maximum in [('name', 100), ('camera', 255)]:
        require(isinstance(value[key], str) and 0 < len(value[key].strip()) <= maximum
                and not any(c in value[key] for c in '\r\n\0'), 'INVALID_PREVIEW', 'Invalid saved shot name/camera')
    require(type(value['start']) is int and type(value['end']) is int
            and -100000 <= value['start'] <= value['end'] <= 100000
            and value['end'] - value['start'] < 360,
            'RESOURCE_LIMIT', 'A shot preview contains 1..360 ordered frames')
    return value
