"""Bind an explicit host approval to one immutable planning result and target file."""
from datetime import datetime
from pathlib import Path
from .core import fields, require, text, digest, load_json

SCHEMA='asset-director.transfer-proposal/1'


def validate_review(review):
    fields(review,{'plan_job_id','plan_id','reviewer','reviewed_at','approved'},
           {'plan_job_id','plan_id','reviewer','reviewed_at','approved'})
    require(type(review['approved']) is bool and review['approved'], 'TRANSFER_REVIEW_REQUIRED','Explicit approval required')
    text(review['reviewer'],160);require(review['reviewer'].strip(),'TRANSFER_REVIEW_REQUIRED','Name approving host/reviewer')
    import re
    require(isinstance(review['plan_job_id'],str) and re.fullmatch(r'j_[0-9a-f]{24}',review['plan_job_id']),
            'TRANSFER_REVIEW_REQUIRED','Invalid planning job ID')
    require(isinstance(review['plan_id'],str) and re.fullmatch(r'tp_[0-9a-f]{64}',review['plan_id']),
            'TRANSFER_REVIEW_REQUIRED','Invalid proposal ID')
    text(review['reviewed_at'],80)
    try:dt=datetime.fromisoformat(review['reviewed_at'].replace('Z','+00:00'))
    except ValueError:dt=None
    require(dt is not None and dt.utcoffset() is not None,'TRANSFER_REVIEW_REQUIRED','Use an offset-aware review timestamp')


def proposal(lib, review):
    validate_review(review)
    from .jobs import read_job
    job,path=read_job(lib,review['plan_job_id'])
    require(job['state']=='SUCCEEDED' and job['specification']['operation']=='transfer-plan',
            'TRANSFER_PLAN_NOT_READY','Use a successful read-only transfer plan')
    for f in job['outputs']:lib.verify_file(f)
    p=load_json(path.parent/'result.json')['data']
    require(p.get('schema')==SCHEMA and p.get('status')=='REVIEW_REQUIRED' and
            p.get('id')==review['plan_id']=='tp_'+digest({k:v for k,v in p.items() if k!='id'}),
            'STALE_TRANSFER_BINDING','Proposal or content identity changed')
    return p,job,path


def checked_binding(lib, options, input_file=None, asset_id=None):
    p,job,path=proposal(lib,options['transfer_binding'])
    require({k:v for k,v in options.items() if k!='transfer_binding'}==p['retarget_options'],
            'STALE_TRANSFER_BINDING','Review applies to exact proposed options; replan changed values')
    if input_file is not None:
        require(Path(input_file).resolve()==Path(job['specification']['inputs'][0]['path']).resolve()
                and asset_id==job['specification']['asset_id'],
                'STALE_TRANSFER_BINDING','Reviewed source or saved target changed')
    from .core import file_hash
    result=path.parent/'result.json'
    return p,{'path':result.relative_to(lib.root).as_posix(),'sha256':file_hash(result),'size':result.stat().st_size}


def prepare(lib, review):
    p,job,_=proposal(lib,review)
    from .jobs import prepare as prepare_job
    options={**p['retarget_options'],'transfer_binding':review}
    return prepare_job(lib,'retarget',job['specification']['inputs'][0]['path'],job['specification']['asset_id'],options)
