"""Evaluate baked candidates after fresh reopening, at physical stitch times."""
import math
import bpy
from mathutils import Vector
from . import sequence_math as qm
from .motion_bricks_stitch_math import boundary_estimate
from .motion_bricks_retarget import load_profile
from .motion_bricks_feet import Soles
from .motion_bricks_quality import PRESET, thresholds, gate, contact_runs


def evaluate(report):
    scene=bpy.context.scene;fps=scene.render.fps/scene.render.fps_base
    frame,subframe=scene.frame_current,scene.frame_subframe
    rows=[]
    try:
        for change in report['changes']:
            joins=[j for j in change.get('timeline',{}).get('connections',[]) if j.get('provider')=='motion-bricks.cpp']
            if not joins:continue
            obj=scene.objects[change['performer']];profile=load_profile(obj);height=profile.get('reference_height_m')
            if height is None:
                rows.append({'performer':obj.name,'status':'FAIL','reason':'NEEDS_PREPARATION',
                    'message':'Prepare this mapping with a fixed reviewed full-character height before acceptance.'})
                continue
            limits=thresholds(height);roles=profile['roles'];soles=Soles(obj,obj,roles)
            def at(f):
                scene.frame_set(math.floor(f),subframe=f-math.floor(f));bpy.context.view_layer.update()
                e=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                return {b.name:{'p':list((e.matrix_world@b.matrix).translation),'q':list((e.matrix_world@b.matrix).to_quaternion())} for b in e.pose.bones}
            def landmarks():
                result={}
                for side,groups in soles.groups.items():
                    choices=[]
                    for skin,indices in groups:
                        e=skin.evaluated_get(bpy.context.evaluated_depsgraph_get())
                        choices.extend((float((e.matrix_world@e.data.vertices[i].co).z),skin,i) for i in indices)
                    _,skin,index=min(choices,key=lambda x:x[0]);result[side]=(skin,index)
                return result
            try:
                for join in joins:
                    edges=[]
                    for edge in (join['start'],join['end']):
                        # Both limits are estimated at the same stitch timestamp.
                        # Rotation logs share the left-near orientation as one frame.
                        h=fps/1536.;left=[at(edge-j*h) for j in (1,2,3,4)];right=[at(edge+j*h) for j in (1,2,3,4)]
                        per_bone=[]
                        for name in left[0]:
                            l=[Vector(v[name]['p']) for v in left];r=[Vector(v[name]['p']) for v in right]
                            lp,lv=map(Vector,boundary_estimate(l,h/fps,'left'));rp,rv=map(Vector,boundary_estimate(r,h/fps,'right'))
                            reference=left[0][name]['q'];z=[Vector(qm.qlog(qm.qmul(qm.inverse(reference),v[name]['q']))) for v in left+right]
                            ql,wl=map(Vector,boundary_estimate(z[:4],h/fps,'left'));qr,wr=map(Vector,boundary_estimate(z[4:],h/fps,'right'))
                            per_bone.append({'bone':name,'position_m':(lp-rp).length,'orientation_deg':math.degrees((ql-qr).length),
                                'root_velocity_m_s':(lv-rv).length,'angular_velocity_deg_s':math.degrees((wl-wr).length)})
                        edges.append({'frame':edge,'seconds':edge/fps,**{key:(next(b[key] for b in per_bone if b['bone']==roles['pelvis']) if key=='root_velocity_m_s' else max(b[key] for b in per_bone)) for key in ('position_m','orientation_deg','root_velocity_m_s','angular_velocity_deg_s')}})
                    count=math.ceil((join['end']-join['start'])/fps*60);sample_fps=count/((join['end']-join['start'])/fps)
                    at((join['start']+join['end'])/2);points=landmarks();poses=[];contacts=[];penetration=0.;flexions=[]
                    for i in range(count+1):
                        pose=at(join['start']+(join['end']-join['start'])*i/count);poses.append(pose);low=soles.heights();contact={}
                        for side,(skin,index) in points.items():
                            e=skin.evaluated_get(bpy.context.evaluated_depsgraph_get());point=e.matrix_world@e.data.vertices[index].co
                            contact[side]={'point':list(point),'low':low[side]};penetration=max(penetration,profile['ground_z']-low[side])
                            hip,knee,foot=[Vector(pose[roles[side+'_'+part]]['p']) for part in ('thigh','shin','foot')]
                            flexions.append(180-math.degrees((hip-knee).angle(foot-knee)))
                        contacts.append(contact)
                    runs=contact_runs(contacts,sample_fps,height,profile['ground_z'])
                    for r in runs:r.update(start_seconds=r['start_index']/sample_fps,end_seconds=r['end_index']/sample_fps)
                    contact_failures=[];cleanup=join['provenance']['foot_retarget'];seconds=(join['end']-join['start'])/fps
                    # Validate a claimed stance at its actual fixed sole vertex.
                    # A rotating heel is not evidence that a planted toe slid.
                    for lock in cleanup.get('support_locks',[]):
                        core=lock.get('core_seconds',cleanup.get('support_lock_core_seconds'));lo,hi=(0.,core) if lock['edge']=='source' else (seconds-core,seconds)
                        points=[];distance_from_ground=[]
                        for i in range(7):
                            at(join['start']+(lo+(hi-lo)*i/6)*fps)
                            point=soles.landmark(lock['mesh'],lock['vertex']);points.append(list(point))
                            distance_from_ground.append(abs(point.z-profile['ground_z']))
                        drift=max(math.dist(a[:2],b[:2]) for a in points for b in points)
                        grounded=max(distance_from_ground)<=limits['penetration_m']
                        if not grounded:contact_failures.append({'metric':'claimed_support_height','side':lock['side'],'edge':lock['edge'],'value':max(distance_from_ground),'limit':limits['penetration_m']})
                        runs.append({'side':lock['side'],'start_seconds':lo,'end_seconds':hi,'drift_m':drift,'grounded':grounded,
                                     'origin':'measured-native-support-extended-by-bridge-IK','confidence':'evaluated-kinematic-only','mesh':lock['mesh'],'vertex':lock['vertex'],'samples':points})
                    merged=[]
                    for lo,hi in sorted((r['start_seconds'],r['end_seconds']) for r in runs if r.get('grounded',True)):
                        if merged and lo<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],hi)
                        else:merged.append([lo,hi])
                    coverage=sum(b-a for a,b in merged)/seconds
                    roots=[Vector(p[roles['pelvis']]['p']) for p in poses]
                    velocities=[(b-a)*sample_fps for a,b in zip(roots,roots[1:])]
                    angular={name:[Vector(qm.qlog(qm.qmul(b[name]['q'],qm.inverse(a[name]['q']))))*sample_fps for a,b in zip(poses,poses[1:])] for name in poses[0]}
                    metrics={key:max(edge[key] for edge in edges) for key in ('position_m','orientation_deg','root_velocity_m_s','angular_velocity_deg_s')}
                    metrics.update(penetration_m=max(0,penetration),planted_drift_m=max((r['drift_m'] for r in runs),default=None),
                        root_speed_m_s=max(v.length for v in velocities),root_acceleration_m_s2=max((b-a).length*sample_fps for a,b in zip(velocities,velocities[1:])),
                        joint_speed_deg_s=max(math.degrees(v.length) for values in angular.values() for v in values),
                        joint_acceleration_deg_s2=max(math.degrees((b-a).length*sample_fps) for v in angular.values() for a,b in zip(v,v[1:])),
                        knee_flexion_max_deg=max(flexions),**join['provenance'].get('correction_metrics',{}))
                    required=[key for key in limits if key!='knee_flexion_min_deg']
                    failures=gate(metrics,limits,required)+contact_failures
                    if not runs or coverage<.2:failures.append({'metric':'planted_contact_coverage','value':coverage,'minimum':.2,'reason':'nonempty grounded stance evidence required; flight/mixed ambiguous state is unsupported'})
                    rows.append({'performer':obj.name,'clip_id':join['clip_id'],'status':'FAIL' if failures else 'PASS','preset':PRESET,
                        'reference_height_m':height,'reference_rest_identity':profile['rest_identity'],'thresholds':limits,'metrics':metrics,
                        'boundaries':edges,'failures':failures,'contacts':{'intervals':runs,'coverage':coverage,'sampling_hz':sample_fps,'samples':contacts,'provenance':'proposal from evaluated sole height and fixed landmark speed; not ground truth'},
                        'largest_joint_speed':max(({'joint':name,'sample_index':i,'degrees_per_second':math.degrees(v.length)} for name,values in angular.items() for i,v in enumerate(values)),key=lambda r:r['degrees_per_second']),
                        'largest_joint_acceleration':max(({'joint':name,'sample_index':i,'degrees_per_second2':math.degrees((b-a).length*sample_fps)} for name,values in angular.items() for i,(a,b) in enumerate(zip(values,values[1:]))),key=lambda r:r['degrees_per_second2']),
                        'quality_scope':'KINEMATIC_ONLY','physical_feasibility':'NOT_DEMONSTRATED','visual_review':'REQUIRED',
                        'derivatives':'cubic one-sided value/derivative estimates at common physical stitch; samples at +/-1,2,3,4 times h=1/1536 s; common rotational frame',
                        'rank_score':sum(metrics[k]/limits[k] for k in required) if not failures else None})
            finally:soles.close()
    finally:scene.frame_set(frame,subframe=subframe);bpy.context.view_layer.update()
    return {'schema':'motion-bricks.validation.v1','status':'PASS' if rows and all(r['status']=='PASS' for r in rows) else 'FAIL',
            'scope':'BAKED_FRESH_REOPEN_KINEMATICS_NOT_PHYSICS','joins':rows,'sampling':'bridge samples <=1/60 s; no native interval retiming'}
