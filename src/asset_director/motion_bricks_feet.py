"""Positional G1 foot retargeting inside a generated interval only.

Mapped foot/toe skin weights identify sole geometry, not planted contacts.
Native Actions remain intact. No fabricated contact annotation or physics claim.
"""
import math
import bpy
from mathutils import Vector, Matrix, Quaternion
from .core import require, digest
from . import motion_bricks_retarget as ret, motion_bricks_stitch_math as seam, sequence_math as qm
from .motion_contacts import set_pose
from .motion_heading import rotation

SIDES = ('left', 'right')


class Soles:
    """Temporary evaluated skins bound to the isolated sampler armature."""
    def __init__(self, source, clone, roles):
        self.objects = []
        self.source_objects = {}
        self.groups = {s: [] for s in SIDES}
        vertices = 0
        try:
            for skin in list(bpy.context.scene.objects):
                if skin.type != 'MESH' or not any(m.type == 'ARMATURE' and m.object == source for m in skin.modifiers):
                    continue
                require(skin.animation_data is None and not skin.constraints and
                        all(m.type == 'ARMATURE' for m in skin.modifiers),
                        'MOTION_BRICKS_SOLE_GEOMETRY', 'Animated or additionally modified skin needs explicit Blender preparation')
                require(skin not in source.children_recursive or skin.parent == source,
                        'MOTION_BRICKS_SOLE_GEOMETRY', 'Nested animated skin parenting needs Blender preparation')
                vertices += len(skin.data.vertices)
                require(vertices <= 200000, 'RESOURCE_LIMIT', 'Foot retargeting exceeds 200000 skin vertices')
                copied = skin.copy(); copied.animation_data_clear()
                if skin.parent == source: copied.parent = clone
                for modifier in copied.modifiers:
                    require(modifier.object == source, 'MOTION_BRICKS_SOLE_GEOMETRY', 'Skin has multiple armature owners')
                    modifier.object = clone
                bpy.context.scene.collection.objects.link(copied); self.objects.append(copied)
                self.source_objects[skin.name] = copied
                for side in SIDES:
                    names = [roles[side+'_foot'], roles[side+'_toe']]
                    groups = {skin.vertex_groups[n].index for n in names if n in skin.vertex_groups}
                    indices = [v.index for v in skin.data.vertices if sum(g.weight for g in v.groups if g.group in groups) > .8]
                    if indices: self.groups[side].append((copied, indices))
            require(all(self.groups.values()), 'MOTION_BRICKS_SOLE_GEOMETRY',
                    'Both mapped feet need observed skin vertices with dominant foot/toe weights')
        except Exception:
            self.close(); raise

    def heights(self):
        result = {}; evaluated = {}
        for side, groups in self.groups.items():
            values = []
            for obj, indices in groups:
                if obj.name not in evaluated:
                    e = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                    # Keep the same evaluated geometry and world transform, but
                    # transform only the observed sole vertices. No pose cache
                    # survives this call, and sampling density is unchanged.
                    evaluated[obj.name] = (e.matrix_world, e.data.vertices)
                world, vertices = evaluated[obj.name]
                values.extend((world @ vertices[i].co).z for i in indices)
            result[side] = min(values)
        return result

    def landmark(self, mesh, vertex):
        require(mesh in self.source_objects, 'ROOT_CONTACT_VERTEX', 'Contact mesh must belong to the mapped rig')
        obj = self.source_objects[mesh]
        require(type(vertex) is int and 0 <= vertex < len(obj.data.vertices), 'ROOT_CONTACT_VERTEX', 'Contact vertex is out of range')
        e = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return e.matrix_world @ e.data.vertices[vertex].co

    def close(self):
        for obj in self.objects: bpy.data.objects.remove(obj, do_unlink=True)
        self.objects.clear()


def model_feet(skeleton, result, first, last, scale, origin):
    points = {s: [] for s in SIDES}
    for frame in range(first, last+1):
        positions = []; rotations = []
        for i, raw in enumerate(result['local_xyzw'][frame]):
            q = Quaternion((raw[3], *raw[:3])); parent = skeleton['parents'][i]
            rotations.append(rotations[parent] @ q if parent >= 0 else q)
            positions.append(Vector(result['roots'][frame]) if parent < 0 else
                             positions[parent] + rotations[parent] @ (Vector(skeleton['neutral_joints'][i])-Vector(skeleton['neutral_joints'][parent])))
        for side, index in [('left', 7), ('right', 14)]:
            points[side].append(ret.axes() @ positions[index]/scale + origin)
    return points


def solve(rig, roles, side, target):
    """Use actual child joint heads; imported display tails are not leg lengths."""
    upper, lower, end = [rig.pose.bones[roles[side+'_'+part]] for part in ('thigh', 'shin', 'foot')]
    world = rig.matrix_world.copy(); inverse = world.inverted()
    a, b, c = [world @ bone.head for bone in (upper, lower, end)]
    lengths = [(b-a).length, (c-b).length]; axis = target-a; distance = axis.length
    require(abs(lengths[0]-lengths[1])+1e-5 < distance < sum(lengths)-1e-5,
            'MOTION_BRICKS_FOOT_REACH', 'Generated foot placement exceeds this rig\'s reach; choose a different interval or an intermediate step')
    axis.normalize(); pole = b-a-axis*(b-a).dot(axis)
    require(pole.length > 1e-6, 'MOTION_BRICKS_FOOT_POLE', 'Generated knee is singular; choose another interval')
    pole.normalize(); along = (lengths[0]**2-lengths[1]**2+distance**2)/(2*distance)
    knee = a+axis*along+pole*math.sqrt(max(0., lengths[0]**2-along**2))
    orientation = (world @ end.matrix).to_quaternion()
    for bone, child, point in [(upper, lower, knee), (lower, end, target)]:
        head = world @ bone.head; current = world @ child.head-head
        correction = current.rotation_difference(point-head)
        loc, q, scale = (world @ bone.matrix).decompose()
        saved_location = bone.location.copy(); saved_scale = bone.scale.copy()
        bone.matrix = inverse @ Matrix.LocRotScale(loc, correction @ q, scale)
        bone.location = saved_location; bone.scale = saved_scale; bpy.context.view_layer.update()
    loc, _, scale = (world @ end.matrix).decompose()
    saved_location = end.location.copy(); saved_scale = end.scale.copy()
    end.matrix = inverse @ Matrix.LocRotScale(loc, orientation, scale)
    end.location = saved_location; end.scale = saved_scale; bpy.context.view_layer.update()
    require((world @ end.head-target).length < 2e-5, 'MOTION_BRICKS_FOOT_SOLVE', 'Positional foot retarget did not converge')


def cleanup(reader, source, profile, request, result, samples, path, origin, geometry, natives, tangents, check, *, support=None):
    clone = reader.clone; roles = profile['roles']; ground = profile['ground_z']
    height = -min(p[1] for p in profile['skeleton']['neutral_joints'])/profile['world_to_model_scale']
    a, b, ap, app, bn, bnn, h = natives
    count = len(samples)-1; duration = geometry['duration_frames']; first = 3; last = len(result['roots'])-4
    window = min(12., .4*(last-first))*duration/(last-first)
    points = model_feet(request['skeleton'], result, first, last, profile['world_to_model_scale'], origin)
    parent = source.parent.matrix_world @ source.matrix_parent_inverse if source.parent else source.matrix_parent_inverse
    inverse = parent.to_3x3().inverted()
    def state(pose, delta): return set_pose(reader, pose, delta, 0.)
    def feet(): return {s: clone.matrix_world @ clone.pose.bones[roles[s+'_toe']].head for s in SIDES}
    def envelope(i):
        u = min(1., 4*i/count, 4*(count-i)/count)
        return u*u*u*(10+u*(-15+6*u))
    soles = Soles(source, clone, roles)
    try:
        # Extend only measured native support into a short bridge-only core.
        # The model receives no contact labels; this is disclosed positional IK.
        from .motion_bricks_contract import contact_plan
        plan=(support or {}).get('contact_plan') or contact_plan()
        locks=[]
        for edge,label in ((0,'source'),(-1,'target')):
            boundary=(support or {}).get('boundaries',{}).get(label,{})
            for side,contact in boundary.get('feet',{}).items():
                if not contact['planted']:continue
                selected=plan[label]['support']
                if selected=='none' or selected not in ('auto','both',side):continue
                state(samples[edge][1],path[edge][1]);anchor=soles.landmark(contact['mesh'],contact['vertex'])
                locks.append({'edge':edge,'side':side,'mesh':contact['mesh'],'vertex':contact['vertex'],'anchor':anchor.copy(),
                              'core_seconds':plan[label]['seconds'],'origin':plan['origin'],
                              'orientations':{roles[side+'_'+part]:(clone.matrix_world@clone.pose.bones[roles[side+'_'+part]].matrix).to_quaternion() for part in ('foot','toe')}})
        fps=bpy.context.scene.render.fps/bpy.context.scene.render.fps_base
        release=min(.30*fps,(duration-sum(plan[e]['seconds']*fps for e in ('source','target')))/2)
        def lock_weight(index,lock):
            elapsed=duration*(index/count if lock['edge']==0 else 1-index/count)
            core=lock['core_seconds']*fps
            if elapsed<=core:return 1.
            u=min(1.,(elapsed-core)/release)
            return 1-u*u*u*(10+u*(-15+6*u))
        def support_orientation(index):
            # Apply one immutable world-orientation trajectory. Repeatedly
            # blending the already projected pose would compound the release
            # weight, steepen it and make the correction depend on pass count.
            for name,orientation in orientation_targets[index].items():
                bone=clone.pose.bones[name];loc,q,scale=(clone.matrix_world@bone.matrix).decompose()
                saved_location=bone.location.copy();saved_scale=bone.scale.copy()
                bone.matrix=clone.matrix_world.inverted()@Matrix.LocRotScale(loc,orientation,scale)
                bone.location=saved_location;bone.scale=saved_scale;bpy.context.view_layer.update()
        def support_target(index,side,target):
            for lock in locks:
                if lock['side']!=side:continue
                weight=lock_weight(index,lock)
                if weight<=0:continue
                foot=clone.matrix_world@clone.pose.bones[roles[side+'_foot']].head
                point=soles.landmark(lock['mesh'],lock['vertex'])
                target=target.lerp(foot+lock['anchor']-point,weight)
            return target
        rows = [];world_orientations=[]
        names=[roles[side+'_'+part] for side in SIDES for part in ('foot','toe')]
        for (_, pose), (_, delta) in zip(samples, path):
            check(); state(pose, delta); rows.append({'feet': feet(), 'low': soles.heights()})
            world_orientations.append((len(world_orientations),{name:{'q':list((clone.matrix_world@clone.pose.bones[name].matrix).to_quaternion())} for name in names}))
        native = [];native_orientations=[]
        for pose, edge, multiplier, velocity in [(ap, 0, -1, 'velocity_in'), (app, 0, -2, 'velocity_in'),
                                                  (bn, -1, 1, 'velocity_out'), (bnn, -1, 2, 'velocity_out')]:
            delta = Vector(path[edge][1]) + inverse @ Vector((*geometry[velocity], 0))*h*multiplier
            state(pose, delta); native.append(feet())
            native_orientations.append({name:list((clone.matrix_world@clone.pose.bones[name].matrix).to_quaternion()) for name in names})
        world_endpoints=(world_orientations[0][1],world_orientations[-1][1]);world_tangents=[]
        for edge,sign in ((0,-1),(1,1)):
            values={}
            for name in names:
                inverse_q=qm.inverse(world_endpoints[edge][name]['q'])
                near=qm.qlog(qm.qmul(inverse_q,native_orientations[2*edge][name]))
                far=qm.qlog(qm.qmul(inverse_q,native_orientations[2*edge+1][name]))
                values[name]={'angular':qm.mul(qm.sub(qm.mul(near,4),far),sign/(2*h))}
            world_tangents.append(values)
        from .motion_bricks_refinement import smooth_rotations
        world_orientations,orientation_filter=smooth_rotations(world_orientations,duration/fps,world_endpoints,world_tangents,fps,check=check)
        orientation_targets=[]
        for index,(_,pose) in enumerate(world_orientations):
            goals={name:Quaternion(value['q']) for name,value in pose.items()}
            for lock in locks:
                for name,q in lock['orientations'].items():goals[name]=goals[name].slerp(q,lock_weight(index,lock))
            orientation_targets.append(goals)
        def raw(index, side):
            x = (last-first)*index/count; k = min(last-first-1, math.floor(x)); u = x-k
            value = points[side][k].lerp(points[side][k+1], u)
            value.z = ground+seam.ground_clearance(value.z-ground,height) + rows[index]['feet'][side].z-rows[index]['low'][side]
            return value
        errors = {}
        for side in SIDES:
            incoming = (3*rows[0]['feet'][side]-4*native[0][side]+native[1][side])/(2*h)
            outgoing = (-3*rows[-1]['feet'][side]+4*native[2][side]-native[3][side])/(2*h)
            step = duration/count
            errors[side] = [(rows[0]['feet'][side]-raw(0, side), incoming-(raw(1, side)-raw(0, side))/step),
                            (rows[-1]['feet'][side]-raw(count, side), outgoing-(raw(count, side)-raw(count-1, side))/step)]
        def targets(index):
            values = {}
            for side in SIDES:
                value = raw(index, side)
                for edge, (position, velocity) in enumerate(errors[side]):
                    value += Vector(seam.edge_residual(list(position), list(velocity), duration*index/count, duration, window, edge))
                values[side] = value
            return values
        required = []
        for index, ((_, pose), (_, delta)) in enumerate(zip(samples, path)):
            check(); state(pose, delta); support_orientation(index); world = clone.matrix_world; lower = 0.
            for side, desired in targets(index).items():
                upper, shin, foot = [clone.pose.bones[roles[side+'_'+p]] for p in ('thigh', 'shin', 'foot')]
                aa, bb, cc = [world @ bone.head for bone in (upper, shin, foot)]
                target = desired-(feet()[side]-cc)
                target = support_target(index,side,target)
                # A nearly straight analytic IK chain amplifies small foot
                # displacements into sharp knee rotations. Keep a measured,
                # bridge-only reach margin; the existing pelvis/correction
                # bounds still reject motion that needs excessive adjustment.
                length = (bb-aa).length+(cc-bb).length-.02*height*envelope(index)
                horizontal = Vector((aa.x-target.x, aa.y-target.y, 0)).length
                require(horizontal < length, 'MOTION_BRICKS_FOOT_REACH', 'Generated horizontal step exceeds this rig\'s reach')
                lower = max(lower, aa.z-target.z-math.sqrt(length*length-horizontal*horizontal))
            required.append(max(0., lower))
        amplitude = max([value/envelope(i) for i, value in enumerate(required) if envelope(i)>1e-10]+[0.])
        require(amplitude <= .12*height, 'MOTION_BRICKS_FOOT_REACH', 'This generated step needs excessive pelvis adjustment; choose another interval')
        corrected = []; maximum = 0.
        for index, ((frame, pose), (_, delta)) in enumerate(zip(samples, path)):
            check(); state(pose, delta);support_orientation(index)
            pelvis = clone.pose.bones[roles['pelvis']]; matrix = clone.matrix_world @ pelvis.matrix
            matrix.translation.z -= amplitude*envelope(index); pelvis.matrix = clone.matrix_world.inverted() @ matrix
            bpy.context.view_layer.update()
            for side, desired in targets(index).items():
                before = feet()[side]; maximum = max(maximum, (desired-before).length)
                target = desired-(before-clone.matrix_world @ clone.pose.bones[roles[side+'_foot']].head)
                target = support_target(index,side,target)
                solve(clone, roles, side, target)
            corrected.append((frame, {n: {'q': list(rotation(clone.pose.bones[n] if n else clone)),
                                           'location': list((clone.pose.bones[n] if n else clone).location),
                                           'scale': list((clone.pose.bones[n] if n else clone).scale)} for n in pose}))
        filter_reports=[]
        # Three fixed alternating smoothing/support projections. This bounded
        # deterministic refinement is measured against the raw prediction.
        for iteration in range(3):
            from .motion_bricks_refinement import smooth_rotations
            corrected,filter_report=smooth_rotations(corrected,duration/fps,(a,b),tangents,fps,
                                                     sigma_seconds=.04 if iteration==0 else .025,check=check)
            filter_reports.append(filter_report)
            residuals = {n: [seam.rotation_residual(corrected[k][1][n]['q'], endpoint[n]['q'],
                           qm.angular_velocity(corrected[j][1][n]['q'], corrected[l][1][n]['q'], duration/count), tangents[edge][n]['angular'])
                           for edge, (k,j,l,endpoint) in enumerate(((0,0,1,a),(-1,-2,-1,b)))] for n in a}
            for index, (_, pose) in enumerate(corrected):
                for n, values in pose.items():
                    values['q'] = seam.correct_rotation(values['q'], residuals[n], duration*index/count, duration, window)
                # Reconcile positional support after rotational seam processing.
                # Every anchor and measured correction is retained for review.
                state(pose,path[index][1]);support_orientation(index)
                for lock in locks:
                    weight=lock_weight(index,lock)
                    if weight<=0:continue
                    # A reviewed planted landmark is a three-dimensional support.
                    # Reconcile foot/toe orientation as well as the ankle position;
                    # moving only XY can silently let the claimed toe lift off.
                    point=soles.landmark(lock['mesh'],lock['vertex']);delta=lock['anchor']-point
                    foot=clone.matrix_world@clone.pose.bones[roles[lock['side']+'_foot']].head
                    maximum=max(maximum,(delta*weight).length)
                    if (delta*weight).length>1e-7:solve(clone,roles,lock['side'],foot+delta*weight)
                # Project only unintended penetration back onto the reviewed plane.
                # Positive neural lifts remain unchanged; this is not a terrain solver.
                low=soles.heights()
                for side in SIDES:
                    # Do not manufacture positive clearance at every sample:
                    # restoring the exact native endpoint would then introduce
                    # a step, amplified by near-straight knee IK. Small native
                    # floor tolerance remains below the hard penetration gate.
                    lift=max(0.,ground-.001*profile['reference_height_m']-low[side])
                    if lift>1e-7:
                        foot=clone.matrix_world@clone.pose.bones[roles[side+'_foot']].head
                        maximum=max(maximum,lift);solve(clone,roles,side,foot+Vector((0,0,lift)))
                for n in pose:
                    owner=clone.pose.bones[n] if n else clone
                    pose[n]={'q':list(rotation(owner)),'location':list(owner.location),'scale':list(owner.scale)}
        # The final projection can change the endpoint tangent. Reconcile it
        # over the generated trajectory, not in one quarter-frame bake segment.
        # Contact quality is measured again on the bake; no pass is inferred.
        from .motion_bricks_world_refinement import refine
        corrected,final_filter=refine(reader,profile,corrected,path,natives,duration/fps,fps,check)
        filter_reports.append(final_filter)
        # Exact source endpoints are authoritative. Tangents are retained by the baker.
        corrected[0] = (samples[0][0], a); corrected[-1] = (samples[-1][0], b)
        return corrected, {'method': 'g1-positional-feet-v1', 'ground_z_m': ground,
            'ground_clearance_heuristic': {'zero_below_m':.02*height,'full_lift_above_m':.05*height,'interpolation':'C2 quintic release; inferred geometry, not contact annotations'},
            'model_feet_sha256': digest({s: [list(p) for p in v] for s,v in points.items()}),
            'max_pelvis_lowering_m': amplitude, 'max_foot_position_correction_m': maximum,
            'rotation_filter':{'iterations':filter_reports,'count':len(filter_reports)},
            'foot_orientation_filter':orientation_filter,'foot_orientation_projection':'fixed world targets; no repeated weight compounding',
            'support_locks':[{'edge':'source' if lock['edge']==0 else 'target','side':lock['side'],'mesh':lock['mesh'],'vertex':lock['vertex'],'anchor_world_m':list(lock['anchor']),
                              'core_seconds':lock['core_seconds'],'origin':lock['origin']} for lock in locks],
            'contact_plan':plan,'support_lock_release_seconds':release/fps,
            'sole_geometry': 'evaluated skin vertices with >0.8 mapped foot/toe weight',
            'contact_annotations': 'Native evaluated support landmarks; deterministic bridge locking. No neural contact labels.',
            'acceptance': 'REQUIRES_EVALUATED_CONTACT_AND_VISUAL_REVIEW'}
    finally:
        soles.close()
