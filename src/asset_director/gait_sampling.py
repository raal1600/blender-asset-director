"""Blender-only bounded native-slot sampler on a disposable unskinned rig copy."""
import math
import bpy
from . import gait_profile, blender_ops as ops
from .core import digest


def inspect(obj, action, slot, take, budget):
    from .action_layer import reason
    refuse = gait_profile.unavailable
    if reason(obj):
        return refuse('This rig needs detailed Blender inspection before automatic pace analysis.')
    if len(obj.data.bones) > 256 or budget[0] < 65:
        return refuse('Automatic gait inspection reached its bounded sampling budget; use Blender for this take.')
    if not 1 <= take['range'][1] - take['range'][0] <= 120:
        return refuse('Automatic pace needs a native cycle between 1 and 120 frame intervals; use Blender or manual calibration for this take.')
    world = obj.matrix_world.copy()
    unit = bpy.context.scene.unit_settings.scale_length
    heads = {b.name: world @ b.head_local * unit for b in obj.data.bones if b.use_deform}
    if len(heads) < 3:
        return refuse('Automatic pace needs an observed upright rig with two support limbs.')
    floor = min(p.z for p in heads.values())
    height = max(p.z for p in heads.values()) - floor
    low = {name for name, p in heads.items() if p.z <= floor + height * .2}
    tips = [name for name in sorted(low) if not any(c.name in low for c in obj.data.bones[name].children_recursive)]
    if len(tips) != 2 or not height * .04 <= (heads[tips[0]] - heads[tips[1]]).length <= height * .7:
        return refuse('Two independent low support landmarks could not be identified confidently; use Blender or manual calibration.')
    if (obj.data.bones[tips[0]] in obj.data.bones[tips[1]].parent_recursive
            or obj.data.bones[tips[1]] in obj.data.bones[tips[0]].parent_recursive):
        return refuse('Support landmarks are not independent limbs.')
    budget[0] -= 65
    scene = bpy.context.scene
    frame, subframe = scene.frame_current, scene.frame_subframe
    rig = obj.copy(); rig.data = obj.data.copy()
    data = rig.data
    # Keep the actual static parent space: native object channels are authored
    # in it. Unparenting would replay those channels in the wrong coordinates.
    rig.animation_data_clear()
    rig.hide_viewport = False
    # Delta travel belongs to the saved timeline, not the native sampled take.
    rig.delta_location = (0, 0, 0)
    scene.collection.objects.link(rig)
    traces = {name: [] for name in tips}
    try:
        ad = rig.animation_data_create(); ad.action = action; ad.use_nla = False
        if slot is not None: ad.action_slot = slot
        for index in range(65):
            f = take['range'][0] + (take['range'][1] - take['range'][0]) * index / 64
            scene.frame_set(math.floor(f), subframe=f - math.floor(f))
            evaluated = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            for name in tips:
                traces[name].append(list(evaluated.matrix_world @ evaluated.pose.bones[name].head * unit))
        profile = gait_profile.estimate(traces, height)
        profile['id'] = digest({'take': take['id'], 'profile': profile,
                                'world_basis': [round(v, 7) for row in world.to_3x3() for v in row],
                                'unit': unit, 'rest': [(b.name, ops.flatten(b.matrix_local)) for b in obj.data.bones]})
        return profile
    finally:
        bpy.data.objects.remove(rig, do_unlink=True)
        bpy.data.armatures.remove(data)
        scene.frame_set(frame, subframe=subframe)
        bpy.context.view_layer.update()
