"""Blender-only performer-native motion/timing. No mappings or invented motion.

Only actual object/action/slot bindings are selectable. All changes happen in a
separate worker file and reopen verification is required before publication.
"""
import math
import bpy
from . import action_layer_contract as contract
from . import blender_ops as ops
from .core import digest, require
from .motion_timing import strip_scale
from .world_placement import ancestor_control, widgets


def slot_id(slot):
    return getattr(slot, 'identifier', None)


def channels(action, slot=None):
    return [[c.data_path, c.array_index, c.extrapolation,
             [[list(k.co), list(k.handle_left), list(k.handle_right), k.interpolation] for k in c.keyframe_points]]
            for c in ops.curves(action, slot)]


def bindings(obj):
    """Unlike catalog scouting, no inferred bone-path ownership here."""
    ad = obj.animation_data
    if not ad:
        return []
    pairs = []
    if ad.action:
        pairs.append((ad.action, getattr(ad, 'action_slot', None)))
    for track in ad.nla_tracks:
        for strip in track.strips:
            if strip.action:
                pairs.append((strip.action, getattr(strip, 'action_slot', None)))
    return list(dict.fromkeys(pairs))


def track_record(track):
    return {'name': track.name, 'mute': track.mute, 'solo': track.is_solo,
            'strips': [{'name': s.name, 'action': s.action.name if s.action else None,
                        'slot': slot_id(getattr(s, 'action_slot', None)),
                        'start': s.frame_start, 'end': s.frame_end,
                        'action_start': s.action_frame_start, 'action_end': s.action_frame_end,
                        'scale': s.scale, 'repeat': s.repeat, 'mute': s.mute,
                        'blend': s.blend_type, 'extrapolation': s.extrapolation,
                        'influence': s.influence, 'blend_in': s.blend_in, 'blend_out': s.blend_out}
                       for s in track.strips]}


def reason(obj):
    ad = obj.animation_data
    members = [obj, *obj.children_recursive]
    if any(o.library or o.override_library or len(o.users_scene) != 1 for o in members):
        return 'Linked or shared scene ownership needs Blender review'
    if any(o.constraints or (o.animation_data and o.animation_data.drivers) for o in members):
        return 'Constraints or drivers need detailed Blender editing'
    if obj.type == 'ARMATURE' and any(p.constraints for p in obj.pose.bones):
        return 'Constrained performance needs the reviewed/manual workflow'
    if any(o != obj and o.animation_data for o in members):
        return 'Animated attachments need coordinated Blender editing'
    if any(getattr(o.data, 'shape_keys', None) and o.data.shape_keys.animation_data for o in members if o.data):
        return 'Shape-key motion needs coordinated Blender editing'
    if ad and (ad.use_tweak_mode or any(t.is_solo for t in ad.nla_tracks)):
        return 'Exit NLA tweak/solo mode in Blender before simple timing edits'
    return None


def audit():
    scene = bpy.context.scene
    require(len(scene.objects) <= 10000 and len(bpy.data.actions) <= 2048, 'RESOURCE_LIMIT', 'Action inspection exceeds its scene bound')
    require(sum(len(c.keyframe_points) for a in bpy.data.actions for c in ops.curves(a)) <= 500000,
            'RESOURCE_LIMIT', 'Action inspection exceeds its keyframe budget; inspect this scene in Blender')
    helpers = widgets(scene)
    performers, bound, cached, binding_count = [], set(), {}, 0
    gait_budget = [3120]  # At most 48 x 65 evaluated poses for this inspection.
    for obj in sorted(scene.objects, key=lambda o: o.name):
        if obj in helpers or obj.get('bad_placement_control') == 1 or obj.type not in {'ARMATURE', 'MESH', 'EMPTY', 'CURVE'}:
            continue
        if obj.type != 'ARMATURE' and not obj.animation_data and any(p.type == 'ARMATURE' for p in ancestors(obj)):
            continue
        ad, takes = obj.animation_data, []
        for action, slot in bindings(obj):
            from .action_timeline import is_generated
            if is_generated(action):
                continue
            if not ops.curves(action, slot):
                continue
            # A layered action needs its actual binding, not whichever slot is first.
            if getattr(action, 'slots', None) and slot not in list(action.slots):
                continue
            binding_count += 1
            require(binding_count <= 4096, 'RESOURCE_LIMIT', 'Too many native performer bindings; inspect in Blender')
            key = (action.name, slot_id(slot))
            if key not in cached:
                cached[key] = (ops.action_range(action, slot), digest(channels(action, slot)))
            interval, channel_hash = cached[key]
            record = {'performer': obj.name, 'action': action.name, 'slot': slot_id(slot),
                      'range': list(interval), 'channels_sha256': channel_hash,
                      'ownership': 'observed active/NLA binding'}
            record['id'] = 'take_' + digest(record)
            takes.append(record); bound.add((action.name, slot_id(slot)))
        require(len(takes) <= 256, 'RESOURCE_LIMIT', 'Performer has too many native takes')
        control = ancestor_control(obj)
        from .action_timeline import describe
        performers.append({'name': obj.name, 'type': obj.type, 'asset_id': obj.get('bad_asset'),
                           'instance': control.get('bad_placement_instance') if control else None,
                           'placement_control': control.name if control else None,
                           'active': {'action': ad.action.name, 'slot': slot_id(getattr(ad, 'action_slot', None))} if ad and ad.action else None,
                           'tracks': [track_record(t) for t in ad.nla_tracks] if ad else [],
                           'takes': takes, 'unsupported': reason(obj), 'timeline': describe(obj, takes, gait_budget)})
    unassigned = [{'action': a.name, 'slot': slot_id(slot)} for a in bpy.data.actions
                  for slot in list(getattr(a, 'slots', [])) or [None]
                  if not a.get('bad_action_travel_v1') and ops.curves(a, slot) and (a.name, slot_id(slot)) not in bound]
    result = {'version': contract.VERSION, 'fps': scene.render.fps / scene.render.fps_base,
              'frame_range': [scene.frame_start, scene.frame_end], 'reference_frame': scene.frame_current,
              'performers': performers, 'unassigned': unassigned,
              'notice': 'Saved native bindings only. Retargeting requires source/target review; motion quality is not approved.'}
    result['sha256'] = digest(result)
    return result


def ancestors(obj):
    while obj.parent:
        obj = obj.parent
        yield obj


def preserved(excluded, *, omit_objects=(), omit_actions=(), omit_parent=()):
    """Keys, rest/skin identity, placement and every unselected performer remain."""
    # Preparation alone uses omit_parent for inspected independent roots; its
    # verifier separately requires their exact new identity-container binding.
    require(sum(len(o.data.vertices) for o in bpy.context.scene.objects if o.type == 'MESH') <= 2000000,
            'RESOURCE_LIMIT', 'Simple Action editing supports at most two million scene mesh vertices; use Blender for this scene')
    require(sum(len(c.keyframe_points) for a in bpy.data.actions for c in ops.curves(a)) <= 500000,
            'RESOURCE_LIMIT', 'Simple Action editing exceeds the bounded keyframe inspection budget')
    rows = []
    for obj in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        if obj.name in omit_objects:continue
        ad = obj.animation_data
        row = {'name': obj.name, 'type': obj.type, 'parent': None if obj.name in omit_parent else obj.parent.name if obj.parent else None,
               'parent_inverse': None if obj.name in omit_parent else ops.flatten(obj.matrix_parent_inverse), 'data': obj.data.name if obj.data else None,
               'local': None if obj.name in excluded else ops.flatten(obj.matrix_basis),
               'materials': [s.material.name if s.material else None for s in obj.material_slots],
               'visibility': [obj.hide_render, obj.hide_viewport],
               'modifiers': [(m.name, m.type, getattr(getattr(m, 'object', None), 'name', None)) for m in obj.modifiers]}
        if obj.name not in excluded:
            row['active'] = (ad.action.name, slot_id(getattr(ad, 'action_slot', None))) if ad and ad.action else None
            row['tracks'] = [track_record(t) for t in ad.nla_tracks] if ad else []
        if obj.type == 'ARMATURE':
            row['rest'] = [(b.name, ops.flatten(b.matrix_local), b.parent.name if b.parent else None) for b in obj.data.bones]
            row['widgets'] = [(p.name, p.custom_shape.name if p.custom_shape else None) for p in obj.pose.bones]
        if obj.type == 'MESH':
            row['geometry'] = digest({'vertices': [list(v.co) for v in obj.data.vertices],
                                      'groups': [g.name for g in obj.vertex_groups],
                                      'weights': [[(g.group, g.weight) for g in v.groups] for v in obj.data.vertices]})
        rows.append(row)
    return digest({'objects': rows, 'actions': {a.name: channels(a) for a in bpy.data.actions if a.name not in omit_actions},
                   'fps': [bpy.context.scene.render.fps, bpy.context.scene.render.fps_base]})


def add_strip(obj, action, slot, name, start, source_range, speed):
    ad = obj.animation_data_create()
    # Blender silently truncates NLA labels to 63 UTF-8 bytes and permits
    # duplicates. Keep the distinguishing job/clip identity in a digest suffix.
    prefix = name.encode('utf-8')[:40].decode('utf-8', errors='ignore')
    label = name if len(name.encode('utf-8')) <= 63 else prefix+' '+digest(name)[:16]
    if ad.nla_tracks.get(label) is not None:
        ordinal = len(ad.nla_tracks)
        while ad.nla_tracks.get(label) is not None:
            label = prefix+' '+digest([name, ordinal])[:16]
            ordinal += 1
    track = ad.nla_tracks.new(prev=ad.nla_tracks[-1]) if ad.nla_tracks else ad.nla_tracks.new()
    track.name = label
    strip = track.strips.new(action.name, int(start), action)
    if hasattr(strip, 'action_slot') and slot:
        strip.action_slot = slot
    strip.action_frame_start, strip.action_frame_end = source_range
    fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
    strip.scale = strip_scale(fps, fps, speed); strip.repeat = 1
    strip.frame_start = start
    # NlaStrip.frame_start moves only the left edge for fractional starts.
    # strips.new accepts an integer, so explicitly restore the intended right
    # edge instead of leaving a gap/rest pose before the next native clip.
    strip.frame_end = start + (source_range[1]-source_range[0])*strip_scale(fps, fps, speed)
    strip.blend_type = 'REPLACE'; strip.extrapolation = 'HOLD'; strip.use_auto_blend = False
    strip.blend_in = strip.blend_out = 0
    return track


def verify_previous_tracks(obj, previous):
    """Verify the exact retained ordered prefix, not ambiguous display labels.

    Edits append after muting the existing tracks. Duplicate old labels are
    legitimate Blender state; every old strip, property and ordering must stay
    identical apart from the explicitly requested track mute.
    """
    tracks = list(obj.animation_data.nla_tracks)
    require(len(tracks) >= len(previous)
            and [track_record(t) for t in tracks[:len(previous)]] == [dict(old, mute=True) for old in previous],
            'ACTION_PRESERVATION_FAILED', 'Previous native track changed')


def apply(options, job_id):
    contract.validate(options)
    require(bpy.app.background, 'BACKGROUND_REQUIRED', 'Action edits require a separate worker')
    scene = bpy.context.scene; before = audit()
    require(before['sha256'] == options['audit_sha256'], 'ACTION_CHANGED', 'Saved Action context changed; inspect again')
    if all(c['mode'] == 'timeline' for c in options['changes']):
        from .action_timeline import apply as apply_timeline
        return apply_timeline(options, job_id, before)
    require(all(not scene.objects[c['performer']].get('bad_action_timeline_v1') for c in options['changes'] if c['performer'] in scene.objects),
            'TIMELINE_REVIEW_REQUIRED', 'Edit the saved clips in the timeline or in Blender')
    pending = []
    for change in options['changes']:
        item = next((p for p in before['performers'] if p['name'] == change['performer']), None)
        require(item is not None and item['unsupported'] is None, 'ACTION_UNSUPPORTED', item['unsupported'] if item else 'Performer is no longer observed')
        obj = scene.objects[item['name']]
        if change['mode'] == 'clip':
            take = next((t for t in item['takes'] if t['id'] == change['take_id']), None)
            require(take is not None, 'ACTION_BINDING_CHANGED', 'Take is not owned by this performer')
            duration = (take['range'][1] - take['range'][0]) / change['speed']
            require(0 < duration <= 3600 and change['start'] + duration <= 100000,
                    'RESOURCE_LIMIT', 'Keep the full take within the bounded playback span; no silent trimming')
            action, slot = next((a, slot) for a, slot in bindings(obj) if a.name == take['action'] and slot_id(slot) == take['slot'])
            pending.append((change, obj, item, (action, slot, take['range'])))
        else:
            require(scene.frame_start <= change['frame'] <= scene.frame_end, 'INVALID_TIMING', 'Hold a frame inside the observed scene range')
            pending.append((change, obj, item, None))
    changed = {obj.name for _, obj, _, _ in pending}
    fingerprint = preserved(changed); frame, subframe = scene.frame_current, scene.frame_subframe
    records = []
    for change, obj, item, motion in pending:
        held = None
        if change['mode'] == 'hold':
            scene.frame_set(change['frame']);bpy.context.view_layer.update()
            held = {'object': obj.matrix_basis.copy(), 'bones': {p.name: p.matrix_basis.copy() for p in obj.pose.bones} if obj.type == 'ARMATURE' else {}}
        ad = obj.animation_data_create()
        # Retain the old active action as a muted native binding before detaching.
        if ad.action and not any(s.action == ad.action and slot_id(getattr(s, 'action_slot', None)) == slot_id(getattr(ad, 'action_slot', None)) for t in ad.nla_tracks for s in t.strips):
            old, slot = ad.action, getattr(ad, 'action_slot', None)
            interval = ops.action_range(old, slot)
            if interval[1] == interval[0]:interval = [interval[0], interval[0] + 1]
            add_strip(obj, old, slot, 'Director retained ' + job_id, math.floor(interval[0]), interval, 1)
        ad.action = None
        for track in ad.nla_tracks:track.mute = True
        if motion:
            action, slot, interval = motion
            ad.use_nla = True
            track = add_strip(obj, action, slot, 'Director action ' + job_id, change['start'], interval, change['speed'])
            record = {'performer': obj.name, 'mode': 'clip', 'track': track_record(track), 'previous_tracks': item['tracks']}
        else:
            obj.matrix_basis = held['object']
            for name, matrix in held['bones'].items():obj.pose.bones[name].matrix_basis = matrix
            record = {'performer': obj.name, 'mode': 'hold', 'frame': change['frame'],
                      'object': ops.flatten(held['object']), 'bones': {name: ops.flatten(m) for name, m in held['bones'].items()}, 'previous_tracks': item['tracks']}
        records.append(record)
    if 'frame_range' in options:scene.frame_start, scene.frame_end = options['frame_range']
    scene.frame_set(frame, subframe=subframe);bpy.context.view_layer.update()
    report = {'version': contract.VERSION, 'request': options, 'changes': records, 'preserved': fingerprint, 'reopened': False,
              'frame_range': [scene.frame_start, scene.frame_end], 'performance_acceptance': 'NOT_EVALUATED'}
    verify(report);bpy.ops.file.make_paths_absolute()
    return report


def verify(report):
    if report.get('timeline_version'):
        from .action_timeline import verify as verify_timeline
        return verify_timeline(report)
    scene = bpy.context.scene
    for change in report['changes']:
        obj = scene.objects.get(change['performer']);require(obj is not None, 'ACTION_RESULT_CHANGED', 'Performer missing')
        ad = obj.animation_data
        require(ad and ad.action is None, 'ACTION_RESULT_CHANGED', 'Unexpected active action after NLA/hold edit')
        verify_previous_tracks(obj, change['previous_tracks'])
        if change['mode'] == 'clip':
            track = ad.nla_tracks.get(change['track']['name'])
            require(track is not None and track_record(track) == change['track'], 'ACTION_RESULT_CHANGED', 'Native clip timing differs')
        else:
            from .world_transform import close_matrix
            require(all(t.mute for t in ad.nla_tracks) and close_matrix(ops.flatten(obj.matrix_basis), change['object'])
                    and all(close_matrix(ops.flatten(obj.pose.bones[name].matrix_basis), m) for name, m in change['bones'].items()),
                    'ACTION_RESULT_CHANGED', 'Held pose differs')
    require(preserved({c['performer'] for c in report['changes']}) == report['preserved'],
            'ACTION_PRESERVATION_FAILED', 'Placement, native keys, rest/skin or unselected performance changed')
    require([scene.frame_start, scene.frame_end] == report['frame_range'], 'ACTION_RESULT_CHANGED', 'Playback range differs')


def verify_saved(report, filename):
    bpy.ops.wm.open_mainfile(filepath=str(filename), load_ui=False, use_scripts=False)
    verify(report)
    from .scene_ops import scene_audit
    report.update(reopened=True, scene_audit=scene_audit(), action_audit=audit())
