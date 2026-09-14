"""Immutable, bounded canonical world-motion records; no pickle or model runtime.

Canonical payload: little-endian header, then timestamp + (position, wxyz quaternion)
per joint per sample. A record is evidence, not a claim of realistic performance.
"""
from __future__ import annotations
import copy
import math
from pathlib import Path
import re
import shutil
import struct
import tempfile
from urllib.parse import urlsplit
from .core import DirectorError, atomic_json, canonical, digest, fields, file_hash, load_json, require, text, within

SCHEMA = 'asset-director.motion/1'
MAGIC = b'BADMOT1\0'
HEADER = struct.Struct('<8sII')
POSE = struct.Struct('<7f')
TIME = struct.Struct('<d')
MAX_FRAMES, MAX_JOINTS, MAX_JOINT_FRAMES = 10000, 256, 600000
PROJECT_USES = {'commercial', 'noncommercial', 'unknown'}
CAPTURE_METHODS = {'optical_mocap', 'inertial_mocap', 'video_reconstruction', 'authored', 'generated', 'unknown'}
STATES = {'PLANTED', 'GLIDING', 'AIRBORNE', 'UNKNOWN'}
RESEARCH_PROVIDERS = {'amass', 'gvhmr', 'babel', 'humanml3d'}


def finite(value, low=-1e6, high=1e6):
    require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
            'INVALID_MOTION', 'Expected a finite bounded number')
    return float(value)


def vector(value, size=3, bound=1e4):
    require(isinstance(value, list) and len(value) == size, 'INVALID_MOTION', 'Invalid vector length')
    return [finite(x, -bound, bound) for x in value]


def quaternion(value):
    q = vector(value, 4, 1.001)
    require(abs(sum(x*x for x in q)-1) < .002, 'INVALID_MOTION', 'Quaternion must be unit length (wxyz)')
    return q


def sha(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'INVALID_MOTION', 'Expected SHA256')
    return value


def identifier(value, prefix='m_'):
    require(isinstance(value, str) and re.fullmatch(re.escape(prefix)+'[0-9a-f]{64}', value),
            'INVALID_MOTION', 'Invalid content-addressed identifier')
    return value


def public_url(value):
    text(value, 2048)
    p = urlsplit(value)
    require(p.scheme == 'https' and p.hostname and not p.username and not p.password and not p.query and not p.fragment,
            'INVALID_MOTION', 'Provenance URL must be HTTPS without credentials, query or fragment')
    return value


def validate_rights(rights):
    fields(rights, {'license_id','license_url','evidence','commercial','adaptation','raw_redistribution','attribution'},
           {'license_id','license_url','evidence','commercial','adaptation','raw_redistribution','attribution'})
    text(rights['license_id'], 100)
    public_url(rights['license_url'])
    text(rights['attribution'], 4000)
    require(isinstance(rights['evidence'], list) and 1 <= len(rights['evidence']) <= 8,
            'RIGHTS_EVIDENCE_REQUIRED', 'Retain local terms/permission evidence, not only a URL')
    for f in rights['evidence']:
        fields(f, {'path','sha256','size'}, {'path','sha256','size'})
        sha(f['sha256'])
        require(type(f['size']) is int and 0 < f['size'] <= 2*1024**2, 'INVALID_MOTION', 'Invalid evidence size')
        # Resolve later against the actual library. Validate syntax here as well.
        require(isinstance(f['path'], str) and not f['path'].startswith('/') and '\\' not in f['path'] and ':' not in f['path']
                and all(x not in ('', '.', '..') for x in f['path'].split('/')),
                'UNSAFE_PATH', 'Evidence must be library-relative')
    require(all(rights[k] in ('allowed','denied','unknown') for k in ('commercial','adaptation','raw_redistribution')),
            'INVALID_MOTION', 'Rights fields are allowed/denied/unknown, not inferred booleans')


def rights_gate(source, rights, project_use):
    validate_rights(rights)
    require(project_use in PROJECT_USES, 'INVALID_MOTION', 'Declare project use')
    reasons = []
    if project_use == 'unknown': reasons.append('PROJECT_USE_REQUIRED')
    if rights['adaptation'] != 'allowed': reasons.append('ADAPTATION_NOT_CLEARED')
    if project_use == 'commercial':
        if rights['commercial'] != 'allowed': reasons.append('COMMERCIAL_NOT_CLEARED')
        # These research adapters are not yet licensed for commercial execution.
        # A caller-supplied "allowed" flag alone must not bypass this restriction.
        if source.get('provider','').lower() in RESEARCH_PROVIDERS:
            reasons.append('RESEARCH_PROVIDER_COMMERCIAL_REVIEW_REQUIRED')
    if rights['license_id'].upper() in {'UNKNOWN','EDITORIAL','CC-BY-ND-4.0','CC-BY-NC-ND-4.0'}:
        reasons.append('LICENSE_REVIEW_REQUIRED')
    if project_use == 'commercial' and '-NC' in rights['license_id'].upper():
        reasons.append('NONCOMMERCIAL_LICENSE')
    return {'eligible': not reasons, 'reasons': reasons, 'project_use': project_use,
            'evidence_interpretation': 'HOST_ATTESTED_NOT_LEGAL_CLEARANCE',
            'raw_redistribution': rights['raw_redistribution']}


def validate_skeleton(skeleton):
    fields(skeleton, {'joints','roles','source_fingerprint'}, {'joints','roles','source_fingerprint'})
    sha(skeleton['source_fingerprint'])
    joints = skeleton['joints']
    require(isinstance(joints, list) and 1 <= len(joints) <= MAX_JOINTS, 'RESOURCE_LIMIT', 'Invalid joint count')
    names = []
    roots = 0
    for j in joints:
        fields(j, {'name','parent','head','tail','rotation'}, {'name','parent','head','tail','rotation'})
        text(j['name'], 160)
        require(j['name'].strip() and j['name'] not in names and not any(ord(c)<32 for c in j['name']),
                'INVALID_SKELETON', 'Joint names must be unique nonempty text without control characters')
        require(j['parent'] is None or j['parent'] in names, 'INVALID_SKELETON', 'Parents must precede children; cycles/disconnected parents rejected')
        roots += j['parent'] is None
        names.append(j['name'])
        head, tail = vector(j['head']), vector(j['tail'])
        require(math.dist(head, tail) > 1e-6, 'INVALID_SKELETON', 'Zero-length joints cannot form a Blender rig')
        quaternion(j['rotation'])
    require(roots == 1, 'INVALID_SKELETON', 'Canonical v1 requires one connected skeleton root')
    roles = skeleton['roles']
    require(isinstance(roles, dict) and len(roles) <= MAX_JOINTS and len(set(roles.values())) == len(roles),
            'INVALID_SKELETON', 'Semantic roles must be one-to-one')
    for role, name in roles.items():
        require(isinstance(role,str) and re.fullmatch('[a-z][a-z0-9_]{0,63}',role) and name in names,
                'INVALID_SKELETON', 'Role must refer to an observed joint')
    return names


def validate_record(record):
    fields(record, {'schema','id','source','rights','timing','coordinates','skeleton','payload','semantics','lineage','contact_annotations'},
           {'schema','source','rights','timing','coordinates','skeleton','payload','semantics','lineage','contact_annotations'})
    require(record['schema'] == SCHEMA, 'MOTION_SCHEMA_VERSION', 'Unsupported motion schema')
    source = record['source']
    fields(source, {'provider','source_id','source_url','raw_files','capture_method','capture_evidence'},
           {'provider','source_id','source_url','raw_files','capture_method','capture_evidence'})
    for k in ('provider','source_id','capture_evidence'): text(source[k], 2000)
    public_url(source['source_url'])
    require(source['capture_method'] in CAPTURE_METHODS, 'INVALID_MOTION', 'Unknown capture method')
    require(source['capture_method']=='unknown' or source['capture_evidence'].strip(),
            'CAPTURE_EVIDENCE_REQUIRED', 'A filename does not establish capture provenance')
    require(isinstance(source['raw_files'],list) and 1<=len(source['raw_files'])<=256,
            'INVALID_MOTION', 'Retain original file hashes')
    for f in source['raw_files']:
        fields(f, {'sha256','size'}, {'sha256','size'}); sha(f['sha256'])
        require(type(f['size']) is int and f['size']>0,'INVALID_MOTION','Invalid source size')
    validate_rights(record['rights'])
    names = validate_skeleton(record['skeleton'])
    timing = record['timing']
    fields(timing, {'duration_seconds','sample_count','source_frame_fps','native_capture_fps','sampling'},
           {'duration_seconds','sample_count','source_frame_fps','native_capture_fps','sampling'})
    finite(timing['duration_seconds'],1e-7,600)
    require(type(timing['sample_count']) is int and 2<=timing['sample_count']<=MAX_FRAMES,
            'RESOURCE_LIMIT','Invalid sample count')
    require(timing['sample_count']*len(names)<=MAX_JOINT_FRAMES,'RESOURCE_LIMIT','Joint-sample budget exceeded')
    finite(timing['source_frame_fps'],.01,1000)
    if timing['native_capture_fps'] is not None: finite(timing['native_capture_fps'],.01,1000)
    require(timing['sampling']=='explicit_timestamps','INVALID_MOTION','Do not infer time from frame count')
    coords = record['coordinates']
    fields(coords, {'unit','up','handedness','source_to_canonical','meters_per_source_unit'},
           {'unit','up','handedness','source_to_canonical','meters_per_source_unit'})
    require(coords['unit']=='meter' and coords['up']=='+Z' and coords['handedness']=='right',
            'INVALID_MOTION','Canonical coordinates are right-handed meters, +Z up')
    rotation(coords['source_to_canonical']); finite(coords['meters_per_source_unit'],1e-6,1e3)
    p = record['payload']
    fields(p, {'sha256','size','format'}, {'sha256','size','format'})
    sha(p['sha256']); require(p['format']=='BADMOT1/world-position-quaternion-wxyz', 'INVALID_MOTION','Unsupported numeric payload')
    require(p['size']==HEADER.size+timing['sample_count']*(TIME.size+len(names)*POSE.size),
            'INVALID_MOTION','Payload size disagrees with shape')
    sem=record['semantics']
    fields(sem,{'title','labels','description'},{'title','labels','description'})
    text(sem['title'],500);text(sem['description'],4000)
    require(isinstance(sem['labels'],list) and len(sem['labels'])<=64,'INVALID_MOTION','Invalid labels')
    for t in sem['labels']:text(t,160)
    require(isinstance(record['lineage'],list) and len(record['lineage'])<=32,'INVALID_MOTION','Invalid lineage')
    for parent in record['lineage']:identifier(parent)
    annotations=record['contact_annotations']
    require(isinstance(annotations,list) and len(annotations)<=1000,'RESOURCE_LIMIT','Contact annotation limit')
    previous={}
    for a in annotations:
        fields(a,{'role','start','end','state','evidence'},{'role','start','end','state','evidence'})
        require(a['role'] in record['skeleton']['roles'] and a['state'] in STATES,'INVALID_MOTION','Invalid annotated contact')
        lo=finite(a['start'],0,timing['duration_seconds']); hi=finite(a['end'],0,timing['duration_seconds'])
        text(a['evidence'],1000)
        require(hi>lo and lo>=previous.get(a['role'],-1) and a['evidence'].strip(),
                'INVALID_MOTION','Contact intervals must be ordered, disjoint, and evidence-backed')
        previous[a['role']]=hi
    computed='m_'+digest({k:v for k,v in record.items() if k!='id'})
    require('id' not in record or record['id']==computed,'MOTION_HASH_MISMATCH','Record content no longer matches its identity')
    return computed


def rotation(values):
    r=vector(values,9,1.001); rows=[r[i:i+3] for i in (0,3,6)]
    require(all(abs(sum(a*b for a,b in zip(rows[i],rows[j]))-(i==j))<1e-5 for i in range(3) for j in range(3)),
            'INVALID_MOTION','Source-to-canonical rotation must be orthonormal')
    det=r[0]*(r[4]*r[8]-r[5]*r[7])-r[1]*(r[3]*r[8]-r[5]*r[6])+r[2]*(r[3]*r[7]-r[4]*r[6])
    require(abs(det-1)<1e-5,'INVALID_MOTION','Reflections are not coordinate rotations')
    return r


def write_payload(path, samples, joint_count):
    require(2<=len(samples)<=MAX_FRAMES and 1<=joint_count<=MAX_JOINTS and len(samples)*joint_count<=MAX_JOINT_FRAMES,
            'RESOURCE_LIMIT','Motion sample budget exceeded')
    last=-1.0
    with Path(path).open('xb') as f:
        f.write(HEADER.pack(MAGIC,len(samples),joint_count))
        for i,sample in enumerate(samples):
            fields(sample, {'time','positions','rotations'}, {'time','positions','rotations'})
            t=finite(sample['time'],0,600)
            require(t>last and (i!=0 or t==0), 'INVALID_TIMING','Samples begin at zero and strictly increase')
            last=t
            require(len(sample['positions'])==joint_count and len(sample['rotations'])==joint_count,
                    'INVALID_MOTION','Sample shape mismatch')
            f.write(TIME.pack(t))
            for p,q in zip(sample['positions'],sample['rotations']): f.write(POSE.pack(*vector(p),*quaternion(q)))
    return {'sha256':file_hash(Path(path)),'size':Path(path).stat().st_size,'format':'BADMOT1/world-position-quaternion-wxyz'}


def read_payload(path, record):
    validate_record(record);p=Path(path)
    require(p.is_file() and p.stat().st_size==record['payload']['size'] and file_hash(p)==record['payload']['sha256'],
            'MOTION_PAYLOAD_CHANGED','Canonical numeric payload is missing or changed')
    n=record['timing']['sample_count'];j=len(record['skeleton']['joints'])
    samples=[];last=-1
    with p.open('rb') as f:
        require(HEADER.unpack(f.read(HEADER.size))==(MAGIC,n,j),'INVALID_MOTION','Numeric header/shape mismatch')
        for i in range(n):
            t=TIME.unpack(f.read(TIME.size))[0]
            finite(t,0,600);require(t>last and (i!=0 or t==0),'INVALID_TIMING','Invalid payload timestamps');last=t
            positions=[];rotations=[]
            for _ in range(j):
                values=POSE.unpack(f.read(POSE.size));positions.append(vector(list(values[:3])));rotations.append(quaternion(list(values[3:])))
            samples.append({'time':t,'positions':positions,'rotations':rotations})
    require(abs(last-record['timing']['duration_seconds'])<1e-7,'INVALID_TIMING','Duration differs from final timestamp')
    return samples


def store(lib, record, payload):
    record=copy.deepcopy(record);record['id']=validate_record(record)
    read_payload(payload,record)
    for f in record['rights']['evidence']:lib.verify_file(f)
    for parent in record['lineage']:load(lib,parent)
    root=within(lib.root,'motions');root.mkdir(exist_ok=True)
    target=root/record['id']
    with lib.lock('motion-records'):
        if target.exists():
            old,_=load(lib,record['id']);require(old==record,'MOTION_HASH_MISMATCH','Existing motion differs')
            return {'status':'REUSED','motion_id':record['id'],'record':str(target/'record.json')}
        stage=Path(tempfile.mkdtemp(prefix='.stage-',dir=root))
        try:
            shutil.copyfile(payload,stage/'motion.bin');atomic_json(stage/'record.json',record)
            stage.rename(target)
        finally:
            if stage.exists():shutil.rmtree(stage)
    return {'status':'STORED','motion_id':record['id'],'record':str(target/'record.json')}


def load(lib, motion_id, *, samples=False):
    identifier(motion_id);root=within(lib.root,'motions/'+motion_id)
    record_path=within(lib.root,f'motions/{motion_id}/record.json')
    require(record_path.is_file(),'MOTION_NOT_FOUND','Unknown motion ID')
    r=load_json(record_path,2*1024**2);require(validate_record(r)==motion_id,'MOTION_HASH_MISMATCH','Record identity mismatch')
    for f in r['rights']['evidence']:lib.verify_file(f)
    # Verify both immutable files even when numeric arrays are not requested.
    path=within(lib.root,f'motions/{motion_id}/motion.bin')
    data=read_payload(path,r) if samples else None
    if not samples:
        require(path.is_file() and path.stat().st_size==r['payload']['size'] and file_hash(path)==r['payload']['sha256'],
                'MOTION_PAYLOAD_CHANGED','Numeric payload missing or modified')
    return r,data


def record_files(lib, motion_id):
    load(lib,motion_id)
    return [{'path':f'motions/{motion_id}/{name}','sha256':file_hash(lib.root/'motions'/motion_id/name),
             'size':(lib.root/'motions'/motion_id/name).stat().st_size} for name in ('record.json','motion.bin')]


def collect(lib, jid):
    from .jobs import read_job
    job,path=read_job(lib,jid)
    require(job['state']=='SUCCEEDED' and job['specification']['operation']=='motion-export',
            'MOTION_NOT_READY','Collect a successful motion-export job')
    for f in job['outputs']:lib.verify_file(f)
    return store(lib,load_json(path.parent/'motion.record.json'),path.parent/'motion.bin')
