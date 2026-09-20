"""Read-only GLB inspection derivative from an isolated, verified preview copy."""
import bpy
from .core import require


def export(destination, observed):
    require(bpy.app.background and bpy.context.scene.get('asset_director_preview_only') is True,
            'PREVIEW_ONLY', 'Embedded conversion requires a separate preview worker')
    require(not destination.exists(), 'OUTPUT_EXISTS', 'Never overwrite a preview derivative')
    objects = list(bpy.context.scene.objects)
    vertices = sum(len(o.data.vertices) for o in objects if o.type == 'MESH')
    require(0 < vertices <= 2000000, 'RESOURCE_LIMIT', 'In-app preview supports 1..2000000 mesh vertices; inspect in Blender')
    require(len(objects) <= 10000, 'RESOURCE_LIMIT', 'Too many objects for in-app preview')
    # No procedural/simulation approximation passed off as the complete world.
    unsupported = {'FLUID', 'CLOTH', 'SOFT_BODY', 'DYNAMIC_PAINT', 'NODES', 'PARTICLE_SYSTEM'}
    require(not bpy.context.scene.rigidbody_world and not bpy.data.cache_files and not bpy.data.volumes,
            'VIEWER_UNSUPPORTED', 'Simulation/volume previews require Blender')
    require(not any(m.type in unsupported for o in objects for m in o.modifiers),
            'VIEWER_UNSUPPORTED', 'Procedural/simulation modifiers need Blender inspection')
    require(not bpy.app.autoexec_fail, 'VIEWER_UNSUPPORTED', 'This scene needs disabled script/driver execution; inspect in Blender')
    takes = observed['takes']
    if observed.get('checkpoint'):
        require(0 <= bpy.context.scene.frame_end - bpy.context.scene.frame_start <= 3600,
                'RESOURCE_LIMIT', 'Saved scene range exceeds 3600 frames; inspect in Blender')
    require(all(0 <= t['end'] - t['start'] <= 3600 for t in takes),
            'RESOURCE_LIMIT', 'A native take exceeds the 3600-frame interactive conversion limit')
    require(sum(t['end'] - t['start'] + 1 for t in takes) <= 20000,
            'RESOURCE_LIMIT', 'Combined native takes exceed the conversion limit')
    pixels = sum(int(i.size[0]) * int(i.size[1]) for i in bpy.data.images)
    require(all(i.source not in {'SEQUENCE', 'MOVIE', 'TILED'} for i in bpy.data.images),
            'VIEWER_UNSUPPORTED', 'Sequence/movie/UDIM textures require Blender inspection')
    require(pixels <= 64 * 1024**2 and all(max(i.size) <= 8192 for i in bpy.data.images),
            'RESOURCE_LIMIT', 'Textures exceed the interactive preview budget')
    # Export only the currently saved scene, preserving native timebase. Materials
    # are glTF approximations; scene cameras/lights and compositor are not a render.
    args = dict(filepath=str(destination), export_format='GLB', use_active_scene=True,
                export_animations=True, export_extras=False, export_cameras=False,
                export_lights=False, export_apply=False)
    supported = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    if 'export_animation_mode' in supported:
        args['export_animation_mode'] = 'SCENE' if observed.get('checkpoint') else 'ACTIONS'
    if 'export_unused_animations' in supported:
        args['export_unused_animations'] = False
    if 'export_frame_range' in supported:
        args['export_frame_range'] = bool(observed.get('checkpoint'))
    result = bpy.ops.export_scene.gltf(**args)
    require('FINISHED' in result and destination.is_file() and destination.stat().st_size <= 128 * 1024**2,
            'VIEWER_EXPORT_FAILED', 'GLB export failed or exceeds 128 MiB')
    return {'kind': 'READ_ONLY_3D_INSPECTION', 'vertices': vertices, 'source_objects': len(objects),
            'material_fidelity': 'GLTF_APPROXIMATION', 'human_acceptance': 'NOT_EVALUATED',
            'notice': 'Saved data, not a live Blender link or rendered evidence. No approval, import or scene edit.'}
