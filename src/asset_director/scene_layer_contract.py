"""Portable, bounded Shots/Light transactions over existing native operations."""
import re
from .core import digest, fields, require
from . import camera_plan, look_contract

VERSION = 'scene-layer-v1'
FIELDS = {'version', 'layer', 'audit_sha256', 'operations'}
ALLOWED = {'shots': {'camera-fit', 'camera-plan'},
           'light': {'light-adjust', 'world-adjust', 'look-adjust', 'light-rig'}}


def fingerprint(state):
    # A saved-file copy inventory changes when bytes are saved, not scene meaning.
    # Checkpoint/file identities are enforced separately by the job and launcher.
    scene = {k: v for k, v in state['scene'].items() if k != 'preview_dependencies'}
    return digest(state | {'scene': scene})


def name(value, limit=255):
    require(isinstance(value, str) and value.strip() and len(value.encode('utf-8')) <= limit
            and not any(c in value for c in '\r\n\0'), 'INVALID_SCHEMA', 'Choose an exact, bounded Blender object name')


def subjects(value):
    require(isinstance(value, list) and 1 <= len(value) <= 128 and all(isinstance(x, str) for x in value)
            and len(set(value)) == len(value), 'SUBJECTS_REQUIRED', 'Choose distinct observed geometry')
    for item in value:name(item)


def validate(options, *, inspect=False):
    fields(options, {'layer'} if inspect else FIELDS, {'layer'} if inspect else FIELDS)
    require(isinstance(options['layer'], str) and options['layer'] in ALLOWED, 'INVALID_SCHEMA', 'Choose Shots or Light')
    if inspect:return options
    require(options['version'] == VERSION and isinstance(options['audit_sha256'], str)
            and re.fullmatch('[a-f0-9]{64}', options['audit_sha256']), 'INVALID_SCHEMA', 'Inspect the exact saved scene first')
    operations = options['operations']
    require(isinstance(operations, list) and 1 <= len(operations) <= (1 if options['layer'] == 'shots' else 4),
            'RESOURCE_LIMIT', 'Save one camera operation or up to four distinct lighting operations')
    seen = set()
    for item in operations:
        fields(item, {'operation', 'options', 'name'}, {'operation', 'options'})
        op, args = item['operation'], item['options']
        require(isinstance(op, str) and op in ALLOWED[options['layer']] and op not in seen,
                'INVALID_SCHEMA', 'Unsupported or duplicate layer operation')
        seen.add(op)
        require('name' not in item or op == 'camera-fit', 'INVALID_SCHEMA', 'Only a fitted camera uses this name field')
        if op == 'camera-fit':
            name(item.get('name'), 63)
            fields(args, {'subjects', 'frames', 'direction', 'lens_mm', 'sensor_width_mm', 'margin', 'projection'},
                   {'subjects', 'frames', 'direction', 'lens_mm'})
            subjects(args['subjects']);camera_plan.triple(args['direction'])
            require(sum(v*v for v in args['direction']) > 1e-18, 'INVALID_SCHEMA', 'Choose a nonzero camera direction')
            camera_plan.number(args['lens_mm'], low=1, high=1000)
            camera_plan.number(args.get('sensor_width_mm', 36), low=1, high=100)
            camera_plan.number(args.get('margin', .1), low=0, high=.4499999)
            require(args.get('projection', 'PERSP') in {'PERSP', 'ORTHO'}, 'INVALID_SCHEMA', 'Unsupported camera projection')
            require(isinstance(args['frames'], list) and 1 <= len(args['frames']) <= 32 and
                    all(type(f) is int and -100000 <= f <= 100000 for f in args['frames']),
                    'RESOURCE_LIMIT', 'Choose up to 32 observed frames')
        elif op == 'camera-plan':
            plan = camera_plan.validate(args);subjects(plan['subjects'])
            require('fps' not in args and 'frame_range' not in args and plan['existing_animation'] == 'preserve',
                    'INVALID_SCHEMA', 'Shots preserves Action timebase and prior camera animation')
            name(plan['camera'], 255) if plan['mode'] == 'adapt' else name(plan['name'], 63)
        elif op == 'light-adjust':look_contract.validate_light_adjust(args)
        elif op == 'world-adjust':look_contract.validate_world_adjust(args)
        elif op == 'look-adjust':look_contract.validate_look_adjust(args)
        elif op == 'light-rig':
            fields(args, {'subjects', 'lights'}, {'subjects', 'lights'});subjects(args['subjects'])
            require(isinstance(args['lights'], list) and 1 <= len(args['lights']) <= 8, 'RESOURCE_LIMIT', 'Create one to eight explicit lights')
            for light in args['lights']:
                fields(light, {'type', 'energy', 'offset', 'color', 'size_ratio'}, {'type', 'energy', 'offset', 'color'})
                require(light['type'] in look_contract.LIGHT_TYPES, 'INVALID_SCHEMA', 'Unsupported light type')
                look_contract.finite(light['energy'], low=0, high=1e6)
                look_contract.vector3(light['offset'], low=-1000, high=1000)
                require(sum(v*v for v in light['offset']) > 1e-12, 'INVALID_SCHEMA', 'Choose a nonzero light offset')
                look_contract.vector3(light['color'], low=0, high=1)
                look_contract.finite(light.get('size_ratio', 1), low=1e-9, high=100)
    return options
