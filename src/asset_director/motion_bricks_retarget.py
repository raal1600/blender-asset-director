"""Explicit humanoid-to-G1 rotation adapter for a reviewed rig profile.

Anatomical roles are supplied by the host and checked against hierarchy/rest
geometry. This is not name-based automatic rig detection. Model proportions
remain G1; the original skin/rest hierarchy is never edited. Generated candidates
still require seam, planted-contact and visual checks on the destination rig.
"""
import math
import json
from .core import digest, require

PROPERTY = 'bad_motion_bricks_profile_v1'

GROUPS = {
    'pelvis': (0,), 'left_thigh': (1,2,3), 'left_shin': (4,),
    'left_foot': (5,6,7), 'right_thigh': (8,9,10), 'right_shin': (11,),
    'right_foot': (12,13,14), 'spine': (15,), 'spine1': (16,), 'chest': (17,),
    'left_upper_arm': (18,19,20), 'left_forearm': (21,), 'left_hand': (22,23,24,25),
    'right_upper_arm': (26,27,28), 'right_forearm': (29,), 'right_hand': (30,31,32,33),
}
OUTPUT = {role: indices[-1] for role,indices in GROUPS.items()}
# Virtual tips have a special conditioning convention, so read physical parents.
OUTPUT.update(left_foot=6,right_foot=13,left_hand=24,right_hand=32)
PRIMARY = {'left_thigh':(1,4,'left_shin'),'left_shin':(4,5,'left_foot'),
           'left_foot':(5,7,'left_toe'),'right_thigh':(8,11,'right_shin'),
           'right_shin':(11,12,'right_foot'),'right_foot':(12,14,'right_toe'),
           'left_upper_arm':(18,21,'left_forearm'),'left_forearm':(21,22,'left_hand'),
           'left_hand':(22,25,'left_hand_tip'),'right_upper_arm':(26,29,'right_forearm'),
           'right_forearm':(29,30,'right_hand'),'right_hand':(30,33,'right_hand_tip')}
CHAINS = [('pelvis','left_thigh','left_shin','left_foot','left_toe'),
          ('pelvis','right_thigh','right_shin','right_foot','right_toe'),
          ('pelvis','spine','spine1','chest'),
          ('chest','left_upper_arm','left_forearm','left_hand','left_hand_tip'),
          ('chest','right_upper_arm','right_forearm','right_hand','right_hand_tip')]


def axes():
    from mathutils import Matrix
    return Matrix.Rotation(math.pi/2,3,'X')  # G1 Y-up/+Z-forward -> Blender Z-up/-Y-forward


def rest_identity(rig):
    return digest({'linear':[list(row) for row in rig.matrix_world.to_3x3()],
                   'bones':[(b.name,b.parent.name if b.parent else None,
                             [list(row) for row in b.matrix_local]) for b in rig.data.bones]})


def build_profile(rig, skeleton, roles, ground_z, *, reference_origin_z=None, reference_height_m=None, encoding='g1-anatomical-frames-v2'):
    from mathutils import Vector, Quaternion, Matrix
    require(encoding in ('g1-serial-axes-v1','g1-anatomical-frames-v2'),
            'MOTION_BRICKS_RETARGET_PROFILE','Unknown anatomical frame calibration')
    require(rig.type=='ARMATURE' and skeleton['id']=='g1skel34' and len(skeleton['parents'])==34,
            'MOTION_BRICKS_RETARGET_PROFILE','Expected an armature and exact G1 model skeleton')
    required=set(GROUPS)|{item[2] for item in PRIMARY.values()}
    require(set(roles)==required and len(set(roles.values()))==len(roles),
            'MOTION_BRICKS_RETARGET_PROFILE','Supply one distinct observed bone for every anatomical role')
    require(all(name in rig.data.bones for name in roles.values()),
            'MOTION_BRICKS_RETARGET_PROFILE','A mapped anatomical bone is missing')
    for chain in CHAINS:
        for parent,child in zip(chain,chain[1:]):
            require(rig.data.bones[roles[parent]] in rig.data.bones[roles[child]].parent_recursive,
                    'MOTION_BRICKS_RETARGET_TOPOLOGY',f'{child} does not descend from {parent}')
    linear=rig.matrix_world.to_3x3();scales=[linear.col[i].length for i in range(3)]
    require(min(scales)>0 and max(scales)-min(scales)<1e-5 and linear.determinant()>0,
            'MOTION_BRICKS_RETARGET_SCALE','Only positive uniform object scale is supported')
    gram=linear.transposed()@linear
    require(max(abs(gram[i][j]) for i in range(3) for j in range(3) if i!=j)<1e-5,
            'MOTION_BRICKS_RETARGET_SCALE','Sheared rest geometry is unsupported')
    require(type(ground_z) in (float,int) and math.isfinite(ground_z),
            'MOTION_BRICKS_RETARGET_GROUND','Supply an observed flat ground height')
    heads={role:rig.matrix_world@rig.data.bones[name].head_local for role,name in roles.items()}
    # Derive directions without translated world coordinates. Subtracting two
    # large translated floats changed the saved alignment after playback.
    inv=axes().inverted()
    canonical={role:inv@(linear@rig.data.bones[name].head_local) for role,name in roles.items()}
    # A pelvis control's head may be below the hip sockets (as on Adventurer).
    # Validate the leg chain and nearby pelvis, not a false root-head ordering.
    require(canonical['left_thigh'].x>canonical['right_thigh'].x
            and canonical['chest'].y>canonical['pelvis'].y
            and all(canonical[s+'_thigh'].y>canonical[s+'_shin'].y>canonical[s+'_foot'].y
                    and canonical['pelvis'].y>canonical[s+'_shin'].y
                    and abs(canonical['pelvis'].y-canonical[s+'_thigh'].y)<.25*(canonical['chest'].y-canonical[s+'_foot'].y)
                    for s in ('left','right')),
            'MOTION_BRICKS_RETARGET_GEOMETRY','Role geometry is not an upright, left/right-consistent humanoid')
    # Mapping scale belongs to the reviewed rest placement, not the current
    # animated vertical/root offset. Playback must not invalidate the profile.
    if reference_origin_z is None:reference_origin_z=float(rig.matrix_world.translation.z)
    require(type(reference_origin_z) in (float,int) and math.isfinite(reference_origin_z),
            'MOTION_BRICKS_RETARGET_PROFILE','Invalid reviewed rest placement')
    height=(linear@rig.data.bones[roles['pelvis']].head_local).z+reference_origin_z-ground_z
    model_height=-min(p[1] for p in skeleton['neutral_joints'])
    require(.2<height<4 and .1<model_height/height<5,
            'MOTION_BRICKS_RETARGET_SCALE','Pelvis/ground height is implausible')
    alignment={role:Quaternion().copy() for role in GROUPS}
    for role,(start,end,target_end) in PRIMARY.items():
        a=Vector(skeleton['neutral_joints'][end])-Vector(skeleton['neutral_joints'][start])
        b=canonical[target_end]-canonical[role]
        require(min(a.length,b.length)>.005,'MOTION_BRICKS_RETARGET_GEOMETRY',f'Degenerate {role} segment')
        alignment[role]=a.normalized().rotation_difference(b.normalized())
    if encoding=='g1-anatomical-frames-v2':
        # A direction alone leaves twist unconstrained. Independent shortest
        # rotations can turn a native elbow into a three-axis model joint even
        # in the rest pose. Calibrate the complete arm plane, using the segment
        # owned by the final shoulder axis (20/28), not the earlier virtual axis.
        # This depends on reviewed rest geometry, never Action labels or pairs.
        def frame(direction,normal):
            u=direction.normalized();n=normal-u*normal.dot(u)
            require(n.length>1e-5,'MOTION_BRICKS_HINGE_CALIBRATION','Straight or degenerate rest arms need a reviewed bent-rest anatomical calibration')
            n.normalize();return Matrix((u,n,u.cross(n))).transposed()
        for side,upper,elbow,wrist in (('left',20,21,22),('right',28,29,30)):
            model_a=Vector(skeleton['neutral_joints'][elbow])-Vector(skeleton['neutral_joints'][upper])
            model_b=Vector(skeleton['neutral_joints'][wrist])-Vector(skeleton['neutral_joints'][elbow])
            native_a=canonical[side+'_forearm']-canonical[side+'_upper_arm']
            native_b=canonical[side+'_hand']-canonical[side+'_forearm']
            mn=model_a.normalized().cross(model_b.normalized());nn=native_a.normalized().cross(native_b.normalized())
            require(nn.length>.02,'MOTION_BRICKS_HINGE_CALIBRATION','Rest elbow bend is too small to determine a stable anatomical plane; use a reviewed rig calibration')
            for role,model_direction,native_direction in ((side+'_upper_arm',model_a,native_a),(side+'_forearm',model_b,native_b)):
                alignment[role]=(frame(native_direction,nn)@frame(model_direction,mn).transposed()).to_quaternion().normalized()
    require(reference_height_m is None or type(reference_height_m) in (int,float) and math.isfinite(reference_height_m) and .3 <= reference_height_m <= 5.,
            'MOTION_BRICKS_REFERENCE_HEIGHT','Supply a fixed reviewed full-character height in metres (0.3 to 5)')
    return {'schema':'motion-bricks.explicit-humanoid-profile.v1','rig':rig.name,
            **({'reference_height_m':reference_height_m} if reference_height_m is not None else {}),
            'rest_identity':rest_identity(rig),'skeleton':skeleton,'roles':dict(roles),
            'encoding':encoding,
            'alignment_wxyz':{r:list(q) for r,q in alignment.items()},
            'world_to_model_scale':model_height/height,'ground_z':ground_z,'reference_origin_z':reference_origin_z,
            'mapping_status':'GEOMETRY_VALIDATED_REQUIRES_ROUNDTRIP_AND_GENERATED_QUALITY',
            'limitations':['Fixed G1 body proportions during inference','No source contact annotations inferred',
                           'Head/fingers/toes outside physical model require separate preserved bridge channels']}


def encode_pose(rig, profile, *, world_origin, placement=(0,0,0)):
    import bpy
    from mathutils import Vector, Quaternion
    require(rest_identity(rig)==profile['rest_identity'],'MOTION_BRICKS_RETARGET_PROFILE','Rig rest or object linear transform changed')
    evaluated=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
    C=axes();Ci=C.inverted();object_rotation=rig.matrix_world.to_quaternion().to_matrix()
    world=[];by_index={i:role for role,indices in GROUPS.items() for i in indices}
    for i in range(34):
        role=by_index[i];name=profile['roles'][role];bone=rig.data.bones[name]
        posed=evaluated.matrix_world.to_quaternion().to_matrix()@evaluated.pose.bones[name].matrix.to_quaternion().to_matrix()
        rest=object_rotation@bone.matrix_local.to_quaternion().to_matrix()
        world.append(((Ci@posed@rest.inverted()@C).to_quaternion()@Quaternion(profile['alignment_wxyz'][role])).normalized())
    root=evaluated.matrix_world@evaluated.pose.bones[profile['roles']['pelvis']].head
    root=Ci@(root+Vector(placement)-Vector(world_origin))*profile['world_to_model_scale']
    local=[]
    for i,q in enumerate(world):
        parent=profile['skeleton']['parents'][i];value=(world[parent].inverted()@q if parent>=0 else q).normalized()
        local.append([value.x,value.y,value.z,value.w])
    return list(root),factor_joint_groups(local)


def decode_rotations(rig,profile,local_xyzw):
    from mathutils import Quaternion
    C=axes();Ci=C.inverted();globals_=[]
    for i,raw in enumerate(local_xyzw):
        q=Quaternion((raw[3],*raw[:3]));parent=profile['skeleton']['parents'][i]
        globals_.append((globals_[parent]@q if parent>=0 else q).normalized())
    object_rotation=rig.matrix_world.to_quaternion().to_matrix();result={}
    for role,index in OUTPUT.items():
        name=profile['roles'][role];q=globals_[index]@Quaternion(profile['alignment_wxyz'][role]).inverted()
        deformation=C@q.to_matrix()@Ci
        rest=object_rotation@rig.data.bones[name].matrix_local.to_quaternion().to_matrix()
        result[name]=(object_rotation.inverted()@deformation@rest).to_quaternion().normalized()
    return result


def apply_rotations(rig,rotations):
    import bpy
    for bone in rig.data.bones:
        if bone.name not in rotations:continue
        pb=rig.pose.bones[bone.name];matrix=rotations[bone.name].to_matrix().to_4x4();matrix.translation=pb.matrix.translation
        parent={'parent_matrix':pb.parent.matrix,'parent_matrix_local':bone.parent.matrix_local} if bone.parent else {}
        basis=bone.convert_local_to_pose(matrix,bone.matrix_local,invert=True,**parent)
        q=basis.to_quaternion().normalized()
        if pb.rotation_mode=='QUATERNION':pb.rotation_quaternion=q
        elif pb.rotation_mode=='AXIS_ANGLE':pb.rotation_axis_angle=(q.angle,*q.axis)
        else:pb.rotation_euler=q.to_euler(pb.rotation_mode,pb.rotation_euler)
        bpy.context.view_layer.update()


def load_profile(rig):
    raw = rig.get(PROPERTY)
    require(isinstance(raw, str) and len(raw.encode('utf-8')) <= 65536,
            'MOTION_BRICKS_PROFILE_REQUIRED', 'Prepare an explicit reviewed humanoid mapping in Blender before generated transitions')
    try:
        profile = json.loads(raw)
        require(profile.get('schema') == 'motion-bricks.explicit-humanoid-profile.v1',
                'MOTION_BRICKS_RETARGET_PROFILE', 'Unsupported rig mapping version')
        rebuilt = build_profile(rig, profile['skeleton'], profile['roles'], profile['ground_z'], reference_origin_z=profile['reference_origin_z'], reference_height_m=profile.get('reference_height_m'), encoding=profile.get('encoding'))
        require(profile.get('encoding') == rebuilt['encoding'] and profile['rest_identity'] == rebuilt['rest_identity'] and
                profile['alignment_wxyz'] == rebuilt['alignment_wxyz'] and
                abs(profile['world_to_model_scale'] - rebuilt['world_to_model_scale']) < 1e-9,
                'MOTION_BRICKS_RETARGET_PROFILE', 'Rig rest, mapping or scale changed; prepare the mapping again')
        return profile
    except (KeyError, TypeError, ValueError) as error:
        from .core import DirectorError
        raise DirectorError('MOTION_BRICKS_RETARGET_PROFILE', 'Malformed explicit rig mapping') from error


def describe(rig):
    from .core import DirectorError
    from .motion_bricks_provider import configured, capabilities
    try:
        profile = load_profile(rig)
        config = configured()
        return {'status': 'CONFIGURED' if config else 'NOT_CONFIGURED',
                'profile_sha256': digest(profile), 'provider': capabilities(config),
                'blocker': None if config else 'Set up the pinned local MotionBricks provider first',
                'contact_acceptance': 'NOT_VERIFIED'}
    except (DirectorError, OSError, ValueError, TypeError) as error:
        return {'status': 'UNAVAILABLE', 'profile_sha256': None, 'blocker': str(error)}


def factor_joint_groups(local_xyzw):
    """Distribute ball-joint rotation over the verified G1 serial axes.

    Numeric axes/rest offsets: NVlabs/GR00T-WholeBodyControl at
    a0732b642c0333077e127a2f56ab0014c196bca4, motionbricks/assets/skeletons/g1/g1.xml
    SHA256 5d76cf92f00dd49d6eb9fae38d7d38e46886848b602ac691051e886c3bcccfb1.
    Converts MuJoCo XYZ to model ZXY. Preserves group-end orientation; this
    does not assert physical feasibility of every other humanoid channel.
    """
    from mathutils import Matrix, Vector, Quaternion
    from . import sequence_math as qm
    identity=(1.,0.,0.,0.)
    hip=(.9961787462234497,-.08733861893415451,0.,0.)
    left=(.9902641773223877,1.387219708703924e-5,-9.8686788987834e-5,.13920098543167114)
    right=(left[0],left[1],-left[2],-left[3])
    left_roll=(.9902682900428772,0.,0.,-.13917197287082672)
    right_roll=(left_roll[0],0.,0.,-left_roll[3])
    groups=[((1,2,3),'XZY',(identity,hip,identity)),((8,9,10),'XZY',(identity,hip,identity)),
            ((18,19,20),'XZY',(left,left_roll,identity)),((26,27,28),'XZY',(right,right_roll,identity)),
            ((22,23,24),'ZXY',(identity,)*3),((30,31,32),'ZXY',(identity,)*3)]
    result=[list(q) for q in local_xyzw]
    for group,order,offsets in groups:
        target=Quaternion()
        for index in group:
            q=result[index];target=target@Quaternion((q[3],*q[:3]))
        axes=[Vector(tuple(float(i=='XYZ'.index(axis)) for i in range(3))) for axis in order]
        rests=[Quaternion(q) for q in offsets]
        def compose(angles):
            values=[q@Quaternion(axis,float(v)) for q,axis,v in zip(rests,axes,angles)]
            return values,values[0]@values[1]@values[2]
        angles=Vector((0.,0.,0.))
        for _ in range(50):
            values,q=compose(angles);error=Vector(qm.qlog(qm.qmul(qm.inverse(list(q)),list(target))))
            if error.length<2e-6:break
            columns=[]
            for j in range(3):
                moved=angles.copy();moved[j]+=.001;_,rotated=compose(moved)
                columns.append(Vector(qm.qlog(qm.qmul(qm.inverse(list(q)),list(rotated))))/.001)
            jacobian=Matrix(columns).transposed()
            delta=(jacobian.transposed()@jacobian+Matrix.Identity(3)*1e-6).inverted()@(jacobian.transposed()@error)
            if delta.length>.4:delta*=.4/delta.length
            angles+=delta
        values,q=compose(angles)
        require(qm.norm(qm.qlog(qm.qmul(qm.inverse(list(q)),list(target))))<1e-5,
                'MOTION_BRICKS_RETARGET_AXES','Native pose cannot be represented reliably by the G1 joint axes')
        for index,q in zip(group,values):result[index]=[q.x,q.y,q.z,q.w]
    return result
