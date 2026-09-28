"""Blender-only compatibility inspection and separately saved placement candidate."""
import bpy
from mathutils import Matrix
from .core import digest, require
from . import action_layer, world_placement, world_transform
from . import world_prepare_contract as contract
from .blender_ops import flatten


def ownership():
    result = {}
    for obj in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        values = [obj.get(k) for k in ('bad_asset', 'bad_job', world_placement.INSTANCE, world_placement.CONTROL)]
        require(all(v is None or type(v) in (str, int, bool) for v in values),
                'WORLD_IDENTITY_CHANGED', 'Malformed placement ownership needs manual inspection')
        result[obj.name] = values
    return result


def settings():
    s = bpy.context.scene
    return {'frame': [s.frame_current, s.frame_subframe], 'range': [s.frame_start, s.frame_end],
            'camera': s.camera.name if s.camera else None, 'world': s.world.name if s.world else None,
            'render': [s.render.engine, s.render.resolution_x, s.render.resolution_y,
                       s.render.resolution_percentage, s.render.pixel_aspect_x, s.render.pixel_aspect_y]}


def audit():
    scene = bpy.context.scene
    require(len(scene.objects) <= 10000, 'RESOURCE_LIMIT', 'Too many objects for World preparation')
    bpy.context.view_layer.update()
    groups, helpers = world_placement.import_groups(scene)
    rows = []
    for (asset, job), members in sorted(groups.items()):
        row = {'asset_id': asset, 'import_job': job, 'members': sorted(o.name for o in members)}
        try:
            control, roots = world_placement.inspect_group(members, helpers)
            row.update(status='ALREADY_PREPARED' if control else 'PREPARABLE', roots=sorted(o.name for o in roots))
            if control:row['control'] = control.name
        except Exception as exc:
            if getattr(exc, 'code', None) != 'WORLD_PLACEMENT_UNSUPPORTED':raise
            row.update(status='UNSUPPORTED', reason=str(exc))
        rows.append(row)
    result = {'version': contract.VERSION, 'groups': rows,
              'preserved': action_layer.preserved(set()), 'ownership': ownership(), 'settings': settings()}
    result['sha256'] = digest(result)
    return result


def sample(names):
    """Bounded evaluated matrices; restoring frame/subframe is unconditional."""
    scene = bpy.context.scene
    original = (scene.frame_current, scene.frame_subframe)
    frames = sorted({original, (scene.frame_start, 0.0), (scene.frame_end, 0.0),
                     ((scene.frame_start + scene.frame_end) // 2, 0.0)})
    rows = []
    try:
        for frame, subframe in frames:
            scene.frame_set(frame, subframe=subframe)
            graph = bpy.context.evaluated_depsgraph_get()
            rows.append({'frame': frame, 'subframe': subframe,
                         'objects': {name: flatten(scene.objects[name].evaluated_get(graph).matrix_world) for name in names}})
    finally:
        scene.frame_set(original[0], subframe=original[1])
    return rows


def apply(options):
    contract.validate(options)
    require(bpy.app.background, 'BACKGROUND_REQUIRED', 'World preparation requires an isolated worker')
    before = audit()
    require(before['sha256'] == options['audit_sha256'], 'WORLD_BASE_CHANGED',
            'Compatibility inspection changed; inspect this exact saved scene again')
    lookup = {(g['asset_id'], g['import_job']): g for g in before['groups']}
    chosen = []
    for request in options['groups']:
        group = lookup.get((request['asset_id'], request['import_job']))
        require(group and group['status'] == 'PREPARABLE', 'WORLD_PLACEMENT_UNSUPPORTED',
                'Every chosen import group must be independently verified as preparable')
        chosen.append(group)
    # No mutation until the complete selection and compatibility identity pass.
    roots = [name for g in chosen for name in g['roots']]
    preserved = action_layer.preserved(set(), omit_parent=roots)
    matrices = sample(sorted(before['ownership']))
    report = {'version': contract.VERSION, 'request': options, 'groups': chosen,
              'preserved': preserved, 'ownership': before['ownership'], 'settings': before['settings'],
              'evaluated': matrices, 'created': [], 'reopened': False,
              'visual_acceptance': 'NOT_EVALUATED', 'publication': 'SEPARATE_CANDIDATE_ONLY'}
    for group in chosen:
        prepared = world_placement.prepare(bpy.context.scene, only_group=(group['asset_id'], group['import_job']))
        require(not prepared['unsupported'] and len(prepared['prepared']) == 1,
                'WORLD_PREPARATION_FAILED', 'Preparation failed after compatibility inspection')
        report['created'].extend(prepared['prepared'])
    verify(report)
    bpy.ops.file.make_paths_absolute()
    return report


def verify(report):
    scene = bpy.context.scene
    roots = [name for g in report['groups'] for name in g['roots']]
    controls = {g['control'] for g in report['created']}
    require(action_layer.preserved(set(), omit_objects=controls, omit_parent=roots) == report['preserved']
            and settings() == report['settings'],
            'WORLD_PRESERVATION_FAILED', 'Preparation changed native animation, skin, local channels or scene state')
    expected = {name: list(values) for name, values in report['ownership'].items()}
    identity = flatten(Matrix.Identity(4))
    for group, created in zip(report['groups'], report['created']):
        control, record = world_transform.observed(scene, created['instance'])
        require(record['members'] == group['members'] and control.name == created['control']
                and world_transform.close_matrix(record['matrix'], identity),
                'WORLD_IDENTITY_CHANGED', 'Prepared instance membership or identity container changed')
        for name in group['roots']:
            obj = scene.objects[name]
            require(obj.parent == control and world_transform.close_matrix(flatten(obj.matrix_parent_inverse), identity),
                    'WORLD_IDENTITY_CHANGED', 'Preparation changed an unexpected parent binding')
        for name in group['members']:expected[name][2] = created['instance']
    actual = ownership()
    require({k: v for k, v in actual.items() if k not in controls} == expected,
            'WORLD_IDENTITY_CHANGED', 'Preparation changed unrelated import ownership')
    sampled = sample(sorted(expected))
    require(len(sampled) == len(report['evaluated']) and all(
        new['frame'] == old['frame'] and new['subframe'] == old['subframe']
        and all(world_transform.close_matrix(new['objects'][name], matrix) for name, matrix in old['objects'].items())
        for old, new in zip(report['evaluated'], sampled)),
        'WORLD_PRESERVATION_FAILED', 'Evaluated placement changed during preparation')


def verify_saved(report, filename):
    bpy.ops.wm.open_mainfile(filepath=str(filename), load_ui=False, use_scripts=False)
    verify(report)
    from .scene_ops import scene_audit
    report['reopened'] = True
    report['scene_audit'] = scene_audit()
    report['world_placement'] = world_transform.audit()
