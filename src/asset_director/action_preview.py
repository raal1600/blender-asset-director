"""One saved scene/timebase for Action inspection, never independent take guesses."""
from contextlib import contextmanager
import json
import struct
import bpy
from .core import require
from .world_placement import widgets


@contextmanager
def hide_helpers(enabled):
    if not enabled:
        yield
        return
    require(bpy.app.background and bpy.context.scene.get('asset_director_preview_only') is True,
            'PREVIEW_ONLY', 'Action presentation needs a separate preview worker')
    helpers = widgets(bpy.context.scene)
    require(not any(o.type == 'MESH' and (o.vertex_groups or any(m.type == 'ARMATURE' for m in o.modifiers)) for o in helpers),
            'WORLD_WIDGET_AMBIGUOUS', 'Rig helper is also skinned geometry; inspect in Blender')
    flags = {o: o.hide_render for o in helpers}
    try:
        for obj in helpers:obj.hide_render = True
        bpy.context.view_layer.update()
        yield
    finally:
        for obj, value in flags.items():obj.hide_render = value
        bpy.context.view_layer.update()


def playback(destination, scene):
    raw = destination.read_bytes()
    length, kind = struct.unpack_from('<II', raw, 12)
    require(raw[:4] == b'glTF' and kind == 0x4e4f534a, 'VIEWER_EXPORT_FAILED', 'Missing scene animation envelope')
    data = json.loads(raw[20:20 + length]);animations = data.get('animations', [])
    require(len(animations) == 1 and animations[0].get('channels'), 'VIEWER_EXPORT_FAILED', 'Action needs one combined scene animation')
    intervals = [data['accessors'][s['input']] for s in animations[0]['samplers']]
    first = min(a['min'][0] for a in intervals);last = max(a['max'][0] for a in intervals)
    fps = scene.render.fps / scene.render.fps_base
    require(abs(first) < 1e-5 and abs(last - (scene.frame_end - scene.frame_start) / fps) < 1e-4,
            'VIEWER_EXPORT_FAILED', 'Combined animation differs from the saved scene timebase')
    return {'version': 'scene-playback-v1', 'start': scene.frame_start, 'end': scene.frame_end,
            'fps': fps, 'duration': last, 'clip': animations[0].get('name'),
            'scope': 'SAVED_SCENE', 'performance_acceptance': 'NOT_EVALUATED'}
