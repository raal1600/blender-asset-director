"""Fixed kinematic gates for reviewed upright rigs; no physics certification.

Thresholds belong to a versioned preset, fixed before candidate selection.
Missing measurements never become zero-error passes. Raw and corrected stages
are separate; candidate rank is meaningful only after every hard gate passes.
"""
import math
from .core import require
from . import sequence_math as qm

PRESET = 'upright-grounded-kinematic-v2'


def trajectory_metrics(rotations, roots, seconds):
    """Finite-interval kinematics of uniformly timed world rotations/roots.

    Angular increments use one common world frame. These are stage diagnostics,
    not endpoint derivatives, contacts, dynamics, or final baked acceptance.
    """
    require(len(rotations)==len(roots)>=3 and seconds>0,'MOTION_BRICKS_QUALITY_DATA','Stage metrics need at least three matching timed poses')
    rate=(len(roots)-1)/seconds
    velocity=[qm.mul(qm.sub(b,a),rate) for a,b in zip(roots,roots[1:])]
    angular={name:[qm.mul(qm.qlog(qm.qmul(qm.unit(b[name]),qm.inverse(qm.unit(a[name])))),rate)
                   for a,b in zip(rotations,rotations[1:])] for name in rotations[0]}
    return {'sampling_hz':rate,'samples':len(roots),'rotation_frame':'common world','position_units':'metres',
            'root_speed_m_s':max(qm.norm(v) for v in velocity),
            'root_acceleration_m_s2':max(qm.norm(qm.sub(b,a))*rate for a,b in zip(velocity,velocity[1:])),
            'joint_speed_deg_s':max(math.degrees(qm.norm(v)) for values in angular.values() for v in values),
            'joint_acceleration_deg_s2':max(math.degrees(qm.norm(qm.sub(b,a))*rate) for values in angular.values() for a,b in zip(values,values[1:])),
            'contact_metrics':'UNAVAILABLE at this stage; evaluated baked support validation is separate',
            'physical_feasibility':'NOT_DEMONSTRATED'}


def thresholds(height):
    require(type(height) in (int,float) and math.isfinite(height) and .3 <= height <= 5,
            'MOTION_BRICKS_REFERENCE_HEIGHT','Prepare the rig with a fixed reviewed full-character height before accepting candidates')
    return {'position_m':.001*height,'orientation_deg':1.,'root_velocity_m_s':.05*height,
            'angular_velocity_deg_s':5.,'planted_drift_m':.01*height,'penetration_m':.005*height,
            'root_acceleration_m_s2':25*height,'joint_acceleration_deg_s2':6000.,
            'root_speed_m_s':3*height,'joint_speed_deg_s':720.,
            'root_correction_m':.1*height,'foot_correction_m':.15*height,
            'rotation_correction_max_deg':45.,'rotation_correction_rms_deg':15.,
            'knee_flexion_min_deg':0.,'knee_flexion_max_deg':170.}


def correction_metrics(raw, corrected, raw_roots, corrected_roots):
    require(len(raw)==len(corrected)==len(raw_roots)==len(corrected_roots)>1,
            'MOTION_BRICKS_QUALITY_DATA','Compare correction stages at identical timestamps')
    angles=[];largest=None
    for index,(before,after) in enumerate(zip(raw,corrected)):
        require(before.keys()==after.keys(),'MOTION_BRICKS_QUALITY_DATA','Correction stages have different joints')
        for name in before:
            angle=math.degrees(qm.norm(qm.qlog(qm.qmul(qm.inverse(qm.unit(before[name]['q'])),qm.unit(after[name]['q'])))))
            angles.append(angle)
            if largest is None or angle>largest['degrees']:largest={'joint':name,'sample_index':index,'degrees':angle}
    return {'rotation_correction_max_deg':max(angles),
            'rotation_correction_rms_deg':math.sqrt(sum(v*v for v in angles)/len(angles)),
            'root_correction_m':max(math.dist(a,b) for a,b in zip(raw_roots,corrected_roots)),
            'largest_rotation_correction':largest}


def gate(metrics, limits, required):
    failures=[]
    for key in required:
        value=metrics.get(key)
        if type(value) not in (int,float) or not math.isfinite(value):failures.append({'metric':key,'reason':'unavailable','limit':limits[key]})
        elif value > limits[key]:failures.append({'metric':key,'value':value,'limit':limits[key]})
    return failures


def contact_runs(samples, fps, height, ground):
    """Proposal from evaluated geometry only; a fixed landmark per side, no names.

    Samples contain side -> {point:[x,y,z], low:z}. Grounded speed eligibility
    and >=0.08 s windows are evidence, never backend-supplied contact labels.
    """
    require(fps>0 and len(samples)>2,'MOTION_BRICKS_QUALITY_DATA','Contact analysis requires physical sampling times')
    result=[]
    for side in ('left','right'):
        start=None
        for i,row in enumerate(samples):
            speed=math.dist(samples[max(0,i-1)][side]['point'][:2],samples[min(len(samples)-1,i+1)][side]['point'][:2])*fps/(min(len(samples)-1,i+1)-max(0,i-1))
            planted=abs(row[side]['low']-ground)<=.005*height and abs(row[side]['point'][2]-ground)<=.005*height and speed<=.12*height
            if planted and start is None:start=i
            if start is not None and (not planted or i==len(samples)-1):
                end=i if planted else i-1
                if (end-start)/fps>=.08-1e-9:
                    points=[v[side]['point'] for v in samples[start:end+1]]
                    drift=max(math.dist(a[:2],b[:2]) for a in points for b in points)
                    result.append({'side':side,'start_index':start,'end_index':end,'drift_m':drift,
                                   'origin':'evaluated-geometry-proposal','confidence':'kinematic-only'})
                start=None
    return result
