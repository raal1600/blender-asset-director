"""Explicit read-only animation inboxes; bounded on-demand sync, never a watcher.

The managed library holds copies, indexes and reviews. A folder is a provenance
hint, not proof of rights. Nothing here writes to a source directory or uses HTTP.
"""
from __future__ import annotations
import copy
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import time
from .core import Asset, DirectorError, atomic_json, digest, fields, load_json, require, rights, tokens, within
from . import license_policy as lp

PROVIDERS={'mixamo','cmu','rokoko','aist','custom','unknown'}
URLS={'mixamo':'https://www.mixamo.com/','cmu':'https://mocap.cs.cmu.edu/',
      'rokoko':'https://www.rokoko.com/','aist':'https://google.github.io/aistplusplus_dataset/',
      'custom':'https://example.invalid/user-supplied','unknown':'https://example.invalid/unknown'}
SUPPORTED={'.fbx','.bvh','.glb'}
PACKAGES={'.blend','.gltf','.zip'}
NATIVE={'.asf','.amc','.npy','.npz','.pkl','.pickle'}
MAX_ENTRIES=4096
MAX_BYTES=500*1024**2
MAX_SCAN_BYTES=2*1024**3
MAX_DEPTH=4


def roots(lib):
    p=within(lib.root,'motion-sources/roots.json')
    if not p.exists(): return {'schema':'asset-director.local-motion-roots/1','roots':[]}
    r=load_json(p,65536); fields(r,{'schema','roots'},{'schema','roots'})
    require(r['schema']=='asset-director.local-motion-roots/1' and isinstance(r['roots'],list) and len(r['roots'])<=16,
            'MOTION_ROOT_INVALID','Invalid root registry')
    ids=set()
    for entry in r['roots']:
        fields(entry,{'id','path','provider','review_id'},{'id','path','provider','review_id'})
        require(entry['provider'] in PROVIDERS and isinstance(entry['path'],str) and Path(entry['path']).is_absolute()
                and entry['id']=='mr_'+digest([entry['path'],entry['provider']]) and entry['id'] not in ids,
                'MOTION_ROOT_INVALID','Invalid or duplicate registered source')
        ids.add(entry['id'])
    return r


def safe_path(path):
    """Do not resolve through a junction/symlink before checking its ancestors."""
    p=Path(path).expanduser().absolute()
    require('..' not in p.parts,'UNSAFE_PATH','Parent traversal is not a source path')
    for component in [*reversed(p.parents),p]:
        s=component.lstat()
        require(not stat.S_ISLNK(s.st_mode) and not (getattr(s,'st_file_attributes',0)&0x400),
                'SOURCE_LINK_REFUSED','Symlinks and Windows reparse points are not source roots/files')
    return p


def add_root(lib,path,provider):
    require(provider in PROVIDERS,'MOTION_ROOT_INVALID','Unknown provider hint')
    p=safe_path(path)
    require(p.is_dir() and p!=Path(p.anchor),'MOTION_ROOT_INVALID','Choose an existing animation folder, not a drive')
    require(not p.is_relative_to(lib.root) and not lib.root.is_relative_to(p),
            'MOTION_ROOT_INVALID','Source folders and managed library must be disjoint')
    row={'path':str(p),'provider':provider,'id':'mr_'+digest([str(p),provider]),'review_id':None}
    with lib.lock('motion-roots'):
        reg=roots(lib)
        for other in reg['roots']:
            if other['id']==row['id']: return {'status':'REUSED','root':other}
            q=Path(other['path'])
            require(not p.is_relative_to(q) and not q.is_relative_to(p),'MOTION_ROOT_OVERLAP','Register non-overlapping provider folders')
        require(len(reg['roots'])<16,'RESOURCE_LIMIT','At most 16 roots')
        reg['roots'].append(row); atomic_json(within(lib.root,'motion-sources/roots.json'),reg)
    return {'status':'REGISTERED','root':row,'provider_hint_is_license':False}


def find_root(lib,root_id):
    rows=[r for r in roots(lib)['roots'] if r['id']==root_id]
    require(len(rows)==1,'MOTION_ROOT_UNKNOWN','Register this directory explicitly first')
    return rows[0]


def stable_read(path,out=None):
    p=safe_path(path); before=p.lstat()
    require(stat.S_ISREG(before.st_mode),'SOURCE_NOT_REGULAR','Source is not a regular file')
    require(0<before.st_size<=MAX_BYTES,'RESOURCE_LIMIT','Source must be nonempty and at most 500 MiB')
    require(time.time_ns()-before.st_mtime_ns>=2*10**9,'SOURCE_UNSTABLE','Recent download: finish writing before sync')
    identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
    fd=os.open(p,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0))
    h=hashlib.sha256(); count=0
    with os.fdopen(fd,'rb') as source:
        require(identity(before)==identity(os.fstat(source.fileno())),'SOURCE_UNSTABLE','File changed while opening')
        for block in iter(lambda:source.read(65536),b''):
            count+=len(block); require(count<=MAX_BYTES,'RESOURCE_LIMIT','Growing source exceeds bound')
            h.update(block)
            if out is not None: out.write(block)
        after=os.fstat(source.fileno())
    safe_path(p)
    require(count==before.st_size and identity(before)==identity(after)==identity(p.lstat()),
            'SOURCE_UNSTABLE','Source changed during hashing/copy')
    return h.hexdigest(),count


def scan(lib,root_id):
    root=find_root(lib,root_id)
    result={'root_id':root_id,'provider_hint':root['provider'],'status':'SCANNED','complete':True,'files':[],'notes':[]}
    try:
        base=safe_path(root['path']); require(base.is_dir(),'ROOT_UNAVAILABLE','Registered source is not a directory')
        todo=[(base,0)]; count=0; size=0
        while todo:
            directory,depth=todo.pop(); safe_path(directory); batch=[]
            with os.scandir(directory) as entries:
                for e in entries:
                    count+=1; require(count<=MAX_ENTRIES,'RESOURCE_LIMIT','Root exceeds entry budget')
                    batch.append(Path(e.path))
            for p in sorted(batch):
                rel=p.relative_to(base).as_posix()
                try:
                    safe_path(p)
                    if p.is_dir():
                        require(depth<MAX_DEPTH,'RESOURCE_LIMIT','Source exceeds four nested directory levels')
                        todo.append((p,depth+1)); continue
                    ext=p.suffix.lower()
                    if ext in PACKAGES|NATIVE:
                        result['notes'].append({'relative_path':rel,'status':'EXPLICIT_PACKAGE_INTAKE_REQUIRED' if ext in PACKAGES else 'NATIVE_CONVERTER_NOT_IMPLEMENTED'})
                        continue
                    if ext not in SUPPORTED: continue
                    size+=p.stat().st_size; require(size<=MAX_SCAN_BYTES,'RESOURCE_LIMIT','Root hashing exceeds 2 GiB budget')
                    sha,n=stable_read(p); result['files'].append({'relative_path':rel,'sha256':sha,'size':n})
                except (DirectorError,OSError) as e:
                    code=e.code if isinstance(e,DirectorError) else 'SOURCE_IO_UNAVAILABLE'
                    result['notes'].append({'relative_path':rel,'status':code}); result['complete']=False
                    if code=='RESOURCE_LIMIT': raise
        result['files'].sort(key=lambda f:f['relative_path'])
    except (DirectorError,OSError) as e:
        result['status']=e.code if isinstance(e,DirectorError) else 'ROOT_UNAVAILABLE'; result['complete']=False
    return result


def review_root(lib,root_id,request):
    with lib.lock('motion-roots'):
        reg=roots(lib); root=find_root(lib,root_id); observed=scan(lib,root_id)
        require(observed['status']=='SCANNED' and observed['complete'],'ROOT_REVIEW_INCOMPLETE','Resolve incomplete scan before approval')
        hashes=[f['sha256'] for f in observed['files'] if Path(f['relative_path']).suffix.lower()=='.fbx']
        review=lp.create_review(lib,root,request,hashes)
        row=next(r for r in reg['roots'] if r['id']==root_id)
        if row['review_id']!=review['id']:
            row['review_id']=review['id']; atomic_json(within(lib.root,'motion-sources/roots.json'),reg)
        return {'status':'REVIEW_RECORDED','review_id':review['id'],'authorized_current_files':len(hashes),
                'future_files_user_attested':review['include_future_files'],'scope':review['scope'],
                'source_origin_independently_verified':False}


def copy_source(lib,root,f):
    source=safe_path(Path(root['path'])/f['relative_path']); ext=source.suffix.lower()
    dest=within(lib.root,'incoming/motion-'+f['sha256']+'/source'+ext)
    ref={'path':dest.relative_to(lib.root).as_posix(),'sha256':f['sha256'],'size':f['size']}
    if dest.exists(): lib.verify_file(ref)
    else:
        dest.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix='.copy-',dir=dest.parent)
        try:
            with os.fdopen(fd,'wb') as out: sha,n=stable_read(source,out)
            require(sha==f['sha256'] and n==f['size'],'SOURCE_UNSTABLE','Download changed since scan')
            os.replace(tmp,dest)
        finally: Path(tmp).unlink(missing_ok=True)
    if ext=='.glb':
        from .acquire import gltf_dependencies
        gltf_dependencies(dest,dest.parent)
    return ref


def preflight(lib,asset_id,purpose='project_use'):
    a=lib.get(asset_id); policy=rights(a,lib=lib,purpose=purpose); integrity='NOT_ACQUIRED'
    if a.local_files:
        try:
            for f in a.local_files:lib.verify_file(f)
            integrity='VERIFIED_COPY'
        except DirectorError as e:integrity=e.code
    indexed=bool(a.metadata.get('indexed_clips')) or ('action' in a.metadata and 'fps' in a.metadata)
    ready=integrity=='VERIFIED_COPY' and policy['eligible']
    return {'asset_id':a.id,'title':a.title,'acquisition':integrity,'policy':policy,'indexed':indexed,
            'import':'READY' if ready else 'BLOCKED','native_playback':('READY' if 'action' in a.metadata else 'SELECT_INDEXED_CLIP') if ready and indexed else 'NOT_READY',
            'clip_ids':a.metadata.get('indexed_clips',[]),'retarget':'TARGET_MAPPING_AND_ALIGNMENT_REQUIRED','performance':'PENDING'}


def sync(lib,root_id=None,*,index=False,blender=None,max_new_files=8):
    from . import jobs
    require(type(max_new_files) is int and 1<=max_new_files<=32,'RESOURCE_LIMIT','New/index work budget is 1..32')
    require(type(index) is bool,'INVALID_SCHEMA','index must be boolean')
    if index:require(blender and Path(blender).is_file(),'BLENDER_NOT_FOUND','Use the registered Blender executable')
    selected=[find_root(lib,root_id)] if root_id else roots(lib)['roots']; reports=[]; used=0
    with lib.lock('local-motion-sync'):
        for root in selected:
            report=scan(lib,root['id']); report['assets']=[]
            state_path=within(lib.root,'motion-sources/state-'+root['id']+'.json')
            old=load_json(state_path) if state_path.exists() else {'entries':{}}
            fields(old,{'entries'},{'entries'}); require(isinstance(old['entries'],dict),'MOTION_ROOT_INVALID','Invalid sync state')
            state=copy.deepcopy(old); visible=set()
            for f in report['files']:
                rel=f['relative_path'];visible.add(rel); sid=digest([f['sha256'],Path(rel).suffix.lower()])
                aid=Asset('local-motion',sid,'','pack',URLS[root['provider']]).id
                try:
                    try:a=lib.get(aid);exists=True
                    except DirectorError as e:
                        if e.code!='ASSET_NOT_FOUND':raise
                        exists=False
                    if not exists and used>=max_new_files:
                        report['assets'].append({'relative_path':rel,'status':'DEFERRED_BUDGET'});report['complete']=False;continue
                    if exists:
                        before=a.to_dict()
                        for item in a.local_files:lib.verify_file(item)
                        require(a.metadata.get('local_motion',{}).get('root_id')==root['id'],
                                'PROVENANCE_CONFLICT','Identical bytes under another root/provider need review')
                    else:
                        used+=1;file=copy_source(lib,root,f);title=Path(rel).stem
                        a=Asset('local-motion',sid,title,'pack',URLS[root['provider']],price=None,downloadable=True,
                            formats=[Path(rel).suffix.lower()],tags=sorted(tokens(title)),local_files=[file],
                            metadata={'local_motion':{'root_id':root['id'],'provider_hint':root['provider'],'source_hash':f['sha256'],'source_names':[rel]},
                                      'semantic_evidence':'FILENAME_CLAIM_ONLY','visual_review':'PENDING'})
                        before=None
                    names=a.metadata['local_motion']['source_names']
                    if rel not in names:
                        names.append(rel);names.sort();a.tags=sorted(set(a.tags)|tokens(Path(rel).stem))
                    review_status='LICENSE_REVIEW_REQUIRED'
                    if root['review_id'] and root['provider']=='mixamo' and a.formats==['.fbx']:
                        try:lp.bind_asset(lib,a,root['review_id']);review_status='REVIEWED_PROJECT_USE'
                        except DirectorError as e:review_status=e.code
                    if before!=a.to_dict():lib.put(a)
                    indexed='NOT_REQUESTED'
                    if index:
                        job=jobs.prepare(lib,'index',asset_id=a.id)
                        if job['state']=='SUCCEEDED':
                            for output in job['outputs']:lib.verify_file(output)
                            jobs.index_result(lib,a.id,job['id']);indexed='REUSED_INDEX'
                        elif job['state']!='PLANNED':indexed='FAILED_INDEX_REVIEW_'+job['id'];report['complete']=False
                        elif exists and used>=max_new_files:indexed='DEFERRED_BUDGET';report['complete']=False
                        else:
                            if exists:used+=1
                            jobs.run(lib,job['id'],blender);jobs.index_result(lib,a.id,job['id']);indexed='INDEXED'
                    state['entries'][rel]={'asset_id':a.id,'sha256':f['sha256'],'source_status':'PRESENT'}
                    report['assets'].append({'relative_path':rel,'asset_id':a.id,'status':'REUSED_COPY' if exists else 'COPIED',
                        'license_review':review_status,'index':indexed,'readiness':preflight(lib,a.id)})
                except (DirectorError,OSError) as e:
                    report['assets'].append({'relative_path':rel,'status':e.code if isinstance(e,DirectorError) else 'SOURCE_IO_UNAVAILABLE'})
                    report['complete']=False
            if report['complete']:
                for rel,entry in state['entries'].items():
                    if rel not in visible:entry['source_status']='MISSING_SOURCE_PRIVATE_COPY_RETAINED'
            report['retained_missing_sources']=[rel for rel,e in state['entries'].items() if e['source_status']!='PRESENT']
            if state!=old:atomic_json(state_path,state)
            reports.append(report)
    status='NO_ROOTS_REGISTERED' if not selected else 'COMPLETE' if all(r['complete'] for r in reports) else 'PARTIAL_OR_BLOCKED'
    return {'status':status,'roots':reports,'new_or_indexed_files':used,'source_writes':False,
            'network_used':False,'live_blender_used':False,'next':'Sync completion is not license, rig or performance acceptance.'}
