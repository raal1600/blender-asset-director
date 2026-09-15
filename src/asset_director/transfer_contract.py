"""Blender-free contracts for read-only transfer planning and contact evidence."""
import math
from .core import fields, require, text
from .motion_assets import finite, vector, sha

PLAN_FIELDS = {'target_object', 'source_meters_per_unit', 'target_meters_per_unit',
               'target_fps', 'root_mode', 'facing', 'source_roles', 'target_roles', 'check_count', 'ground_contact', 'start', 'end', 'max_output_intervals', 'max_source_keys'}
CONTACT_FIELDS = {'target_object', 'mesh', 'feet', 'ground_z', 'meters_per_unit',
                  'tolerance_m', 'near_ground_m', 'glide_speed_m_s', 'frames', 'sample'}


def name(value):
    text(value, 160)
    require(value.strip(), 'INVALID_SCHEMA', 'Empty object/bone name')


def names(values, maximum=16):
    require(isinstance(values, list) and 1 <= len(values) <= maximum,
            'INVALID_SCHEMA', 'Provide bounded explicit names')
    for v in values: name(v)
    require(len(set(values)) == len(values), 'INVALID_SCHEMA', 'Duplicate names')


def role_map(value):
    require(isinstance(value, dict) and 1 <= len(value) <= 256, 'MAPPING_REVIEW_REQUIRED', 'Invalid role map')
    for k, v in value.items(): name(k); name(v)
    require(len(set(value.values())) == len(value), 'MAPPING_REVIEW_REQUIRED', 'Roles must be one-to-one')


def checkpoints(options, limit=257):
    require(('frames' in options) != ('sample' in options), 'INVALID_SCHEMA', 'Provide frames OR sample, exactly one')
    if 'frames' in options:
        frames = options['frames']
        require(isinstance(frames, list) and 1 <= len(frames) <= limit, 'RESOURCE_LIMIT', 'Checkpoint budget exceeded')
        for f in frames: finite(f, -100000, 100000)
        require(all(a < b for a, b in zip(frames, frames[1:])), 'INVALID_SCHEMA', 'Checkpoints must strictly increase')
        return list(frames)
    s = options['sample']
    fields(s, {'start', 'end', 'count'}, {'start', 'end', 'count'})
    start, end, count = s['start'], s['end'], s['count']
    finite(start, -100000, 100000); finite(end, -100000, 100000)
    require(type(count) is int and 2 <= count <= limit and end > start,
            'RESOURCE_LIMIT', 'Invalid bounded sampling range/count')
    return [start+(end-start)*i/(count-1) for i in range(count)]


def plan(options):
    fields(options, PLAN_FIELDS, PLAN_FIELDS-{'source_roles', 'target_roles', 'check_count', 'ground_contact', 'start', 'end', 'max_output_intervals', 'max_source_keys'})
    require(('start' in options) == ('end' in options), 'SOURCE_RANGE_REVIEW', 'Provide both start and end for an excerpt')
    if 'start' in options:
        finite(options['start'], -10000, 10000); finite(options['end'], -10000, 10000)
        require(options['end'] > options['start'], 'SOURCE_RANGE_REVIEW', 'Excerpt must increase')
    source_limit = options.get('max_source_keys', 500000)
    require(type(source_limit) is int and 1 <= source_limit <= 1000000, 'RESOURCE_LIMIT',
            'max_source_keys must be an explicit integer in 1..1000000')
    name(options['target_object'])
    for k in ('source_meters_per_unit', 'target_meters_per_unit'): finite(options[k], 1e-6, 1e3)
    finite(options['target_fps'], 1, 120)
    limit = options.get('max_output_intervals', 360)
    require(type(limit) is int and 1 <= limit <= 7200, 'RESOURCE_LIMIT',
            'max_output_intervals must be an explicit integer in 1..7200')
    require(options['root_mode'] in ('preserve_world', 'morphology_scaled'), 'INVALID_PROFILE', 'Declare root displacement policy')
    count = options.get('check_count', 65)
    require(type(count) is int and 2 <= count <= 257, 'RESOURCE_LIMIT', 'Use 2..257 planning checkpoints')
    for k in ('source_roles', 'target_roles'):
        if k in options: role_map(options[k])
    if 'ground_contact' in options:
        from .pose_contract import validate
        validate({'rotation':[1,0,0,0,1,0,0,0,1], 'translation_bone':'proposal-anchor',
                  'translation_scale':1, 'target_origin':[0,0,0], 'ground_contact':options['ground_contact']})
    facing = options['facing']
    require(isinstance(facing, dict), 'FACING_REVIEW_REQUIRED', 'Declare facing evidence')
    if facing.get('mode') == 'anatomical':
        fields(facing, {'mode'}, {'mode'})
    else:
        fields(facing, {'mode', 'source_forward', 'target_forward', 'evidence'},
               {'mode', 'source_forward', 'target_forward', 'evidence'})
        require(facing['mode'] == 'explicit', 'FACING_REVIEW_REQUIRED', 'Unsupported facing mode')
        for k in ('source_forward', 'target_forward'):
            v = vector(facing[k]); require(math.hypot(v[0], v[1]) > 1e-6 and abs(v[2]) < 1e-6,
                                           'FACING_REVIEW_REQUIRED', 'Facing must be nonzero and world-Z horizontal')
        text(facing['evidence'], 2000); require(facing['evidence'].strip(), 'FACING_REVIEW_REQUIRED', 'Explain reviewed facing')


def contact(options):
    fields(options, CONTACT_FIELDS, CONTACT_FIELDS-{'frames', 'sample'})
    name(options['target_object']); name(options['mesh'])
    feet = options['feet']; fields(feet, {'left', 'right'}, {'left', 'right'})
    for group_names in feet.values(): names(group_names)
    require(not set(feet['left']) & set(feet['right']), 'INVALID_GROUND_CONTACT', 'Separate left/right sole groups')
    finite(options['meters_per_unit'], 1e-6, 1e3); finite(options['ground_z'], -1e4, 1e4)
    finite(options['tolerance_m'], 1e-6, .1)
    finite(options['near_ground_m'], options['tolerance_m'], .5)
    finite(options['glide_speed_m_s'], 1e-6, 10)
    checkpoints(options)


def camera_check(options):
    # Mirror the existing camera-check contract earlier; scene facts remain in Blender.
    fields(options, {'subjects','frames','camera','margin','sample','targets','occlusion'}, {'subjects','camera'})
    names(options['subjects'], 128); name(options['camera'])
    require(not ('frames' in options and 'sample' in options), 'INVALID_SCHEMA', 'Use frames OR sample')
    count = 1
    if 'frames' in options:
        f = options['frames']; require(isinstance(f,list) and 1 <= len(f) <= 32, 'RESOURCE_LIMIT', 'Use 1..32 frames')
        require(all(type(x) is int and -100000 <= x <= 100000 for x in f), 'RESOURCE_LIMIT', 'Camera frames must be bounded integers')
        count = len(set(f))
    if 'sample' in options:
        s = options['sample']; fields(s, {'start','end','count'}, {'start','end','count'})
        require(all(type(s[k]) is int for k in s) and -100000 <= s['start'] <= s['end'] <= 100000
                and 1 <= s['count'] <= 32, 'RESOURCE_LIMIT', 'Use 1..32 integer camera samples')
        count = min(s['count'], s['end']-s['start']+1)
    finite(options.get('margin',0), 0, .449999999)
    if 'occlusion' in options: require(type(options['occlusion']) is bool,'INVALID_SCHEMA','occlusion must be boolean')
    require(not options.get('occlusion') or count*len(options['subjects'])*9 <= 400, 'RESOURCE_LIMIT', 'Occlusion ray budget exceeded')
    from .camera_plan import validate_targets
    validate_targets(options.get('targets'))


def alignment(value):
    require(isinstance(value, dict) and 1 <= len(value) <= 256, 'INVALID_ALIGNMENT', 'Provide bounded reference bases')
    for bone, raw in value.items():
        name(bone)
        require(isinstance(raw, list) and len(raw)==16, 'INVALID_ALIGNMENT', 'Reference basis must be 4x4')
        require(all(type(v) in (int,float) and math.isfinite(v) and abs(v)<=1e4 for v in raw),
                'INVALID_ALIGNMENT','Nonfinite or oversized reference basis')
        require(max(abs(raw[12+i]-v) for i,v in enumerate((0,0,0,1)))<1e-5,
                'INVALID_ALIGNMENT','Reference basis must be affine')
        rows=[[raw[r*4+c] for c in range(3)] for r in range(3)]
        require(max(abs(sum(a*b for a,b in zip(rows[i],rows[j]))-(i==j)) for i in range(3) for j in range(3))<1e-4,
                'INVALID_ALIGNMENT','Reference must not stretch or shear bones')
        a,b,c=rows
        det=a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
        require(abs(det-1)<1e-4,'INVALID_ALIGNMENT','Reflected reference bases are unsupported')
