"""Read-only, paged view of the existing catalog for the local scene workbench.

Listing is metadata, not a claim that bytes or suitability were verified. Exact
selection verifies all files and pins the content and rights evidence together.
"""
from pathlib import Path
import re
from .core import DirectorError, digest, require, rights, tokens

MODEL_SUFFIXES = {'.glb', '.gltf', '.fbx', '.obj', '.blend'}


def describe(lib, asset, *, verify=False):
    record = asset.to_dict()
    identity = {key: value for key, value in record.items() if key != 'checked_at'}
    policy = rights(asset, lib=lib)
    if verify:
        require(asset.local_files, 'SOURCE_REQUIRED', 'Acquire or explicitly intake this asset first')
        for file in asset.local_files:
            lib.verify_file(file)
    return {
        'id': asset.id, 'version': digest(identity), 'title': asset.title,
        'kind': asset.kind, 'provider': asset.provider, 'files': asset.local_files,
        'policy': policy, 'verified': verify, 'metadata': asset.metadata,
        'source_url': asset.source_url, 'author': asset.author,
        'license_id': asset.license_id, 'license_url': asset.license_url,
        'evidence': asset.evidence,
        'models': [f['path'] for f in asset.local_files if Path(f['path']).suffix.lower() in MODEL_SUFFIXES],
        'package_images': [f['path'] for f in asset.local_files if Path(f['path']).suffix.lower() in {'.png', '.jpg', '.jpeg'}],
        'notice': 'Indexed metadata; not rig compatibility, artistic acceptance, or legal clearance.'
    }


def catalog(lib, query='', offset=0, limit=24, asset_id=None, verify=False, kind=None):
    require(isinstance(query, str) and len(query) <= 2000, 'INVALID_QUERY', 'Search is limited to 2000 characters')
    require(type(offset) is int and offset >= 0 and type(limit) is int and 1 <= limit <= 50,
            'RESOURCE_LIMIT', 'Use a nonnegative offset and 1..50 records per page')
    if asset_id is not None:
        require(isinstance(asset_id, str) and re.fullmatch(r'a_[a-f0-9]{24}', asset_id), 'INVALID_ASSET', 'Invalid catalog identity')
        return describe(lib, lib.get(asset_id), verify=verify)
    require(not verify, 'INVALID_QUERY', 'Byte verification requires one explicit asset')
    require(kind is None or kind in {'model','pack','animation','material','hdri'}, 'INVALID_QUERY', 'Invalid asset kind')
    search = tokens(query)
    matched = [asset for asset in lib.all() if asset.local_files and (kind is None or asset.kind == kind) and
               (not search or search <= tokens(asset.title + ' ' + ' '.join(asset.tags)))]
    selected = matched[offset:offset + limit]
    summaries=[]
    for asset in selected:
        item=describe(lib,asset)
        item['file_count']=len(item.pop('files'))
        item['models']=item['models'][:16]
        item['package_images']=item['package_images'][:1]
        item['metadata']={k:v for k,v in item['metadata'].items() if k in {'action','slot','fps','duration','source_object','frame_range','rig_compatibility','visual_review'}}
        summaries.append(item)
    return {'schema': 1, 'items': summaries,
            'total': len(matched), 'offset': offset,
            'next_offset': offset + limit if offset + limit < len(matched) else None}


def validate_import(lib, asset, options):
    """An explicit file must be one exact recorded package member, not a path."""
    if 'file' in options:
        require(isinstance(options['file'], str) and any(f['path'] == options['file'] for f in asset.local_files),
                'SOURCE_NOT_IN_ASSET', 'Choose an exact acquired package member')
        require(Path(options['file']).suffix.lower() in MODEL_SUFFIXES, 'FORMAT_UNSUPPORTED', 'Choose a supported model member')
    if 'selection' in options:
        selection = options['selection']
        require(isinstance(selection, list) and 1 <= len(selection) <= 64 and
                all(isinstance(s, str) and 0 < len(s) <= 255 for s in selection) and len(set(selection)) == len(selection),
                'COLLECTION_SELECTION_REQUIRED', 'Select one to 64 distinct observed collections')
    if 'collection' in options:
        require(isinstance(options['collection'], str) and 0 < len(options['collection']) <= 255,
                'INVALID_COLLECTION', 'Invalid destination collection name')
