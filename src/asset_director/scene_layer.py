"""Blender-only Shots/Light transactions. No new arbitrary-code executor."""
import bpy
from .core import digest, require
from . import scene_layer_contract as contract, scene_ops, action_layer


def editable(obj, *, camera=False):
    if obj.library or obj.override_library or obj.data.library or obj.data.users != 1 or obj.parent or obj.children or obj.constraints:
        return 'Linked, shared, parented or constrained objects need detailed Blender editing'
    for owner in (obj, obj.data):
        ad = owner.animation_data
        if ad and (ad.drivers or ad.use_tweak_mode or any(not t.mute or t.is_solo for t in ad.nla_tracks)):
            return 'Driven or active NLA state needs detailed Blender editing'
        if ad and ad.action and not camera:
            return 'Animated lights need detailed Blender editing'
        if camera and owner == obj.data and ad and ad.action and any(c.data_path not in {'lens', 'dof.use_dof', 'dof.focus_distance'} for c in action_layer.ops.curves(ad.action, getattr(ad, 'action_slot', None))):
            return 'Camera sensor/other data animation needs detailed Blender editing'
    return None


def audit(layer):
    contract.validate({'layer': layer}, inspect=True)
    scene = bpy.context.scene;bpy.context.view_layer.update()
    require(len(scene.objects) <= 10000, 'RESOURCE_LIMIT', 'Scene exceeds bounded layer inspection')
    cameras = []
    for obj in sorted(scene.objects, key=lambda o: o.name):
        if obj.type != 'CAMERA':continue
        data = obj.data
        cameras.append({'name': obj.name, 'matrix_world': scene_ops.flatten(obj.matrix_world),
            'projection': data.type, 'lens_mm': data.lens, 'sensor_width_mm': data.sensor_width,
            'sensor_height_mm': data.sensor_height, 'sensor_fit': data.sensor_fit,
            'shift': [data.shift_x, data.shift_y], 'clip': [data.clip_start, data.clip_end],
            'ortho_scale': data.ortho_scale, 'unsupported': editable(obj, camera=True),
            'active_motion': {'object': obj.animation_data.action.name if obj.animation_data and obj.animation_data.action else None,
                              'data': data.animation_data.action.name if data.animation_data and data.animation_data.action else None}})
    look = scene_ops.look_audit()
    # The old helper inventories all datablocks; expose only this scene's lights.
    look['state']['lights'] = [x for x in look['state']['lights'] if x['name'] in scene.objects]
    look['editable']['lights'] = [x for x in look['editable']['lights'] if x in scene.objects]
    for light in look['state']['lights']:light['unsupported'] = editable(scene.objects[light['name']])
    state = {'version': contract.VERSION, 'layer': layer, 'scene': scene_ops.scene_audit(),
             'cameras': cameras, 'look': look, 'preserved': action_layer.preserved(set()),
             'visual_acceptance': 'NOT_EVALUATED'}
    state['sha256'] = digest(state)
    return state


def preflight(options, before):
    scene = bpy.context.scene;changed = set()
    for item in options['operations']:
        op, args = item['operation'], item['options']
        if 'subjects' in args:scene_ops.subjects(args['subjects'])
        if op in {'camera-fit', 'camera-plan'}:
            frames = args['frames'] if op == 'camera-fit' else [k['frame'] for k in args['keyframes']]
            require(all(scene.frame_start <= f <= scene.frame_end for f in frames), 'INVALID_TIMEBASE', 'Camera frames must stay in the saved Action range')
            if op == 'camera-fit' or args.get('mode', 'create') == 'create':
                name = item['name'] if op == 'camera-fit' else args['name']
                require(name not in bpy.data.objects, 'NAME_TAKEN', 'Choose a new camera name; no silent rename')
            else:
                obj = scene.objects.get(args['camera'])
                require(obj is not None and obj.type == 'CAMERA' and not editable(obj, camera=True),
                        'LAYER_UNSUPPORTED', 'This camera needs detailed Blender editing')
                changed.add(obj.name)
            if op == 'camera-plan':
                for entry in args['keyframes']:
                    require('subject' not in entry['aim'] or entry['aim']['subject'] in args['subjects'],
                            'SUBJECTS_REQUIRED', 'Camera aim must reference an observed selected subject')
        elif op == 'light-adjust':
            for entry in args['lights']:
                obj = scene.objects.get(entry['name'])
                require(obj is not None and obj.type == 'LIGHT' and not editable(obj),
                        'LAYER_UNSUPPORTED', 'This light needs detailed Blender editing')
                require(not scene_ops.look_contract.unsupported_properties(obj.data.type, set(entry)-{'name'}),
                        'LIGHT_PROPERTY_UNSUPPORTED', 'Property is not supported by this observed light type')
                changed.add(obj.name)
        elif op == 'world-adjust':
            world = scene.world
            require(world is not None and not world.library and not world.override_library and world.users == 1,
                    'LAYER_UNSUPPORTED', 'Shared or linked world needs detailed Blender editing')
            for owner in (world, world.node_tree):
                require(not getattr(owner, 'animation_data', None), 'LAYER_UNSUPPORTED', 'Animated world needs detailed Blender editing')
            require(set(args) <= set(before['look']['editable']['world']), 'WORLD_GRAPH_UNSUPPORTED', 'World graph does not support the requested edit')
        elif op == 'look-adjust':
            require(not scene.animation_data, 'LAYER_UNSUPPORTED', 'Animated scene settings need detailed Blender editing')
    return changed


def apply(options, owner):
    contract.validate(options)
    require(bpy.app.background, 'BACKGROUND_REQUIRED', 'Layer changes require a separate worker')
    before = audit(options['layer'])
    require(before['sha256'] == options['audit_sha256'], 'LAYER_CHANGED', 'Saved layer context changed; inspect again')
    changed = preflight(options, before)
    original_objects = set(bpy.context.scene.objects.keys());original_actions = set(bpy.data.actions.keys())
    preserved = action_layer.preserved(set(), omit_objects=changed)
    results = [];created = set()
    functions = {'camera-fit': scene_ops.camera_fit, 'camera-plan': scene_ops.camera_plan,
                 'light-adjust': scene_ops.light_adjust, 'world-adjust': scene_ops.world_adjust,
                 'look-adjust': scene_ops.look_adjust, 'light-rig': scene_ops.light_rig}
    for index, item in enumerate(options['operations']):
        op, args = item['operation'], item['options']
        retained_data = None
        if op == 'camera-plan' and args.get('mode') == 'adapt':
            data = bpy.context.scene.objects[args['camera']].data;ad = data.animation_data
            if ad and ad.action:
                old, slot = ad.action, getattr(ad, 'action_slot', None)
                interval = action_layer.ops.action_range(old, slot)
                if interval[0] == interval[1]:interval = [interval[0], interval[0] + 1]
                track = action_layer.add_strip(data, old, slot, 'Director retained lens '+owner, int(interval[0]), interval, 1)
                track.mute = True;ad.action = None
                retained_data = {'action': old.name, 'track': track.name, 'muted': True}
        result = functions[op](args, owner + '_' + str(index))
        if retained_data:result['preserved_data_animation'] = retained_data
        if op == 'camera-fit':
            camera = bpy.context.scene.objects[result['camera']];camera.name = item['name']
            require(camera.name == item['name'], 'NAME_TAKEN', 'Camera name did not survive creation')
            result['camera'] = camera.name;created.add(camera.name)
        if op == 'camera-plan' and args.get('mode', 'create') == 'create':created.add(result['camera'])
        if op == 'light-rig':created.update(result['created_lights'])
        results.append({'operation': op, 'data': result})
    new_actions = set(bpy.data.actions.keys()) - original_actions
    permitted_actions = set()
    if options['layer'] == 'shots':
        for name in changed | created:
            obj = bpy.context.scene.objects[name]
            for data in (obj, obj.data):
                if data.animation_data and data.animation_data.action:permitted_actions.add(data.animation_data.action.name)
    require(new_actions <= permitted_actions, 'LAYER_PRESERVATION_FAILED', 'An unrelated new action appeared')
    require(set(bpy.context.scene.objects.keys()) == original_objects | created,
            'LAYER_PRESERVATION_FAILED', 'Unrequested objects changed')
    require(action_layer.preserved(set(), omit_objects=changed | created, omit_actions=new_actions) == preserved,
            'LAYER_PRESERVATION_FAILED', 'World placement, original animation or unrelated geometry changed')
    after = audit(options['layer'])
    for key in ('fps', 'frame_range', 'resolution', 'pixel_aspect', 'units', 'materials'):
        require(after['scene'][key] == before['scene'][key], 'LAYER_PRESERVATION_FAILED', 'Unrequested scene setting changed: '+key)
    if options['layer'] == 'shots':
        comparable = lambda look: look | {'state': {k:v for k,v in look['state'].items() if k != 'objects'}}
        require(comparable(after['look']) == comparable(before['look']), 'LAYER_PRESERVATION_FAILED', 'Camera edit changed lighting')
    else:
        require(after['cameras'] == before['cameras'] and after['scene']['camera'] == before['scene']['camera'],
                'LAYER_PRESERVATION_FAILED', 'Lighting edit changed cameras')
    return {'version': contract.VERSION, 'layer': options['layer'], 'request': options,
            'operations': results, 'after_audit': after, 'reopened': False,
            'preserved': preserved, 'omitted_objects': sorted(changed | created), 'new_actions': sorted(new_actions),
            'visual_acceptance': 'NOT_EVALUATED'}


def verify_saved(report, filename):
    bpy.ops.wm.open_mainfile(filepath=str(filename), load_ui=False, use_scripts=False)
    after = audit(report['layer'])
    require(after['sha256'] == report['after_audit']['sha256'], 'LAYER_RESULT_CHANGED', 'Reopened camera/light scene differs from the verified result')
    require(action_layer.preserved(set(), omit_objects=report['omitted_objects'], omit_actions=report['new_actions']) == report['preserved'],
            'LAYER_PRESERVATION_FAILED', 'Saved layer result changed original geometry or native animation')
    report.update(reopened=True, scene_audit=after['scene'], after_audit=after)
