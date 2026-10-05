"""Evaluated quarter-frame preview sampling without changing native Actions.

Blender's time remapping evaluates frame 4*f at native frame f. Raising export
FPS by the same factor preserves seconds. Only the disposable preview worker's
scene settings change, and all settings are restored on every exit path.
"""
from contextlib import contextmanager
from math import gcd
import bpy
from .core import require


def subdivisions(scene):
    from .action_timeline import PROPERTY, load
    return 4 if any(obj.get(PROPERTY) and load(obj).get('connections') for obj in scene.objects) else 1


@contextmanager
def evaluated_sampling(scene, factor):
    if factor == 1:
        yield
        return
    require(bpy.app.background and scene.get('asset_director_preview_only') is True,
            'PREVIEW_ONLY', 'Subframe sampling requires an isolated preview worker')
    r=scene.render
    old=(scene.frame_start,scene.frame_end,scene.frame_current,scene.frame_subframe,
         r.fps,r.fps_base,r.frame_map_old,r.frame_map_new)
    divisor=gcd(r.frame_map_old,r.frame_map_new*factor)
    numerator,denominator=r.frame_map_old//divisor,r.frame_map_new*factor//divisor
    require(1<=numerator<=900 and 1<=denominator<=900 and r.fps*factor<=32767,
            'VIEWER_UNSUPPORTED', 'Scene time remapping exceeds exact preview sampling limits')
    try:
        r.frame_map_old=numerator;r.frame_map_new=denominator;r.fps=old[4]*factor
        scene.frame_end=max(old[1],old[1]*factor)
        scene.frame_start=old[0]*factor;scene.frame_end=old[1]*factor
        require((scene.frame_start,scene.frame_end,r.fps,r.frame_map_old,r.frame_map_new)==
                (old[0]*factor,old[1]*factor,old[4]*factor,numerator,denominator),
                'VIEWER_UNSUPPORTED','Blender clamped the exact subframe preview timebase')
        yield
    finally:
        scene.frame_start=min(old[0],scene.frame_start)
        scene.frame_end=old[1];scene.frame_start=old[0]
        r.fps=old[4];r.fps_base=old[5];r.frame_map_old=old[6];r.frame_map_new=old[7]
        scene.frame_set(old[2],subframe=old[3])
