"""Blender-only native clip bridges; disposable sampling, retained source Actions.

This is bounded interpolation, with optional explicitly authored contact IK.
It is not generated choreography or retargeting. Native root motion is retained;
the separate delta Action owns added placement alignment or reviewed travel.
"""
import json
import math
import re
import bpy
from mathutils import Quaternion, Vector
from . import blender_ops as ops, motion_stitch_math as sm
from .action_timeline_contract import connection
from .core import DirectorError, require

PATH = re.compile(r'^(?:(pose\.bones\[("(?:[^"\\]|\\.)*")\])\.)?(location|rotation_euler|rotation_quaternion|rotation_axis_angle|scale)$')


def channel_spec(obj, action, slot):
    spec = {}
    for curve in ops.curves(action, slot):
        match = PATH.fullmatch(curve.data_path)
        require(match and not curve.modifiers and not curve.sampled_points,
                'STITCH_CHANNEL_REVIEW', 'Connections require native transform keys without procedural channels')
        name = json.loads(match[2]) if match[2] else ''
        owner = obj.pose.bones.get(name) if name and obj.type == 'ARMATURE' else obj if not name else None
        require(owner is not None, 'STITCH_CHANNEL_REVIEW', 'Unresolved animation owner needs Blender review')
        prop = match[3]
        expected = 'rotation_quaternion' if owner.rotation_mode == 'QUATERNION' else 'rotation_axis_angle' if owner.rotation_mode == 'AXIS_ANGLE' else 'rotation_euler'
        require(not prop.startswith('rotation_') or prop == expected,
                'STITCH_CHANNEL_REVIEW', 'Rotation channels do not match the observed owner mode')
        require(0 <= curve.array_index < (4 if prop in {'rotation_quaternion', 'rotation_axis_angle'} else 3),
                'STITCH_CHANNEL_REVIEW', 'Unsupported transform channel')
        spec.setdefault(name, set()).add((prop, curve.array_index))
    require(spec, 'STITCH_CHANNEL_REVIEW', 'No native transform keys')
    return spec


def reason(obj, action, slot):
    from .action_layer import reason as performer_reason, ancestors
    from .action_timeline import travel_reason
    if performer_reason(obj):
        return performer_reason(obj)
    if any(p.constraints or p.animation_data for p in ancestors(obj)):
        return 'Animated or constrained parents need reviewed connections in Blender'
    if obj.type == 'ARMATURE':
        if len(obj.data.bones) > 256:
            return 'This rig exceeds the bounded connection sampler'
        blocker = travel_reason(obj, action, slot, allow_native_root=True)
        if blocker:
            return blocker
    else:
        # An object-motion adapter can be added without assuming human anatomy.
        # For now only stationary object rotations/scales can use pose bridges.
        for curve in ops.curves(action, slot):
            if curve.data_path == 'location':
                values = [float(p[1]) for k in curve.keyframe_points for p in (k.co, k.handle_left, k.handle_right)]
                if values and max(values)-min(values) > 1e-7:
                    return 'Native object travel needs reviewed alignment in Blender'
    try:
        channel_spec(obj, action, slot)
    except DirectorError as error:
        return str(error)
    return None


class Sampler:
    def __init__(self, obj):
        self.scene = bpy.context.scene
        self.frame = self.scene.frame_current, self.scene.frame_subframe
        self.clone = obj.copy()
        self.data = obj.data.copy() if obj.type == 'ARMATURE' else None
        if self.data:
            self.clone.data = self.data
        from .native_motion_basis import seed
        try:
            self.native_basis = seed(self.clone, obj)
        except Exception:
            bpy.data.objects.remove(self.clone, do_unlink=True)
            if self.data:
                bpy.data.armatures.remove(self.data)
            raise
        self.clone.delta_location = (0, 0, 0)
        self.clone.hide_viewport = False
        self.scene.collection.objects.link(self.clone)
        self.count = 0

    def read(self, motion, elapsed, phase=0., endpoint=False):
        self.count += 1
        require(self.count <= 4096, 'RESOURCE_LIMIT', 'Connection inspection exceeded 4096 pose samples')
        clip, take, action, slot, _ = motion
        clone = self.clone
        from .native_motion_basis import restore
        restore(clone, self.native_basis)
        clone.delta_location = (0, 0, 0)
        ad = clone.animation_data_create(); ad.action = action; ad.use_nla = False
        if slot is not None:
            ad.action_slot = slot
        f = sm.source_frame(*take['range'], elapsed, phase, endpoint)
        self.scene.frame_set(math.floor(f), subframe=f-math.floor(f))
        bpy.context.view_layer.update()
        evaluated = clone.evaluated_get(bpy.context.evaluated_depsgraph_get())
        result = {}
        for name in channel_spec(clone, action, slot):
            owner = evaluated.pose.bones[name] if name else evaluated
            from .motion_heading import rotation
            q = rotation(owner)
            require(all(v > 0 and math.isfinite(v) for v in owner.scale),
                    'STITCH_SCALE_REVIEW', 'Reflected or singular scales need Blender review')
            result[name] = {'location': list(owner.location), 'q': list(q.normalized()), 'scale': list(owner.scale)}
        return result

    def close(self):
        bpy.data.objects.remove(self.clone, do_unlink=True)
        if self.data:
            bpy.data.armatures.remove(self.data)
        self.scene.frame_set(self.frame[0], subframe=self.frame[1])
        bpy.context.view_layer.update()


def prepare(obj, motions, *, execution=None):
    plans = [{'phase': 0., 'join': None, 'root_offset': [0., 0., 0.], 'travel_before': [0., 0.]} for _ in motions]
    if not any(m[0].get('transition') for m in motions):
        return plans
    reader = Sampler(obj)
    keys = 0
    try:
        for index, motion in enumerate(motions):
            clip, take, action, slot, timing = motion
            if index:
                plans[index]['root_offset'] = list(plans[index-1]['root_offset'])
                before = plans[index-1]['travel_before']
                displacement = motions[index-1][0]['travel']['delta_m'] if motions[index-1][0]['travel'] else [0., 0.]
                plans[index]['travel_before'] = [x+y for x,y in zip(before, displacement)]
            if not clip.get('transition'):
                continue
            previous = motions[index-1]
            for m in (previous, motion):
                blocker = reason(obj, m[2], m[3])
                require(not blocker, 'STITCH_UNSUPPORTED', blocker or '')
            require(channel_spec(obj, action, slot) == channel_spec(obj, previous[2], previous[3]),
                    'STITCH_CHANNEL_REVIEW', 'These clips animate different channels; use an intermediate clip or Blender')
            geometry = connection(previous[0], clip, previous[1], take)
            if clip['transition'].get('mode') == 'generated':
                from .motion_bricks_timeline import prepare as generate
                from .motion_bricks_retarget import load_profile
                from .core import digest
                require(digest(load_profile(obj)) == clip['transition']['profile_sha256'],
                        'MOTION_BRICKS_RETARGET_PROFILE', 'Selected rig mapping changed; inspect again')
                require(plans[index-1]['phase'] == 0, 'MOTION_BRICKS_PHASE', 'Generated repositioning requires intact outgoing clip phase')
                join = generate(reader, obj, previous, motion, geometry, execution)
                keys += len(join['samples']) * len(join['samples'][0][1]) * 10
                require(keys <= 200000, 'RESOURCE_LIMIT', 'Generated connections exceed the key budget')
                plans[index]['join'] = join
                plans[index]['travel_before'] = [x+y for x,y in zip(plans[index]['travel_before'], join['delta_m'])]
                continue
            dt = min(1/64, (previous[4]['native_end']-previous[0]['start'])/4,
                     (timing['native_end']-clip['start'])/4)
            previous_elapsed = previous[4]['cycles'] * (previous[1]['range'][1]-previous[1]['range'][0])
            phase = plans[index-1]['phase']
            a = reader.read(previous, previous_elapsed, phase, True)
            ap = reader.read(previous, previous_elapsed-dt*previous[0]['speed'], phase)
            b = reader.read(motion, 0)
            bn = reader.read(motion, dt*clip['speed'])
            phase_note = 'Original opening retained; no reviewed phase shift requested'
            cost_before = sm.pose_cost(a, b)
            match_before = sm.match_cost(ap, a, b, bn, dt, geometry['duration_frames'])
            matched_phase = None
            pose_after, match_after = cost_before, match_before
            if clip['transition']['match_phase'] and clip['repeat_reviewed']:
                finish = reader.read(motion, take['range'][1]-take['range'][0], endpoint=True)
                if sm.closed(b, finish):
                    candidates = [(match_before, 0., b)]
                    for i in range(1, 32):
                        pose = reader.read(motion, 0, i/32)
                        following = reader.read(motion, dt*clip['speed'], i/32)
                        candidates.append((sm.match_cost(ap, a, pose, following, dt, geometry['duration_frames']), i/32, pose))
                    match_after, matched_phase, matched = min(candidates, key=lambda row: (row[0], row[1]))
                    pose_after = sm.pose_cost(a, matched)
                    # The match is at the BEGINNING of the extra interval.
                    # Advance the incoming cycle through that time; matching its
                    # end to the same phase would introduce a stop/reversal wiggle.
                    plans[index]['phase'] = (matched_phase + geometry['duration_frames']*clip['speed']/(take['range'][1]-take['range'][0])) % 1
                    b = reader.read(motion, 0, plans[index]['phase'])
                    phase_note = 'Pose/velocity matched at connection start, then advanced through its duration; contact quality still requires review'
                else:
                    phase_note = 'Loop endpoint poses do not close; original opening retained'
            bn = reader.read(motion, dt*clip['speed'], plans[index]['phase'])
            duration = geometry['duration_frames']
            subdivisions = math.ceil(duration*4)
            keys += (subdivisions+1)*len(a)*10
            require(keys <= 200000, 'RESOURCE_LIMIT', 'Connections exceed 200000 generated scalar keys; split the edit')
            samples = [(geometry['start']+duration*i/subdivisions,
                        sm.bridge(a, b, ap, bn, dt, duration, i/subdivisions)) for i in range(subdivisions+1)]
            # Object location is a verified native root owner. Keep both source
            # Actions unchanged and align incoming placement with a separate
            # delta channel, whose endpoint velocity is zero. The sum of the
            # pose bridge and alignment is the same Hermite bridge between the
            # aligned endpoints, preserving native root velocities exactly.
            alignment = [0., 0., 0.]
            if '' in a:
                require(obj.type == 'ARMATURE' or math.dist(a['']['location'], b['']['location']) < 1e-5,
                        'STITCH_ROOT_REVIEW', 'Object placements differ; align this motion explicitly in Blender')
                if obj.type == 'ARMATURE':
                    require(not previous[0]['travel'] and not clip['travel']
                            or math.dist(a['']['location'], b['']['location']) < 1e-5,
                            'STITCH_ROOT_REVIEW', 'Native root alignment cannot also own an added travel path')
                    derivatives = sm.tangents(a, b, ap, bn, dt)
                    alignment = [x-y+(v+w)*duration*.5 for x,y,v,w in zip(
                        a['']['location'], b['']['location'], derivatives[0]['']['location'], derivatives[1]['']['location'])]
                    plans[index]['root_offset'] = [x+y for x,y in zip(plans[index-1]['root_offset'], alignment)]
            from .motion_contacts import cleanup
            samples, contact = cleanup(reader, obj, previous, motion, geometry, samples,
                                       plans[index-1]['root_offset'], alignment, plans[index]['travel_before'],
                                       ap, bn, dt, (plans[index-1]['phase'], plans[index]['phase']))
            plans[index]['travel_before'] = [x+y for x,y in zip(plans[index]['travel_before'], geometry['delta_m'])]
            plans[index]['join'] = {**geometry, 'contact_cleanup': contact, 'samples': samples, 'pose_cost_before': cost_before,
                                    'provider': 'native', 'implementation': 'native-stitch-c1-v2',
                                    'generation_mode': 'deterministic', 'root_owner': 'native-object-location-plus-alignment' if any(alignment) else 'native-pose-plus-optional-path',
                                    'root_alignment_local': alignment,
                                    'boundary_tangents': sm.tangents(a, b, ap, bn, dt),
                                    'channels': {n: [list(pair) for pair in sorted(v)] for n, v in channel_spec(obj, action, slot).items()},
                                    'pose_cost_after': pose_after, 'phase_note': phase_note,
                                    'matched_phase': matched_phase,
                                    'match_cost_before': match_before,
                                    'match_cost_after': match_after}
        existing = sum(len(c.keyframe_points) for a in bpy.data.actions for c in ops.curves(a))
        require(existing+keys <= 500000, 'RESOURCE_LIMIT', 'Saved motion plus connections exceeds the inspection key budget')
        return plans
    finally:
        reader.close()


def bake(obj, plan, job_id, clip_id):
    """Bake a short separate Action in the owners' existing rotation modes."""
    from .action_layer import channels, add_strip
    from .action_timeline import GENERATED
    from .core import digest
    action = bpy.data.actions.new('Director connection '+clip_id+' '+job_id)
    action[GENERATED] = 1
    if plan.get('provider') == 'motion-bricks.cpp':
        action['asset_director_provider'] = plan['provider']
        action['asset_director_generation_mode'] = plan['generation_mode']
        action['asset_director_provenance'] = json.dumps(plan['provenance'], sort_keys=True)
    ad = obj.animation_data_create(); ad.action = action
    eulers, quaternions, axis_angles = {}, {}, {}
    for frame, pose in plan['samples']:
        for name, state in pose.items():
            owner = obj.pose.bones[name] if name else obj
            q = Quaternion(state['q'])
            if name in quaternions and q.dot(quaternions[name]) < 0:
                q.negate()
            quaternions[name] = q.copy()
            if owner.rotation_mode == 'QUATERNION':
                prop = 'rotation_quaternion'; values = list(q)
            elif owner.rotation_mode == 'AXIS_ANGLE':
                axis, angle = q.to_axis_angle(); prop = 'rotation_axis_angle'
                if abs(math.sin(angle/2)) < 1e-5:
                    endpoint = 0 if frame == plan['start'] else 1 if frame == plan['end'] else None
                    angular = Vector(plan['boundary_tangents'][endpoint][name]['angular']) if endpoint is not None else None
                    if angular is not None and angular.length > 1e-8:
                        axis = angular.normalized()
                    elif name in axis_angles:
                        axis = Vector(axis_angles[name][1:])
                if name in axis_angles and axis.dot(Vector(axis_angles[name][1:])) < 0:
                    axis.negate(); angle = -angle
                if name in axis_angles:
                    angle += round((axis_angles[name][0]-angle)/(2*math.pi))*2*math.pi
                values = [angle, *axis]; axis_angles[name] = values
            else:
                converted = q.to_euler(owner.rotation_mode, eulers.get(name, owner.rotation_euler.copy()))
                eulers[name] = converted.copy(); prop = 'rotation_euler'; values = list(converted)
            expected = {'location': state['location'], 'scale': state['scale'], prop: values}
            # A bridge must not acquire previously unkeyed default channels.
            # Retain exact original ownership and let verification refuse a
            # bridge that cannot be represented by those native components.
            for channel, index in plan['channels'][name]:
                target = getattr(owner, channel)
                target[index] = expected[channel][index]
                owner.keyframe_insert(channel, index=index, frame=frame)
    from . import sequence_math as qm
    for curve in ops.curves(action):
        match = PATH.fullmatch(curve.data_path)
        name = json.loads(match[2]) if match[2] else ''
        prop, component = match[3], curve.array_index
        slopes = []
        for index in (0, 1):
            tangent = plan['boundary_tangents'][index][name]
            if prop in {'location', 'scale'}:
                slope = tangent[prop][component]
            else:
                # Convert the exact body angular tangent into the retained native
                # rotation coordinates. Anchor Euler conversion to this key's
                # representation so a 2*pi-equivalent orientation cannot spin.
                state = plan['samples'][0 if index == 0 else -1][1][name]
                q = state['q']; h = 1/128
                forward = Quaternion(qm.qmul(q, qm.qexp(qm.mul(tangent['angular'], h))))
                backward = Quaternion(qm.qmul(q, qm.qexp(qm.mul(tangent['angular'], -h))))
                owner = obj.pose.bones[name] if name else obj
                if prop == 'rotation_quaternion':
                    if forward.dot(Quaternion(q)) < 0: forward.negate()
                    if backward.dot(Quaternion(q)) < 0: backward.negate()
                    # The key may use the opposite quaternion sign for continuity.
                    keyed = {c.array_index: c.keyframe_points[0 if index == 0 else -1].co[1]
                             for c in ops.curves(action) if c.data_path == curve.data_path}
                    sign = -1 if sum(q[j]*value for j,value in keyed.items()) < 0 else 1
                    slope = sign*(forward[component]-backward[component])/(2*h)
                elif prop == 'rotation_euler':
                    reference = Quaternion(q).to_euler(owner.rotation_mode)
                    a = backward.to_euler(owner.rotation_mode, reference)
                    b = forward.to_euler(owner.rotation_mode, reference)
                    slope = (b[component]-a[component])/(2*h)
                else:
                    keyed = {c.array_index: c.keyframe_points[0 if index == 0 else -1].co[1]
                             for c in ops.curves(action) if c.data_path == curve.data_path}
                    reference = [keyed.get(j, owner.rotation_axis_angle[j]) for j in range(4)]
                    axis = Vector(reference[1:]).normalized()
                    def coordinates(value):
                        candidate, angle = value.to_axis_angle()
                        if candidate.dot(axis) < 0: candidate.negate(); angle = -angle
                        angle += round((reference[0]-angle)/(2*math.pi))*2*math.pi
                        return [angle, *candidate]
                    if abs(math.sin(reference[0]/2)) < 1e-5:
                        slope = 0. if component else Vector(tangent['angular']).dot(axis)
                    else:
                        av, bv = coordinates(backward), coordinates(forward)
                        slope = (bv[component]-av[component])/(2*h)
            slopes.append(slope)
        sm.smooth_keys(curve, slopes, continuous=plan.get('provider')=='motion-bricks.cpp')
    slot = getattr(ad, 'action_slot', None); ad.action = None
    track = add_strip(obj, action, slot, action.name, plan['start'], [plan['start'], plan['end']], 1)
    track.strips[0].extrapolation = 'NOTHING'
    require(abs(track.strips[0].frame_start-plan['start']) < 1e-4
            and abs(track.strips[0].frame_end-plan['end']) < 1e-4,
            'STITCH_RESULT_CHANGED', 'Connection strip does not cover its complete planned interval')
    return action.name, digest(channels(action))
