"""Blender-only mapping for the provider's exact G1 rest geometry.

No arbitrary retargeting is claimed. Bone axes may differ because conversion
uses complete rest matrices; names, hierarchy, rest heads and object ownership
must still match. Provider outputs remain candidates until quality acceptance.
"""
from __future__ import annotations
import math
from .core import DirectorError, require
from .motion_bricks_provider import CONVENTIONS, REQUEST_SCHEMA, validate_result


def _basis():
    from mathutils import Matrix
    return Matrix.Rotation(math.pi / 2, 4, "X")


def validate_rig(rig, skeleton):
    from mathutils import Matrix, Vector
    require(rig.type == "ARMATURE", "MOTION_BRICKS_UNSUPPORTED_RIG", "Select an armature")
    require(max(abs(rig.matrix_world[r][c] - Matrix.Identity(4)[r][c]) for r in range(4) for c in range(4)) < 1e-6,
            "MOTION_BRICKS_ROOT_OWNERSHIP", "The canonical G1 rig must have an identity object transform; apply an explicit verified rig conversion first")
    names = skeleton["joint_names"]
    require(set(rig.data.bones.keys()) == set(names), "MOTION_BRICKS_UNSUPPORTED_RIG", "Expected exactly the loaded G1 model joints")
    basis = _basis()
    for i, name in enumerate(names):
        bone = rig.data.bones[name]; parent = skeleton["parents"][i]
        require((bone.parent.name if bone.parent else None) == (names[parent] if parent >= 0 else None),
                "MOTION_BRICKS_UNSUPPORTED_RIG", f"G1 parent differs for {name}")
        require((bone.head_local - basis @ Vector(skeleton["neutral_joints"][i])).length <= 1e-6,
                "MOTION_BRICKS_REST_POSE", f"G1 rest position differs for {name}; matching names alone are insufficient")
    return rig


def _activate(rig, action):
    rig.animation_data_create(); rig.animation_data.action = action
    slots = list(getattr(action, "slots", []))
    if slots:
        require(len(slots) == 1 and slots[0].target_id_type == "OBJECT",
                "MOTION_BRICKS_ACTION_SLOT", "Canonical G1 provider requires one unambiguous OBJECT action slot")
        rig.animation_data.action_slot = slots[0]


def evaluated_poses(rig, skeleton, times, action=None):
    """Sample evaluated armature matrices, including constraint evaluation."""
    import bpy
    from mathutils import Quaternion, Vector
    validate_rig(rig, skeleton)
    scene = bpy.context.scene; names = skeleton["joint_names"]
    previous_frame = scene.frame_current + scene.frame_subframe
    previous_action = rig.animation_data.action if rig.animation_data else None
    previous_slot = rig.animation_data.action_slot if rig.animation_data and hasattr(rig.animation_data, "action_slot") else None
    basis = _basis().to_3x3(); inverse = basis.inverted(); roots, rotations = [], []
    try:
        if action is not None:
            _activate(rig, action)
        for frame in times:
            scene.frame_set(math.floor(frame), subframe=frame - math.floor(frame))
            bpy.context.view_layer.update(); evaluated = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            globals_ = []
            for name in names:
                pose = evaluated.pose.bones[name].matrix.to_3x3()
                rest = rig.data.bones[name].matrix_local.to_3x3()
                rotation = inverse @ pose @ rest.inverted() @ basis
                gram = rotation.transposed() @ rotation
                require(max(abs(gram[r][c]-(1 if r==c else 0)) for r in range(3) for c in range(3)) <= 1e-5
                        and rotation.determinant() > 0, "MOTION_BRICKS_RIG_SCALE",
                        "Evaluated G1 bone scale/shear/reflection cannot be represented by local quaternions")
                globals_.append(rotation.to_quaternion().normalized())
            root = inverse @ evaluated.pose.bones[names[0]].matrix.translation
            # Reject animated non-root translations instead of discarding them.
            positions = []
            for i, name in enumerate(names):
                parent = skeleton["parents"][i]
                expected = root if parent < 0 else positions[parent] + globals_[parent] @ Vector(
                    [skeleton["neutral_joints"][i][j] - skeleton["neutral_joints"][parent][j] for j in range(3)])
                actual = inverse @ evaluated.pose.bones[name].matrix.translation
                require((expected-actual).length <= 1e-5, "MOTION_BRICKS_JOINT_TRANSLATION",
                        f"Evaluated non-root translation or altered bone length is unsupported: {name}")
                positions.append(expected)
            roots.append(list(root)); local = []
            for i, world in enumerate(globals_):
                parent = skeleton["parents"][i]
                q = globals_[parent].inverted() @ world if parent >= 0 else world
                q.normalize(); local.append([q.x, q.y, q.z, q.w])
            rotations.append(local)
    finally:
        if rig.animation_data:
            rig.animation_data.action = previous_action
            if previous_slot is not None:
                rig.animation_data.action_slot = previous_slot
        scene.frame_set(math.floor(previous_frame), subframe=previous_frame - math.floor(previous_frame))
    return {"roots": roots, "local_xyzw": rotations}


def make_request(rig, skeleton, source_action, target_action, source_start, target_start, frames=40, seed=0):
    import bpy
    scene = bpy.context.scene
    step = (scene.render.fps / scene.render.fps_base) / 30
    return {"schema": REQUEST_SCHEMA, "conventions": dict(CONVENTIONS), "skeleton": skeleton,
            "frames": frames, "seed": seed,
            "source": evaluated_poses(rig, skeleton, [source_start+i*step for i in range(4)], source_action),
            "target": evaluated_poses(rig, skeleton, [target_start+i*step for i in range(4)], target_action)}


def apply_candidate(rig, request, result, *, name="MotionBricks candidate", start_frame=1):
    """Bake a new action on a compatible, unconstrained canonical rig.

    No source Action is rewritten. The caller must accept quality before using
    the candidate in a finished sequence. Duration is (N-1)/30 seconds between
    the first and last sample; N includes both four-frame context regions.
    """
    import bpy
    from mathutils import Matrix, Quaternion, Vector
    validate_result(result, request); skeleton = request["skeleton"]; validate_rig(rig, skeleton)
    require(not any(pb.constraints for pb in rig.pose.bones) and not rig.constraints,
            "MOTION_BRICKS_RIG_CONSTRAINTS", "Bake on an unconstrained verified G1 rig; active constraints would alter the accepted provider poses")
    data = rig.animation_data
    require(not data or (not data.drivers and not any(not t.mute for t in data.nla_tracks)),
            "MOTION_BRICKS_RIG_CONSTRAINTS", "Active drivers or NLA tracks would double-apply candidate motion")
    previous = data.action if data else None
    previous_slot = data.action_slot if data and hasattr(data, "action_slot") else None
    action = bpy.data.actions.new(name); action.use_fake_user = True
    basis = _basis().to_3x3(); inverse = basis.inverted(); names = skeleton["joint_names"]
    step = (bpy.context.scene.render.fps / bpy.context.scene.render.fps_base) / 30
    previous_quaternions = {}; previous_eulers = {}
    try:
        _activate(rig, action)
        for frame, (root, local) in enumerate(zip(result["roots"], result["local_xyzw"])):
            globals_, positions, desired = [], [], []
            for i, xyzw in enumerate(local):
                parent = skeleton["parents"][i]; q = Quaternion((xyzw[3], *xyzw[:3]))
                world = globals_[parent] @ q if parent >= 0 else q; globals_.append(world)
                position = Vector(root) if parent < 0 else positions[parent] + globals_[parent] @ (
                    Vector(skeleton["neutral_joints"][i]) - Vector(skeleton["neutral_joints"][parent]))
                positions.append(position)
                rest_orientation = rig.data.bones[names[i]].matrix_local.to_3x3()
                matrix = (basis @ world.to_matrix() @ inverse @ rest_orientation).to_4x4()
                matrix.translation = basis @ position; desired.append(matrix)
                bone = rig.data.bones[names[i]]; pose = rig.pose.bones[names[i]]
                arguments = {"parent_matrix": desired[parent], "parent_matrix_local": bone.parent.matrix_local} if parent >= 0 else {}
                pose.matrix_basis = bone.convert_local_to_pose(matrix, bone.matrix_local, invert=True, **arguments)
                old = previous_quaternions.get(names[i])
                if pose.rotation_mode == "QUATERNION" and old is not None and old.dot(pose.rotation_quaternion) < 0:
                    pose.rotation_quaternion.negate()
                previous_quaternions[names[i]] = pose.rotation_quaternion.copy()
                rotation_path = "rotation_quaternion" if pose.rotation_mode == "QUATERNION" else (
                    "rotation_axis_angle" if pose.rotation_mode == "AXIS_ANGLE" else "rotation_euler")
                if rotation_path == "rotation_euler":
                    if names[i] in previous_eulers:
                        pose.rotation_euler.make_compatible(previous_eulers[names[i]])
                    previous_eulers[names[i]] = pose.rotation_euler.copy()
                time = start_frame + frame * step
                for property_name in ("location", rotation_path, "scale"):
                    pose.keyframe_insert(property_name, frame=time, group=names[i])
        # Generated frames must not inherit Bezier overshoot between samples.
        if hasattr(action, "layers"):
            curves = [fc for layer in action.layers for strip in layer.strips
                      for bag in strip.channelbags for fc in bag.fcurves]
        else:
            curves = list(action.fcurves)
        for curve in curves:
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"
        action["asset_director_provider"] = "motion-bricks.cpp"
        action["asset_director_provider_mode"] = result["mode"]
        action["asset_director_request_hash"] = result["request_hash"]
        action["asset_director_quality_status"] = "CANDIDATE_REQUIRES_SEAM_AND_CONTACT_VALIDATION"
        action["asset_director_model_revision"] = result["model_revision"]
        return action
    except BaseException:
        rig.animation_data.action = previous
        if previous_slot is not None:
            rig.animation_data.action_slot = previous_slot
        bpy.data.actions.remove(action)
        raise
