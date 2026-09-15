"""Reviewed target-space sequencing: complete clips plus a reversible bridge.

Only Actions are appended from verified retarget results; no source character is
imported or target skin replaced. A constant planar transform changes only the
incoming anchor channels in a COPY. A quintic/log-quaternion bridge is a separate
Action. NLA references those Actions at native speed without overlapping away any
part of either clip. This is kinematic interpolation, not a contact/IK solver.
"""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
import re
import bpy
from mathutils import Matrix, Vector, Quaternion
from .core import require, digest, atomic_json, load_json
from . import blender_ops as ops, sequence_math as sm, sequence_contract as sc
from . import sequence_review as reviews, transfer_blender as tb

PATH = re.compile(r'^pose\.bones\[("(?:[^"\\]|\\.)*")\]\.(location|rotation_quaternion)$')


def frame(f):
    bpy.context.scene.frame_set(math.floor(f), subframe=f-math.floor(f))
    bpy.context.view_layer.update()


def flat(m): return [float(v) for row in m for v in row]


def signature(action, slot):
    return tb.action_signature(action, slot)


def snapshot(target):
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and
              any(m.type == 'ARMATURE' and m.object == target for m in o.modifiers)]
    require(sum(len(o.data.vertices) for o in meshes) <= 2000000, 'RESOURCE_LIMIT', 'Target preservation mesh budget exceeded')
    return {'rig': ops.rig_report(target)['fingerprint'], 'world': flat(target.matrix_world),
            'skin': digest([{'name':o.name, 'verts':[list(v.co) for v in o.data.vertices],
                            'weights':[[(g.group, g.weight) for g in v.groups] for v in o.data.vertices],
                            'groups':[g.name for g in o.vertex_groups],
                            'polygons':[list(p.vertices) for p in o.data.polygons],
                            'materials':[m.name if m else None for m in o.data.materials]} for o in meshes]),
            'display': ops.rig_report(target)['bone_display'],
            'object_inventory': sorted([o.name, o.type] for o in bpy.data.objects),
            'actions': {a.name: signature(a, None) for a in bpy.data.actions}}


def preserve(before, target):
    after = snapshot(target)
    for k in ('rig', 'world', 'skin', 'display', 'object_inventory'):
        require(before[k] == after[k], 'SEQUENCE_PRESERVATION_FAILED', 'Existing target changed: '+k)
    require(all(after['actions'].get(n) == sig for n, sig in before['actions'].items()),
            'SEQUENCE_PRESERVATION_FAILED', 'An original action changed or disappeared')
    return {'mesh_weights_rest_display_objects_original_actions': 'PRESERVED',
            'original_action_count': len(before['actions'])}


def append_clip(lib, descriptor, target):
    path = lib.verify_file(descriptor['file'])
    # Always read the authoritative hashed result, not an existing same-name
    # Action or caller-editable custom property that claims the same job.
    with bpy.data.libraries.load(str(path), link=False) as (source, dest):
        require(descriptor['action'] in source.actions, 'SEQUENCE_CLIP_INVALID', 'Bound action absent from result')
        dest.actions = [descriptor['action']]
    action = dest.actions[0]
    action.use_fake_user = True
    require(action and action.get('bad_job') == descriptor['job_id']
            and action.get('bad_target_fingerprint') == descriptor['target_fingerprint'],
            'SEQUENCE_CLIP_INVALID', 'Action job/target identity mismatch')
    ops.assign(target, action, descriptor['slot'])
    slot = target.animation_data.action_slot
    require(all(abs(a-b) < 1e-5 for a,b in zip(ops.action_range(action,slot), descriptor['range'])),
            'SEQUENCE_CLIP_INVALID', 'Action range differs from receipt')
    return action, slot


def validate_action(target, action, slot, anchor):
    paths = {}; times = {'location': set(), 'rotation_quaternion': set()}
    for c in ops.curves(action, slot):
        match = PATH.fullmatch(c.data_path)
        require(match and not c.modifiers, 'SEQUENCE_CHANNEL_UNSUPPORTED', 'Use baked pose location/quaternion channels without modifiers')
        bone, prop = json.loads(match[1]), match[2]
        require(bone in target.pose.bones and c.array_index < (3 if prop == 'location' else 4),
                'SEQUENCE_CHANNEL_UNSUPPORTED', 'Unknown pose channel')
        paths.setdefault(bone, set()).add((prop, c.array_index))
        vals = [float(k.co.y) for k in c.keyframe_points]
        require(vals and all(math.isfinite(v) for v in vals) and all(k.interpolation == 'LINEAR' for k in c.keyframe_points),
                'SEQUENCE_CHANNEL_UNSUPPORTED', 'Native target clips must have finite linear baked curves')
        if prop == 'location' and bone != anchor:
            require(max(vals)-min(vals) < 1e-5, 'SEQUENCE_ROOT_OWNERSHIP', 'A second bone has animated translation')
        if bone == anchor: times[prop].update(float(k.co.x) for k in c.keyframe_points)
        # Every animated bone must belong to the same anatomical subtree. A
        # stationary floor-level root remains unmapped and is not another owner.
        b = target.data.bones[bone]
        while b and b.name != anchor: b = b.parent
        require(b is not None, 'SEQUENCE_ROOT_OWNERSHIP', 'Animated bone is outside the declared anchor subtree')
    expected = {('location',i) for i in range(3)} | {('rotation_quaternion',i) for i in range(4)}
    require(anchor in paths and all(v == expected for v in paths.values()),
            'SEQUENCE_CHANNEL_UNSUPPORTED', 'Use complete location/quaternion channels for each keyed bone')
    for bone in paths:
        require(target.pose.bones[bone].rotation_mode == 'QUATERNION',
                'SEQUENCE_CHANNEL_UNSUPPORTED', 'Target keyed bones must retain reviewed quaternion mode')
    return paths, {k:sorted(v) for k,v in times.items()}


class Reader:
    def __init__(self, target, limit):
        self.target = target; self.limit = limit; self.count = 0
        self.basis = {p.name:p.matrix_basis.copy() for p in target.pose.bones}
        self.world = flat(target.matrix_world)

    def read(self, action, slot, f):
        self.count += 1
        require(self.count <= self.limit, 'RESOURCE_LIMIT', 'Sequence pose-evaluation budget exceeded')
        target = self.target
        ops.assign(target, action, slot.identifier)
        for track in target.animation_data.nla_tracks: track.mute = True
        for p in target.pose.bones: p.matrix_basis = self.basis[p.name]
        frame(f)
        require(flat(target.matrix_world) == self.world, 'SEQUENCE_ROOT_OWNERSHIP',
                'Animated object placement conflicts with pose-anchor ownership')
        ev = target.evaluated_get(bpy.context.evaluated_depsgraph_get())
        result = {}
        for pb in target.pose.bones:
            require(max(abs(v-1) for v in pb.scale) < 1e-5, 'SEQUENCE_SCALE_UNSUPPORTED', 'Pose scaling is not supported')
            result[pb.name] = {'location': list(pb.location), 'q': list(pb.rotation_quaternion),
                               'world': target.matrix_world @ ev.pose.bones[pb.name].matrix}
        return result


def transformed(reader, action, slot, f, anchor, transform):
    state = reader.read(action, slot, f)
    pb = reader.target.pose.bones[anchor]; bone = pb.bone
    desired = reader.target.matrix_world.inverted() @ transform @ state[anchor]['world']
    if pb.parent:
        basis = bone.convert_local_to_pose(desired, bone.matrix_local,
            parent_matrix=pb.parent.matrix, parent_matrix_local=pb.parent.bone.matrix_local, invert=True)
    else: basis = bone.convert_local_to_pose(desired, bone.matrix_local, invert=True)
    loc, q, scale = basis.decompose()
    require(max(abs(v-1) for v in scale) < 1e-4, 'SEQUENCE_SCALE_UNSUPPORTED', 'Anchor transform would introduce scale')
    state[anchor]['location'] = list(loc); state[anchor]['q'] = list(q.normalized())
    for name in state:
        bone = reader.target.data.bones[name]
        while bone and bone.name != anchor: bone = bone.parent
        if bone: state[name]['world'] = transform @ state[name]['world']
    return state


def velocity(a, b, dt, name):
    return sm.mul(sm.sub(b[name]['location'], a[name]['location']), 1/dt)


def world_velocity(a, b, dt, name):
    return (b[name]['world'].translation-a[name]['world'].translation)/dt


def load_clips(lib, request, target, reader):
    descriptors = []; actions = []; roles = {}; anchor = None
    fp = ops.rig_report(target)['fingerprint']; world = flat(target.matrix_world)
    for item in request['clips']:
        d, _, _ = reviews.clip(lib, item['job_id'])
        require(d['owner'] == target.name and d['target_fingerprint'] == fp
                and max(abs(a-b) for a,b in zip(d['world'], world)) < 1e-5,
                'STALE_SEQUENCE_BINDING', 'Clip belongs to another target/rest/world placement')
        require(abs(d['meters_per_unit']-request['meters_per_unit']) < 1e-9,
                'SEQUENCE_UNIT_MISMATCH', 'Use the reviewed target unit conversion, not the source scale')
        require(anchor is None or anchor == d['anchor'], 'SEQUENCE_ROOT_OWNERSHIP', 'Clips disagree on target anchor')
        anchor = d['anchor']
        for role, name in d['roles'].items():
            require(role not in roles or roles[role] == name, 'SEQUENCE_ROLE_CONFLICT', 'Reviewed roles disagree')
            roles[role] = name
        action, slot = append_clip(lib, d, target)
        paths, times = validate_action(target, action, slot, anchor)
        d['curve_signature'] = signature(action, slot); d['bones'] = sorted(paths)
        d['anchor_key_times'] = times
        require(not descriptors or sorted(paths) == descriptors[0]['bones'],
                'SEQUENCE_CHANNEL_COVERAGE', 'Clips must cover the same keyed bones; missing channels need an explicit pose-fill review')
        descriptors.append(d); actions.append((action, slot))
    for pb in target.pose.bones:
        if pb.name not in descriptors[0]['bones']:
            require(max(abs(pb.matrix_basis[r][c]-(r==c)) for r in range(4) for c in range(4)) < 1e-5,
                    'SEQUENCE_REFERENCE_REVIEW', 'Unkeyed controls must retain the retargeter rest reference')
    from .transfer_contract import role_map
    role_map(roles)
    report = ops.rig_report(target, roles)
    require(report['anatomical_height'] and report['anatomical_height'] > 0,
            'SEQUENCE_ROLE_REVIEW_REQUIRED', 'Reviewed sequence anatomy is incomplete')
    return descriptors, actions, roles, anchor


def plan(lib, spec):
    tb.guard(); request = spec['options']; sc.validate('sequence-plan', request)
    target = bpy.data.objects.get(request['target_object']); tb.rigid_object(target)
    target.animation_data_create()
    require(not target.animation_data.use_tweak_mode, 'SEQUENCE_STATE_CHANGED', 'Exit NLA tweak mode before planning')
    before = snapshot(target)
    reader = Reader(target, request['budget']['max_pose_samples'])
    descriptors, actions, roles, anchor = load_clips(lib, request, target, reader)
    fps = request['fps']; timeline = []; joins = []; cursor = 1.0
    for pb in target.pose.bones:
        require(max(abs(v-1) for v in pb.scale) < 1e-5, 'SEQUENCE_SCALE_UNSUPPORTED', 'Pose scales must remain one')
    transforms = [Matrix.Identity(4)]
    created_keys = sum(sum(len(c.keyframe_points) for c in ops.curves(a,s)) for a,s in actions)
    for i, d in enumerate(descriptors):
        if i:
            cfg = request['joins'][i-1]; pa, ps = actions[i-1]; a, s = actions[i]
            pd = descriptors[i-1]; dt = min(1/(fps*8), pd['duration_seconds']/4, d['duration_seconds']/4)
            A = transformed(reader,pa,ps,pd['range'][1],anchor,transforms[-1])
            Ap = transformed(reader,pa,ps,pd['range'][1]-dt*pd['fps'],anchor,transforms[-1])
            B = reader.read(a,s,d['range'][0]); Bn = reader.read(a,s,d['range'][0]+dt*d['fps'])
            yaw = Matrix.Rotation(math.radians(cfg['yaw_degrees']),4,'Z')
            endpoint = A[anchor]['world'].translation.copy()
            va = world_velocity(Ap,A,dt,anchor); vb = yaw.to_3x3() @ world_velocity(B,Bn,dt,anchor)
            displacement = (va+vb)*(cfg['duration_seconds']*.5) if cfg['placement'] == 'continue_velocity' else Vector((0,0,0))
            displacement.z = 0
            delta = endpoint+displacement-(yaw @ B[anchor]['world'].translation); delta.z = 0
            transform = Matrix.Translation(delta) @ yaw; transforms.append(transform)
            Bt = transformed(reader,a,s,d['range'][0],anchor,transform)
            names = sorted(set(pd['bones']) | set(d['bones']))
            angle = max(sm.norm(sm.qlog(sm.qmul(sm.inverse(sm.unit(A[n]['q'])), sm.unit(Bt[n]['q'])))) for n in names)
            require(angle < math.pi-.005, 'BRIDGE_ROTATION_REVIEW', 'Near-180-degree joint mismatch needs an intermediate pose')
            bridge_end = cursor+cfg['duration_seconds']*fps
            times = sm.grid(cursor,bridge_end,1/cfg['subdivisions'],2049)
            created_keys += len(times)*len(names)*7
            created_keys += sum(len(c.keyframe_points) for c in ops.curves(a,s))  # aligned copy
            joins.append({'from':i-1,'to':i,'start':cursor,'end':bridge_end,
                          'duration_seconds':cfg['duration_seconds'],'subdivisions':cfg['subdivisions'],
                          'derivative_dt_seconds':dt,'alignment':flat(transform), 'yaw_degrees':cfg['yaw_degrees'],
                          'planar_bridge_displacement_m':list(displacement*request['meters_per_unit']),
                          'unaligned_anchor_gap_m':(endpoint-B[anchor]['world'].translation).length*request['meters_per_unit'],
                          'aligned_pose_rms_m':math.sqrt(sum((A[roles[r]]['world'].translation-Bt[roles[r]]['world'].translation).length_squared for r in roles)/len(roles))*request['meters_per_unit'],
                          'max_local_joint_angle_degrees':math.degrees(angle),
                          'anchor_velocity_difference_m_s':(va-vb).length*request['meters_per_unit'],
                          'bone_names':names,'sample_frames':times,
                          'boundary_poses':{key:{r:{'position':list(state[n]['world'].translation),
                              'rotation':list(state[n]['world'].to_quaternion().normalized())} for r,n in roles.items()}
                              for key,state in (('start',A),('end',Bt))},
                          'method':'quintic_hermite_log_quaternion_exact_endpoints',
                          'contact_policy':'DIAGNOSE_ONLY','performance':'PENDING'})
            cursor = bridge_end
        duration = d['duration_seconds']
        timeline.append({'clip':i, 'start':cursor, 'end':cursor+duration*fps,
                         'source_range':d['range'], 'source_fps':d['fps'],
                         'playback_speed':1.0, 'duration_seconds':duration,
                         'alignment':flat(transforms[i])})
        cursor += duration*fps
    total = (cursor-1)/fps; budget = request['budget']
    require(total <= budget['max_duration_seconds'] and created_keys <= budget['max_created_keys'],
            'RESOURCE_LIMIT', 'Sequence duration or created-key budget exceeded')
    require(cursor-1 <= 10000, 'RESOURCE_LIMIT', 'Sequence exceeds the bounded global frame-coordinate sampling span')
    estimated_pose_samples = 129+sum(len(d['anchor_key_times']['location'])+len(d['anchor_key_times']['rotation_quaternion'])
                                     for d in descriptors[1:])+24*len(joins)
    require(estimated_pose_samples <= budget['max_pose_samples'], 'RESOURCE_LIMIT',
            'Alignment, seam and sparse-global pose work exceeds the reviewed budget')
    require(reader.count <= budget['max_pose_samples'], 'RESOURCE_LIMIT', 'Planning pose work exceeds budget')
    contact_frames = sorted(set([1+(cursor-1)*i/64 for i in range(65)] +
                                [f for j in joins for f in sm.grid(j['start'],j['end'],.5/j['subdivisions'],2049)]))
    measured_contact_samples = len(contact_frames) + (len(contact_frames)-2)//256
    require(measured_contact_samples <= budget['max_contact_samples'], 'RESOURCE_LIMIT', 'Sequence contact checkpoint budget exceeded')
    if request['contact'] is not None:
        mesh = bpy.data.objects.get(request['contact']['mesh'])
        require(mesh and mesh.type == 'MESH', 'TARGET_REQUIRED', 'Contact mesh is absent')
        # GroundContact evaluates twice per checkpoint (left/right) and verifies
        # topology. Bound that actual work across batches, not just each batch.
        require(2*measured_contact_samples*len(mesh.data.vertices) <= budget['max_mesh_evaluations'],
                'RESOURCE_LIMIT', 'Total sequence contact mesh-evaluation budget exceeded')
    # Planning only owns a disposable process and never publishes a target blend.
    result = {'schema':sc.SCHEMA,'status':'REVIEW_REQUIRED','request':copy.deepcopy(request),
              'target_fingerprint':before['rig'],'target_world':before['world'], 'roles':roles,'anchor':anchor,
              'clips':descriptors,'timeline':timeline,'joins':joins,'fps':fps,'duration_seconds':total,
              'final_key_frame':cursor,'contact_frames':contact_frames,'preservation_baseline':before,
              'estimated_created_keys':created_keys,'estimated_pose_samples':estimated_pose_samples,
              'estimated_contact_samples_including_batch_boundaries':measured_contact_samples,
              'planning_pose_evaluations':reader.count,
              'root_owner':'existing target pose-bone anchor; no added object controller',
              'full_clips':True,'source_time_warp':False,'performance':'PENDING',
              'limits':['not full inertialization, IK, foot locking or a naturalness guarantee',
                        'explicit yaw; no guess from travel direction','native linear baked pose curves only',
                        'constant target world placement across source results',
                        'interpolated bridge may overshoot or penetrate; inspect measured evidence']}
    result['id'] = 'sq_'+digest(result)
    return result


def align_action(reader, original, slot, descriptor, anchor, transform, label):
    data = {}
    for prop, times in descriptor['anchor_key_times'].items():
        data[prop] = []
        previous = None
        for f in times:
            pose = transformed(reader,original,slot,f,anchor,transform)[anchor]
            v = pose['location'] if prop == 'location' else pose['q']
            if prop == 'rotation_quaternion' and previous and sm.dot(previous,v) < 0: v = sm.mul(v,-1)
            data[prop].append((f,v)); previous = v
    result = original.copy(); result.name = label; result.use_fake_user = True
    ops.assign(reader.target,result,slot.identifier)
    dest_slot = reader.target.animation_data.action_slot
    pb = reader.target.pose.bones[anchor]
    for c in ops.curves(result,dest_slot):
        if c.data_path in (pb.path_from_id('location'),pb.path_from_id('rotation_quaternion')):
            c.keyframe_points.clear()
    for prop, entries in data.items():
        for f,v in entries:
            setattr(pb,prop,v); pb.keyframe_insert(prop,frame=f,group=anchor)
    for c in ops.curves(result,dest_slot):
        if c.data_path in (pb.path_from_id('location'),pb.path_from_id('rotation_quaternion')):
            for k in c.keyframe_points: k.interpolation='LINEAR'
    return result,dest_slot


def bridge_action(reader, actions, descriptors, joins, index, anchor, transforms, fps, label):
    j = joins[index]; a, sa = actions[index]; b, sb = actions[index+1]
    da, db = descriptors[index], descriptors[index+1]; dt=j['derivative_dt_seconds']; T=j['duration_seconds']
    A = transformed(reader,a,sa,da['range'][1],anchor,transforms[index])
    Ap = transformed(reader,a,sa,da['range'][1]-dt*da['fps'],anchor,transforms[index])
    B = transformed(reader,b,sb,db['range'][0],anchor,transforms[index+1])
    Bn = transformed(reader,b,sb,db['range'][0]+dt*db['fps'],anchor,transforms[index+1])
    names = j['bone_names']; target=reader.target
    tangents={n:(velocity(Ap,A,dt,n),velocity(B,Bn,dt,n),
                 sm.mul(sm.angular_velocity(A[n]['q'],Ap[n]['q'],dt),-1),
                 sm.angular_velocity(B[n]['q'],Bn[n]['q'],dt)) for n in names}
    def evaluate(n,u):
        va,vb,wa,wb=tangents[n]
        return sm.hermite(A[n]['location'],B[n]['location'],va,vb,T,u), sm.rotation_bridge(A[n]['q'],B[n]['q'],wa,wb,T,u)
    result=bpy.data.actions.new(label); ops.assign(target,result); result.use_fake_user=True
    for global_frame in j['sample_frames']:
        u=(global_frame-j['start'])/(j['end']-j['start']); u=min(1,max(0,u))
        local_frame=1+global_frame-j['start']
        for n in names:
            p,q=evaluate(n,u); pb=target.pose.bones[n]
            pb.location=p;pb.rotation_quaternion=q
            pb.keyframe_insert('location',frame=local_frame,group=n)
            pb.keyframe_insert('rotation_quaternion',frame=local_frame,group=n)
    # Tangent-aware Bezier handles preserve endpoint slope far better than a
    # piecewise linear bake. Internal interpolation is still an approximation.
    slot=target.animation_data.action_slot
    for c in ops.curves(result,slot):
        match=PATH.fullmatch(c.data_path); n=json.loads(match[1]); prop=match[2]
        ks=list(c.keyframe_points)
        for i,k in enumerate(ks):
            u=(float(k.co.x)-1)/(T*fps); u=min(1,max(0,u)); h=1e-5
            lo=max(0,u-h);hi=min(1,u+h)
            p0,q0=evaluate(n,lo); p1,q1=evaluate(n,hi)
            vv0=p0 if prop=='location' else q0;vv1=p1 if prop=='location' else q1
            slope=(vv1[c.array_index]-vv0[c.array_index])/((hi-lo)*T*fps)
            left=(float(k.co.x)-float(ks[i-1].co.x))/3 if i else (float(ks[1].co.x)-float(k.co.x))/3
            right=(float(ks[i+1].co.x)-float(k.co.x))/3 if i<len(ks)-1 else left
            k.interpolation='BEZIER';k.handle_left_type='FREE';k.handle_right_type='FREE'
            k.handle_left=(k.co.x-left,k.co.y-slope*left);k.handle_right=(k.co.x+right,k.co.y+slope*right)
        c.update()
    return result,slot


def nla(target, action, slot, source_range, source_fps, fps, start, label, final=False):
    track=target.animation_data.nla_tracks.new();track.name=label
    strip=track.strips.new(label,math.floor(start),action)
    strip.action_slot=slot;strip.action_frame_start=source_range[0];strip.action_frame_end=source_range[1]
    strip.scale=fps/source_fps;strip.repeat=1;strip.frame_start_ui=start
    strip.extrapolation='HOLD_FORWARD' if final else 'NOTHING'
    strip.blend_type='REPLACE';strip.blend_in=0;strip.blend_out=0;strip.use_auto_blend=False;strip.influence=1
    end=start+(source_range[1]-source_range[0])*fps/source_fps
    require(abs(strip.frame_start-start)<1e-4 and abs(strip.frame_end-end)<1e-4,
            'SEQUENCE_TIMING_FAILED','NLA strip timing differs from the exact plan')
    return {'track':track.name,'action':action.name,'slot':slot.identifier,
            'start':float(strip.frame_start),'end':float(strip.frame_end),'source_range':source_range,
            'scale':float(strip.scale),'signature':signature(action,slot),'extrapolation':strip.extrapolation}


def check(target,manifest):
    tb.rigid_object(target)
    require(ops.rig_report(target)['fingerprint']==manifest['target_fingerprint']
            and flat(target.matrix_world)==manifest['target_world'],
            'SEQUENCE_STATE_CHANGED','Target rest or world placement changed')
    require(target.animation_data.action is None,'SEQUENCE_STATE_CHANGED','An active action overrides sequence NLA')
    expected_tracks = {x['track'] for x in manifest['strips']}
    require({t.name for t in target.animation_data.nla_tracks if not t.mute} == expected_tracks
            and target.animation_data.use_nla and not any(t.is_solo for t in target.animation_data.nla_tracks),
            'SEQUENCE_STATE_CHANGED', 'Another track, solo setting or disabled NLA changes the reviewed composition')
    for item in manifest['strips']:
        track=target.animation_data.nla_tracks.get(item['track'])
        require(track and not track.mute and len(track.strips)==1,'SEQUENCE_STATE_CHANGED','Sequence track missing or muted')
        strip=track.strips[0]
        require(strip.action.name==item['action'] and strip.action_slot.identifier==item['slot']
                and signature(strip.action,strip.action_slot)==item['signature']
                and abs(strip.frame_start-item['start'])<1e-5 and abs(strip.frame_end-item['end'])<1e-5
                and abs(strip.scale-item['scale'])<1e-6 and strip.repeat==1 and strip.blend_in==0 and strip.blend_out==0
                and strip.blend_type=='REPLACE' and not strip.use_animated_time and not strip.use_animated_influence
                and not strip.mute and abs(strip.influence-1)<1e-7 and not strip.use_auto_blend
                and strip.extrapolation==item['extrapolation']
                and abs(strip.action_frame_start-item['source_range'][0])<1e-5
                and abs(strip.action_frame_end-item['source_range'][1])<1e-5,
                'SEQUENCE_STATE_CHANGED','Action, slot, placement or influence changed')
    for original in manifest['source_original_signatures']:
        action = bpy.data.actions.get(original['imported_action'])
        require(action is not None, 'SEQUENCE_STATE_CHANGED', 'Original clip action disappeared')
        slots = [s for s in action.slots if s.identifier == original['slot']]
        require(len(slots)==1 and signature(action, slots[0])==original['curve_signature'],
                'SEQUENCE_STATE_CHANGED', 'Original clip curves changed')
    preserve(manifest['preservation_baseline'], target)
    report=ops.rig_report(target,manifest['roles']);fps=manifest['fps'];meters=manifest['meters_per_unit']
    scene=bpy.context.scene
    require(abs(scene.render.fps/scene.render.fps_base-fps)<1e-6,'SEQUENCE_STATE_CHANGED','Sequence FPS changed')
    from .motion_morph import inclusive_scene_end
    expected_end, _ = inclusive_scene_end(1, manifest['duration_seconds'], fps)
    require(scene.frame_start==1 and scene.frame_end==expected_end, 'SEQUENCE_STATE_CHANGED', 'Sequence playback range changed')
    boundaries=sorted(set(f for j in manifest['joins'] for f in (j['start'],j['end'])))
    seams=[]; endpoint_errors=[]
    with ops.restore_context():
        for join in manifest['joins']:
            for key in ('start','end'):
                frame(join[key]);ev=target.evaluated_get(bpy.context.evaluated_depsgraph_get())
                pos_error=0.;rot_error=0.
                for role,name in manifest['roles'].items():
                    measured=ev.matrix_world@ev.pose.bones[name].matrix
                    expected=join['boundary_poses'][key][role]
                    pos_error=max(pos_error,(measured.translation-Vector(expected['position'])).length*meters)
                    rot_error=max(rot_error,1-abs(measured.to_quaternion().normalized().dot(Quaternion(expected['rotation']))))
                require(pos_error <= 1e-4 and rot_error <= 1e-6, 'SEQUENCE_ENDPOINT_MISMATCH',
                        'Evaluated NLA boundary differs from the reviewed source pose')
                endpoint_errors.append({'frame':join[key], 'position_error_m':pos_error,
                                        'quaternion_one_minus_abs_dot':rot_error, 'status':'PASS'})
        for f in boundaries:
            eps=1/32; points=[]
            for t in (f-eps,f,f+eps):
                frame(t);ev=target.evaluated_get(bpy.context.evaluated_depsgraph_get())
                points.append({r:(ev.matrix_world@ev.pose.bones[n].matrix).copy() for r,n in manifest['roles'].items()})
            positions=[p['hips'].translation for p in points]
            left=(positions[1]-positions[0])*(fps/eps);right=(positions[2]-positions[1])*(fps/eps)
            seams.append({'frame':f,'probe_half_width_frames':eps,
                          'anchor_velocity_change_m_s':(right-left).length*meters,
                          'max_joint_displacement_across_probe_m':max((points[2][r].translation-points[0][r].translation).length for r in points[0])*meters,
                          'max_rotation_across_probe_degrees':max(math.degrees(sm.norm(sm.qlog(sm.qmul(sm.inverse(list(points[0][r].to_quaternion().normalized())),list(points[2][r].to_quaternion().normalized()))))) for r in points[0]),
                          'max_joint_angular_velocity_change_rad_s':max(sm.norm(sm.sub(
                              sm.angular_velocity(list(points[1][r].to_quaternion()),list(points[2][r].to_quaternion()),eps/fps),
                              sm.angular_velocity(list(points[0][r].to_quaternion()),list(points[1][r].to_quaternion()),eps/fps))) for r in points[0])})
        samples=ops.samples_for(target,report,1,manifest['final_key_frame'],max_samples=129)
    contact=[];cfg=manifest['request']['contact']
    if cfg is not None:
        frames=manifest['contact_frames']
        for offset in range(0,len(frames)-1,256):
            batch=frames[offset:offset+257]
            contact.append(tb.contact_check({**cfg,'target_object':target.name,'meters_per_unit':meters,'frames':batch}))
    return {'qa_roles':manifest['roles'],'qa_anatomical_height':report['anatomical_height'],
            'duration_seconds':manifest['duration_seconds'],'final_key_frame':manifest['final_key_frame'],
            'scene_frame_end':scene.frame_end,'seams':seams,'endpoint_errors':endpoint_errors,
            'sparse_global_samples':samples,
            'contact_batches':contact,'contact_status':('NOT_MEASURED' if cfg is None else
                'SAMPLED_PENETRATION' if any(c['status']=='PENETRATION_DETECTED' for c in contact) else 'REVIEW_MEASURED_EXTREMA'),
            'performance':'PENDING','human':'NOT_ESTABLISHED',
            'scope':'finite seam differences and bounded mesh samples, not continuous C1/contact or artistic proof'}


def execute(lib,spec,directory,owner):
    tb.guard();p,_,_=reviews.proposal(lib,spec['options']['sequence_binding'])
    target=bpy.data.objects.get(p['request']['target_object']);tb.rigid_object(target)
    before=snapshot(target)
    require(before==p['preservation_baseline'],'STALE_SEQUENCE_BINDING','Target state differs from reviewed plan')
    reader=Reader(target,p['request']['budget']['max_pose_samples'])
    descriptors,actions,roles,anchor=load_clips(lib,p['request'],target,reader)
    require(descriptors==p['clips'] and roles==p['roles'],'STALE_SEQUENCE_BINDING','Clip identity/semantic evidence changed')
    fps=p['fps'];transforms=[Matrix([t['alignment'][i:i+4] for i in (0,4,8,12)]) for t in p['timeline']]
    actual=[actions[0]]
    for i in range(1,len(actions)):
        actual.append(align_action(reader,*actions[i],descriptors[i],anchor,transforms[i],f'BAD_SEQ_{owner}_ALIGNED_{i}'))
    bridges=[bridge_action(reader,actions,descriptors,p['joins'],i,anchor,transforms,fps,f'BAD_SEQ_{owner}_BRIDGE_{i}') for i in range(len(actions)-1)]
    for track in target.animation_data.nla_tracks:
        track.mute=True
        track.is_solo=False
    target.animation_data.use_nla=True
    target.animation_data.action=None
    # Restore non-animated target channels to their captured baseline. Do not
    # leave the final sampled incoming pose as a new reference for other bones.
    for pb in target.pose.bones:pb.matrix_basis=reader.basis[pb.name]
    strips=[]
    for i,(action,slot) in enumerate(actual):
        t=p['timeline'][i]
        strips.append(nla(target,action,slot,descriptors[i]['range'],descriptors[i]['fps'],fps,t['start'],f'BAD_SEQ_{owner}_CLIP_{i}',i==len(actual)-1))
        if i<len(bridges):
            j=p['joins'][i];a,s=bridges[i]
            strips.append(nla(target,a,s,[1,1+j['duration_seconds']*fps],fps,fps,j['start'],f'BAD_SEQ_{owner}_JOIN_{i}'))
    scene=bpy.context.scene;scene.render.fps=int(fps);scene.render.fps_base=int(fps)/fps;scene.frame_start=1
    from .motion_morph import inclusive_scene_end
    scene.frame_end,_=inclusive_scene_end(1,p['duration_seconds'],fps);frame(1)
    evidence=preserve(before,target)
    manifest={**p,'meters_per_unit':p['request']['meters_per_unit'],'sequence_job_id':owner,'strips':strips,
              'source_original_signatures':[{**d,'imported_action':a.name} for d,(a,_) in zip(descriptors,actions)],
              'pose_evaluations':reader.count,'preservation':evidence}
    scene['bad_sequence_id']=p['id'];atomic_json(Path(directory)/'sequence.json',manifest)
    qa=check(target,manifest)
    return {'sequence_id':p['id'],'target':target.name,'strips':strips,'roles':roles,'anchor':anchor,
            'full_clips':True,'duration_seconds':p['duration_seconds'],'final_key_frame':p['final_key_frame'],
            'fps':fps,'preservation':evidence,'qa':qa,'performance':'PENDING','human':'NOT_ESTABLISHED',
            'reversal':'original input remains unchanged; mute sequence tracks and restore prior active action/NLA for manual inspection'}


def check_job(lib,options):
    job,data,directory,_,_=reviews.completed(lib,options['sequence_job_id'],{'sequence-execute'})
    path=directory/'sequence.json'
    require(reviews.ref(lib,path) in job['outputs'],'STALE_SEQUENCE_BINDING','Sequence manifest changed')
    manifest=load_json(path)
    require(bpy.context.scene.get('bad_sequence_id')==manifest['id'],'STALE_SEQUENCE_BINDING','Wrong sequence scene')
    return check(bpy.data.objects[manifest['request']['target_object']],manifest)
