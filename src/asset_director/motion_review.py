"""Timestamp-aware diagnostics and evidence receipts, never a naturalness oracle."""
from collections import Counter
import math
from .core import atomic_json, digest, fields, require, text, within, load_json
from .motion_assets import finite, load

DEFAULTS={'contact_height_m':.025,'airborne_height_m':.06,'stationary_speed_mps':.025,
          'moving_speed_mps':.08,'vertical_speed_mps':.12,'min_state_seconds':.06}


def contact_states(times,positions,*,ground_z,sole_offset,thresholds=None):
    require(len(times)==len(positions)>=2,'INVALID_MOTION','Need matched timestamps/positions')
    require(all(b>a for a,b in zip(times,times[1:])),'INVALID_TIMING','Times must increase')
    values=dict(DEFAULTS);values.update(thresholds or {});fields(values,set(DEFAULTS),set(DEFAULTS))
    for v in values.values():finite(v,0,10)
    require(values['contact_height_m']<values['airborne_height_m'] and values['stationary_speed_mps']<values['moving_speed_mps'],
            'INVALID_MOTION','Hysteresis thresholds must be ordered')
    finite(ground_z);finite(sole_offset,-2,2)
    states=[];current='UNKNOWN';pending=None;since=0;speed=[];clearance=[]
    for i,(time,p) in enumerate(zip(times,positions)):
        dt=times[i]-times[i-1] if i else times[1]-times[0];prev=positions[i-1] if i else p
        horizontal=math.hypot(p[0]-prev[0],p[1]-prev[1])/dt;vz=abs(p[2]-prev[2])/dt
        h=p[2]-sole_offset-ground_z;speed.append(horizontal);clearance.append(h)
        if i==0:candidate='UNKNOWN'
        elif h>values['airborne_height_m']:candidate='AIRBORNE'
        elif h>values['contact_height_m'] or h < -values['contact_height_m'] or vz>values['vertical_speed_mps']:candidate='UNKNOWN'
        elif horizontal<=values['stationary_speed_mps']:candidate='PLANTED_CANDIDATE'
        elif horizontal>=values['moving_speed_mps']:candidate='GLIDING_CANDIDATE'
        else:candidate=current if current in ('PLANTED_CANDIDATE','GLIDING_CANDIDATE') else 'UNKNOWN'
        if candidate==current:pending=None
        elif candidate in ('UNKNOWN','AIRBORNE'):current=candidate;pending=None
        elif pending!=candidate:pending=candidate;since=time
        elif time-since>=values['min_state_seconds']:current=candidate;pending=None
        states.append(current)
    intervals=[]
    for i,state in enumerate(states):
        if not intervals or intervals[-1]['state']!=state:intervals.append({'state':state,'start':times[i],'end':times[i],'samples':1})
        else:intervals[-1]['end']=times[i];intervals[-1]['samples']+=1
    return {'intervals':intervals,'state_counts':dict(Counter(states)),
        'min_clearance_m':min(clearance),'max_clearance_m':max(clearance),'max_horizontal_speed_mps':max(speed),
        'thresholds':values,'intent':'UNKNOWN','automatic_pose_correction':False}


def diagnostics(record,samples,options=None):
    options=options or {};fields(options,{'ground_z','sole_offsets','thresholds'})
    times=[s['time'] for s in samples];indices={j['name']:i for i,j in enumerate(record['skeleton']['joints'])}
    roles=record['skeleton']['roles'];contacts={}
    if 'ground_z' in options:
        finite(options['ground_z']);offsets=options.get('sole_offsets',{})
        require(isinstance(offsets,dict) and set(offsets)<={'foot_l','foot_r'},'INVALID_MOTION','Calibrate sole offsets by foot role')
        for role in ('foot_l','foot_r'):
            if role in roles and role in offsets:
                contacts[role]=contact_states(times,[s['positions'][indices[roles[role]]] for s in samples],
                    ground_z=options['ground_z'],sole_offset=offsets[role],thresholds=options.get('thresholds'))
    root_name=roles.get('hips') or next(j['name'] for j in record['skeleton']['joints'] if j['parent'] is None)
    positions=[s['positions'][indices[root_name]] for s in samples]
    velocity=[[(b[k]-a[k])/(t2-t1) for k in range(3)] for a,b,t1,t2 in zip(positions,positions[1:],times,times[1:])]
    mid=[(a+b)/2 for a,b in zip(times,times[1:])]
    acc=[[(b[k]-a[k])/(t2-t1) for k in range(3)] for a,b,t1,t2 in zip(velocity,velocity[1:],mid,mid[1:])]
    max_angular=0
    for a,b in zip(samples,samples[1:]):
        for qa,qb in zip(a['rotations'],b['rotations']):
            dot=abs(sum(x*y for x,y in zip(qa,qb)))/math.sqrt(sum(x*x for x in qa)*sum(x*x for x in qb))
            max_angular=max(max_angular,2*math.acos(min(1.0,dot))/(b['time']-a['time']))
    annotations=[]
    for a in record['contact_annotations']:
        idx=indices[roles[a['role']]];points=[s['positions'][idx] for s in samples if a['start']<=s['time']<a['end']]
        annotations.append({**a,'measured_samples':len(points),
           'horizontal_excursion_m':max((math.hypot(p[0]-points[0][0],p[1]-points[0][1]) for p in points),default=None),
           'intent_origin':'EXPLICIT_ANNOTATION','automatic_lock':False})
    return {'motion_id':record['id'],'duration_seconds':times[-1]-times[0],'sample_count':len(samples),
      'root_role':root_name,'root_displacement_m':math.dist(positions[0],positions[-1]),
      'max_root_speed_mps':max((math.sqrt(sum(x*x for x in v)) for v in velocity),default=0),
      'max_root_acceleration_mps2':max((math.sqrt(sum(x*x for x in v)) for v in acc),default=0),
      'max_joint_angular_speed_radps':max_angular,'contacts':contacts,'annotated_contacts':annotations,
      'technical':'NUMERIC_DATA_VALID','performance':'NOT_EVALUATED','human':'NOT_ESTABLISHED',
      'unmeasured':['dance/style','force or center-of-mass balance','joint-limit safety',
                    'sole contact without calibration','continuous rendered appearance','collision'],
      'notice':'Contact labels are kinematic candidates, not intended support or dance-quality scores.'}


def record_review(lib,review):
    fields(review,{'motion_id','decision','reviewer','evidence_kind','artifacts','notes'},
           {'motion_id','decision','reviewer','evidence_kind','artifacts','notes'})
    record,_=load(lib,review['motion_id'])
    require(review['decision'] in ('ACCEPT','REJECT','UNCERTAIN'),'INVALID_REVIEW','Invalid decision')
    require(review['reviewer'] in ('human','image_model','video_model'),'INVALID_REVIEW','Name actual reviewer type')
    require(review['evidence_kind'] in ('continuous_playback','video','stills','metrics'),'INVALID_REVIEW','Name actual evidence kind')
    require(isinstance(review['artifacts'],list) and 1<=len(review['artifacts'])<=8,'INVALID_REVIEW','Retain bounded evidence receipts')
    for f in review['artifacts']:
        fields(f,{'path','sha256','size'},{'path','sha256','size'});lib.verify_file(f)
    text(review['notes'],4000);require(review['notes'].strip(),'INVALID_REVIEW','Explain the evidence-linked decision')
    if review['decision']=='ACCEPT':
        require(review['evidence_kind'] in ('continuous_playback','video') and review['reviewer'] in ('human','video_model'),
                'TEMPORAL_EVIDENCE_REQUIRED','Stills and metrics cannot establish temporal performance acceptance')
    rid='review_'+digest(review);path=within(lib.root,'motion-reviews/'+record['id']+'/'+rid+'.json')
    result={**review,'id':rid,'evidence_assertion':'ATTESTED_BY_CALLER_NOT_SENSOR_PROOF'}
    if path.exists():require(load_json(path)==result,'REVIEW_CHANGED','Existing immutable review differs')
    else:atomic_json(path,result)
    return {'status':'RECORDED','review_id':rid,'decision':review['decision'],'path':str(path)}
