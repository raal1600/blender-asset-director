"""Reviewed hinge planes for rigs whose straight rest limbs are ambiguous.

Motion measurements propose an anatomical calibration. They do not change the
rest pose, native channels, model interface, or any generated quality threshold.
"""
import math
import re
from .core import require

SCHEMA = 'motion-bricks.hinge-calibration.v1'
MAX_DISPERSION_DEGREES = 5.


def plane_summary(observations):
    require(isinstance(observations,list) and 8<=len(observations)<=128,
            'MOTION_BRICKS_HINGE_CALIBRATION','At least eight non-singular measured elbow poses are required per side')
    normals=[];previous=-math.inf
    for row in observations:
        require(isinstance(row,dict) and set(row)=={'frame','bend_degrees','normal_world_rest'},
                'MOTION_BRICKS_HINGE_CALIBRATION','Malformed measured hinge observation')
        frame,bend,normal=row['frame'],row['bend_degrees'],row['normal_world_rest']
        require(type(frame) in (int,float) and math.isfinite(frame) and frame>previous
                and type(bend) in (int,float) and 10<=bend<=165
                and isinstance(normal,list) and len(normal)==3
                and all(type(v) in (int,float) and math.isfinite(v) for v in normal),
                'MOTION_BRICKS_HINGE_CALIBRATION','Use ordered physical samples with non-singular elbow bends and finite normals')
        length=math.sqrt(sum(v*v for v in normal))
        require(abs(length-1)<.001,'MOTION_BRICKS_HINGE_CALIBRATION','Measured hinge normals must be unit vectors')
        normals.append([v/length for v in normal]);previous=frame
    mean=[sum(v[i] for v in normals)/len(normals) for i in range(3)];length=math.sqrt(sum(v*v for v in mean))
    require(length>.9,'MOTION_BRICKS_HINGE_CALIBRATION','Measured bending planes disagree; review a different calibration interval')
    mean=[v/length for v in mean]
    maximum=max(math.degrees(math.acos(max(-1.,min(1.,sum(a*b for a,b in zip(mean,v)))))) for v in normals)
    require(maximum<=MAX_DISPERSION_DEGREES,'MOTION_BRICKS_HINGE_CALIBRATION',
            'Elbow bending plane varies by more than 5 degrees; this interval does not establish a supported hinge calibration')
    return {'normal_world_rest':mean,'maximum_angle_degrees':maximum,'samples':len(normals)}


def validate(value,rest_identity,mapping_sha256):
    fields={'schema','rest_identity','mapping_sha256','source_action_sha256','source_slot_identifier',
            'source_fps','source_range','observations','reviewed'}
    require(isinstance(value,dict) and set(value)==fields and value['schema']==SCHEMA and value['reviewed'] is True,
            'MOTION_BRICKS_HINGE_CALIBRATION','Supply the explicitly reviewed hinge-calibration evidence, not an unreviewed proposal')
    require(value['rest_identity']==rest_identity and value['mapping_sha256']==mapping_sha256,
            'MOTION_BRICKS_HINGE_CALIBRATION','Rest geometry or role mapping changed after hinge review')
    require(isinstance(value['source_action_sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['source_action_sha256'])
            and isinstance(value['source_slot_identifier'],str) and 0<len(value['source_slot_identifier'])<=255
            and type(value['source_fps']) in (int,float) and 1<=value['source_fps']<=120,
            'MOTION_BRICKS_HINGE_CALIBRATION','Calibration must retain its actual Action content, slot and physical timebase')
    interval=value['source_range']
    require(isinstance(interval,list) and len(interval)==2 and all(type(v) in (int,float) and math.isfinite(v) for v in interval)
            and -100000<=interval[0]<interval[1]<=100000
            and isinstance(value['observations'],dict) and set(value['observations'])=={'left','right'},
            'MOTION_BRICKS_HINGE_CALIBRATION','Calibration interval and both anatomical sides are required')
    result={side:plane_summary(rows) for side,rows in value['observations'].items()}
    require(all(interval[0]<=row['frame']<=interval[1] for rows in value['observations'].values() for row in rows),
            'MOTION_BRICKS_HINGE_CALIBRATION','Hinge samples are outside the selected calibration interval')
    return result
