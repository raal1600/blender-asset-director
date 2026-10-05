"""Explicit authored contact chains for bounded native transition cleanup.

No bone-name inference, retargeting or contact classifier. Metadata is optional;
invalid annotations are refused instead of silently treated as ground truth.
"""
import json
import math
import bpy
from mathutils import Vector, Matrix, Quaternion
from .core import require, digest, DirectorError

RIG_PROPERTY = 'bad_contact_rig_v1'
ACTION_PROPERTY = 'bad_contact_intervals_v1'


def rest_identity(obj, chains):
    names={c[key] for c in chains for key in ('upper','lower','end')}
    for name in list(names):
        parent=obj.data.bones[name].parent
        while parent is not None:
            names.add(parent.name);parent=parent.parent
    names=sorted(names)
    return digest([{'name':name,'parent':obj.data.bones[name].parent.name if obj.data.bones[name].parent else None,
                    'matrix':[float(x) for row in obj.data.bones[name].matrix_local for x in row],
                    'length':obj.data.bones[name].length} for name in names])


def contract(obj):
    raw=obj.get(RIG_PROPERTY)
    if raw is None:return None
    require(obj.type=='ARMATURE' and isinstance(raw,str) and len(raw)<=16384,
            'CONTACT_RIG_INVALID','Contact metadata requires a bounded rig annotation')
    try:value=json.loads(raw)
    except (ValueError,TypeError) as error:raise DirectorError('CONTACT_RIG_INVALID','Invalid contact rig JSON') from error
    require(isinstance(value,dict) and set(value)=={'version','chains','rest_sha256','ground_z_m','height_m'}
            and value['version']=='native-contact-rig-v1' and isinstance(value['chains'],list)
            and 1<=len(value['chains'])<=4,'CONTACT_RIG_INVALID','Use 1 to 4 explicit contact chains')
    require(all(type(value[k]) in (int,float) and math.isfinite(value[k]) for k in ('ground_z_m','height_m'))
            and .1<=value['height_m']<=100,'CONTACT_RIG_INVALID','Contact ground and reference height must be finite metres')
    used=set();ids=set()
    for chain in value['chains']:
        require(isinstance(chain,dict) and set(chain)=={'id','upper','lower','end','pole_local'}
                and all(isinstance(chain[k],str) and chain[k] for k in ('id','upper','lower','end'))
                and chain['id'] not in ids,'CONTACT_RIG_INVALID','Contact chains need distinct authored identities')
        ids.add(chain['id'])
        names=[chain[k] for k in ('upper','lower','end')]
        require(len(set(names))==3 and not used.intersection(names) and all(n in obj.pose.bones for n in names),
                'CONTACT_RIG_INVALID','Contact chains must resolve to distinct observed rig bones')
        used.update(names)
        upper,lower,end=[obj.data.bones[n] for n in names]
        require(lower.parent==upper and end.parent==lower and lower.use_connect and end.use_connect
                and (upper.tail_local-lower.head_local).length<1e-6 and (lower.tail_local-end.head_local).length<1e-6,
                'CONTACT_RIG_INVALID','Contact cleanup requires a connected two-bone chain and foot')
        require(all(b.inherit_scale=='FULL' and b.use_inherit_rotation for b in (upper,lower,end)),
                'CONTACT_RIG_INVALID','Nonstandard contact-chain inheritance needs Blender preparation')
        pole=chain['pole_local']
        require(isinstance(pole,list) and len(pole)==3 and all(type(x) in (int,float) and math.isfinite(x) for x in pole)
                and Vector(pole).length>1e-6,'CONTACT_RIG_INVALID','Contact knee pole must be an explicit nonzero rig-local direction')
    require(rest_identity(obj,value['chains'])==value['rest_sha256'],'CONTACT_RIG_CHANGED','Contact rest hierarchy changed; review its authored mapping')
    return value


def annotations(obj, action, rig):
    raw=action.get(ACTION_PROPERTY)
    if raw is None:return []
    require(rig is not None and isinstance(raw,str) and len(raw)<=32768,'CONTACT_ANNOTATION_INVALID','Contact intervals require a verified rig annotation')
    try:value=json.loads(raw)
    except (ValueError,TypeError) as error:raise DirectorError('CONTACT_ANNOTATION_INVALID','Invalid contact intervals JSON') from error
    require(isinstance(value,dict) and set(value)=={'version','rig_sha256','intervals'}
            and value['version']=='native-contact-intervals-v1' and value['rig_sha256']==digest(rig)
            and isinstance(value['intervals'],list) and 1<=len(value['intervals'])<=128,
            'CONTACT_ANNOTATION_INVALID','Contact intervals must identify this exact rig mapping')
    ids={c['id'] for c in rig['chains']};previous={}
    for item in value['intervals']:
        require(isinstance(item,dict) and set(item)=={'chain','start','end'} and isinstance(item['chain'],str) and item['chain'] in ids
                and all(type(item[k]) in (int,float) and math.isfinite(item[k]) for k in ('start','end'))
                and -100000<=item['start']<item['end']<=100000,
                'CONTACT_ANNOTATION_INVALID','Use increasing authored source-frame contact intervals')
        require(item['start']>=previous.get(item['chain'],-100001),'CONTACT_ANNOTATION_INVALID','Contact intervals must be ordered and non-overlapping')
        previous[item['chain']]=item['end']
    return value['intervals']


def describe(obj, action, slot=None, take=None):
    try:
        rig=contract(obj);intervals=annotations(obj,action,rig)
        return {'status':'AUTHORED' if intervals else 'UNANNOTATED','rig_sha256':digest(rig) if rig else None,
                'intervals':intervals,'provenance':'explicit source metadata' if intervals else None,'blocker':None}
    except (DirectorError,KeyError,TypeError,ValueError) as error:
        return {'status':'INVALID','blocker':str(error),'intervals':[]}


def _rotation(owner, q):
    if owner.rotation_mode=='QUATERNION':owner.rotation_quaternion=q
    elif owner.rotation_mode=='AXIS_ANGLE':axis,angle=q.to_axis_angle();owner.rotation_axis_angle=(angle,*axis)
    else:owner.rotation_euler=q.to_euler(owner.rotation_mode,owner.rotation_euler)


def set_pose(reader, pose, delta, heading):
    from .native_motion_basis import restore
    from .motion_heading import set_heading
    obj=reader.clone;obj.animation_data_clear();restore(obj,reader.native_basis)
    obj.delta_location=Vector(reader.native_basis['defaults']['']['delta_location'])+Vector(delta)
    base=reader.native_basis['defaults']['']
    if abs(heading)>1e-12:
        set_heading(obj,{'base_rotation_mode':base['rotation_mode'],'base_delta_rotation':base['delta_rotation_quaternion']},heading)
    for name,state in pose.items():
        owner=obj.pose.bones[name] if name else obj
        owner.location=state['location'];owner.scale=state['scale'];_rotation(owner,Quaternion(state['q']))
    bpy.context.view_layer.update()
    return obj


def foot_world(obj, chain):
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return evaluated.matrix_world @ evaluated.pose.bones[chain['end']].head


def solve(obj, chain, target, orientation=None):
    """Analytic two-bone position IK, retaining foot world orientation and scale."""
    bpy.context.view_layer.update()
    world=obj.matrix_world.copy();inverse=world.inverted()
    lengths_world=[v.length for v in world.to_3x3().col]
    require(world.to_3x3().determinant()>0 and max(lengths_world)-min(lengths_world)<1e-6*max(lengths_world),
            'CONTACT_RIG_INVALID','Contact cleanup needs a positive uniform world scale')
    upper,lower,end=[obj.pose.bones[chain[k]] for k in ('upper','lower','end')]
    require(all(abs(v-1)<1e-6 for bone in (upper,lower,end) for v in bone.scale),
            'CONTACT_RIG_INVALID','Contact chain pose scales must stay at one')
    lengths=[(world.to_3x3()@bone.vector).length for bone in (upper,lower)]
    hip=world@upper.head;to_target=Vector(target)-hip;distance=to_target.length
    require(abs(lengths[0]-lengths[1])+1e-5<distance<sum(lengths)-1e-5,
            'CONTACT_UNREACHABLE','Planted foot leaves its measured two-bone reach; change the transition or author an intermediate step')
    axis=to_target.normalized();pole=world.to_3x3()@Vector(chain['pole_local']);pole-=axis*pole.dot(axis)
    require(pole.length>1e-6,'CONTACT_UNREACHABLE','Contact knee pole becomes singular; author an intermediate step')
    pole.normalize();along=(lengths[0]**2-lengths[1]**2+distance**2)/(2*distance)
    knee=hip+axis*along+pole*math.sqrt(max(0,lengths[0]**2-along**2))
    foot_rotation=orientation.copy() if orientation is not None else (world@end.matrix).to_quaternion()
    def rotate_to(bone, desired):
        head=world@bone.head;current=world.to_3x3()@bone.vector
        correction=current.rotation_difference(Vector(desired)-head)
        matrix=world@bone.matrix
        location,rotation,scale=matrix.decompose()
        corrected=Matrix.LocRotScale(location,correction@rotation,scale)
        saved_location=bone.location.copy();saved_scale=bone.scale.copy()
        bone.matrix=inverse@corrected
        bone.location=saved_location;bone.scale=saved_scale
        bpy.context.view_layer.update()
    rotate_to(upper,knee);rotate_to(lower,target)
    current=world@end.matrix
    location,_,scale=current.decompose();saved_location=end.location.copy();saved_scale=end.scale.copy()
    end.matrix=inverse@Matrix.LocRotScale(location,foot_rotation,scale)
    end.location=saved_location;end.scale=saved_scale
    bpy.context.view_layer.update()
    require((foot_world(obj,chain)-Vector(target)).length<2e-4,'CONTACT_SOLVE_FAILED','Contact solve differs from its requested target')


def cleanup(reader, obj, previous, motion, geometry, samples, previous_offset, alignment, travel_before, ap, bn, dt, phases=(0.,0.)):
    """Constrain only explicitly shared planted boundaries, plus annotated ground."""
    from . import motion_heading, motion_stitch_math, sequence_math
    from .motion_heading import rotation
    rig=contract(obj)
    aa=annotations(obj,previous[2],rig);bb=annotations(obj,motion[2],rig)
    if not rig or not (aa or bb):return samples,None
    reader.count += len(samples)*len(rig['chains'])
    require(reader.count<=4096,'RESOURCE_LIMIT','Contact cleanup exceeds the bounded 4096-pose budget; split the sequence')
    require(aa and bb,'CONTACT_ANNOTATION_INVALID','Both connected clips need authored contact intervals')
    require(previous[0].get('heading_deg',0)==motion[0].get('heading_deg',0),
            'CONTACT_TURN_REVIEW','Planted contact through a heading turn needs an authored turning step')
    scale=bpy.context.scene.unit_settings.scale_length
    parent=obj.parent.matrix_world@obj.matrix_parent_inverse if obj.parent else obj.matrix_parent_inverse
    basis=parent.to_3x3();inverse=basis.inverted()
    require(max(obj.scale)-min(obj.scale)<1e-6 and min(obj.scale)>0,
            'CONTACT_RIG_INVALID','Contact cleanup needs positive uniform object scale')
    def delta(u):
        travel=Vector((*travel_before,0))+Vector((*motion_heading.path_at(geometry,u),0))
        return inverse@(travel/scale)+Vector(previous_offset)+Vector(alignment)*motion_heading.ease(u)
    def state(pose,u):return set_pose(reader,pose,delta(u),geometry['heading_in_deg'])
    a_frame=motion_stitch_math.source_frame(*previous[1]['range'],previous[4]['cycles']*(previous[1]['range'][1]-previous[1]['range'][0]),phases[0],endpoint=True)
    b_frame=motion_stitch_math.source_frame(*motion[1]['range'],0,phases[1])
    active=lambda intervals,frame:{r['chain'] for r in intervals if r['start']-1e-7<=frame<=r['end']+1e-7}
    shared=active(aa,a_frame)&active(bb,b_frame)
    require(shared,'CONTACT_INTERVAL_REVIEW','Connected endpoints share no authored planted foot; choose a stance-compatible join or an intermediate step')
    targets={};endpoint_error={}
    for chain in rig['chains']:
        if chain['id'] not in shared:continue
        for name in (chain['upper'],chain['lower'],chain['end']):
            require(name in samples[0][1] and all(abs(x-1)<1e-6 for x in samples[0][1][name]['scale']),
                    'CONTACT_RIG_INVALID','Contact bones need native rotation channels and unit pose scale')
        a=foot_world(state(samples[0][1],0.),chain).copy()
        qa=(reader.clone.matrix_world@reader.clone.pose.bones[chain['end']].matrix).to_quaternion()
        b=foot_world(state(samples[-1][1],1.),chain).copy()
        qb=(reader.clone.matrix_world@reader.clone.pose.bones[chain['end']].matrix).to_quaternion()
        if qa.dot(qb)<0:qb.negate()
        require(qa.rotation_difference(qb).angle<=math.radians(1),
                'CONTACT_TURN_REVIEW','A planted foot changes orientation across the join; use an authored pivot or intermediate step')
        mismatch=(a-b).length*scale;endpoint_error[chain['id']]=mismatch
        require(mismatch<=.001*rig['height_m'],'CONTACT_BOUNDARY_MISMATCH',
                'Authored planted feet disagree at the aligned boundaries; change the clip phase or use an intermediate step')
        require(abs(a.z*scale-rig['ground_z_m'])<=.005*rig['height_m'],
                'CONTACT_ANNOTATION_INVALID','Authored planted foot does not meet its declared ground plane')
        from .motion_stitch import channel_spec
        spec=channel_spec(obj,motion[2],motion[3])
        for name in (chain['upper'],chain['lower'],chain['end']):
            mode=obj.pose.bones[name].rotation_mode
            prop='rotation_quaternion' if mode=='QUATERNION' else 'rotation_axis_angle' if mode=='AXIS_ANGLE' else 'rotation_euler'
            require(all((prop,i) in spec.get(name,set()) for i in range(4 if mode in {'QUATERNION','AXIS_ANGLE'} else 3)),
                    'CONTACT_CHANNEL_REVIEW','Contact cleanup requires all native rotation components on each authored chain bone')
        fps=bpy.context.scene.render.fps/bpy.context.scene.render.fps_base
        before_delta=delta(0.)-inverse@(Vector((*geometry['velocity_in'],0))*dt/scale)
        after_delta=delta(1.)+inverse@(Vector((*geometry['velocity_out'],0))*dt/scale)
        before=foot_world(set_pose(reader,ap,before_delta,geometry['heading_in_deg']),chain).copy()
        before_q=(reader.clone.matrix_world@reader.clone.pose.bones[chain['end']].matrix).to_quaternion()
        after=foot_world(set_pose(reader,bn,after_delta,geometry['heading_out_deg']),chain).copy()
        after_q=(reader.clone.matrix_world@reader.clone.pose.bones[chain['end']].matrix).to_quaternion()
        require(max(sequence_math.norm(sequence_math.angular_velocity(list(before_q),list(qa),dt/fps)),
                    sequence_math.norm(sequence_math.angular_velocity(list(qb),list(after_q),dt/fps)))<=math.radians(5),
                'CONTACT_TURN_REVIEW','Authored planted foot pivots at a boundary; use an authored turning step')
        require(max((a-before).length,(after-b).length)*scale*fps/dt<=.05*rig['height_m'],
                'CONTACT_ANNOTATION_INVALID','Authored planted boundary has measurable foot velocity; review its interval or clip phase')
        targets[chain['id']]=(a,b,qa,qb)
    corrected=[];drift=0.;penetration=0.
    for f,pose in samples:
        u=(f-geometry['start'])/geometry['duration_frames'];clone=state(pose,u)
        for chain in rig['chains']:
            endpoints=targets.get(chain['id'])
            target=endpoints[0].lerp(endpoints[1],motion_heading.ease(u)) if endpoints else None
            if target is None:
                target=foot_world(clone,chain).copy()
                tail=clone.matrix_world@clone.pose.bones[chain['end']].tail
                low=min(target.z,tail.z)
                if low*scale>=rig['ground_z_m']:continue
                target.z+=rig['ground_z_m']/scale-low
            solve(clone,chain,target,endpoints[2].slerp(endpoints[3],motion_heading.ease(u)) if endpoints else None)
        converted={name:{'location':list((clone.pose.bones[name] if name else clone).location),
                         'q':list(rotation(clone.pose.bones[name] if name else clone).normalized()),
                         'scale':list((clone.pose.bones[name] if name else clone).scale)} for name in pose}
        for chain in rig['chains']:
            point=foot_world(clone,chain)
            tail=clone.matrix_world@clone.pose.bones[chain['end']].tail
            penetration=max(penetration,max(0,rig['ground_z_m']-min(point.z,tail.z)*scale))
            if chain['id'] in targets:drift=max(drift,(point-targets[chain['id']][0]).length*scale)
        corrected.append((f,converted))
    return corrected,{'method':'authored-two-bone-contact-v1','rig_sha256':digest(rig),
                      'provenance':'explicit per-Action planted source intervals; verified rest mapping',
                      'chains':sorted(shared),'interval':[geometry['start'],geometry['end']],
                      'sample_count':len(samples),'endpoint_position_error_m':endpoint_error,
                      'sampled_drift_m':drift,'sampled_penetration_m':penetration,
                      'ground_z_m':rig['ground_z_m'],'height_m':rig['height_m']}
