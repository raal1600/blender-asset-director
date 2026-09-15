"""Reviewed Mixamo project-use policy; no downloader, legal inference or DRM.

Evidence + explicit user attestation authorize an exact current snapshot or an
explicitly opted-in future inbox. Immutable per-file grants follow derivatives.
"""
from __future__ import annotations
from datetime import datetime
import re
from .core import DirectorError, atomic_json, digest, fields, file_hash, load_json, require, text, within

LICENSE = 'LicenseRef-Adobe-Mixamo'
POLICY = 'adobe-mixamo-project-v1'
FAQ = 'https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html'
TERMS = 'https://www.adobe.com/legal/terms.html'
SCOPE = 'personal-commercial-projects-no-standalone-redistribution'
SCENE_KEY = 'bad_project_license_grants'


def identifier(value, prefix):
    require(isinstance(value, str) and re.fullmatch(prefix+'[0-9a-f]{64}', value),
            'LICENSE_REVIEW_INVALID', 'Invalid content-addressed license identifier')
    return value


def file_ref(lib, path):
    p = within(lib.root, path)
    require(p.is_file(), 'LICENSE_EVIDENCE_MISSING', 'Retained evidence is missing')
    return {'path':path, 'sha256':file_hash(p), 'size':p.stat().st_size}


def put(lib, directory, prefix, data):
    data = dict(data); data['id'] = prefix+digest(data)
    path = within(lib.root, 'licenses/'+directory+'/'+data['id']+'.json')
    if path.exists(): require(load_json(path)==data, 'LICENSE_EVIDENCE_CHANGED', 'Immutable review/grant changed')
    else: atomic_json(path, data)
    return data


def create_review(lib, root, request, hashes):
    required = {'policy','reviewer','reviewed_at','official_downloads_attested','terms_reviewed','include_future_files','evidence'}
    fields(request, required, required)
    require(root['provider']=='mixamo' and request['policy']==POLICY,
            'LICENSE_PROFILE_UNSUPPORTED', 'Only the reviewed Mixamo profile is implemented here')
    text(request['reviewer'], 200); text(request['reviewed_at'], 100)
    require(request['reviewer'].strip(), 'LICENSE_REVIEW_REQUIRED', 'Identify the approving user/reviewer')
    try:
        date = datetime.fromisoformat(request['reviewed_at'].replace('Z','+00:00'))
        require(date.tzinfo is not None, 'LICENSE_REVIEW_REQUIRED', 'Use a timezone-aware review date')
    except ValueError: raise DirectorError('LICENSE_REVIEW_REQUIRED', 'Invalid review date') from None
    require(request['official_downloads_attested'] is True and request['terms_reviewed'] is True
            and type(request['include_future_files']) is bool,
            'LICENSE_REVIEW_REQUIRED', 'Actual origin/terms approval and explicit future-file scope are required')
    evidence = request['evidence']
    require(isinstance(evidence,list) and len(evidence)==2, 'LICENSE_EVIDENCE_MISSING', 'Retain FAQ and applicable terms evidence')
    for e in evidence:
        fields(e, {'url','file'}, {'url','file'}); fields(e['file'], {'path','sha256','size'}, {'path','sha256','size'})
        require(type(e['file']['size']) is int and 0<e['file']['size']<=2*1024**2,
                'LICENSE_EVIDENCE_MISSING', 'Evidence must be bounded UTF-8 text')
        lib.verify_file(e['file']).read_text(encoding='utf-8-sig')
    require({e['url'] for e in evidence}=={FAQ,TERMS}, 'LICENSE_EVIDENCE_MISSING', 'Expected official Adobe evidence URLs')
    hashes = sorted(set(hashes))
    require(all(re.fullmatch('[0-9a-f]{64}',h) for h in hashes), 'LICENSE_REVIEW_INVALID', 'Invalid source hashes')
    require(hashes or request['include_future_files'], 'LICENSE_REVIEW_REQUIRED', 'Empty current-files approval grants nothing')
    return put(lib, 'reviews', 'lr_', {'schema':'asset-director.provider-review/1', 'root_id':root['id'],
        'provider':'mixamo', 'scope':SCOPE, **request, 'authorized_hashes':hashes,
        'provenance_basis':'USER_ATTESTED_NOT_PROVIDER_VERIFIED'})


def load_review(lib, review_id):
    identifier(review_id,'lr_'); p=within(lib.root,'licenses/reviews/'+review_id+'.json')
    require(p.is_file(), 'LICENSE_REVIEW_REQUIRED', 'Provider review missing')
    r=load_json(p,2*1024**2)
    require(isinstance(r,dict) and r.get('id')==review_id=='lr_'+digest({k:v for k,v in r.items() if k!='id'})
            and r.get('schema')=='asset-director.provider-review/1' and r.get('policy')==POLICY
            and r.get('provider')=='mixamo' and r.get('scope')==SCOPE
            and r.get('official_downloads_attested') is True and r.get('terms_reviewed') is True,
            'LICENSE_REVIEW_INVALID', 'Review hash/profile changed')
    require(not within(lib.root,'licenses/revocations/'+review_id+'.json').exists(), 'LICENSE_REVOKED', 'Provider review was revoked')
    require({e['url'] for e in r['evidence']}=={FAQ,TERMS}, 'LICENSE_REVIEW_INVALID', 'Evidence URLs changed')
    for e in r['evidence']: lib.verify_file(e['file'])
    return r


def revoke(lib, review_id, reason):
    identifier(review_id,'lr_'); text(reason,1000)
    require(reason.strip(), 'LICENSE_REVIEW_REQUIRED', 'Record a revocation reason')
    p=within(lib.root,'licenses/revocations/'+review_id+'.json')
    if p.exists(): return {'status':'ALREADY_REVOKED','review_id':review_id}
    load_review(lib,review_id); atomic_json(p,{'review_id':review_id,'reason':reason})
    return {'status':'REVOKED','review_id':review_id,'existing_files_deleted':False}


def bind_asset(lib, asset, review_id):
    r=load_review(lib,review_id); local=asset.metadata.get('local_motion',{})
    require(local.get('root_id')==r['root_id'] and local.get('provider_hint')=='mixamo'
            and asset.local_files and asset.formats==['.fbx'],
            'LICENSE_SCOPE_MISMATCH','Review covers only this attested inbox FBX')
    for f in asset.local_files:
        lib.verify_file(f)
        require(r['include_future_files'] or f['sha256'] in r['authorized_hashes'],
                'LICENSE_REVIEW_REQUIRED','New content is outside the approved snapshot')
    grant=put(lib,'grants','lg_',{'schema':'asset-director.asset-grant/1','review_id':review_id,
        'policy':POLICY,'scope':SCOPE,'asset_id':asset.id,'files':asset.local_files})
    asset.license_id=LICENSE; asset.license_url=FAQ; asset.price=0; asset.evidence='user_attested'
    asset.author='Adobe Mixamo (user-attested acquisition)'; asset.metadata['license_grant']=grant['id']
    return grant


def load_grant(lib, grant_id):
    identifier(grant_id,'lg_'); p=within(lib.root,'licenses/grants/'+grant_id+'.json')
    require(p.is_file(),'LICENSE_REVIEW_REQUIRED','Per-asset grant missing')
    g=load_json(p,2*1024**2)
    require(isinstance(g,dict) and g.get('id')==grant_id=='lg_'+digest({k:v for k,v in g.items() if k!='id'})
            and g.get('schema')=='asset-director.asset-grant/1' and g.get('policy')==POLICY and g.get('scope')==SCOPE,
            'LICENSE_REVIEW_INVALID','Grant hash/profile changed')
    r=load_review(lib,g['review_id'])
    require(isinstance(g.get('files'),list) and 1<=len(g['files'])<=256,'LICENSE_REVIEW_INVALID','Invalid file scope')
    for f in g['files']:
        lib.verify_file(f)
        require(r['include_future_files'] or f['sha256'] in r['authorized_hashes'],'LICENSE_SCOPE_MISMATCH','Grant exceeds original approval')
    return g


def asset_gate(lib, asset, purpose='project_use'):
    reasons=[]; gid=asset.metadata.get('license_grant')
    if purpose!='project_use': reasons.append('RAW_REDISTRIBUTION_NOT_AUTHORIZED')
    try:
        require(lib is not None and gid,'LICENSE_REVIEW_REQUIRED','Reviewed Mixamo grant required')
        g=load_grant(lib,gid)
        require(g['files']==asset.local_files and (asset.id==g['asset_id'] or asset.metadata.get('parent_asset')==g['asset_id'])
                and asset.license_id==LICENSE,'LICENSE_SCOPE_MISMATCH','Do not relabel grants or apply to other bytes')
    except DirectorError as e: reasons.append(e.code)
    return {'eligible':not reasons,'reasons':reasons,'raw_redistribution':'DENIED','license_grant':gid,
        'scope':SCOPE,'provenance':'USER_ATTESTED','commercial_clearance':'NOT_A_LEGAL_CLEARANCE',
        'third_party_rights':'NOT_VERIFIED','attribution_required':False}


def dependencies(lib, grant_ids):
    require(isinstance(grant_ids,list) and len(grant_ids)<=32,'RESOURCE_LIMIT','Project grant limit is 32')
    found={}
    for gid in sorted(set(grant_ids)):
        g=load_grant(lib,gid); r=load_review(lib,g['review_id'])
        for f in [file_ref(lib,'licenses/grants/'+gid+'.json'),file_ref(lib,'licenses/reviews/'+r['id']+'.json'),
                  *[e['file'] for e in r['evidence']]]: found[f['path']]=f
    return [found[p] for p in sorted(found)]


def derivation(lib, sha):
    identifier(sha,''); p=within(lib.root,'licenses/derived/'+sha+'.json')
    if not p.exists(): return []
    r=load_json(p,65536)
    require(r.get('sha256')==sha and r.get('schema')=='asset-director.project-lineage/1',
            'LICENSE_SCOPE_MISMATCH','Invalid derivative lineage')
    dependencies(lib,r['grants']); return r['grants']


def retain_derivation(lib, path, grants):
    if not grants: return
    dependencies(lib,grants); sha=file_hash(path); p=within(lib.root,'licenses/derived/'+sha+'.json')
    r={'schema':'asset-director.project-lineage/1','sha256':sha,'grants':sorted(set(grants)),'raw_redistribution':'DENIED'}
    if p.exists(): require(load_json(p)==r,'LICENSE_SCOPE_MISMATCH','Derivative scope conflict')
    else: atomic_json(p,r)


def canonical_rights(lib, grants):
    evidence=dependencies(lib,grants)
    require(0<len(evidence)<=8,'RESOURCE_LIMIT','Split canonical exports with many license reviews')
    return {'license_id':LICENSE,'license_url':FAQ,'evidence':evidence,'commercial':'allowed',
            'adaptation':'allowed','raw_redistribution':'denied','attribution':'Adobe Mixamo; reviewed private project use',
            'review_grants':sorted(set(grants))}


def validate_motion_scope(lib, source, rights):
    gids=rights.get('review_grants',[])
    require(lib is not None and gids and rights['license_id']==LICENSE and rights['raw_redistribution']=='denied',
            'LICENSE_REVIEW_REQUIRED','Restricted motion needs its project-use grants')
    dependencies(lib,gids)
    originals={f['sha256'] for gid in gids for f in load_grant(lib,gid)['files']}
    for f in source.get('raw_files',[]):
        scope=set(gids) if f['sha256'] in originals else set(derivation(lib,f['sha256']))
        require(set(gids)<=scope,'LICENSE_SCOPE_MISMATCH','Motion source is not bound to these grants')
