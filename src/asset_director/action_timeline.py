"""Blender-only timeline executor. Originals stay in muted tracks; travel owns
only delta_location, never World placement, bones, or an existing root channel.
"""
import json
import math
import bpy
from mathutils import Vector
from . import action_timeline_contract as contract, blender_ops as ops
from .core import digest, require, DirectorError

PROPERTY = 'bad_action_timeline_v1'
GENERATED = 'bad_action_travel_v1'


def is_generated(action):
    return action.get(GENERATED) == 1


def load(obj):
    from .action_layer import track_record, channels
    from .native_motion_basis import MAX_TIMELINE_JSON_BYTES
    raw = obj.get(PROPERTY)
    if raw is None:
        return None
    require(isinstance(raw, str) and len(raw.encode('utf-8')) <= MAX_TIMELINE_JSON_BYTES, 'TIMELINE_CHANGED', 'Invalid saved timeline metadata')
    try:
        value = json.loads(raw)
        contract.validate({'performer': obj.name, 'mode': 'timeline', 'clips': value['clips']})
        ad = obj.animation_data
        require(value['version'] == contract.VERSION and ad and not ad.action, 'TIMELINE_CHANGED', 'Timeline binding changed in Blender')
        parent = obj.parent.matrix_world @ obj.matrix_parent_inverse if obj.parent else obj.matrix_parent_inverse
        require(value['parent_matrix'] == ops.flatten(parent)
                and value['meters_per_unit'] == bpy.context.scene.unit_settings.scale_length,
                'TIMELINE_CHANGED', 'World placement or units changed; review this saved travel in Blender before editing its timeline')
        active = [track_record(t) for t in ad.nla_tracks if not t.mute]
        require(active == value['tracks'], 'TIMELINE_CHANGED', 'Timeline tracks changed in Blender; inspect before replacing them')
        for name, signature in value['generated'].items():
            require(name in bpy.data.actions and digest(channels(bpy.data.actions[name])) == signature,
                    'TIMELINE_CHANGED', 'Saved travel keys changed in Blender')
        return value
    except (KeyError, TypeError, ValueError) as exc:
        raise DirectorError('TIMELINE_CHANGED', 'Saved timeline needs Blender review') from exc


def travel_reason(obj, action, slot):
    """Conservative eligibility, not a gait/contact or semantic classifier."""
    from .action_layer import ancestors
    if obj.type != 'ARMATURE':
        return 'Travel currently supports native rigged characters only'
    members = {obj, *obj.children_recursive}
    if any(o not in members for o in bpy.context.scene.objects
           if any(m.type == 'ARMATURE' and m.object == obj for m in o.modifiers)):
        return 'Skin outside the performer hierarchy needs Blender preparation'
    if any(p.constraints or p.animation_data for p in ancestors(obj)):
        return 'Animated or constrained parents need reviewed travel in Blender'
    scale = bpy.context.scene.unit_settings.scale_length
    world = obj.matrix_world.to_3x3()
    for curve in ops.curves(action, slot):
        path = curve.data_path
        if curve.modifiers or curve.sampled_points:
            return 'Procedural or sampled motion needs travel review in Blender'
        if path.startswith('delta_'):
            return 'Native delta channels already own travel'
        if path.startswith('pose.bones[') and path.endswith('.location'):
            owner_path = path[:-len('.location')]
            try: bone = obj.path_resolve(owner_path)
            except (ValueError, AttributeError): return 'Unresolved bone channels need Blender review'
            basis = world @ bone.bone.matrix_local.to_3x3()
        elif path == 'location':
            basis = (obj.parent.matrix_world @ obj.matrix_parent_inverse).to_3x3() if obj.parent else obj.matrix_parent_inverse.to_3x3()
        elif path in {'rotation_euler', 'rotation_quaternion', 'rotation_axis_angle', 'scale'}:
            values = [float(k.co[1]) for k in curve.keyframe_points]
            if values and max(values) - min(values) > 1e-7:
                return 'Native object rotation/scale needs reviewed travel in Blender'
            continue
        else:
            continue
        if curve.array_index > 2:
            return 'Unsupported translation channel'
        values = [float(p[1]) for k in curve.keyframe_points for p in (k.co, k.handle_left, k.handle_right)]
        vector = basis.col[curve.array_index]
        if values and (max(values) - min(values)) * math.hypot(vector.x, vector.y) * scale > .02:
            return 'This take has native planar travel; a second path would double its movement'
    return None


def describe(obj, takes, gait_budget=None):
    from .action_layer import bindings
    from . import gait_sampling, gait_profile, motion_stitch, motion_heading
    if gait_budget is None: gait_budget = [3120]
    saved, error = None, None
    try: saved = load(obj)
    except DirectorError as exc: error = str(exc)
    pairs = {(a.name, getattr(slot, 'identifier', None)): (a, slot) for a, slot in bindings(obj)}
    for take in takes:
        a, slot = pairs[(take['action'], take['slot'])]
        take['travel_blocker'] = travel_reason(obj, a, slot)
        take['stitch_blocker'] = motion_stitch.reason(obj, a, slot)
        take['stitch_channels'] = (digest({n: sorted(v) for n, v in motion_stitch.channel_spec(obj, a, slot).items()})
                                   if take['stitch_blocker'] is None else None)
        try:
            take['heading_blocker'] = motion_heading.reason(obj, a, slot)
        except DirectorError as exc:
            take['heading_blocker'] = str(exc)
        take['gait'] = (gait_profile.unavailable(take['travel_blocker']) if take['travel_blocker']
                        else gait_sampling.inspect(obj, a, slot, take, gait_budget))
    scale = bpy.context.scene.unit_settings.scale_length
    origin = saved['origin_m'] if saved else [float(v) * scale for v in obj.matrix_world.translation]
    return {'version': contract.VERSION, 'managed': saved is not None, 'clips': saved['clips'] if saved else [],
            'stitch_version': contract.STITCH_VERSION, 'connections': saved.get('connections', []) if saved else [],
            'edit_version': contract.EDIT_VERSION,
            'origin_m': origin, 'meters_per_unit': scale, 'error': error,
            'notice': 'Automatic pace is a bounded support-motion estimate, not contact or performance approval.'}


def apply(options, job_id, before):
    from . import action_layer as layer, motion_stitch, motion_stitch_math, motion_heading, native_motion_basis
    scene = bpy.context.scene
    pending = []
    native_bases, heading_bases = {}, {}
    # Every clip, owner, travel and timing is validated before any mutation.
    for change in options['changes']:
        item = next((p for p in before['performers'] if p['name'] == change['performer']), None)
        require(item and not item['unsupported'] and not item['timeline']['error'],
                'ACTION_UNSUPPORTED', 'Performer or saved timeline needs Blender review')
        obj = scene.objects[item['name']]
        saved = load(obj)
        heading_active = any(c.get('heading_deg', 0.) != 0 for c in change['clips']) or bool(saved and 'base_delta_rotation' in saved)
        try:
            native_bases[obj.name] = native_motion_basis.capture(obj)
        except DirectorError:
            if heading_active or saved and saved.get('native_basis') is not None:
                raise
        if heading_active:
            heading_bases[obj.name] = motion_heading.state(obj, saved)
        motions = []
        has_travel = any(c['travel'] for c in change['clips'])
        for clip in change['clips']:
            take = next((t for t in item['takes'] if t['id'] == clip['take_id']), None)
            require(take is not None, 'ACTION_BINDING_CHANGED', 'Take is not owned by this performer')
            plan = contract.timing(clip, take)
            if has_travel or plan['cycles'] > 1 + 1e-9:
                require(not take['travel_blocker'], 'TRAVEL_UNSUPPORTED', take['travel_blocker'] or '')
            if clip['travel']:
                require(not take['travel_blocker'], 'TRAVEL_UNSUPPORTED', take['travel_blocker'] or '')
            action, slot = next((a, s) for a, s in layer.bindings(obj)
                                if a.name == take['action'] and layer.slot_id(s) == take['slot'])
            if heading_active:
                blocker = motion_heading.reason(obj, action, slot)
                require(not blocker, 'HEADING_UNSUPPORTED', blocker or '')
            motions.append((clip, dict(take, range=contract.source_range(clip, take)), action, slot, plan))
        if any(c['travel'] for c in change['clips']) or saved or heading_active:
            parent = obj.parent.matrix_world @ obj.matrix_parent_inverse if obj.parent else obj.matrix_parent_inverse
            require(abs(parent.to_3x3().determinant()) > 1e-10, 'TRAVEL_UNSUPPORTED', 'Singular parent transform')
            require(all(not c.data_path.startswith('delta_') for a, slot in layer.bindings(obj)
                        if not is_generated(a) for c in ops.curves(a, slot)),
                    'TRAVEL_UNSUPPORTED', 'Existing delta animation cannot be replaced by a path')
        stitches = motion_stitch.prepare(obj, motions)
        pending.append((change, item, obj, saved, motions, stitches))
    interval = options.get('frame_range', before['frame_range'])
    # Count the entire batch, including generated travel, before mutating any
    # performer. Separate per-performer budgets alone can overfill a saved scene.
    generated_keys = 0
    for change, _, _, _, motions, stitches in pending:
        for stitch in stitches:
            if stitch['join']:
                samples = stitch['join']['samples']
                generated_keys += sum(len(pose)*10 for _, pose in samples)
        if any(c['travel'] for c in change['clips']) or change['performer'] in heading_bases:
            generated_keys += 14*len(motions) + sum(len(s['join']['samples'])*7 for s in stitches if s['join'])
    existing_keys = sum(len(c.keyframe_points) for a in bpy.data.actions for c in ops.curves(a))
    require(existing_keys+generated_keys <= 500000, 'RESOURCE_LIMIT',
            'Saved motion and requested connections exceed the inspection key budget; split or simplify the edit')
    require(all(interval[0] <= c['start'] and c['start'] + c['frames'] - 1 <= interval[1]
                for change in options['changes'] for c in change['clips']),
            'INVALID_TIMING', 'Playback must contain every timeline clip')
    changed = {obj.name for _, _, obj, _, _, _ in pending}
    fingerprint = layer.preserved(changed)
    old_actions = {a.name for a in bpy.data.actions}
    frame, subframe = scene.frame_current, scene.frame_subframe
    records = []
    for change, item, obj, saved, motions, stitches in pending:
        # Clear means hold the first timeline pose, not restore a hidden old walk.
        scene.frame_set(saved['clips'][0]['start'] if saved and saved['clips'] else before['frame_range'][0])
        bpy.context.view_layer.update()
        def raw_pose(owner):
            prop = 'rotation_quaternion' if owner.rotation_mode == 'QUATERNION' else 'rotation_axis_angle' if owner.rotation_mode == 'AXIS_ANGLE' else 'rotation_euler'
            return {key: list(getattr(owner, key)) for key in ('location', prop, 'scale')}
        held = {'object': raw_pose(obj), 'bones': {p.name: raw_pose(p) for p in obj.pose.bones} if obj.type == 'ARMATURE' else {}}
        base_delta = saved['base_delta'] if saved else list(obj.delta_location)
        origin = saved['origin_m'] if saved else item['timeline']['origin_m']
        ad = obj.animation_data_create()
        if ad.action and not any(s.action == ad.action and layer.slot_id(getattr(s, 'action_slot', None)) == layer.slot_id(getattr(ad, 'action_slot', None)) for t in ad.nla_tracks for s in t.strips):
            old, slot = ad.action, getattr(ad, 'action_slot', None)
            source_range = ops.action_range(old, slot)
            if source_range[1] == source_range[0]:source_range = [source_range[0], source_range[0] + 1]
            layer.add_strip(obj, old, slot, 'Director retained ' + job_id, math.floor(source_range[0]), source_range, 1)
        ad.action = None
        for track in ad.nla_tracks:track.mute = True
        ad.use_nla = True
        obj.delta_location = base_delta
        heading_base = heading_bases.get(obj.name)
        if heading_base:
            motion_heading.set_heading(obj, heading_base, 0.)
        if not motions:
            if heading_base:
                motion_heading.set_heading(obj, heading_base, saved['clips'][0].get('heading_deg', 0.) if saved and saved['clips'] else 0.)
            for prop, values in held['object'].items():
                setattr(obj, prop, values)
            obj.delta_location = base_delta
            for name, pose in held['bones'].items():
                for prop, values in pose.items():
                    setattr(obj.pose.bones[name], prop, values)
        generated = {}
        connections, connection_checks = [], []
        for index, (clip, take, action, slot, plan) in enumerate(motions):
            stitch = stitches[index]
            if stitch['join']:
                join = stitch['join']
                name, signature = motion_stitch.bake(obj, join, job_id, clip['id'])
                generated[name] = signature
                connections.append({k: v for k, v in join.items() if k not in {'samples', 'channels'}} | {
                    'clip_id': clip['id'], 'phase': stitch['phase'], 'method': contract.STITCH_VERSION,
                    'contact_acceptance': 'NOT_EVALUATED', 'performance_acceptance': 'NOT_EVALUATED'})
                samples = join['samples']
                connection_checks.extend(samples[i] for i in (0, len(samples)//2, len(samples)-1))
            span = take['range'][1]-take['range'][0]
            cursor = float(clip['start'])
            for part, (a, b, repeat) in enumerate(motion_stitch_math.segments(*take['range'], plan['cycles']*span, stitch['phase'])):
                track = layer.add_strip(obj, action, slot, 'Director clip ' + clip['id'] + ' ' + job_id + ' ' + str(part),
                                        cursor, [a, b], clip['speed'])
                strip = track.strips[0]; strip.repeat = repeat
                strip.extrapolation = 'HOLD' if index == 0 and part == 0 else 'HOLD_FORWARD'
                cursor += (b-a)*repeat/clip['speed']
                require(abs(strip.frame_end-cursor) < .02,
                        'ACTION_RESULT_CHANGED', 'Native clip endpoint differs from planned timing')
            require(abs(cursor-plan['native_end']) < .02, 'ACTION_RESULT_CHANGED', 'Phase alignment changed clip duration')
        if any(c['travel'] for c in change['clips']) or heading_base and motions:
            # Parent inverse converts world metres to delta-location coordinates.
            parent = obj.parent.matrix_world @ obj.matrix_parent_inverse if obj.parent else obj.matrix_parent_inverse
            basis = parent.to_3x3()
            require(abs(basis.determinant()) > 1e-10, 'TRAVEL_UNSUPPORTED', 'Singular parent transform')
            inverse = basis.inverted()
            unit = scene.unit_settings.scale_length
            path = bpy.data.actions.new('Director travel ' + job_id + ' ' + obj.name)
            path[GENERATED] = 1
            ad.action = path
            displacement = Vector((0, 0, 0))
            previous_euler = None
            for index, (clip, take, action, slot, plan) in enumerate(motions):
                join = stitches[index]['join']
                if join:
                    begin = displacement.copy()
                    finish = displacement + Vector((*join['delta_m'], 0))/unit
                    for f, _ in join['samples']:
                        u = (f-join['start'])/join['duration_frames']
                        offset = motion_heading.path_at(join, max(0., min(1., u)))
                        obj.delta_location = Vector(base_delta) + inverse @ (begin+Vector((*offset, 0))/unit)
                        obj.keyframe_insert('delta_location', frame=f, group='Director travel')
                        if heading_base:
                            prop, previous_euler = motion_heading.set_heading(obj, heading_base, motion_heading.heading_at(join, u), previous_euler)
                            obj.keyframe_insert(prop, frame=f, group='Director heading')
                    displacement = Vector(finish)
                # Stop travel when native motion stops, including fractional
                # final frames; the rounded occupied tail is a hold, not slide.
                for f, step in [(clip['start'], False), (plan['native_end'], True)]:
                    if step and clip['travel']:
                        displacement += Vector((*clip['travel']['delta_m'], 0)) / unit
                    obj.delta_location = Vector(base_delta) + inverse @ displacement
                    obj.keyframe_insert('delta_location', frame=f, group='Director travel')
                    if heading_base:
                        prop, previous_euler = motion_heading.set_heading(obj, heading_base, clip.get('heading_deg', 0.), previous_euler)
                        obj.keyframe_insert(prop, frame=f, group='Director heading')
            for curve in ops.curves(path):
                for key in curve.keyframe_points:key.interpolation = 'LINEAR'
                curve.extrapolation = 'CONSTANT'
            slot = getattr(ad, 'action_slot', None)
            ad.action = None
            source_range = [change['clips'][0]['start'], change['clips'][-1]['start'] + change['clips'][-1]['frames'] - 1]
            layer.add_strip(obj, path, slot, 'Director path ' + job_id, source_range[0], source_range, 1)
            generated[path.name] = digest(layer.channels(path))
        timeline = {'version': contract.VERSION, 'clips': change['clips'], 'base_delta': base_delta,
                    'connections': connections,
                    'origin_m': origin, 'tracks': [layer.track_record(t) for t in ad.nla_tracks if not t.mute],
                    'generated': generated,
                    'parent_matrix': ops.flatten(obj.parent.matrix_world @ obj.matrix_parent_inverse if obj.parent else obj.matrix_parent_inverse),
                    'meters_per_unit': scene.unit_settings.scale_length}
        if obj.name in native_bases:
            timeline['native_basis'] = native_bases[obj.name]
        if heading_base:
            timeline.update(heading_base)
        serialized = json.dumps(timeline, sort_keys=True, allow_nan=False)
        require(len(serialized.encode('utf-8')) <= native_motion_basis.MAX_TIMELINE_JSON_BYTES,
                'RESOURCE_LIMIT', 'Saved native motion metadata exceeds its bounded size; split the edit')
        obj[PROPERTY] = serialized
        records.append({'performer': obj.name, 'mode': 'timeline', 'timeline': timeline,
                        'connection_checks': connection_checks, 'previous_tracks': item['tracks']})
    scene.frame_start, scene.frame_end = interval
    scene.frame_set(frame, subframe=subframe);bpy.context.view_layer.update()
    report = {'version': layer.contract.VERSION, 'request': options, 'changes': records,
              'preserved': fingerprint, 'new_actions': sorted({a.name for a in bpy.data.actions} - old_actions),
              'frame_range': list(interval), 'reopened': False, 'performance_acceptance': 'NOT_EVALUATED',
              'contact_acceptance': 'NOT_EVALUATED', 'timeline_version': contract.VERSION}
    verify(report)
    bpy.ops.file.make_paths_absolute()
    return report


def verify(report):
    from . import action_layer as layer
    for change in report['changes']:
        obj = bpy.context.scene.objects.get(change['performer'])
        require(obj is not None and load(obj) == change['timeline'], 'TIMELINE_CHANGED', 'Saved timeline changed')
        layer.verify_previous_tracks(obj, change['previous_tracks'])
        scene = bpy.context.scene
        frame, subframe = scene.frame_current, scene.frame_subframe
        try:
            for f, pose in change.get('connection_checks', []):
                scene.frame_set(math.floor(f), subframe=f-math.floor(f)); bpy.context.view_layer.update()
                for name, expected in pose.items():
                    owner = obj.pose.bones[name] if name else obj
                    from .motion_heading import rotation
                    q = rotation(owner)
                    from . import sequence_math as sm
                    require(math.dist(owner.location, expected['location']) < 2e-4
                            and math.dist(owner.scale, expected['scale']) < 2e-4
                            and sm.norm(sm.qlog(sm.qmul(sm.inverse(sm.unit(list(q))), sm.unit(expected['q'])))) < 2e-3,
                            'STITCH_RESULT_CHANGED', 'Saved connection pose differs from its measured plan')
        finally:
            scene.frame_set(frame, subframe=subframe); bpy.context.view_layer.update()
    require(layer.preserved({c['performer'] for c in report['changes']}, omit_actions=report['new_actions']) == report['preserved'],
            'ACTION_PRESERVATION_FAILED', 'Timeline changed native sources, rest/skin, placement or another performer')
    require([bpy.context.scene.frame_start, bpy.context.scene.frame_end] == report['frame_range'],
            'TIMELINE_CHANGED', 'Timeline playback range changed')
