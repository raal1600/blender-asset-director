"""Bounded explicit world-Z heading previews, never inferred anatomical facing.

One generated delta Action owns heading and path. Native rotation, static World
placement, source Actions and skin/rest data remain unchanged. This is not IK.
"""
import math
import bpy
from mathutils import Quaternion, Vector
from .core import require
from . import blender_ops as ops, sequence_math


def rotation(obj):
    if obj.rotation_mode == 'QUATERNION':
        return obj.rotation_quaternion.copy()
    if obj.rotation_mode == 'AXIS_ANGLE':
        return Quaternion(Vector(obj.rotation_axis_angle[1:]), obj.rotation_axis_angle[0])
    return obj.rotation_euler.to_quaternion()


def state(obj, saved=None):
    if saved and 'base_delta_rotation' in saved:
        return {k: saved[k] for k in ('base_rotation', 'base_delta_rotation', 'base_rotation_mode')}
    from .native_motion_basis import seed
    clone = obj.copy()
    try:
        basis = seed(clone, obj)
        return {'base_rotation': list(rotation(clone)), 'base_rotation_mode': clone.rotation_mode,
                # Re-converting the restored Euler delta changes float bits on
                # some poses/platforms and invalidates the next saved edit.
                # Retain the exact verified baseline; do not loosen identity.
                'base_delta_rotation': list(basis['defaults']['']['delta_rotation_quaternion'])}
    finally:
        bpy.data.objects.remove(clone, do_unlink=True)


def reason(obj, action, slot):
    from .action_timeline import travel_reason
    if obj.rotation_mode == 'AXIS_ANGLE':
        return 'Native object axis-angle rotation needs Blender heading editing; Director will not change its rotation mode'
    blocker = travel_reason(obj, action, slot)
    if blocker:
        return blocker
    parent = obj.parent.matrix_world @ obj.matrix_parent_inverse if obj.parent else obj.matrix_parent_inverse
    basis = parent.to_3x3()
    lengths = [v.length for v in basis.col]
    if basis.determinant() <= 1e-10 or min(lengths) <= 1e-8 or max(lengths)-min(lengths) > 1e-6*max(lengths):
        return 'Heading needs a static, positive uniformly scaled parent space; prepare this hierarchy in Blender'
    if any(abs(basis.col[i].dot(basis.col[j])) > 1e-6*lengths[i]*lengths[j] for i in range(3) for j in range(i)):
        return 'Sheared parent space needs Blender heading preparation'
    from .native_motion_basis import seed
    clone = obj.copy()
    try:
        seed(clone, obj)
        for curve in ops.curves(action, slot):
            if curve.data_path in {'rotation_euler', 'rotation_quaternion', 'rotation_axis_angle'}:
                expected = getattr(clone, curve.data_path)[curve.array_index]
                if any(abs(k.co[1]-expected) > 1e-5 for k in curve.keyframe_points):
                    return 'This take owns a different native object rotation; use an observed turn take or Blender'
    finally:
        bpy.data.objects.remove(clone, do_unlink=True)
    return None


def delta_quaternion(obj, base, heading_deg):
    parent = obj.parent.matrix_world @ obj.matrix_parent_inverse if obj.parent else obj.matrix_parent_inverse
    # Blender composes object orientation as parent * delta_rotation * native
    # rotation (not native * delta). Conjugate world yaw through the parent only.
    basis = parent.to_quaternion()
    return basis.inverted() @ Quaternion((0, 0, 1), math.radians(heading_deg)) @ basis @ Quaternion(base['base_delta_rotation'])


def set_heading(obj, base, degrees, previous_euler=None):
    require(obj.rotation_mode == base['base_rotation_mode'], 'HEADING_CHANGED', 'Native rotation ownership changed')
    q = delta_quaternion(obj, base, degrees)
    if obj.rotation_mode == 'QUATERNION':
        if q.dot(obj.delta_rotation_quaternion) < 0:
            q.negate()
        obj.delta_rotation_quaternion = q
        return 'delta_rotation_quaternion', None
    order = obj.rotation_mode if obj.rotation_mode != 'AXIS_ANGLE' else 'XYZ'
    obj.delta_rotation_euler = q.to_euler(order, previous_euler or obj.delta_rotation_euler)
    return 'delta_rotation_euler', obj.delta_rotation_euler.copy()


def ease(u):
    u = max(0., min(1., u))
    return u*u*u*(10+u*(-15+6*u))


def heading_at(join, u):
    # Brake, turn while the path is stationary, accelerate. Pose interpolation
    # remains explicitly approximate; feet are not locked to the ground.
    fraction = ease((u-.25)*2) if join.get('mode') == 'turn' else ease(u)
    return join['heading_in_deg'] + join['turn_delta_deg']*fraction


def path_at(join, u):
    """World metre displacement from the beginning of a connection."""
    duration = join['duration_frames']
    va, vb = join['velocity_in'], join['velocity_out']
    zero = [0., 0.]
    if join.get('mode') != 'turn':
        return sequence_math.hermite(zero, join['delta_m'], va, vb, duration, u)
    stop = [v*duration/8 for v in va]
    if u < .25:
        return sequence_math.hermite(zero, stop, va, zero, duration/4, max(0., u*4))
    if u <= .75:
        return stop
    return sequence_math.hermite(stop, join['delta_m'], zero, vb, duration/4, min(1., (u-.75)*4))
