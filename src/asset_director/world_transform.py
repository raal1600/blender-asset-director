"""Blender-only bounded placement. Validate the complete batch before mutation."""
import bpy
from mathutils import Matrix
from .core import digest, require
from .blender_ops import curves, flatten
from .world_placement import INSTANCE, CONTROL, ancestor_control, widgets
from . import world_transform_contract as contract


def close_matrix(actual, expected):
    return all(abs(a - b) <= max(1e-5, abs(b) * 1e-6) for a, b in zip(actual, expected))


def observed(scene, identity):
    """Resolve an identity only in this scene, including ownership postconditions."""
    members = [o for o in scene.objects if o.get(INSTANCE) == identity]
    controls = [o for o in members if o.get(CONTROL) == 1]
    require(len(controls) == 1, 'WORLD_IDENTITY_CHANGED', 'Placement identity is missing or ambiguous')
    control = controls[0]
    require(control.type == 'EMPTY' and control.parent is None and not control.animation_data,
            'WORLD_IDENTITY_CHANGED', 'Placement control is no longer an independent unanimated root')
    asset, job = control.get('bad_asset'), control.get('bad_job')
    require(isinstance(asset, str) and isinstance(job, str)
            and all(o.get('bad_asset') == asset and o.get('bad_job') == job for o in members),
            'WORLD_IDENTITY_CHANGED', 'Placement ownership changed')
    helpers = widgets(scene)
    owned = set(members)
    require(owned == {o for o in scene.objects if o.get('bad_asset') == asset and o.get('bad_job') == job
                      and o not in helpers}, 'WORLD_IDENTITY_CHANGED', 'Asset membership changed')
    require(all(not o.library and not o.override_library and len(o.users_scene) == 1
                and not o.constraints and not (o.animation_data and o.animation_data.drivers)
                and not (o.type == 'ARMATURE' and any(p.constraints for p in o.pose.bones))
                for o in members), 'WORLD_PLACEMENT_UNSUPPORTED', 'Linked, shared, constrained or driven instances need Blender review')
    require(all(ancestor_control(o) == control and all(c in owned or c in helpers for c in o.children)
                for o in members), 'WORLD_IDENTITY_CHANGED', 'Asset hierarchy changed')
    matrix = flatten(control.matrix_world)
    contract.matrix(matrix)
    return control, {'instance': identity, 'control': control.name, 'asset_id': asset, 'import_job': job,
                     'matrix': matrix, 'members': sorted(o.name for o in members if o != control),
                     'rigged': any(o.type == 'ARMATURE' for o in members)}


def audit():
    scene = bpy.context.scene
    require(len(scene.objects) <= 10000, 'RESOURCE_LIMIT', 'Too many objects to inspect placement')
    identities = sorted({o.get(INSTANCE) for o in scene.objects if isinstance(o.get(INSTANCE), str)})
    result = {'version': contract.VERSION, 'instances': [], 'unsupported': []}
    for identity in identities:
        try:
            _, record = observed(scene, identity)
            result['instances'].append(record)
        except Exception as exc:
            result['unsupported'].append({'instance': identity, 'reason': str(exc)})
    result['unprepared'] = sorted({o.get('bad_job') for o in scene.objects
                                   if isinstance(o.get('bad_job'), str) and not o.get(INSTANCE) and o not in widgets(scene)})
    return result


def preserved_state(changed_controls):
    """Bind native animation/local hierarchy and unrelated objects across Save/reopen."""
    scene = bpy.context.scene
    objects = []
    for obj in sorted(scene.objects, key=lambda o: o.name):
        ad = obj.animation_data
        objects.append({'name': obj.name, 'type': obj.type, 'parent': obj.parent.name if obj.parent else None,
                        'parent_inverse': flatten(obj.matrix_parent_inverse),
                        'local': None if obj.name in changed_controls else flatten(obj.matrix_basis),
                        'data': obj.data.name if obj.data else None,
                        'materials': [s.material.name if s.material else None for s in obj.material_slots],
                        'modifiers': [(m.name, m.type) for m in obj.modifiers],
                        'hide_render': obj.hide_render, 'hide_viewport': obj.hide_viewport,
                        'action': ad.action.name if ad and ad.action else None,
                        'slot': getattr(getattr(ad, 'action_slot', None), 'identifier', None),
                        'nla': [(t.name, t.mute, [(s.name, s.action.name if s.action else None, s.frame_start,
                                                 s.frame_end, s.scale, s.repeat, s.mute) for s in t.strips])
                                for t in ad.nla_tracks] if ad else [],
                        'widgets': [(p.name, p.custom_shape.name if p.custom_shape else None) for p in obj.pose.bones]
                                   if obj.type == 'ARMATURE' else []})
    actions = {a.name: [[c.data_path, c.array_index, c.extrapolation,
                        [[list(k.co), list(k.handle_left), list(k.handle_right), k.interpolation] for k in c.keyframe_points]]
                       for c in curves(a)] for a in bpy.data.actions}
    return digest({'objects': objects, 'actions': actions, 'frame': scene.frame_current,
                   'range': [scene.frame_start, scene.frame_end], 'fps': [scene.render.fps, scene.render.fps_base],
                   'camera': scene.camera.name if scene.camera else None,
                   'world': scene.world.name if scene.world else None})


def apply(options):
    contract.validate(options)
    scene = bpy.context.scene
    require(bpy.app.background, 'BACKGROUND_REQUIRED', 'World saves run in an isolated worker')
    require(len(scene.objects) <= 10000, 'RESOURCE_LIMIT', 'Too many scene objects')
    pending = []
    # Do not prepare, move, or repair anything until EVERY requested target passed.
    for change in options['transforms']:
        control, record = observed(scene, change['instance'])
        require(close_matrix(record['matrix'], change['expected_matrix']),
                'WORLD_BASE_CHANGED', 'Placement changed since this draft; refresh before saving')
        pending.append((control, record, change['matrix']))
    controls = {control.name for control, _, _ in pending}
    preserved = preserved_state(controls)
    for control, _, values in pending:
        control.matrix_world = Matrix([values[i:i + 4] for i in range(0, 16, 4)])
    bpy.context.view_layer.update()
    report = {'version': contract.VERSION, 'transforms': [
        {'instance': record['instance'], 'control': control.name, 'before': record['matrix'], 'after': values}
        for control, record, values in pending], 'preserved': preserved, 'reopened': False}
    verify(report)
    # The launcher copies the result to its immutable Scenes directory.
    bpy.ops.file.make_paths_absolute()
    return report


def verify(report):
    for change in report['transforms']:
        control, record = observed(bpy.context.scene, change['instance'])
        require(control.name == change['control'] and close_matrix(record['matrix'], change['after']),
                'WORLD_RESULT_CHANGED', 'Saved placement did not match the requested transform')
    require(preserved_state({x['control'] for x in report['transforms']}) == report['preserved'],
            'WORLD_PRESERVATION_FAILED', 'Native animation, local hierarchy or unrelated state changed')


def verify_saved(report, filename):
    bpy.ops.wm.open_mainfile(filepath=str(filename), load_ui=False, use_scripts=False)
    verify(report)
    from .scene_ops import scene_audit
    report['reopened'] = True
    report['scene_audit'] = scene_audit()
    report['world_placement'] = audit()
