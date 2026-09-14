"""Explicit local-motion registration, review, refresh and preflight commands."""
from pathlib import Path
from .core import load_json
from . import local_motion as lm, license_policy as lp, settings

COMMANDS={'motion-roots','motion-root-add','motion-root-scan','motion-root-review',
          'motion-license-revoke','motion-sync','motion-preflight'}


def add_parsers(sub):
    sub.add_parser('motion-roots')
    p=sub.add_parser('motion-root-add');p.add_argument('path');p.add_argument('--provider',required=True,choices=sorted(lm.PROVIDERS))
    p=sub.add_parser('motion-root-scan');p.add_argument('root_id')
    p=sub.add_parser('motion-root-review');p.add_argument('root_id');p.add_argument('--review',required=True)
    p=sub.add_parser('motion-license-revoke');p.add_argument('review_id');p.add_argument('--reason',required=True)
    p=sub.add_parser('motion-sync');p.add_argument('--root');p.add_argument('--index',action='store_true')
    p.add_argument('--blender',default=settings.blender_path());p.add_argument('--max-new-files',type=int,default=8)
    p=sub.add_parser('motion-preflight');p.add_argument('asset_id');p.add_argument('--purpose',choices=['project_use','raw_redistribution'],default='project_use')


def dispatch(lib,args):
    c=args.command
    if c=='motion-roots':return lm.roots(lib)
    if c=='motion-root-add':return lm.add_root(lib,args.path,args.provider)
    if c=='motion-root-scan':return lm.scan(lib,args.root_id)
    if c=='motion-root-review':return lm.review_root(lib,args.root_id,load_json(Path(args.review),2*1024**2))
    if c=='motion-license-revoke':return lp.revoke(lib,args.review_id,args.reason)
    if c=='motion-sync':return lm.sync(lib,args.root,index=args.index,blender=args.blender,max_new_files=args.max_new_files)
    if c=='motion-preflight':return lm.preflight(lib,args.asset_id,args.purpose)
    raise AssertionError('Unregistered local-motion command')
