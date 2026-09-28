"""Task-local whole-asset placement, independent of native animation channels.

Only explicit import-job groups are prepared. Unknown/shared hierarchies remain
untouched and are reported, not guessed from names. Never edits source assets.
"""
import json
from uuid import uuid4
import bpy
from mathutils import Matrix
from .core import require

INSTANCE = 'bad_placement_instance'
CONTROL = 'bad_placement_control'
VISIBILITY = 'bad_world_widget_visibility_v1'


def widgets(scene):
    return {p.custom_shape for rig in scene.objects if rig.type == 'ARMATURE'
            for p in rig.pose.bones if p.custom_shape and p.custom_shape.name in scene.objects}


def import_groups(scene, only_job=None, only_group=None):
    """Read explicit ownership only; helper geometry is never a guessed member."""
    helpers, groups = widgets(scene), {}
    for obj in scene.objects:
        asset, job = obj.get('bad_asset'), obj.get('bad_job')
        if (isinstance(asset, str) and isinstance(job, str) and obj not in helpers
                and (only_job is None or job == only_job)
                and (only_group is None or (asset, job) == only_group)):
            groups.setdefault((asset, job), []).append(obj)
    return groups, helpers


def inspect_group(members, helpers):
    """Shared read-only eligibility check for task copies and reviewed candidates."""
    require(all(not o.library and not o.override_library and len(o.users_scene) == 1 for o in members),
            'WORLD_PLACEMENT_UNSUPPORTED', 'Linked, shared-scene or overridden asset needs manual preparation')
    require(all(not o.constraints and not (o.animation_data and o.animation_data.drivers)
                and not (o.type == 'ARMATURE' and any(p.constraints for p in o.pose.bones)) for o in members),
            'WORLD_PLACEMENT_UNSUPPORTED', 'Constrained or driven hierarchy needs reviewed preparation')
    owned = set(members)
    require(all(o.parent is None or o.parent in owned for o in members)
            and all(c in owned or c in helpers for o in members for c in o.children),
            'WORLD_PLACEMENT_UNSUPPORTED', 'Asset shares a hierarchy with unowned objects')
    existing = [o for o in members if o.get(CONTROL) == 1]
    if existing:
        require(len(existing) == 1, 'WORLD_PLACEMENT_UNSUPPORTED', 'Duplicated placement identity needs review')
        control = existing[0]
        instance = control.get(INSTANCE)
        require(control.type == 'EMPTY' and control.parent is None and not control.animation_data
                and isinstance(instance, str) and all(o.get(INSTANCE) == instance for o in members)
                and all(o == control or ancestor_control(o) == control for o in members),
                'WORLD_PLACEMENT_UNSUPPORTED', 'Placement hierarchy changed; inspect before arranging')
        return control, []
    require(not any(o.get(INSTANCE) for o in members), 'WORLD_PLACEMENT_UNSUPPORTED',
            'Placement control is missing; do not infer a replacement')
    roots = [o for o in members if o.parent is None]
    require(roots and any(o.type == 'MESH' for o in members),
            'WORLD_PLACEMENT_UNSUPPORTED', 'No independent mesh asset roots')
    return None, roots


def prepare(scene, only_job=None, only_group=None):
    """Prepare supported groups in this working copy; preserve animated bases."""
    # Collection append/link does not eagerly evaluate matrix_world. Establish
    # the actual scene-frame baseline before comparing identity-parent results;
    # otherwise the first update looks like an illegal placement mutation.
    bpy.context.view_layer.update()
    groups, helpers = import_groups(scene, only_job, only_group)
    result = {'prepared': [], 'unsupported': []}
    for (asset, job), members in sorted(groups.items()):
        try:
            control, roots = inspect_group(members, helpers)
            if control:
                instance = control[INSTANCE]
            else:
                before = {o: o.matrix_world.copy() for o in members}
                control = bpy.data.objects.new('World placement - ' + roots[0].name, None)
                scene.collection.objects.link(control)
                control.empty_display_type = 'PLAIN_AXES'
                control.empty_display_size = .4
                control['bad_asset'], control['bad_job'] = asset, job
                control[CONTROL] = 1
                instance = 'instance_' + str(uuid4())
                control[INSTANCE] = instance
                for obj in members:
                    obj[INSTANCE] = instance
                # Identity parent adds a placement layer without changing any
                # root's local channels, keys, parent inverse or native scale.
                for root in roots:
                    root.parent = control
                    root.matrix_parent_inverse = Matrix.Identity(4)
                bpy.context.view_layer.update()
                require(all(max(abs(a-b) for ra, rb in zip(o.matrix_world, before[o]) for a, b in zip(ra, rb)) < 1e-5
                            for o in members), 'WORLD_PLACEMENT_CHANGED', 'Preparation changed existing transforms')
            result['prepared'].append({'asset': asset, 'job': job, 'instance': instance,
                                       'control': control.name, 'members': [o.name for o in members if o != control]})
        except Exception as exc:
            # Refusals occur before modification. A failed postcondition is fatal
            # to this disposable task initialization, never a partial success.
            if getattr(exc, 'code', None) != 'WORLD_PLACEMENT_UNSUPPORTED':
                raise
            result['unsupported'].append({'asset': asset, 'job': job, 'reason': str(exc)})
    return result


def ancestor_control(obj):
    seen = set()
    while obj and obj not in seen:
        if obj.get(CONTROL) == 1:
            return obj
        seen.add(obj)
        obj = obj.parent
    return None


def select_instances(objects):
    """Resolve observed picked members to independent controls without doubling."""
    controls = {ancestor_control(o) for o in objects}
    require(controls and None not in controls, 'WORLD_SELECTION_REQUIRED',
            'Choose a prepared asset; use detailed Blender tools for unsupported objects')
    for control in controls:
        require(control.name in bpy.context.view_layer.objects and not control.hide_get(),
                'WORLD_SELECTION_REQUIRED', 'Placement control is not visible in this view layer')
    for obj in list(bpy.context.selected_objects):
        obj.select_set(False)
    for control in controls:
        control.select_set(True)
    bpy.context.view_layer.objects.active = sorted(controls, key=lambda o: o.name)[0]
    return controls


def restore_widgets(scene):
    """Restore only recorded, still-observed widgets when leaving World tasks."""
    stored = json.loads(scene.get(VISIBILITY, '{}'))
    require(isinstance(stored, dict) and all(isinstance(k, str) and type(v) is bool for k, v in stored.items()),
            'WORLD_VISIBILITY_INVALID', 'Invalid World widget visibility record')
    for obj in widgets(scene):
        if obj.name in stored and obj.name in bpy.context.view_layer.objects:
            obj.hide_set(stored[obj.name])
    if VISIBILITY in scene:
        del scene[VISIBILITY]


def hide_widgets(scene):
    observed = widgets(scene)
    require(not any(o.vertex_groups or any(m.type == 'ARMATURE' for m in o.modifiers) for o in observed if o.type == 'MESH'),
            'WORLD_WIDGET_AMBIGUOUS', 'A rig shape is also skinned geometry; inspect it before hiding controls')
    scene[VISIBILITY] = json.dumps({o.name: o.hide_get() for o in observed if o.name in bpy.context.view_layer.objects})
    for obj in observed:
        if obj.name in bpy.context.view_layer.objects:
            obj.hide_set(True)


def install_tools(task, report):
    """Scoped controls/keymaps in this dedicated World process, never preferences."""
    def in_world(context):
        return (context.mode == 'OBJECT' and context.workspace is not None
                and context.workspace.name == 'Asset Director - World')

    class AD_OT_world_select(bpy.types.Operator):
        bl_idname = 'asset_director.world_select'
        bl_label = 'Select whole asset'
        control: bpy.props.StringProperty()

        def execute(self, context):
            obj = context.scene.objects.get(self.control)
            if not obj or obj.get(CONTROL) != 1:
                return {'CANCELLED'}
            for selected in list(context.selected_objects):
                selected.select_set(False)
            select_instances([obj])
            return {'FINISHED'}

    class AD_OT_world_transform(bpy.types.Operator):
        bl_idname = 'asset_director.world_transform'
        bl_label = 'Arrange whole asset'
        operation: bpy.props.EnumProperty(items=[('MOVE', 'Move', ''), ('ROTATE', 'Rotate', ''), ('SCALE', 'Scale', '')])

        @classmethod
        def poll(cls, context):
            return in_world(context) and bool(context.selected_objects)

        def invoke(self, context, event):
            try:
                picked = list(context.selected_objects)
                if any(o.get('bad_asset') or ancestor_control(o) for o in picked):
                    select_instances(picked)
                operation = {'MOVE': bpy.ops.transform.translate, 'ROTATE': bpy.ops.transform.rotate,
                             'SCALE': bpy.ops.transform.resize}[self.operation]
                operation('INVOKE_DEFAULT')
                return {'FINISHED'}
            except Exception as exc:
                self.report({'ERROR'}, str(exc))
                return {'CANCELLED'}

    class AD_PT_world_placement(bpy.types.Panel):
        bl_label = 'World placement'
        bl_idname = 'AD_PT_world_placement'
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = 'Asset Director'

        @classmethod
        def poll(cls, context):
            return context.workspace and context.workspace.name == 'Asset Director - World'

        def draw(self, context):
            layout = self.layout
            layout.label(text='Place whole assets; animation stays intact.')
            for item in report['prepared']:
                layout.operator(AD_OT_world_select.bl_idname, text=item['control']).control = item['control']
            row = layout.row()
            for operation, label in [('MOVE', 'Move'), ('ROTATE', 'Rotate'), ('SCALE', 'Scale')]:
                row.operator(AD_OT_world_transform.bl_idname, text=label).operation = operation
            layout.label(text='G / R / S arrange the whole selected asset.')
            layout.label(text='Save normally; use Action for rig editing.')
            layout.label(text='Rigged assets: use uniform scale.')
            for item in report['unsupported']:
                layout.label(text='Needs detailed preparation: ' + item['asset'], icon='INFO')
                layout.label(text=item['reason'])

    for cls in (AD_OT_world_select, AD_OT_world_transform, AD_PT_world_placement):
        bpy.utils.register_class(cls)
    config = bpy.context.window_manager.keyconfigs.addon
    if config:
        keymap = config.keymaps.new(name='Object Mode', space_type='EMPTY')
        for key, operation in [('G', 'MOVE'), ('R', 'ROTATE'), ('S', 'SCALE')]:
            item = keymap.keymap_items.new(AD_OT_world_transform.bl_idname, key, 'PRESS')
            item.properties.operation = operation
