"""Read-only, paged view of the existing catalog for the local scene workbench.

Listing is metadata, not a claim that bytes or suitability were verified. Exact
selection verifies all files and pins the content and rights evidence together.
"""
from pathlib import Path
import re
from .core import DirectorError, digest, require, rights, tokens
from .catalog_presentation import presentation, classification, reference_image, SUBCATEGORIES

MODEL_SUFFIXES = {'.glb', '.gltf', '.fbx', '.obj', '.blend'}


def describe(lib, asset, *, verify=False, labels=None):
    record = asset.to_dict()
    identity = {key: value for key, value in record.items() if key != 'checked_at'}
    # Index receipts describe derived catalog work, not a new source version.
    identity['metadata'] = {k: v for k, v in identity.get('metadata', {}).items()
                            if k not in {'indexed_clips', 'index_job'}}
    version=digest(identity)
    display=presentation(asset)
    label=(labels or {}).get(asset.id)
    if label and label['version']==version and asset.kind in {'model','pack'}:
        display['subcategory']={'id':label['subcategory'],'basis':'User catalog label for this exact source version'}
    policy = rights(asset, lib=lib)
    if verify:
        require(asset.local_files, 'SOURCE_REQUIRED', 'Acquire or explicitly intake this asset first')
        for file in asset.local_files:
            lib.verify_file(file)
    return {
        'id': asset.id, 'version': version, 'title': asset.title, **display,
        'kind': asset.kind, 'provider': asset.provider, 'files': asset.local_files,
        'policy': policy, 'verified': verify, 'metadata': asset.metadata,
        'source_url': asset.source_url, 'author': asset.author,
        'license_id': asset.license_id, 'license_url': asset.license_url,
        'evidence': asset.evidence,
        'models': [f['path'] for f in asset.local_files if Path(f['path']).suffix.lower() in MODEL_SUFFIXES
                   and (not asset.metadata.get('prepared_member') or f['path'] == asset.metadata['prepared_member'])],
        'package_images': [f['path'] for f in asset.local_files if reference_image(f['path'])],
        'notice': 'Indexed metadata; not rig compatibility, artistic acceptance, or legal clearance.'
    }


def production_catalog_ids(project_file):
    """Read retained membership, without verifying or replacing pinned versions."""
    from .core import load_json
    project = load_json(Path(project_file))
    require(isinstance(project, dict) and project.get('owner') == 'asset-director-launcher',
            'PROJECT_REQUIRED', 'Use a launcher project')
    workbench = project.get('workbench', {})
    require(isinstance(workbench, dict), 'PROJECT_REQUIRED', 'Invalid launcher workbench')
    refs = workbench.get('catalogPins', [])
    require(isinstance(refs, list) and len(refs) <= 2000, 'RESOURCE_LIMIT', 'Too many catalog pins')
    ids = []
    for ref in refs:
        require(isinstance(ref, dict) and isinstance(ref.get('id'), str) and
                re.fullmatch(r'a_[a-f0-9]{24}', ref['id']) and ref['id'] not in ids and
                isinstance(ref.get('version'), str) and re.fullmatch(r'[a-f0-9]{64}', ref['version']),
                'INVALID_PIN', 'Invalid or duplicate catalog pin')
        ids.append(ref['id'])
    return ids


def catalog(lib, query='', offset=0, limit=24, asset_id=None, verify=False, kind=None, kinds=None, subcategory=None, labels=None, exclude_ids=None):
    require(isinstance(query, str) and len(query) <= 2000, 'INVALID_QUERY', 'Search is limited to 2000 characters')
    require(type(offset) is int and offset >= 0 and type(limit) is int and 1 <= limit <= 50,
            'RESOURCE_LIMIT', 'Use a nonnegative offset and 1..50 records per page')
    require(exclude_ids is None or isinstance(exclude_ids, list) and len(exclude_ids) <= 2000 and
            all(isinstance(a, str) and re.fullmatch(r'a_[a-f0-9]{24}', a) for a in exclude_ids) and
            len(set(exclude_ids)) == len(exclude_ids), 'INVALID_QUERY', 'Invalid excluded catalog identities')
    require(exclude_ids is None or asset_id is None, 'INVALID_QUERY', 'Exclusion is a list filter only')
    excluded = set(exclude_ids or [])
    if asset_id is not None:
        require(isinstance(asset_id, str) and re.fullmatch(r'a_[a-f0-9]{24}', asset_id), 'INVALID_ASSET', 'Invalid catalog identity')
        return describe(lib, lib.get(asset_id), verify=verify,labels=labels)
    require(not verify, 'INVALID_QUERY', 'Byte verification requires one explicit asset')
    require(kind is None or kind in {'model','pack','animation','material','hdri'}, 'INVALID_QUERY', 'Invalid asset kind')
    require(kinds is None or isinstance(kinds, list) and 1 <= len(kinds) <= 5 and
            all(isinstance(k, str) and k in {'model','pack','animation','material','hdri'} for k in kinds)
            and len(set(kinds)) == len(kinds), 'INVALID_QUERY', 'Invalid asset kind group')
    search = tokens(query)
    require(subcategory is None or isinstance(subcategory, str) and subcategory in SUBCATEGORIES,
            'INVALID_QUERY', 'Invalid subcategory')
    matched = [asset for asset in lib.all() if asset.id not in excluded and asset.local_files and (kind is None or asset.kind == kind) and (kinds is None or asset.kind in kinds) and
               (subcategory is None or describe(lib,asset,labels=labels)['subcategory']['id'] == subcategory) and
               (not search or search <= tokens(asset.title + ' ' + ' '.join(asset.tags)))]
    matched.sort(key=lambda asset:(asset.title.casefold(),asset.id))
    # Adding the final item on a page can shrink the available-to-add list.
    # Keep the unscoped CLI's existing offset contract unchanged.
    if exclude_ids is not None:
        offset = min(offset, ((len(matched)-1)//limit)*limit) if matched else 0
    selected = matched[offset:offset + limit]
    summaries=[]
    for asset in selected:
        item=describe(lib,asset,labels=labels)
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
    if asset.metadata.get('prepared_member'):
        require(options.get('file') == asset.metadata['prepared_member'], 'MEMBER_REVIEW_REQUIRED',
                'This preparation checked one exact member; other package models need their own reviewed intake')
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


def verify_project(lib, project_file):
    """One bounded verification call for all pinned native records in a project.

    The launcher validates project ownership before requesting this. This read-only
    helper never converts an attestation to a grant or edits catalog records.
    """
    from .core import load_json
    project = load_json(Path(project_file))
    require(project.get('owner') == 'asset-director-launcher', 'PROJECT_REQUIRED', 'Use a launcher project')
    refs = project.get('workbench', {}).get('catalogPins', [])
    require(isinstance(refs, list) and len(refs) <= 2000, 'RESOURCE_LIMIT', 'Too many catalog pins')
    checked, ids = [], set()
    for ref in refs:
        require(isinstance(ref, dict) and isinstance(ref.get('id'), str) and
                ref['id'] not in ids and isinstance(ref.get('version'), str),
                'INVALID_PIN', 'Invalid or duplicate catalog pin')
        ids.add(ref['id'])
        current = catalog(lib, asset_id=ref['id'], verify=True)
        require(current['version'] == ref['version'], 'STALE_CATALOG_PIN',
                'Catalog content or rights evidence changed for ' + ref['id'] + '; explicitly review a new version')
        checked.append({'id': ref['id'], 'version': ref['version']})
    return {'schema': 1, 'ok': True, 'pins': checked, 'license_approval': False}
