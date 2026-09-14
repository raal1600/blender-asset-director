"""CLI for immutable records, evidence, metadata scouting and reviewed profiles."""
from pathlib import Path
import shutil
from .core import atomic_json, file_hash, load_json, require, within
from . import motion_assets as ma


def add_parsers(sub):
    from .local_motion_cli import add_parsers as add_local
    add_local(sub)
    sub.add_parser('motion-providers')
    q=sub.add_parser('motion-scout');q.add_argument('query');q.add_argument('--use',required=True,choices=sorted(ma.PROJECT_USES));q.add_argument('--remote',action='store_true');q.add_argument('--limit',type=int,default=8)
    q=sub.add_parser('motion-evidence');q.add_argument('path',help='Explicit local terms/permission text, never credentials')
    q=sub.add_parser('motion-collect');q.add_argument('job_id')
    q=sub.add_parser('motion-show');q.add_argument('motion_id');q.add_argument('--full',action='store_true')
    q=sub.add_parser('motion-diagnostics');q.add_argument('motion_id');q.add_argument('--options')
    q=sub.add_parser('motion-review');q.add_argument('--review',required=True)
    q=sub.add_parser('retarget-profile');q.add_argument('--source',required=True);q.add_argument('--target',required=True);q.add_argument('--mode',choices=['preserve_world','morphology_scaled'],default='morphology_scaled')


def dispatch(lib,args):
    cmd=args.command
    from .local_motion_cli import COMMANDS, dispatch as local_dispatch
    if cmd in COMMANDS: return local_dispatch(lib,args)
    if cmd=='motion-providers':
        from .motion_scout import capabilities
        return capabilities()
    if cmd=='motion-scout':
        from .motion_scout import search
        return search(lib,args.query,args.use,remote=args.remote,limit=args.limit)
    if cmd=='motion-evidence':
        p=Path(args.path).expanduser().resolve()
        require(p.is_file() and p.suffix.lower() in {'.txt','.md','.html'} and 0<p.stat().st_size<=2*1024**2,
                'RIGHTS_EVIDENCE_REQUIRED','Provide explicit bounded UTF-8 terms/permission text')
        p.read_text(encoding='utf-8-sig');h=file_hash(p);dest=within(lib.root,'licenses/motion-'+h+'.txt')
        if dest.exists():require(file_hash(dest)==h,'RIGHTS_EVIDENCE_CHANGED','Stored evidence changed')
        else:
            with dest.open('xb') as out,p.open('rb') as inp:shutil.copyfileobj(inp,out)
        return {'path':dest.relative_to(lib.root).as_posix(),'sha256':h,'size':dest.stat().st_size,
                'notice':'Bytes retained; interpretation and ownership still require review'}
    if cmd=='motion-collect':return ma.collect(lib,args.job_id)
    if cmd=='motion-show':
        r,_=ma.load(lib,args.motion_id)
        return r if args.full else {k:r[k] for k in ('id','schema','source','timing','semantics')} | {'joints':len(r['skeleton']['joints']),'performance':'NOT_EVALUATED'}
    if cmd=='motion-diagnostics':
        from .motion_review import diagnostics
        r,s=ma.load(lib,args.motion_id,samples=True)
        return diagnostics(r,s,load_json(Path(args.options)) if args.options else None)
    if cmd=='motion-review':
        from .motion_review import record_review
        return record_review(lib,load_json(Path(args.review)))
    if cmd=='retarget-profile':
        from .motion_body import build_profile
        def skeleton(path):
            data=load_json(Path(path));data=data.get('data',data)
            return data.get('skeleton',data)
        result=build_profile(skeleton(args.source),skeleton(args.target),args.mode)
        path=within(lib.root,'retarget-profiles/'+result['id']+'.json')
        if path.exists():require(load_json(path)==result,'STALE_RETARGET_PROFILE','Cached profile changed')
        else:atomic_json(path,result)
        return {**result,'path':str(path)}
    require(False,'UNKNOWN_COMMAND','Unknown motion command')
