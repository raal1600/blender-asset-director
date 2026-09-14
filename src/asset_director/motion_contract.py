"""Portable contracts for canonical motion and source-shaped clay jobs."""
from .core import fields, require, text
from .motion_assets import finite, rotation, validate_rights, identifier, vector

OPS={
 'motion-export':{'target_object','action','slot','start','end','sample_fps','meters_per_unit','source_to_canonical','roles','source','rights','semantics','project_use','native_capture_fps','contact_annotations'},
 'body-audit':{'target_object','meters_per_unit','source_to_canonical','roles'},
 'clay-proxy':{'motion_id','project_use','length_scales','radius_ratio','color'},
 'motion-source':{'motion_id','project_use','fps'},
 'motion-retarget':{'motion_id','project_use','target_object','target_fps','mapping','alignment','pose_space','expected_source_fingerprint','expected_target_fingerprint','target_meters_per_unit'},
}
MUTATIONS={'clay-proxy','motion-source','motion-retarget'}
TARGETS={'motion-export','body-audit','clay-proxy','motion-retarget'}


def validate(op,o):
    require(op in OPS,'UNKNOWN_OPERATION','Unknown motion operation');fields(o,OPS[op])
    if op in ('motion-export','body-audit'):
        fields(o,OPS[op],{'target_object','meters_per_unit','source_to_canonical','roles'})
        text(o['target_object'],160);require(o['target_object'].strip(),'INVALID_MOTION','Name target rig')
        finite(o['meters_per_unit'],1e-6,1e3);rotation(o['source_to_canonical'])
        require(isinstance(o['roles'],dict) and len(o['roles'])<=256,'INVALID_MOTION','Provide reviewed roles')
    if op=='motion-export':
        fields(o,OPS[op],{'action','start','end','sample_fps','source','rights','semantics','project_use'})
        text(o['action'],160);finite(o['start'],-1e6,1e6);finite(o['end'],-1e6,1e6)
        require(o['end']>o['start'],'INVALID_TIMING','Empty source interval');finite(o['sample_fps'],1,240)
        validate_rights(o['rights'])
    if 'motion_id' in o:identifier(o['motion_id'])
    if op in MUTATIONS:fields(o,OPS[op],{'motion_id','project_use'})
    if 'project_use' in o:require(o['project_use'] in ('commercial','noncommercial','unknown'),'INVALID_MOTION','Declare project use')
    if op=='clay-proxy':
        scales=o.get('length_scales',{})
        require(isinstance(scales,dict) and len(scales)<=128,'INVALID_MOTION','Bounded semantic segment scales required')
        for role,scale in scales.items():text(role,64);finite(scale,.5,2)
        finite(o.get('radius_ratio',.1),.025,.3)
        color=vector(o.get('color',[.45,.45,.45]));require(all(0<=v<=1 for v in color),'INVALID_MOTION','Invalid clay color')
    if op=='motion-source':fields(o,OPS[op],{'fps'});finite(o['fps'],1,240)
    if op=='motion-retarget':
        fields(o,OPS[op],{'target_object','target_fps','mapping','alignment','pose_space','expected_source_fingerprint','expected_target_fingerprint','target_meters_per_unit'})
        finite(o['target_fps'],1,240)
        finite(o['target_meters_per_unit'],1e-6,1e3)
        from .motion_assets import sha
        for k in ('expected_source_fingerprint','expected_target_fingerprint'):sha(o[k])
        require(isinstance(o['mapping'],dict) and o['mapping'] and len(set(o['mapping'].values()))==len(o['mapping']),
                'MAPPING_REVIEW_REQUIRED','Provide a one-to-one reviewed mapping')
        require(isinstance(o['alignment'],dict) and o['alignment'],'ALIGNMENT_REVIEW_REQUIRED','Provide target reference bases')
        from .pose_contract import validate as validate_pose
        validate_pose(o['pose_space'])
