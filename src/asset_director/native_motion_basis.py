"""Exact native defaults, separate from generated timeline pose/path channels.

Keyed components are replayed by the native Action. Unkeyed components are
preserved, not replaced by an invented rest pose. Managed saved defaults may be
reused only while native keys, rest, units, parent space and static defaults match.
"""
import copy
import json
import bpy
from mathutils import Quaternion
from . import blender_ops as ops
from .core import digest, require

VERSION = 'native-motion-basis-v1'
MAX_TIMELINE_JSON_BYTES = 2 * 1024 * 1024


def _timeline(obj):
    raw = obj.get('bad_action_timeline_v1')
    if raw is None:
        return {}
    require(isinstance(raw, str) and len(raw) <= MAX_TIMELINE_JSON_BYTES
            and len(raw.encode('utf-8')) <= MAX_TIMELINE_JSON_BYTES,
            'NATIVE_BASIS_CHANGED', 'Invalid or oversized saved native defaults')
    try:
        result = json.loads(raw)
    except (ValueError, TypeError) as error:
        raise ValueError('Invalid saved native defaults') from error
    require(isinstance(result, dict), 'NATIVE_BASIS_CHANGED', 'Invalid saved native defaults')
    return result


def _rotation(owner):
    return ('rotation_quaternion' if owner.rotation_mode == 'QUATERNION'
            else 'rotation_axis_angle' if owner.rotation_mode == 'AXIS_ANGLE' else 'rotation_euler')


def _owners(obj):
    return {'': obj, **({p.name: p for p in obj.pose.bones} if obj.type == 'ARMATURE' else {})}


def _defaults(obj, timeline):
    result = {name: {'rotation_mode': owner.rotation_mode, **{
        prop: list(getattr(owner, prop)) for prop in ('location', _rotation(owner), 'scale')}}
        for name, owner in _owners(obj).items()}
    # Generated heading is a delta transform; native object rotation is never
    # inferred from a travel vector. Preserve the explicitly recorded base delta.
    result['']['delta_location'] = list(timeline.get('base_delta', obj.delta_location))
    q = timeline.get('base_delta_rotation')
    if q is None:
        q = list(obj.delta_rotation_quaternion if obj.rotation_mode == 'QUATERNION'
                 else obj.delta_rotation_euler.to_quaternion())
    result['']['delta_rotation_quaternion'] = list(q)
    result['']['delta_scale'] = list(obj.delta_scale)
    return result


def _observed(obj):
    from .action_layer import bindings, channels, slot_id
    from .action_timeline import is_generated
    from .motion_stitch import channel_spec
    masks, sources = {}, []
    for action, slot in bindings(obj):
        if is_generated(action) or not ops.curves(action, slot):
            continue
        # Use the same transform-only eligibility as native connections. A
        # procedural channel is not silently interpreted as a stable default.
        for owner, fields in channel_spec(obj, action, slot).items():
            masks.setdefault(owner, set()).update(fields)
        source = {'action': action.name, 'slot': slot_id(slot),
                  'channels': digest(channels(action, slot)), 'range': list(ops.action_range(action, slot))}
        if action.get('bad_contact_intervals_v1') is not None:
            source['contact_annotations_sha256'] = digest(action['bad_contact_intervals_v1'])
        sources.append(source)
    parent = obj.parent.matrix_world @ obj.matrix_parent_inverse if obj.parent else obj.matrix_parent_inverse
    inputs = {'unit': bpy.context.scene.unit_settings.scale_length,
              'parent': obj.parent.name if obj.parent else None,
              'parent_matrix': [float(v) for row in parent for v in row],
              'armature_pose_position': obj.data.pose_position if obj.type == 'ARMATURE' else None,
              'sources': sorted(sources, key=lambda r: (r['action'], r['slot'] or '')),
              'rest': [{'name': b.name, 'parent': b.parent.name if b.parent else None,
                        'matrix': [float(v) for row in b.matrix_local for v in row], 'deform': b.use_deform,
                        'inheritance': {key: getattr(b, key, None) for key in (
                            'inherit_scale', 'use_inherit_rotation', 'use_local_location', 'use_connect',
                            'use_relative_parent')}}
                       for b in obj.data.bones] if obj.type == 'ARMATURE' else []}
    if obj.get('bad_contact_rig_v1') is not None:
        inputs['contact_rig_sha256'] = digest(obj['bad_contact_rig_v1'])
    return inputs, masks


def _static(defaults, masks):
    result = copy.deepcopy(defaults)
    for name, fields in masks.items():
        for prop, index in fields:
            if prop in result[name]:
                result[name][prop][index] = None
    return result


def capture(obj):
    """Read/verify the native baseline. Never mutate the real performer."""
    timeline = _timeline(obj)
    inputs, masks = _observed(obj)
    defaults = _defaults(obj, timeline)
    static = _static(defaults, masks)
    identity = digest({'version': VERSION, 'inputs': inputs, 'static': static})
    saved = timeline.get('native_basis')
    if saved is not None:
        require(isinstance(saved, dict) and set(saved) == {'version', 'identity', 'inputs', 'defaults', 'static'}
                and saved['version'] == VERSION and saved['inputs'] == inputs and saved['static'] == static
                and saved['identity'] == identity and _static(saved['defaults'], masks) == static,
                'NATIVE_BASIS_CHANGED', 'Native source, rest, placement, units or unkeyed pose changed; inspect this motion in Blender')
        return copy.deepcopy(saved)
    return {'version': VERSION, 'identity': identity, 'inputs': inputs, 'defaults': defaults, 'static': static}


def seed(clone, obj):
    """Restore a disposable clone to the verified, non-generated native basis."""
    basis = capture(obj)
    clone.animation_data_clear()
    restore(clone, basis)
    return basis


def restore(clone, basis):
    """Replay an already verified baseline during bounded disposable sampling."""
    owners = _owners(clone)
    for name, fields in basis['defaults'].items():
        owner = owners[name]
        owner.rotation_mode = fields['rotation_mode']
        for prop, values in fields.items():
            if prop not in {'rotation_mode', 'delta_rotation_quaternion'}:
                setattr(owner, prop, values)
        if name == '':
            q = Quaternion(fields['delta_rotation_quaternion'])
            if owner.rotation_mode == 'QUATERNION':
                owner.delta_rotation_quaternion = q
            else:
                owner.delta_rotation_euler = q.to_euler(owner.rotation_mode if owner.rotation_mode != 'AXIS_ANGLE' else 'XYZ')
    return clone
