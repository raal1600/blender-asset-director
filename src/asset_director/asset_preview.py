"""Bounded, private inspection copies. No writes to the original library/project."""
from pathlib import Path
import copy
import shutil
from .core import Asset, Library, atomic_json, fields, file_hash, load_json, require, within

FORMATS = {'.blend', '.gltf', '.glb', '.fbx', '.bvh'}
MAX_BYTES = 512 * 1024 * 1024
MAX_FILES = 4096


def snapshot(request_file):
    request_file = Path(request_file).resolve()
    request = load_json(request_file, 2 * 1024 * 1024)
    fields(request, {'schema', 'id', 'title', 'version', 'source_kind', 'root', 'files', 'file', 'motion'},
           {'schema', 'id', 'title', 'version', 'source_kind', 'root', 'files', 'file'})
    require(request['schema'] == 'asset-director.asset-preview/1', 'INVALID_PREVIEW', 'Unknown preview request')
    records = request['files']
    require(isinstance(records, list) and 0 < len(records) <= MAX_FILES, 'RESOURCE_LIMIT', 'Preview supports at most 4096 package files')
    names = set()
    for f in records:
        fields(f, {'path', 'size', 'sha256'}, {'path', 'size', 'sha256'})
        require(type(f['size']) is int and f['size'] >= 0, 'INVALID_PREVIEW', 'Invalid file size')
        require(f['path'].casefold() not in names, 'INVALID_PREVIEW', 'Duplicate package member')
        names.add(f['path'].casefold())
    total = sum(f['size'] for f in records)
    require(total <= MAX_BYTES, 'RESOURCE_LIMIT', 'Preview copy exceeds 512 MiB; choose a smaller reviewed package')
    require(request['file'] in [f['path'] for f in records] and Path(request['file']).suffix.lower() in FORMATS,
            'FORMAT_UNSUPPORTED', 'Choose one recorded blend, glTF, GLB, FBX or BVH member')
    source_root = Path(request['root']).resolve(strict=True)
    directory = request_file.parent
    require(not directory.is_relative_to(source_root) and not source_root.is_relative_to(directory),
            'ORIGINAL_OVERWRITE', 'Preview output must be separate from its source root')
    destination = directory / 'library'
    require(not destination.exists(), 'PREVIEW_EXISTS', 'Preview attempts are immutable; request a new copy')
    require(shutil.disk_usage(directory).free >= total * 2 + 128 * 1024 * 1024,
            'DISK_SPACE', 'Not enough free space for this bounded preview')
    # Validate every byte before allocating the snapshot; verify again after copy.
    sources = []
    for f in records:
        p = within(source_root, f['path'])
        require(p.is_file() and p.stat().st_size == f['size'] and file_hash(p) == f['sha256'],
                'STALE_SOURCE', 'Source changed; refresh its catalog/package record')
        sources.append(p)
    destination.mkdir()
    files = []
    for source, f in zip(sources, records):
        relative = 'incoming/package/' + f['path']
        target = within(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open('rb') as inp, target.open('xb') as out:
            shutil.copyfileobj(inp, out, 1024 * 1024)
        require(target.stat().st_size == f['size'] and file_hash(target) == f['sha256']
                and source.stat().st_size == f['size'] and file_hash(source) == f['sha256'],
                'STALE_SOURCE', 'Source changed during preview snapshot; failed attempt retained')
        files.append({**f, 'path': relative})
    # Inspection-only transient record in a separate SQLite library. It is not
    # intake into the user's catalog and carries no manufactured rights grant.
    meta = {'preview_only': True}
    motion = copy.deepcopy(request.get('motion') or {})
    if motion:
        fields(motion, {'file', 'action', 'slot', 'source_object', 'fps', 'frame_start', 'frame_end'},
               {'file', 'action', 'source_object', 'fps', 'frame_start', 'frame_end'})
        require(motion['file']['path'] == request['file'], 'INDEX_SOURCE_MISMATCH', 'Preview must use the indexed take member')
        motion['file'] = next(f for f in files if f['path'] == 'incoming/package/' + request['file'])
        meta.update(motion)
    asset = Asset('local', request['id'] + ':' + request['version'], request['title'],
                  'animation' if motion else 'model', '', local_files=files, metadata=meta)
    with Library(destination) as lib:
        lib.put(asset)
    return request, destination, asset


def prepare(request_file, blender):
    from . import jobs
    request_file = Path(request_file).resolve()
    receipt = request_file.parent / 'receipt.json'
    status = {'schema': 'asset-director.asset-preview/1', 'state': 'PREPARING',
              'selection_changed': False, 'production_use_approved': False}
    atomic_json(receipt, status)
    try:
        request, directory, asset = snapshot(request_file)
        status.update(source_id=request['id'], source_version=request['version'],
                      source_kind=request['source_kind'], title=request['title'], file=request['file'])
        with Library(directory) as lib:
            job = jobs.prepare(lib, 'asset-preview', asset_id=asset.id,
                               options={'file': 'incoming/package/' + request['file']})
            status.update(job_id=job['id'], state='RUNNING')
            atomic_json(receipt, status)
            job = jobs.run(lib, job['id'], blender, timeout=180)
            require(job['state'] == 'SUCCEEDED', 'PREVIEW_FAILED', 'Blender preview failed; inspect the retained job log')
            blend = next(f for f in job['outputs'] if f['path'].endswith('/result.blend'))
            report = next(f for f in job['outputs'] if f['path'].endswith('/result.json'))
            data = load_json(lib.verify_file(report))['data']
            viewer=request_file.parent/'PREVIEW_COPY.blend'
            with lib.verify_file(blend).open('rb') as inp,viewer.open('xb') as target:
                shutil.copyfileobj(inp,target,1024*1024)
            require(file_hash(viewer)==blend['sha256'],'STALE_PREVIEW','Viewer copy differs from the prepared job')
            # Recheck originals after the complete native operation.
            for f in request['files']:
                p = within(Path(request['root']), f['path'])
                require(p.stat().st_size == f['size'] and file_hash(p) == f['sha256'],
                        'STALE_SOURCE', 'Original changed during preparation; preview not launched')
            status.update(state='READY', blend={**blend, 'path': viewer.name},
                          job_blend={**blend,'path':'library/'+blend['path']},
                          report={**report, 'path': 'library/' + report['path']}, data=data)
            atomic_json(receipt, status)
            return status
    except Exception as error:
        status.update(state='FAILED', code=getattr(error, 'code', type(error).__name__),
                      message=str(error) if hasattr(error, 'code') else 'Preview preparation failed; retained attempt needs inspection')
        atomic_json(receipt, status)
        raise
