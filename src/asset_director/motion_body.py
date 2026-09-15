"""Stable rest-anatomy measurements and reviewable, rig-pair-specific scale profiles.

No body identity, skin, mass, or center-of-mass is inferred from bone lengths.
"""
from __future__ import annotations
import math
from .core import digest, fields, require
from .motion_assets import finite, validate_skeleton

PROFILE_SCHEMA = 'asset-director.retarget-profile/1'


def body_profile(skeleton):
    validate_skeleton(skeleton)
    bones={j['name']:j for j in skeleton['joints']}; roles=skeleton['roles']
    lengths={role:math.dist(bones[name]['head'],bones[name]['tail']) for role,name in roles.items()}
    chains={}
    for side in ('l','r'):
        for label,a,b,end in [('leg','thigh','calf','foot'),('arm','upperarm','forearm','hand')]:
            keys=[a+'_'+side,b+'_'+side,end+'_'+side]
            if not all(k in roles for k in keys):continue
            # Segment lengths are head-to-head for chains, not arbitrary bone tails.
            first,second,last=(bones[roles[k]] for k in keys)
            def ancestor(child,parent):
                p=bones[child]['parent']
                while p is not None:
                    if p==parent:return True
                    p=bones[p]['parent']
                return False
            require(ancestor(second['name'],first['name']) and ancestor(last['name'],second['name']),
                    'BODY_CHAIN_REVIEW_REQUIRED','Semantic limb roles do not follow the observed hierarchy')
            parts=[math.dist(first['head'],second['head']),math.dist(second['head'],last['head'])]
            require(min(parts)>1e-5,'BODY_CHAIN_REVIEW_REQUIRED','Degenerate anatomical chain')
            chains[label+'_'+side]={'segments_m':parts,'length_m':sum(parts)}
    widths={}
    for prefix,label in [('upperarm','shoulder_width_m'),('thigh','hip_width_m')]:
        if all(prefix+'_'+s in roles for s in ('l','r')):
            widths[label]=math.dist(*(bones[roles[prefix+'_'+s]]['head'] for s in ('l','r')))
    return {'schema':'asset-director.body-profile/1','skeleton_hash':digest(skeleton),
            'rig_fingerprint':skeleton['source_fingerprint'],'method':'measured_stable_rest_skeleton',
            'bone_lengths_m':lengths,'chains':chains,'widths':widths,
            'missing_chains':sorted({'leg_l','leg_r','arm_l','arm_r'}-chains.keys()),
            'not_inferred':['body mass','skin surface','sole height','identity','capture confidence']}


def build_profile(source,target,root_mode='morphology_scaled'):
    s=body_profile(source);t=body_profile(target)
    require(root_mode in ('preserve_world','morphology_scaled'),'INVALID_PROFILE','Unsupported root policy')
    shared=sorted(set(source['roles']) & set(target['roles']))
    mapping={source['roles'][r]:target['roles'][r] for r in shared}
    ratios={k:t['chains'][k]['length_m']/s['chains'][k]['length_m'] for k in s['chains'] if k in t['chains']}
    if root_mode=='morphology_scaled':
        require(all(k in ratios for k in ('leg_l','leg_r')),'BODY_PROFILE_INCOMPLETE','Both measured leg chains are required')
        ratio=sum(t['chains'][k]['length_m'] for k in ('leg_l','leg_r'))/sum(s['chains'][k]['length_m'] for k in ('leg_l','leg_r'))
        finite(ratio,.25,4)
        require(abs(ratios['leg_l']-ratios['leg_r'])/ratio<=.20,
                'BODY_ASYMMETRY_REVIEW','Left/right leg ratios differ by more than 20%; do not choose one silently')
    else:ratio=1.0
    result={'schema':PROFILE_SCHEMA,'source_fingerprint':source['source_fingerprint'],
            'target_fingerprint':target['source_fingerprint'],'source_skeleton_hash':digest(source),
            'target_skeleton_hash':digest(target),'mapping':mapping,'chain_ratios':ratios,
            'root_mode':root_mode,'suggested_translation_scale_xyz':[ratio,ratio,ratio],
            'scale_basis':'bilateral hip-to-knee-to-ankle reach' if root_mode=='morphology_scaled' else 'preserve world distance',
            'status':'ALIGNMENT_REVIEW_REQUIRED','required_next':['review mapping','supply world alignment',
                'supply target pose-basis alignment','choose current target origin','review contacts after transfer'],
            'warning':'Root scale is a proposal, not per-limb IK or a contact guarantee.'}
    result['id']='rp_'+digest(result)
    return result


def validate_profile(profile,source_fingerprint=None,target_fingerprint=None):
    require(isinstance(profile,dict) and profile.get('schema')==PROFILE_SCHEMA,'INVALID_PROFILE','Unsupported retarget profile')
    require(profile.get('id')=='rp_'+digest({k:v for k,v in profile.items() if k!='id'}),
            'STALE_RETARGET_PROFILE','Retarget profile contents changed')
    if source_fingerprint is not None:
        require(profile['source_fingerprint']==source_fingerprint,'STALE_RETARGET_PROFILE','Source rig changed')
    if target_fingerprint is not None:
        require(profile['target_fingerprint']==target_fingerprint,'STALE_RETARGET_PROFILE','Target rig changed')
    return profile
