"""Blender-only optional copy inventory; never a license or a source grant."""
from pathlib import Path
import bpy
from .core import file_hash

VERSION = 'preview-dependencies-v1'


def inventory():
    fallback = {'version': VERSION, 'mode': 'ALL_PINNED'}
    # Only a clean saved snapshot can bind this observation to checkpoint bytes.
    if not bpy.data.filepath or bpy.data.is_dirty:
        return fallback
    source = Path(bpy.data.filepath)
    if not source.is_file() or source.stat().st_size > 512 * 1024 * 1024:
        return fallback
    # Linked/nested libraries and time-varying resources retain the old behavior.
    if any((bpy.data.libraries, bpy.data.movieclips, bpy.data.sounds,
            bpy.data.cache_files, bpy.data.volumes)):
        return fallback
    known = set()
    for block in list(bpy.data.images) + list(bpy.data.fonts):
        value = block.filepath
        if not value or value == '<builtin>' or block.packed_file:
            continue
        if isinstance(block, bpy.types.Image):
            if block.source == 'GENERATED':
                continue
            if block.source != 'FILE':
                return fallback
        # Relative remapping, UDIMs and sequences must not be guessed.
        if value.startswith('//') or not Path(value).is_absolute() or any(c in value for c in '<>*?'):
            return fallback
        known.add(str(Path(value).resolve()))
    raw = bpy.utils.blend_paths(absolute=False, packed=False, local=False)
    if len(raw) > 4096 or any(not p or p.startswith('//') or not Path(p).is_absolute() for p in raw):
        return fallback
    paths = {str(Path(p).resolve()) for p in raw}
    # Unknown RNA paths (e.g. a modifier cache) cannot be silently omitted.
    if paths != known:
        return fallback
    return {'version': VERSION, 'mode': 'EXACT_ABSOLUTE_FILES',
            'source_sha256': file_hash(source), 'paths': sorted(paths)}
