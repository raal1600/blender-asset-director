"""Actual evaluated Blender camera samples; never writes a scene or camera."""
import math
import bpy
from .core import require
from .shot_view_contract import validate
from .scene_ops import flatten


def inspect(value):
    validate(value)
    scene = bpy.context.scene;render = scene.render
    require(bpy.app.background and scene.get('asset_director_preview_only') is True,
            'PREVIEW_ONLY', 'Shot projection needs a separate preview worker')
    camera = scene.objects.get(value['camera'])
    require(camera is not None and camera.type == 'CAMERA', 'CAMERA_REQUIRED', 'Saved shot camera was not found')
    require(scene.frame_start <= value['start'] <= value['end'] <= scene.frame_end,
            'INVALID_TIMEBASE', 'Shot range differs from this saved scene')
    require(not render.use_border and not render.use_multiview,
            'VIEWER_UNSUPPORTED', 'Render borders and multiview need Blender camera inspection')
    width, height = render.resolution_x, render.resolution_y
    aspect = width * render.pixel_aspect_x / (height * render.pixel_aspect_y)
    require(math.isfinite(aspect) and aspect > 0, 'INVALID_PREVIEW', 'Invalid saved camera aspect')
    frame, subframe = scene.frame_current, scene.frame_subframe;samples = []
    try:
        for current in range(value['start'], value['end'] + 1):
            scene.frame_set(current)
            deps = bpy.context.evaluated_depsgraph_get();evaluated = camera.evaluated_get(deps)
            require(evaluated.data.type in {'PERSP', 'ORTHO'}, 'VIEWER_UNSUPPORTED', 'This camera projection needs Blender')
            matrix = evaluated.matrix_world.normalized()
            require(abs(matrix.determinant()) > 1e-12, 'VIEWER_UNSUPPORTED', 'Camera transform is singular')
            projection = evaluated.calc_matrix_camera(deps, x=width, y=height,
                scale_x=render.pixel_aspect_x, scale_y=render.pixel_aspect_y)
            sample = {'frame': current, 'projection': evaluated.data.type,
                      'matrix_world': flatten(matrix), 'projection_matrix': flatten(projection)}
            require(all(math.isfinite(x) for key in ('matrix_world', 'projection_matrix') for x in sample[key]),
                    'VIEWER_UNSUPPORTED', 'Camera projection contains non-finite values')
            samples.append(sample)
    finally:
        scene.frame_set(frame, subframe=subframe)
    return {'version': 'shot-camera-samples-v1', 'shot': value, 'aspect': aspect,
            'fps': render.fps / render.fps_base, 'samples': samples,
            'sampling': 'INTEGER_FRAMES', 'lighting': 'INSPECTION_APPROXIMATION',
            'depth_of_field': 'NOT_SIMULATED', 'human_acceptance': 'NOT_EVALUATED'}
