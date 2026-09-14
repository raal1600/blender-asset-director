"""Motion-specific discovery; no crawler and no capture-method quality hierarchy."""
import os
import re
from .core import Asset, DirectorError, require, rights, text, within
from .motion_assets import load, rights_gate
from .providers import Providers

ALIASES={'moonwalking':'moonwalk','backslide':'moonwalk','backsliding':'moonwalk',
 'dancing':'dance','dances':'dance','walking':'walk','walks':'walk','running':'run',
 'runs':'run','jogging':'jog','jumping':'jump','jumps':'jump','turning':'turn','turns':'turn',
 'gliding':'glide','clapping':'clap'}
STOP={'a','an','the','to','of','and','with','realistic','person','animation','motion','my','this'}


def words(value):
    value=re.sub(r'([a-z])([A-Z])',r'\1 \2',value)
    value=re.sub(r'backward\s+glide','moonwalk',value.lower())
    return {ALIASES.get(x,x) for x in re.findall('[a-z0-9]+',value) if x not in STOP}


def capabilities():
    return {
      'local':{'search':'READY','acquisition':'ALREADY_LOCAL'},
      'sketchfab':{'search':'PUBLIC_API','acquisition':'EXISTING_AUTHENTICATED_ADAPTER','note':'animationCount is not dance-quality evidence'},
      'quaternius':{'search':'CURATED_PACK','acquisition':'EXISTING_FREE_ADAPTER','note':'Index actual clips; do not promise a dance from the pack title'},
      'cmu':{'search':'HOST_SEARCH_OR_LOCAL_INDEX','acquisition':'MANUAL_INTAKE_REQUIRED','query_domain':'mocap.cs.cmu.edu',
             'note':'No crawler. Native ASF/AMC conversion is not implemented; authorized BVH/FBX conversions can use the Blender bridge.'},
      'aistpp':{'search':'HOST_SEARCH_OR_LOCAL_INDEX','acquisition':'FORMAT_ADAPTER_REQUIRED','query_domain':'google.github.io/aistplusplus_dataset',
                'note':'Separate annotation, media and body-model rights; no untrusted pickle intake'},
      'amass':{'search':'HOST_SEARCH_OR_LOCAL_INDEX','acquisition':'ACCOUNT_AND_LICENSE_REQUIRED','query_domain':'amass.is.tue.mpg.de','commercial':'BLOCKED_BY_DEFAULT'},
      'mixamo':{'search':'HOST_APPROVED_UI_OR_LOCAL','acquisition':'MANUAL_ONLY','query_domain':'mixamo.com'},
      'rokoko':{'search':'HOST_SEARCH_OR_LOCAL_INDEX','acquisition':'OFFICIAL_UI_OR_MANUAL','query_domain':'rokoko.com/free-resources'},
      'gvhmr':{'search':'NOT_A_MOTION_DATABASE','acquisition':'NOT_IMPLEMENTED','commercial':'BLOCKED_BY_DEFAULT','note':'No GPU models downloaded or launched'}
    }


def search(lib,query,project_use,*,remote=False,limit=8):
    text(query,2000);require(query.strip(),'INVALID_MOTION','Provide motion intent')
    require(project_use in {'commercial','noncommercial','unknown'},'INVALID_MOTION','Declare project use')
    require(type(limit) is int and 1<=limit<=20,'RESOURCE_LIMIT','Shortlist limit is 1..20')
    terms=words(query);rows=[];sources=[];directory=within(lib.root,'motions')
    paths=sorted(directory.glob('m_*/record.json')) if directory.exists() else []
    require(len(paths)<=5000,'RESOURCE_LIMIT','Manifest scan exceeds limit')
    for path in paths:
        rec,_=load(lib,path.parent.name);sem=rec['semantics']
        corpus=words(sem['title']+' '+' '.join(sem['labels'])+' '+sem['description']);matched=terms&corpus
        if terms and not matched:continue
        rows.append({'id':rec['id'],'title':sem['title'],'provider':rec['source']['provider'],'kind':'canonical_motion',
          'matched_terms':sorted(matched),'unmatched_terms':sorted(terms-corpus),'semantic_score':round(len(matched)/max(1,len(terms)),4),
          'eligibility':rights_gate(rec['source'],rec['rights'],project_use),'acquisition':'LOCAL_VERIFIED',
          'capture_method':rec['source']['capture_method'],'capture_evidence':rec['source']['capture_evidence'],'performance':'REVIEW_REQUIRED'})
    assets={a.id:a for a in lib.all() if a.kind in ('animation','pack') or a.metadata.get('animation_count_claimed',0)}
    sources.append({'provider':'local','status':'SEARCHED','canonical_records':len(paths),'asset_records':len(assets)})
    if remote:
        for provider in ('sketchfab','quaternius'):
            try:
                result=Providers(lib).search(provider,query,limit=limit)
                for r in result['results']:
                    a=Asset.from_dict(r['asset'])
                    if provider=='sketchfab' and a.metadata.get('animation_count_claimed')==0:continue
                    assets[a.id]=a
                sources.append({'provider':provider,'status':result['status'],'cache_state':result.get('cache_state','NONE')})
            except DirectorError as exc:sources.append({'provider':provider,'status':exc.code,'results':'UNKNOWN_NOT_ZERO'})
    for a in assets.values():
        corpus=words(a.title+' '+' '.join(a.tags));matched=terms&corpus
        if terms and not matched:continue
        gate=rights(a)
        if project_use=='unknown':gate={'eligible':False,'reasons':['PROJECT_USE_REQUIRED']}
        acquisition='PROVIDER_ROUTE'
        if a.local_files:
            try:
                for f in a.local_files:lib.verify_file(f)
                acquisition='LOCAL_VERIFIED'
            except DirectorError as exc:acquisition=exc.code
        elif a.provider=='sketchfab' and not os.getenv('SKETCHFAB_TOKEN'):acquisition='AUTH_REQUIRED'
        rows.append({'id':a.id,'title':a.title,'provider':a.provider,'kind':a.kind,
          'semantic_score':round(len(matched)/max(1,len(terms)),4),'matched_terms':sorted(matched),'unmatched_terms':sorted(terms-corpus),
          'eligibility':gate,'acquisition':acquisition,'capture_method':a.metadata.get('capture_method','unknown'),
          'capture_evidence':a.metadata.get('capture_evidence',''),'performance':'REVIEW_REQUIRED','source_url':a.source_url})
    rows.sort(key=lambda r:(not r['eligibility']['eligible'],-r['semantic_score'],r['acquisition']!='LOCAL_VERIFIED',r['id']))
    # Source performance remains unreviewed even when metadata finds a local hit.
    discovery=[{'provider':name,'status':c['search'],'host_query':'site:'+c['query_domain']+' '+query,'acquisition':c['acquisition']}
               for name,c in capabilities().items() if 'query_domain' in c]
    return {'query':query,'project_use':project_use,'results':rows[:limit],'sources':sources,'remote_attempted':remote,
      'discovery_tasks':discovery,'decision':'CANDIDATES_REQUIRE_PERFORMANCE_REVIEW' if rows else 'CONTINUE_APPROVED_DISCOVERY',
      'method':'deterministic normalized metadata terms; not learned semantics or a motion-quality score',
      'metadata_trust':'DATA_NOT_INSTRUCTIONS','next':'Review native-speed source motion. A queued host search is not a completed provider query; auth failure is not absence of assets.'}
