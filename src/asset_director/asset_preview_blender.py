"""Blender-only native inspection, no rig transfer or production checkpoint."""
from pathlib import Path
import bpy
from .core import require
from . import blender_ops as ops


def create(lib, asset, member):
    require(asset.metadata.get('preview_only') is True and bpy.app.background and not bpy.data.objects,
            'PREVIEW_ONLY', 'Preview needs an empty isolated inspection job')
    file = next(f for f in asset.local_files if f['path'] == member)
    source = lib.verify_file(file)
    native = None
    if asset.kind == 'animation':
        from .native_clip import import_native
        native = import_native(lib, asset)
    elif source.suffix.lower() == '.blend':
        # A verified COPY, never the original, and no saved UI or asset script.
        bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    else:
        ops.import_file(source, lib.root / 'incoming/package')
    require(0 < len(bpy.data.objects) <= 10000, 'RESOURCE_LIMIT', 'Preview requires 1..10000 objects')
    # Unrecorded external files are not silently adopted into a preview copy.
    root = (lib.root / 'incoming/package').resolve()
    known = {lib.verify_file(f).resolve() for f in asset.local_files}
    for datablocks in (bpy.data.images, bpy.data.libraries, bpy.data.movieclips, bpy.data.sounds,
                       bpy.data.fonts, bpy.data.cache_files, bpy.data.volumes):
        for block in datablocks:
            value = getattr(block, 'filepath', '')
            if not value or value == '<builtin>' or getattr(block, 'packed_file', None):
                continue
            if getattr(block, 'source', None) == 'GENERATED':
                continue
            p = Path(bpy.path.abspath(value, library=getattr(block, 'library', None))).resolve()
            require(p.is_relative_to(root) and p in known and p.is_file(), 'EXTERNAL_REFERENCE',
                    'Preview requires recorded, package-local dependencies; unrecorded external reference found')
    bpy.ops.file.make_paths_absolute()
    bindings, unassigned = ops.clip_bindings(list(bpy.data.objects))
    # Do not offer guessed bone-path mappings as a take selector.
    takes = [{'object': o.name, 'action': a.name, 'slot': slot.identifier if slot else None,
              'start': start, 'end': end, 'basis': evidence}
             for o, a, slot, start, end, evidence in bindings if evidence == 'animation/NLA slot binding']
    require(len(takes) <= 256, 'RESOURCE_LIMIT', 'Preview has too many native takes')
    scene = bpy.context.scene
    scene['asset_director_preview_only'] = True
    scene.name = 'Asset Director - PREVIEW COPY'
    for workspace in bpy.data.workspaces:
        if workspace.name == 'Layout': workspace.name = 'Asset Director - Preview'
    return {'preview_only': True, 'objects': [{'name': o.name, 'type': o.type} for o in bpy.data.objects],
            'takes': takes, 'unassigned_actions': unassigned, 'native_clip': native,
            'fps': scene.render.fps / scene.render.fps_base, 'blender_version': bpy.app.version_string,
            'notice': 'Inspection copy, not selected/imported, no rights or animation-quality approval.'}
