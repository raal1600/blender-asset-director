"""Scene-independent production contracts. No keyword-to-scene recipes or model calls.

The host interprets creative meaning. This module checks explicit claims against
an observed audit, routes responsibilities, and refuses stale handoffs/reviews.
It is not an agent scheduler, a vision model, or a host permission sandbox.
"""
from __future__ import annotations
import math
from pathlib import Path
from .core import digest, fields, file_hash, require, text

VERSION = 1
CAPABILITY_ROLES = {
    'assets': 'production-design', 'set': 'production-design',
    'reference': 'production-design', 'character-motion': 'performance',
    'object-motion': 'performance', 'camera': 'cinematography',
    'lighting': 'lighting-lookdev', 'materials': 'lighting-lookdev',
    'edit': 'editorial-finishing', 'graphics': 'editorial-finishing',
    'sound': 'editorial-finishing', 'delivery': 'editorial-finishing',
}
ROLES = ('director-producer', 'production-design', 'performance', 'cinematography',
         'lighting-lookdev', 'editorial-finishing', 'continuity-qa')


def intake(goal: str) -> dict:
    text(goal, 8000)
    require(goal.strip(), 'BRIEF_REQUIRED', 'Provide a nonempty creative brief')
    return {'schema_version': VERSION, 'goal': goal,
            'status': 'HOST_INTERPRETATION_REQUIRED',
            'next': 'Inspect the actual scene, then fill the production contract; never infer required assets from a preset scene.',
            'capabilities': sorted(CAPABILITY_ROLES),
            'assumptions': [], 'targets': {}, 'requirements': [], 'shots': [],
            'policy': {'preserve_original_file': True, 'reuse_before_search': True,
                       'paid_assets': 0, 'local_ai': False, 'heavy_gpu_render': False},
            'semantic_analysis': 'NOT_PERFORMED'}


def unique_strings(values, label, limit=256):
    require(isinstance(values, list) and len(values) <= limit, 'INVALID_SCHEMA', label + ' must be a bounded list')
    for value in values:
        text(value, 1000)
        require(value.strip(), 'INVALID_SCHEMA', 'Empty ' + label)
    require(len(set(values)) == len(values), 'INVALID_SCHEMA', 'Duplicate ' + label)
    return set(values)


def audit_objects(audit):
    require(isinstance(audit, dict) and isinstance(audit.get('objects'), list),
            'AUDIT_REQUIRED', 'Use actual inspect/scene-audit output, not a prose description')
    objects = audit['objects']
    require(len(objects) <= 10000, 'RESOURCE_LIMIT', 'Audit is too large')
    result = {}
    for obj in objects:
        require(isinstance(obj, dict), 'INVALID_SCHEMA', 'Invalid audited object')
        name, kind = obj.get('name'), obj.get('type')
        text(name, 1000); text(kind, 100)
        require(name and name not in result, 'AUDIT_AMBIGUOUS', 'Audited object names must be unique')
        result[name] = obj
    return result


def compile_plan(brief: dict, audit: dict) -> dict:
    """Validate host-authored semantics; do not invent objects, suitability or shots."""
    allowed = {'schema_version','goal','deliverable','capabilities','targets','requirements',
               'shots','preserve','assumptions','budget'}
    fields(brief, allowed, {'schema_version','goal','deliverable','capabilities','targets','requirements'})
    require(brief['schema_version'] == VERSION, 'INVALID_SCHEMA', 'Unsupported production contract')
    text(brief['goal'], 8000)
    require(brief['goal'].strip(), 'BRIEF_REQUIRED', 'Empty goal')
    require(brief['deliverable'] in {'still','sequence','scene','asset','repair'}, 'INVALID_SCHEMA', 'Unknown deliverable')
    caps = unique_strings(brief['capabilities'], 'capabilities', 32)
    require(caps and caps <= CAPABILITY_ROLES.keys(), 'CAPABILITY_REQUIRED', 'Select supported capabilities explicitly')
    objects = audit_objects(audit)
    targets = brief['targets']
    require(isinstance(targets, dict) and len(targets) <= 256, 'INVALID_SCHEMA', 'Invalid targets')
    for label, refs in targets.items():
        text(label, 200)
        require(label.strip(), 'INVALID_SCHEMA', 'Empty target label')
        names = unique_strings(refs, 'target references')
        require(names and names <= objects.keys(), 'TARGET_NOT_OBSERVED', 'Target must name actual audited objects')
    preserve = unique_strings(brief.get('preserve', list(objects)), 'preserved objects', 10000)
    require(preserve <= objects.keys(), 'TARGET_NOT_OBSERVED', 'Preserved object was not observed')
    assumptions = brief.get('assumptions', [])
    unique_strings(assumptions, 'assumptions')
    requirements = brief['requirements']
    require(isinstance(requirements, list) and len(requirements) <= 256, 'INVALID_SCHEMA', 'Invalid requirements')
    gaps, blocked, seen = [], [], set()
    for item in requirements:
        fields(item, {'id','kind','query','state','refs','evidence'}, {'id','kind','state','refs','evidence'})
        rid = text(item['id'], 200)
        require(rid and rid not in seen, 'INVALID_SCHEMA', 'Requirement IDs must be unique')
        seen.add(rid)
        require(item['kind'] in {'model','material','hdri','animation','scene','other'}, 'INVALID_SCHEMA', 'Unknown requirement kind')
        refs = unique_strings(item['refs'], 'requirement references')
        require(refs <= objects.keys(), 'TARGET_NOT_OBSERVED', 'Requirement references were not observed')
        evidence = unique_strings(item['evidence'], 'requirement evidence')
        state = item['state']
        require(state in {'reuse','adapt','missing','uncertain'}, 'INVALID_SCHEMA', 'Unknown gap assessment')
        require(evidence, 'EVIDENCE_REQUIRED', 'Record the observation or reason behind every assessment')
        if state in {'reuse','adapt'}:
            require(refs, 'EVIDENCE_REQUIRED', 'Reused/adapted assets need actual object references')
        if state == 'missing':
            require(not refs, 'CONTRADICTORY_GAP', 'An existing unsuitable asset is adapt/uncertain, not absent')
            q = text(item.get('query'), 2000)
            require(q.strip(), 'QUERY_REQUIRED', 'A missing asset needs a host-authored search query')
            if item['kind'] == 'other':
                blocked.append({'id':rid, 'reason':'PROVIDER_CAPABILITY_REVIEW'})
            else:
                gaps.append({'requirement':rid, 'kind':item['kind'], 'query':q,
                             'order':['local','supported_external'], 'status':'NOT_SEARCHED'})
        if state == 'uncertain': blocked.append({'id':rid, 'reason':'ASSESSMENT_REQUIRED'})
    require(not gaps or 'assets' in caps, 'SCOUT_REQUIRED', 'Add assets capability to resolve missing assets')
    shots = brief.get('shots', [])
    require(isinstance(shots, list) and len(shots) <= 100, 'INVALID_SCHEMA', 'Invalid shot plan')
    ids = set()
    for shot in shots:
        fields(shot, {'id','purpose','frames','targets'}, {'id','purpose','frames','targets'})
        sid = text(shot['id'], 200); purpose = text(shot['purpose'], 2000)
        require(sid and sid not in ids and purpose.strip(), 'INVALID_SCHEMA', 'Shot needs unique ID and purpose')
        ids.add(sid)
        bounds = shot['frames']
        require(isinstance(bounds,list) and len(bounds)==2 and all(type(f) is int for f in bounds)
                and 0 <= bounds[0] <= bounds[1] <= 100000, 'INVALID_TIMEBASE', 'Invalid inclusive frame range')
        require(unique_strings(shot['targets'], 'shot targets') <= targets.keys(), 'TARGET_NOT_OBSERVED', 'Unknown semantic target')
    fps = audit.get('fps')
    if shots:
        require(type(fps) in (int,float) and math.isfinite(fps) and fps > 0,
                'INVALID_TIMEBASE', 'Shot timing requires the actual project FPS')
    budget = brief.get('budget', {})
    fields(budget, {'preview_frames','repair_passes','paid_assets','local_ai','heavy_gpu_render'})
    previews, repairs = budget.get('preview_frames', 8), budget.get('repair_passes', 2)
    require(type(previews) is int and 0 <= previews <= 8 and type(repairs) is int and 0 <= repairs <= 2,
            'RESOURCE_LIMIT', 'Baseline allows at most eight CPU frames and two repairs')
    require(budget.get('paid_assets',0) == 0 and budget.get('local_ai',False) is False
            and budget.get('heavy_gpu_render',False) is False, 'BUDGET_NOT_AUTHORIZED', 'Budget exceeds baseline policy')
    selected = {'director-producer','continuity-qa'} | {CAPABILITY_ROLES[c] for c in caps}
    roles = [{'name':r,'module':'references/roles/'+r+'.md',
              'capabilities':sorted(c for c in caps if CAPABILITY_ROLES[c]==r),
              'scene_write':False} for r in ROLES if r in selected]
    limitations = []
    if 'character-motion' in caps and not any(o['type']=='ARMATURE' for o in objects.values()):
        limitations.append('RIG_ASSESSMENT_REQUIRED: no armature was observed; do not substitute a character')
    if 'sound' in caps: limitations.append('Sound is planning-only; no verified audio acquisition/mixing backend')
    return {'schema_version':VERSION, 'plan_id':'p_'+digest({'brief':brief,'audit':audit})[:24],
            'audit_revision':digest(audit), 'status':'CONTRACT_VALIDATED_NOT_EXECUTED',
            'goal':brief['goal'], 'deliverable':brief['deliverable'], 'targets':targets,
            'preserve':sorted(preserve), 'assumptions':assumptions, 'roles':roles,
            'capabilities':sorted(caps), 'requirements':requirements, 'gap_queries':gaps,
            'blocked_requirements':blocked, 'shots':shots, 'fps':fps,
            'budget':{'preview_frames':previews,'repair_passes':repairs,'paid_assets':0,'local_ai':False,'heavy_gpu_render':False},
            'executor':'single controlled Blender writer; specialists propose, do not mutate',
            'limitations':limitations, 'visual_acceptance':'PENDING',
            'assessment_notice':'Semantic assessments are host-authored and require review; validation is not proof of realism.'}


def validate_handoff(plan, proposal, audit):
    """Check a proposal before preparing existing bounded jobs. Does not execute it."""
    fields(proposal, {'plan_id','audit_revision','role','capability','subjects','reason'},
           {'plan_id','audit_revision','role','capability','subjects','reason'})
    require(plan['audit_revision']==digest(audit)==proposal['audit_revision']
            and proposal['plan_id']==plan['plan_id'], 'STALE_HANDOFF', 'Reinspect and recompile against the current scene')
    cap = proposal['capability']
    require(cap in plan['capabilities'] and CAPABILITY_ROLES.get(cap)==proposal['role'],
            'ROLE_SCOPE', 'This role does not own the requested capability')
    subjects = unique_strings(proposal['subjects'], 'proposal subjects')
    named = {name for names in plan['targets'].values() for name in names}
    require(subjects <= named, 'ROLE_SCOPE', 'Change proposal targets objects outside the approved target set')
    require(text(proposal['reason'],2000).strip(), 'EVIDENCE_REQUIRED', 'Explain the scoped change')
    return {'status':'HANDOFF_VALIDATED_NOT_EXECUTED', 'plan_id':plan['plan_id'],
            'audit_revision':plan['audit_revision'], 'executor_required':True}


def validate_review(review, audit, *, vision_available=False):
    fields(review, {'audit_revision','technical','visual','evidence','findings'},
           {'audit_revision','technical','visual','evidence','findings'})
    require(review['audit_revision']==digest(audit), 'STALE_REVIEW', 'Review belongs to a different scene audit')
    require(review['technical'] in {'PASS','FAIL','UNTESTED'} and review['visual'] in {'PASS','FAIL','PENDING'},
            'INVALID_SCHEMA', 'Invalid review status')
    require(isinstance(review['evidence'],list) and len(review['evidence'])<=32, 'INVALID_SCHEMA', 'Invalid review evidence')
    images = 0
    for record in review['evidence']:
        fields(record, {'path','sha256'}, {'path','sha256'})
        p=Path(text(record['path'],4096)).expanduser()
        require(p.is_file() and file_hash(p)==record['sha256'], 'EVIDENCE_CHANGED', 'Review evidence missing or changed')
        images += int(p.suffix.lower() in {'.png','.jpg','.jpeg','.webp'})
    if review['technical']!='UNTESTED':
        require(review['evidence'], 'EVIDENCE_REQUIRED', 'A technical verdict needs evidence')
    if review['visual']!='PENDING':
        require(vision_available and images, 'VISION_REQUIRED', 'Visual verdict needs verified host vision and actual images')
    require(isinstance(review['findings'],list) and len(review['findings'])<=100, 'INVALID_SCHEMA', 'Invalid findings')
    for item in review['findings']:
        fields(item, {'owner','finding','basis'}, {'owner','finding','basis'})
        require(item['owner'] in ROLES and item['basis'] in {'measured','visual','hypothesis'}, 'INVALID_SCHEMA', 'Invalid finding owner/basis')
        require(text(item['finding'],2000).strip(), 'INVALID_SCHEMA', 'Empty finding')
        if item['basis']=='visual': require(vision_available and images, 'VISION_REQUIRED', 'Cannot report unseen observations')
    return {'status':'REVIEW_RECORD_VALIDATED', 'technical':review['technical'], 'visual':review['visual'],
            'human_acceptance':'NOT_ESTABLISHED', 'findings':review['findings'],
            'notice':'Evidence hashes bind files; they do not certify the reviewer conclusion or host vision capability.'}
