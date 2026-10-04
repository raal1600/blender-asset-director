"""Blender-only bounded native-slot sampler on a disposable unskinned rig copy."""
import math
import bpy
from . import gait_profile, blender_ops as ops, native_motion_basis
from .core import digest, DirectorError


def inspect(obj, action, slot, take, budget):
    from .action_layer import reason
    refuse = gait_profile.unavailable
    if reason(obj):
        return refuse('This rig needs detailed Blender inspection before automatic pace analysis.')
    if len(obj.data.bones) > 256 or budget[0] < 65:
        return refuse('Automatic gait inspection reached its bounded sampling budget; use Blender for this take.')
    if not 1 <= take['range'][1] - take['range'][0] <= 120:
        return refuse('Automatic pace needs a native cycle between 1 and 120 frame intervals; use Blender or manual calibration for this take.')
    scene = bpy.context.scene
    frame, subframe = scene.frame_current, scene.frame_subframe
    rig = obj.copy(); rig.data = obj.data.copy()
    data = rig.data
    # Keep the actual static parent space: native object channels are authored
    # in it. Unparenting would replay those channels in the wrong coordinates.
    try:
        basis = native_motion_basis.seed(rig, obj)
    except (DirectorError, ValueError, KeyError, TypeError) as error:
        bpy.data.objects.remove(rig, do_unlink=True)
        bpy.data.armatures.remove(data)
        return refuse(str(error))
    rig.hide_viewport = False
    scene.collection.objects.link(rig)
    try:
        ad = rig.animation_data_create(); ad.action = action; ad.use_nla = False
        if slot is not None: ad.action_slot = slot
        scene.frame_set(math.floor(take['range'][0]), subframe=take['range'][0] % 1)
        bpy.context.view_layer.update()
        # Translation must not affect stride or its identity. Multiplying full
        # world points and later subtracting them introduced float cancellation
        # after saved travel, despite identical native keys and World placement.
        world = rig.matrix_world.to_3x3()
        unit = scene.unit_settings.scale_length
        heads = {b.name: world @ b.head_local * unit for b in rig.data.bones if b.use_deform}
        if len(heads) < 3:
            return refuse('Automatic pace needs an observed upright rig with two support limbs.')
        floor = min(p.z for p in heads.values())
        height = max(p.z for p in heads.values()) - floor
        low = {name for name, p in heads.items() if p.z <= floor + height * .2}
        tips = [name for name in sorted(low) if not any(c.name in low for c in rig.data.bones[name].children_recursive)]
        if len(tips) != 2 or not height * .04 <= (heads[tips[0]] - heads[tips[1]]).length <= height * .7:
            return refuse('Two independent low support landmarks could not be identified confidently; use Blender or manual calibration.')
        if (rig.data.bones[tips[0]] in rig.data.bones[tips[1]].parent_recursive
                or rig.data.bones[tips[1]] in rig.data.bones[tips[0]].parent_recursive):
            return refuse('Support landmarks are not independent limbs.')
        budget[0] -= 65
        traces = {name: [] for name in tips}
        for index in range(65):
            f = take['range'][0] + (take['range'][1] - take['range'][0]) * index / 64
            scene.frame_set(math.floor(f), subframe=f - math.floor(f))
            evaluated = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            for name in tips:
                traces[name].append(list(evaluated.matrix_world.to_3x3() @ evaluated.pose.bones[name].head * unit))
        profile = gait_profile.estimate(traces, height)
        profile['binding'] = basis['identity']
        profile['id'] = digest({'version': 'native-gait-calibration-v2', 'take': take['id'],
                                'basis': basis['identity'], 'estimator': gait_profile.VERSION})
        return profile
    finally:
        bpy.data.objects.remove(rig, do_unlink=True)
        bpy.data.armatures.remove(data)
        scene.frame_set(frame, subframe=subframe)
        bpy.context.view_layer.update()
