"""Read-only display taxonomy. Never changes catalog records, versions or rights."""
from pathlib import Path
import re

SUBCATEGORIES = {'character', 'environment', 'prop', 'rigged-model', 'model', 'pack',
                 'motion', 'material', 'hdri'}


def classification(asset):
    meta, tags = asset.metadata, {t.lower() for t in asset.tags}
    fixed = {'animation': 'motion', 'material': 'material', 'hdri': 'hdri'}
    if asset.kind in fixed:
        return {'id': fixed[asset.kind], 'basis': 'Catalog asset type'}
    explicit = meta.get('subcategory')
    if explicit in {'character', 'environment', 'prop'}:
        return {'id': explicit, 'basis': 'Recorded subcategory'}
    categories = {c for c in ('character', 'environment', 'prop') if c in tags or c+'s' in tags}
    if len(categories) == 1:
        return {'id': categories.pop(), 'basis': 'Recorded source tag; not visual acceptance'}
    if 'rigged' in tags:
        return {'id': 'rigged-model', 'basis': 'Recorded rigged tag; character/prop classification not established'}
    return {'id': 'pack' if asset.kind == 'pack' else 'model', 'basis': 'No specific subcategory recorded'}


def reference_image(filename):
    """Conservative source-reference naming, not a claim of a generated 3D preview."""
    p = Path(filename)
    return p.suffix.lower() in {'.png', '.jpg', '.jpeg'} and bool(
        re.search(r'(^|[ _.-])(preview|thumbnail|thumb|screenshot|reference)([ _.-]|$)', p.stem, re.I))


def presentation(asset):
    meta = asset.metadata
    return {'subcategory': classification(asset), 'tags': asset.tags,
            'motion': {k: meta[k] for k in ('action', 'slot', 'source_object', 'fps', 'duration',
                       'frame_start', 'frame_end', 'frame_range') if k in meta},
            'bundled_clip_count': len(meta.get('indexed_clips', [])) if isinstance(meta.get('indexed_clips'), list) else None}
