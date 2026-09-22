"""Read-only GLB inspection derivative from an isolated, verified preview copy."""
import bpy
from contextlib import contextmanager
from array import array
from .core import require
from .viewer_textures import plan


@contextmanager
def preview_textures():
    """Remap temporary image buffers and restore even after export failure.

    scale() alone does not mark Blender images dirty. The exporter otherwise
    reuses full-size packed/file bytes instead of encoding the resized buffer.
    """
    require(bpy.app.background and bpy.context.scene.get('asset_director_preview_only') is True,
            'PREVIEW_ONLY', 'Texture reduction requires a separate preview worker')
    originals = list(bpy.data.images)
    report = plan([{'name': i.name, 'size': list(i.size), 'source': i.source} for i in originals])
    copies = []
    try:
        for original, record in zip(originals, report['images']):
            if record['source_size'] == record['preview_size']:
                continue
            temporary = original.copy()
            copies.append((original, temporary))
            # Image.copy() omits unsaved pixel edits, including generated images.
            if original.is_dirty:
                pixels = array('f', [0]) * len(original.pixels)
                original.pixels.foreach_get(pixels)
                temporary.scale(*original.size)
                temporary.pixels.foreach_set(pixels)
                del pixels
            temporary.scale(*record['preview_size'])
            temporary.pixels[0] = temporary.pixels[0]
            temporary.update()
            require(list(temporary.size) == record['preview_size'] and temporary.is_dirty,
                    'VIEWER_EXPORT_FAILED', 'Preview texture reduction did not produce an exportable buffer')
            original.user_remap(temporary)
        yield report
    finally:
        for original, temporary in reversed(copies):
            temporary.user_remap(original)
            bpy.data.images.remove(temporary)


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
    # Export only the currently saved scene, preserving native timebase. Materials
    # are glTF approximations; scene cameras/lights and compositor are not a render.
    # Honor object/collection render visibility, including explicitly repaired
    # rig widgets. Hidden helpers must not reappear in the inspection derivative.
    args = dict(filepath=str(destination), export_format='GLB', use_active_scene=True, use_renderable=True,
                export_animations=True, export_extras=False, export_cameras=False,
                export_lights=False, export_apply=False)
    supported = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    if 'export_animation_mode' in supported:
        args['export_animation_mode'] = 'SCENE' if observed.get('checkpoint') else 'ACTIONS'
    if 'export_unused_animations' in supported:
        args['export_unused_animations'] = False
    if 'export_frame_range' in supported:
        args['export_frame_range'] = bool(observed.get('checkpoint'))
    with preview_textures() as textures:
        result = bpy.ops.export_scene.gltf(**args)
    require('FINISHED' in result and destination.is_file() and destination.stat().st_size <= 128 * 1024**2,
            'VIEWER_EXPORT_FAILED', 'GLB export failed or exceeds 128 MiB')
    return {'kind': 'READ_ONLY_3D_INSPECTION', 'vertices': vertices, 'source_objects': len(objects),
            'material_fidelity': 'GLTF_APPROXIMATION', 'human_acceptance': 'NOT_EVALUATED', 'textures': textures,
            'notice': 'Saved data, not a live Blender link or rendered evidence. No approval, import or scene edit.'}
