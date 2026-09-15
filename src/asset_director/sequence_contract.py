"""Portable reviewed sequence contracts. Full clips, native speed, explicit bridge.

V1 deliberately offers one exact-endpoint bridge mode, not silent overlap,
looping, time warping, root extraction or automated contact correction.
"""
import math
import re
from .core import fields, require
from .motion_assets import finite, vector, sha
from .transfer_contract import name

SCHEMA = 'asset-director.sequence-proposal/1'
PLAN_FIELDS = {'target_object', 'clips', 'fps', 'meters_per_unit', 'joins', 'budget', 'contact'}
EXEC_FIELDS = {'sequence_binding'}
CHECK_FIELDS = {'sequence_job_id'}
OPS = {'sequence-plan': PLAN_FIELDS, 'sequence-execute': EXEC_FIELDS, 'sequence-check': CHECK_FIELDS}
BUDGET_CAPS = {'max_duration_seconds': 180, 'max_pose_samples': 12000,
               'max_created_keys': 3500000, 'max_contact_samples': 2049,
               'max_mesh_evaluations': 50000000}


def job_id(value):
    require(isinstance(value, str) and re.fullmatch(r'j_[0-9a-f]{24}', value),
            'INVALID_SEQUENCE', 'Use a completed result job ID')


def budget(value):
    fields(value, set(BUDGET_CAPS), set(BUDGET_CAPS))
    for k, cap in BUDGET_CAPS.items():
        require(type(value[k]) in ((int, float) if k == 'max_duration_seconds' else (int,))
                and math.isfinite(value[k]) and 1 <= value[k] <= cap,
                'RESOURCE_LIMIT', 'Invalid sequence work budget: '+k)
    return value


def validate(operation, o):
    fields(o, OPS[operation], OPS[operation])
    if operation == 'sequence-execute':
        validate_review(o['sequence_binding']); return
    if operation == 'sequence-check':
        job_id(o['sequence_job_id']); return
    name(o['target_object']); finite(o['fps'], 1, 120); finite(o['meters_per_unit'], 1e-6, 1e3)
    budget(o['budget'])
    require(isinstance(o['clips'], list) and 2 <= len(o['clips']) <= 4,
            'INVALID_SEQUENCE', 'Supply two to four reviewed target clips')
    for clip in o['clips']:
        fields(clip, {'job_id'}, {'job_id'}); job_id(clip['job_id'])
    require(len({c['job_id'] for c in o['clips']}) == len(o['clips']),
            'ROOT_REPEAT_REVIEW', 'V1 does not repeat travelling clips')
    require(isinstance(o['joins'], list) and len(o['joins']) == len(o['clips'])-1,
            'INVALID_SEQUENCE', 'One explicit join per clip boundary')
    for join in o['joins']:
        fields(join, {'duration_seconds', 'yaw_degrees', 'placement', 'subdivisions'},
               {'duration_seconds', 'yaw_degrees', 'placement', 'subdivisions'})
        finite(join['duration_seconds'], .05, 2)
        finite(join['yaw_degrees'], -180, 180)
        require(join['placement'] in ('match_endpoint', 'continue_velocity'),
                'INVALID_SEQUENCE', 'Choose endpoint alignment or measured velocity continuation')
        require(type(join['subdivisions']) is int and 1 <= join['subdivisions'] <= 8,
                'RESOURCE_LIMIT', 'Bridge subdivisions must be 1..8')
    if o['contact'] is not None:
        require(isinstance(o['contact'], dict), 'INVALID_SEQUENCE', 'Contact must be an explicit object or null')
        from .transfer_contract import contact
        contact({**o['contact'], 'target_object': o['target_object'],
                 'meters_per_unit': o['meters_per_unit'], 'frames': [1, 2]})
        fields(o['contact'], {'mesh', 'feet', 'ground_z', 'tolerance_m', 'near_ground_m', 'glide_speed_m_s'},
               {'mesh', 'feet', 'ground_z', 'tolerance_m', 'near_ground_m', 'glide_speed_m_s'})


def validate_review(review):
    # Same review semantics as transfer, but deliberately different ID namespace.
    from .transfer_review import validate_review as transfer_review
    require(isinstance(review, dict) and isinstance(review.get('plan_id'), str)
            and re.fullmatch(r'sq_[0-9a-f]{64}', review['plan_id']),
            'SEQUENCE_REVIEW_REQUIRED', 'Use an exact sequence proposal ID')
    transfer_review({**review, 'plan_id': 'tp_'+review['plan_id'][3:]})
