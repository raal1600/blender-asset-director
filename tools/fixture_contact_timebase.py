"""Change only contact timestamps when a fixture copies an Action's timebase.

This is source-FPS normalization in disposable validation inputs, not native
retiming in the application. Distances, vertex identities and provenance remain
unchanged; the caller records original and derived content identities.
"""
import json
import math


def rescale_contacts(properties, source_fps, target_fps):
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
           for v in (source_fps, target_fps)):
        raise ValueError('Fixture contact timebases must be positive finite FPS')
    ratio = target_fps / source_fps
    result = {}
    for key, field in [('bad_root_contact_preparation_v1', 'contacts'),
                       ('bad_contact_intervals_v1', 'intervals')]:
        if key not in properties:
            continue
        raw = properties[key]
        if not isinstance(raw, str):
            raise ValueError('Fixture contacts must retain their serialized metadata')
        value = json.loads(raw)
        if not isinstance(value, dict) or not isinstance(value.get(field), list) or not value[field]:
            raise ValueError('Fixture contact metadata has no reviewed intervals')
        if field == 'intervals' and value.get('version') != 'native-contact-intervals-v1':
            raise ValueError('Unsupported fixture contact annotation version')
        for item in value[field]:
            if not isinstance(item, dict) or any(type(item.get(k)) not in (int, float)
                    or not math.isfinite(item[k]) for k in ('start', 'end')) or item['start'] >= item['end']:
                raise ValueError('Fixture contact intervals must be finite and increasing')
            item['start'] *= ratio
            item['end'] *= ratio
        result[key] = json.dumps(value, sort_keys=True)
    return result
