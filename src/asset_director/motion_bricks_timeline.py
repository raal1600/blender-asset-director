"""Generated, separately baked transition between intact native Action strips.

Blender samples evaluated native contexts. An isolated pinned provider predicts
placement and body motion. Compact seam residuals affect the generated interval
only. Neither native clip is phase shifted or blended through that interval.
"""
import copy
import math
import bpy
from mathutils import Quaternion, Vector
from .core import require, digest, atomic_json
from . import motion_bricks_provider as provider, motion_bricks_retarget as ret
from . import motion_stitch_math as sm, sequence_math as qm, motion_bricks_stitch_math as seam


def native_tangents(a, b, ap, app, bn, bnn, h):
    result = sm.tangents(a,b,ap,bn,h)
    for index,(edge,near,far,sign) in enumerate(((a,ap,app,-1),(b,bn,bnn,1))):
        for name in a:
            r1=qm.qlog(qm.qmul(qm.inverse(edge[name]['q']),near[name]['q']))
            r2=qm.qlog(qm.qmul(qm.inverse(edge[name]['q']),far[name]['q']))
            result[index][name]['angular']=qm.mul(qm.sub(qm.mul(r1,4),r2),sign/(2*h))
            for key in ('location','scale'):
                result[index][name][key]=qm.mul(qm.add(qm.sub(qm.mul(near[name][key],4),far[name][key]),qm.mul(edge[name][key],-3)),sign/(2*h))
    return result


def prepare(reader, obj, previous, motion, geometry, execution=None):
    from .motion_stitch import channel_spec
    from .motion_contacts import set_pose
    profile=ret.load_profile(obj);scene=bpy.context.scene;fps=scene.render.fps/scene.render.fps_base
    require(scene.unit_settings.scale_length==1.,'MOTION_BRICKS_UNITS','This humanoid adapter currently requires scene metres (unit scale 1)')
    require(not any(m[0].get('heading_deg',0) for m in (previous,motion)),
            'MOTION_BRICKS_HEADING','Explicit humanoid generation currently preserves the saved heading; use native clips with their observed facing')
    require(not motion[0]['transition']['match_phase'],'MOTION_BRICKS_PHASE','Generated repositioning preserves both native boundaries; disable phase matching')
    clone=reader.clone;duration=geometry['duration_frames'];model_frames=min(range(24,65,4),key=lambda n:abs((n-7)*fps/30-duration))
    model_duration=(model_frames-7)*fps/30;retime=duration/model_duration
    require(.85<=retime<=1.15,'MOTION_BRICKS_DURATION','Choose a generated interval between about 0.6 and 1.9 seconds')
    spec=channel_spec(obj,motion[2],motion[3])
    for role in ret.GROUPS:
        name=profile['roles'][role];bone=obj.pose.bones[name]
        prop='rotation_quaternion' if bone.rotation_mode=='QUATERNION' else 'rotation_axis_angle' if bone.rotation_mode=='AXIS_ANGLE' else 'rotation_euler'
        require(all((prop,i) in spec.get(name,set()) for i in range(4 if prop!='rotation_euler' else 3)),
                'MOTION_BRICKS_CHANNELS','Every mapped body joint needs complete native rotation channels')
    config=provider.configured();require(config is not None,'MOTION_BRICKS_NOT_CONFIGURED','Set up the pinned local MotionBricks provider first')
    execution=execution or {};cancelled=execution.get('cancelled');progress=execution.get('progress')
    def check():require(not (cancelled and cancelled()),'MOTION_BRICKS_CANCELLED','Generated connection cancelled')
    def emit(stage):
        check()
        if progress:progress({'provider':'motion-bricks.cpp','stage':stage,'clip_id':motion[0]['id']})
    def pose(m,elapsed,endpoint=False):return reader.read(m,elapsed,0.,endpoint)
    elapsed=previous[4]['cycles']*(previous[1]['range'][1]-previous[1]['range'][0])
    h=min(1/64,(previous[4]['native_end']-previous[0]['start'])/8,(motion[4]['native_end']-motion[0]['start'])/8)
    require(elapsed>=3*fps/30*previous[0]['speed'] and motion[4]['native_end']-motion[0]['start']>=3*fps/30,
            'MOTION_BRICKS_CONTEXT','Each clip needs at least four native context samples at 30 FPS')
    a=pose(previous,elapsed,True);ap=pose(previous,elapsed-h*previous[0]['speed']);app=pose(previous,elapsed-2*h*previous[0]['speed'])
    b=pose(motion,0);bn=pose(motion,h*motion[0]['speed']);bnn=pose(motion,2*h*motion[0]['speed'])
    tangents=native_tangents(a,b,ap,app,bn,bnn,h)
    def state(p):return set_pose(reader,p,(0,0,0),0.)
    def hip():
        evaluated=clone.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return evaluated.matrix_world@evaluated.pose.bones[profile['roles']['pelvis']].head
    state(a);hip_a=hip();origin=Vector((hip_a.x,hip_a.y,profile['ground_z']))
    state(b);hip_b=hip()
    request={'schema':provider.REQUEST_SCHEMA,'conventions':dict(provider.CONVENTIONS),'skeleton':profile['skeleton'],
             'frames':model_frames,'seed':motion[0]['transition']['seed'],'target_placement':'predicted','argmax':True}
    emit('sampling_native_contexts')
    roundtrip=[]
    for side,m in (('source',previous),('target',motion)):
        roots=[];rotations=[]
        velocity=Vector((*geometry['velocity_in' if side=='source' else 'velocity_out'],0))
        for i in range(4):
            relative=(i-3 if side=='source' else i)*fps/30
            p=pose(m,elapsed+relative*m[0]['speed'] if side=='source' else relative*m[0]['speed'],side=='source' and i==3)
            state(p);before={n:clone.pose.bones[n].matrix.copy() for n in spec if n}
            root,q=ret.encode_pose(clone,profile,world_origin=origin,placement=velocity*relative)
            ret.apply_rotations(clone,ret.decode_rotations(clone,profile,q))
            maximum=max((clone.pose.bones[n].matrix.translation-v.translation).length for n,v in before.items())
            angle=max(qm.norm(qm.qlog(qm.qmul(qm.inverse(list(v.to_quaternion())),list(clone.pose.bones[n].matrix.to_quaternion())))) for n,v in before.items())
            require(maximum<1e-5 and angle<math.radians(.05),'MOTION_BRICKS_RETARGET_ROUNDTRIP','Mapped native pose does not round-trip; review the anatomical mapping')
            roundtrip.append({'position_rig_units':maximum,'orientation_degrees':math.degrees(angle)})
            roots.append(root);rotations.append(q)
        request[side]={'roots':roots,'local_xyzw':rotations}
    result=provider.execute(config,request,cancelled=cancelled,progress=progress)
    emit('retargeting_generated_interval')
    first,last=3,model_frames-4;raw=[]
    def capture():
        return {n:{'q':list((clone.pose.bones[n] if n else clone).matrix_basis.to_quaternion().normalized()),
                   'location':list((clone.pose.bones[n] if n else clone).location),
                   'scale':list((clone.pose.bones[n] if n else clone).scale)} for n in spec}
    for i in range(first,last+1):
        p=sm.bridge(a,b,ap,bn,h,duration,(i-first)/(last-first));state(p)
        ret.apply_rotations(clone,ret.decode_rotations(clone,profile,result['local_xyzw'][i]));raw.append(capture())
    step=duration/(last-first);window=min(6.,(last-first)/4)*step
    residuals={n:[seam.rotation_residual(raw[k][n]['q'],p[n]['q'],qm.angular_velocity(raw[j][n]['q'],raw[l][n]['q'],step),tangents[edge][n]['angular'])
                  for edge,(k,j,l,p) in enumerate(((0,0,1,a),(-1,-2,-1,b)))] for n in spec}
    worlds=[ret.axes()@Vector(v)/profile['world_to_model_scale']+origin for v in result['roots']]
    expected_b=worlds[last].copy();expected_b.z=hip_b.z
    root_errors=[hip_a-worlds[first],expected_b-worlds[last]]
    # Both source Actions own their native vertical motion. Placement is predicted XY.
    parent=obj.parent.matrix_world@obj.matrix_parent_inverse if obj.parent else obj.matrix_parent_inverse
    inverse=parent.to_3x3().inverted();samples=[];path=[];count=math.ceil(duration*4)
    for index in range(count+1):
        check();time=duration*index/count;x=(last-first)*index/count;k=min(last-first-1,math.floor(x));t=x-k;p={}
        for n in spec:
            q=Quaternion(raw[k][n]['q']).slerp(Quaternion(raw[k+1][n]['q']),t)
            p[n]={'q':seam.correct_rotation(list(q),residuals[n],time,duration,window),
                  'location':list(Vector(raw[k][n]['location']).lerp(Vector(raw[k+1][n]['location']),t)),
                  'scale':list(Vector(raw[k][n]['scale']).lerp(Vector(raw[k+1][n]['scale']),t))}
        if index==0:p=copy.deepcopy(a)
        elif index==count:p=copy.deepcopy(b)
        state(p);desired=worlds[first+k].lerp(worlds[first+k+1],t)
        for edge,value in enumerate(root_errors):desired+=Vector(seam.edge_residual(list(value),[0.,0.,0.],time,duration,window,edge))
        f=geometry['start']+time;samples.append((f,p));path.append((f,list(inverse@(desired-hip()))))
    from .motion_bricks_feet import cleanup
    samples,foot_retarget=cleanup(reader,obj,profile,request,result,samples,path,origin,geometry,(a,b,ap,app,bn,bnn,h),tangents,check)
    delta=expected_b-hip_b
    provenance={'request_sha256':digest(request),'result_sha256':digest(result),'profile_sha256':digest(profile),
                'source_revision':result['source_revision'],'model_revision':result['model_revision'],'library_sha256':result['library_sha256'],
                'seed':request['seed'],'sampling':'argmax','device':result['device'],'target_placement':'predicted','model_frames':model_frames,
                'model_fps':30,'generated_retime_ratio':retime,'native_clips_retimed':False,'roundtrip':roundtrip,
                'resource_measurements':result['resource_measurements'],'raw_boundary_diagnostics':result['boundary_diagnostics'],
                'seam_residual_free_model_indices':[first+window/step,last-window/step],
                'foot_retarget':foot_retarget,'contact_quality':'NOT_VERIFIED','visual_quality':'REQUIRES_REVIEW'}
    if execution.get('directory'):
        filename='motion-bricks-'+motion[0]['id']+'.json'
        atomic_json(execution['directory']/filename,{'request':request,'result':result,'provenance':provenance})
        provenance['evidence_file']=filename
    emit('baking_generated_connection')
    return {**geometry,'placement_pending':False,'delta_m':[delta.x,delta.y],'provider':'motion-bricks.cpp','implementation':'motion-bricks-predicted-placement-v1',
            'generation_mode':'generated','phase_note':'Both native clips retained from original boundaries; no phase shift',
            'root_owner':'native-pose-plus-model-selected-placement','root_alignment_local':[0.,0.,0.],
            'contact_cleanup':None,'retarget_cleanup':foot_retarget,'samples':samples,'path_offsets_local':path,'boundary_tangents':tangents,
            'channels':{n:[list(pair) for pair in sorted(fields)] for n,fields in spec.items()},'provenance':provenance}
