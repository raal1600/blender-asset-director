"""Generated, separately baked transition between intact native Action strips.

Blender samples evaluated native contexts. An isolated pinned provider predicts
placement and body motion. Compact seam residuals affect the generated interval
only. Neither native clip is phase shifted or blended through that interval.
"""
import copy
import math
from time import monotonic
import uuid
import bpy
from mathutils import Quaternion, Vector
from .core import require, digest, atomic_json, implementation_hash
from . import motion_bricks_provider as provider, motion_bricks_retarget as ret
from . import motion_bricks_contract as contract
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
    clone=reader.clone;duration=geometry['duration_frames'];timing=contract.duration_plan(duration/fps)
    model_frames=timing['model_frames'];retime=timing['generated_retime_ratio']
    spec=channel_spec(obj,motion[2],motion[3])
    for role in ret.GROUPS:
        name=profile['roles'][role];bone=obj.pose.bones[name]
        prop='rotation_quaternion' if bone.rotation_mode=='QUATERNION' else 'rotation_axis_angle' if bone.rotation_mode=='AXIS_ANGLE' else 'rotation_euler'
        require(all((prop,i) in spec.get(name,set()) for i in range(4 if prop!='rotation_euler' else 3)),
                'MOTION_BRICKS_CHANNELS','Every mapped body joint needs complete native rotation channels')
    config=provider.configured();require(config is not None,'MOTION_BRICKS_NOT_CONFIGURED','Set up the pinned local MotionBricks provider first')
    execution=execution or {};cancelled=execution.get('cancelled');progress=execution.get('progress')
    started=monotonic();trace=[];request_id='transition_'+uuid.uuid4().hex
    def check():require(not (cancelled and cancelled()),'MOTION_BRICKS_CANCELLED','Generated connection cancelled')
    def emit(stage):
        check()
        trace.append({'stage':stage,'seconds_from_transition_start':monotonic()-started})
        if progress:progress({'provider':'motion-bricks.cpp','stage':stage,'clip_id':motion[0]['id']})
    def pose(m,elapsed,endpoint=False):return reader.read(m,elapsed,0.,endpoint)
    elapsed=previous[4]['cycles']*(previous[1]['range'][1]-previous[1]['range'][0])
    h=min(1/64,(previous[4]['native_end']-previous[0]['start'])/8,(motion[4]['native_end']-motion[0]['start'])/8)
    schedules={side:contract.context_schedule(m[1]['range'],fps*m[0]['speed'],side,
        elapsed=m[4]['cycles']*(m[1]['range'][1]-m[1]['range'][0]))
        for side,m in (('source',previous),('target',motion))}
    a=pose(previous,elapsed,True);ap=pose(previous,elapsed-h*previous[0]['speed']);app=pose(previous,elapsed-2*h*previous[0]['speed'])
    b=pose(motion,0);bn=pose(motion,h*motion[0]['speed']);bnn=pose(motion,2*h*motion[0]['speed'])
    tangents=native_tangents(a,b,ap,app,bn,bnn,h)
    def state(p):return set_pose(reader,p,(0,0,0),0.)
    def hip():
        evaluated=clone.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return evaluated.matrix_world@evaluated.pose.bones[profile['roles']['pelvis']].head
    state(a);hip_a=hip();origin=Vector((hip_a.x,hip_a.y,profile['ground_z']))
    state(ap);hip_ap=hip();state(app);hip_app=hip()
    state(b);hip_b=hip();state(bn);hip_bn=hip();state(bnn);hip_bnn=hip()
    # Match evaluated world-root velocity throughout the compact seam window.
    # A position-only residual leaves the baker to correct the entire velocity
    # error in its first quarter-frame segment, producing a sharp acceleration.
    root_velocities=[(3*hip_a-4*hip_ap+hip_app)/(2*h)+Vector((*geometry['velocity_in'],0)),
                     (-3*hip_b+4*hip_bn-hip_bnn)/(2*h)+Vector((*geometry['velocity_out'],0))]
    sampling=contract.sampling_settings(motion[0]['transition'].get('sampling','argmax'),motion[0]['transition']['seed'])
    request={'schema':provider.REQUEST_SCHEMA,'conventions':dict(provider.CONVENTIONS),'skeleton':profile['skeleton'],
             'frames':model_frames,'seed':sampling['seed'],'target_placement':'predicted','argmax':sampling['argmax']}
    emit('sampling_native_contexts')
    roundtrip=[]
    for side,m in (('source',previous),('target',motion)):
        roots=[];rotations=[]
        velocity=Vector((*geometry['velocity_in' if side=='source' else 'velocity_out'],0))
        for i,source_frame in enumerate(schedules[side]['source_frames']):
            relative=schedules[side]['seconds_from_stitch'][i]*fps
            p=pose(m,source_frame-m[1]['range'][0],abs(source_frame-m[1]['range'][1])<1e-7)
            state(p);before={n:clone.pose.bones[n].matrix.copy() for n in spec if n}
            root,q=ret.encode_pose(clone,profile,world_origin=origin,placement=velocity*relative)
            ret.apply_rotations(clone,ret.decode_rotations(clone,profile,q))
            maximum=max((clone.pose.bones[n].matrix.translation-v.translation).length for n,v in before.items())
            angle=max(qm.norm(qm.qlog(qm.qmul(qm.inverse(list(v.to_quaternion())),list(clone.pose.bones[n].matrix.to_quaternion())))) for n,v in before.items())
            require(maximum<1e-5 and angle<math.radians(.05),'MOTION_BRICKS_RETARGET_ROUNDTRIP','Mapped native pose does not round-trip; review the anatomical mapping')
            roundtrip.append({'position_rig_units':maximum,'orientation_degrees':math.degrees(angle)})
            roots.append(root);rotations.append(q)
        request[side]={'roots':roots,'local_xyzw':rotations}
    from . import action_layer as layer, blender_ops as ops
    dependencies={'schema':contract.INPUT_SCHEMA,'domain':contract.DOMAIN_VERSION,
        'implementation_sha256':implementation_hash(),
        'character':{'asset_id':obj.get('bad_asset'),'rig_label':obj.name,'rest_identity':profile['rest_identity'],
                     'profile_sha256':digest(profile),'profile':profile},
        'scene':{'fps_numerator':scene.render.fps,'fps_denominator':scene.render.fps_base,
                 'unit_scale':scene.unit_settings.scale_length,
                 'parent_matrix':ops.flatten(obj.parent.matrix_world@obj.matrix_parent_inverse if obj.parent else obj.matrix_parent_inverse),
                 'object_linear':[list(row) for row in obj.matrix_world.to_3x3()],
                 'native_basis_sha256':digest(reader.native_basis),
                 'evaluation_policy':'unconstrained native transform channels; stable parents; no drivers'},
        'inputs':{side:{'take_id':m[1]['id'],'action_label':m[2].name,'slot':layer.slot_id(m[3]),
                        'channel_sha256':digest(layer.channels(m[2],m[3])), 'clip':m[0],
                        'context_schedule':schedules[side],
                        'root_preparation':m[2].get('bad_root_contact_preparation_v1'),
                        'contact_metadata':m[2].get('bad_contact_intervals_v1')}
                  for side,m in (('source',previous),('target',motion))},
        'evaluated_model_request':request,'timing':timing,'sampling':sampling,
        'root':{'owner':'native object/pelvis plus one composed delta path',
                'model_origin_blender_m':list(origin),'model_to_blender':'Y-up/+Z-forward to Z-up/-Y-forward',
                'native_world_velocity_m_s':[list(v*fps) for v in root_velocities]},
        'placement':{'target_xy':'predicted','target_heading':'native-context','target_height':'native',
                     'heading_override':False,'hard_model_pins':False},
        'provider':{'source_revision':provider.SOURCE_REVISION,'ggml_revision':provider.GGML_REVISION,
                    'model_revision':provider.MODEL_REVISION,'configuration_sha256':provider.configuration_identity()}}
    input_contract={'schema':contract.INPUT_SCHEMA,'request_id':request_id,
                    'dependency_fingerprint':digest(dependencies),'dependencies':dependencies}
    directory=execution.get('directory')
    prefix='motion-bricks-'+motion[0]['id']
    if directory:atomic_json(directory/(prefix+'-input.json'),input_contract)
    emit('provider_start')
    result=provider.execute(config,request,cancelled=cancelled,progress=progress)
    # Retain raw predictions even when later retargeting or quality checks fail.
    if directory:atomic_json(directory/(prefix+'-raw.json'),{'request_id':request_id,'request':request,'result':result})
    emit('retargeting_generated_interval')
    first,last=3,model_frames-4;raw=[]
    def capture():
        return {n:{'q':list((clone.pose.bones[n] if n else clone).matrix_basis.to_quaternion().normalized()),
                   'location':list((clone.pose.bones[n] if n else clone).location),
                   'scale':list((clone.pose.bones[n] if n else clone).scale)} for n in spec}
    for i in range(first,last+1):
        p=sm.bridge(a,b,ap,bn,h,duration,(i-first)/(last-first));state(p)
        ret.apply_rotations(clone,ret.decode_rotations(clone,profile,result['local_xyzw'][i]));raw.append(capture())
    if directory:atomic_json(directory/(prefix+'-retargeted.json'),{'request_id':request_id,'poses':raw,'first_model_index':first})
    emit('seam_processing')
    step=duration/(last-first);window=min(6.,(last-first)/4)*step
    residuals={n:[seam.rotation_residual(raw[k][n]['q'],p[n]['q'],qm.angular_velocity(raw[j][n]['q'],raw[l][n]['q'],step),tangents[edge][n]['angular'])
                  for edge,(k,j,l,p) in enumerate(((0,0,1,a),(-1,-2,-1,b)))] for n in spec}
    worlds=[ret.axes()@Vector(v)/profile['world_to_model_scale']+origin for v in result['roots']]
    expected_b=worlds[last].copy();expected_b.z=hip_b.z
    root_errors=[(hip_a-worlds[first],root_velocities[0]-(worlds[first+1]-worlds[first])/step),
                 (expected_b-worlds[last],root_velocities[1]-(worlds[last]-worlds[last-1])/step)]
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
        for edge,(value,velocity) in enumerate(root_errors):desired+=Vector(seam.edge_residual(list(value),list(velocity),time,duration,window,edge))
        f=geometry['start']+time;samples.append((f,p));path.append((f,list(inverse@(desired-hip()))))
    from .motion_bricks_feet import cleanup
    emit('contact_processing')
    samples,foot_retarget=cleanup(reader,obj,profile,request,result,samples,path,origin,geometry,(a,b,ap,app,bn,bnn,h),tangents,check)
    delta=expected_b-hip_b
    provenance={'request_sha256':digest(request),'result_sha256':digest(result),'profile_sha256':digest(profile),
                'source_revision':result['source_revision'],'model_revision':result['model_revision'],'library_sha256':result['library_sha256'],
                'seed':request['seed'],'sampling':sampling['mode'],'sampling_settings':sampling,'device':result['device'],'target_placement':'predicted','model_frames':model_frames,
                'request_id':request_id,'dependency_fingerprint':input_contract['dependency_fingerprint'],
                'input_schema':contract.INPUT_SCHEMA,'output_timing':timing,
                'model_fps':30,'generated_retime_ratio':retime,'native_clips_retimed':False,'roundtrip':roundtrip,
                'resource_measurements':result['resource_measurements'],'raw_boundary_diagnostics':result['boundary_diagnostics'],
                'seam_residual_free_model_indices':[first+window/step,last-window/step],
                'root_seam_correction':{'method':'evaluated-world-velocity-compact-residual-v1','window_frames':window,
                                        'native_velocities_m_per_frame':[list(v) for v in root_velocities]},
                'foot_retarget':foot_retarget,'contact_quality':'NOT_VERIFIED','visual_quality':'REQUIRES_REVIEW'}
    emit('baking_generated_connection')
    provenance['transition_trace']=trace
    if directory:
        filename=prefix+'.json'
        atomic_json(directory/filename,{'input_contract':input_contract,'request':request,'result':result,'provenance':provenance})
        atomic_json(directory/(prefix+'-corrected.json'),{'request_id':request_id,'samples':samples,'path_offsets_local':path})
        provenance['evidence_file']=filename
    return {**geometry,'placement_pending':False,'delta_m':[delta.x,delta.y],'provider':'motion-bricks.cpp','implementation':'motion-bricks-predicted-placement-v1',
            'generation_mode':'generated','phase_note':'Both native clips retained from original boundaries; no phase shift',
            'root_owner':'native-pose-plus-model-selected-placement','root_alignment_local':[0.,0.,0.],
            'contact_cleanup':None,'retarget_cleanup':foot_retarget,'samples':samples,'path_offsets_local':path,'boundary_tangents':tangents,
            'channels':{n:[list(pair) for pair in sorted(fields)] for n,fields in spec.items()},'provenance':provenance}
