"""Action-only presentation in a dedicated task; no animation or preference edits."""
import re
from pathlib import Path
from .core import fields, require, within


def validate_context(task):
    controls = task.get('rigControls', False)
    require(type(controls) is bool and (not controls or task['stage'] == 'action'),
            'INVALID_TASK', 'Rig controls belong to the Action task')
    context = task.get('actionContext')
    if context is None:
        require(not controls, 'INVALID_TASK', 'Inspect the selected performer before rig editing')
        return
    keys = {'version', 'checkpointId', 'sha256', 'inspectionId', 'audit_sha256', 'performer', 'frame'}
    fields(context, keys, keys)
    require(task['stage'] == 'action' and context['version'] == 'action-layer-v1' and task.get('input')
            and context['sha256'] == task['input']['sha256'] and task['targets'] == [context['performer']]
            and type(context['frame']) is int and context['frame'] == task['frame'],
            'INVALID_TASK', 'Performer context differs from the editing task')
    for key, prefix in [('checkpointId', 'cp_'), ('inspectionId', 'run_')]:
        require(isinstance(context[key], str) and re.fullmatch(prefix + r'[0-9a-f-]{36}', context[key]),
                'INVALID_TASK', 'Invalid performer inspection identity')
    require(isinstance(context['audit_sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', context['audit_sha256']),
            'INVALID_TASK', 'Invalid performer inspection fingerprint')


def verify_observed(task):
    """Run before frame/selection changes so the exact saved audit still applies."""
    context = task.get('actionContext')
    if context is None:
        return
    from .action_layer import audit
    observed = audit()
    require(observed['sha256'] == context['audit_sha256'], 'ACTION_CHANGED', 'Performer bindings changed before manual handoff')
    performer = next((p for p in observed['performers'] if p['name'] == context['performer']), None)
    require(performer is not None and observed['frame_range'][0] <= context['frame'] <= observed['frame_range'][1],
            'TARGET_CHANGED', 'Requested performer or frame is not in the saved scene')
    require(not task.get('rigControls') or performer['type'] == 'ARMATURE',
            'INVALID_TASK', 'Selected performer has no armature controls')


def presentation(task, enabled=False):
    import bpy
    from . import world_placement
    require(task['stage'] == 'action', 'INVALID_TASK', 'Rig controls belong to Action')
    context = task.get('actionContext')
    name = context['performer'] if context else next(iter(task['targets']), None)
    obj = bpy.context.scene.objects.get(name) if name else None
    if enabled:
        require(obj is not None and obj.type == 'ARMATURE' and obj.name in bpy.context.view_layer.objects
                and not obj.hide_get(), 'TARGET_HIDDEN', 'Select the observed visible armature to edit its rig')
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        require(bpy.ops.object.mode_set.poll(), 'TASK_CONTEXT_CHANGED', 'Leave the current editing mode first')
        bpy.ops.object.mode_set(mode='OBJECT')
    world_placement.restore_widgets(bpy.context.scene)
    if not enabled:
        # Refuse ambiguous skinned helpers instead of hiding character geometry.
        world_placement.hide_widgets(bpy.context.scene)
    window = bpy.context.window
    if window:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.overlay.show_bones = enabled
    if enabled:
        for selected in list(bpy.context.selected_objects):
            selected.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        require(bpy.ops.object.mode_set.poll(), 'TASK_CONTEXT_CHANGED', 'Pose editing is unavailable in this task')
        bpy.ops.object.mode_set(mode='POSE')
    return {'rig_controls': enabled, 'performer': name, 'mode': bpy.context.mode}


def install_tools(task):
    import bpy

    class AD_OT_action_controls(bpy.types.Operator):
        bl_idname = 'asset_director.action_controls'
        bl_label = 'Show or hide performer rig controls'
        enabled: bpy.props.BoolProperty(default=True)

        def execute(self, context):
            try:
                require(bool(bpy.data.filepath) and Path(bpy.data.filepath).resolve() ==
                        within(Path(task['projectDirectory']), task['workingScene']),
                        'TASK_CONTEXT_CHANGED', 'Return to the dedicated editing copy')
                presentation(task, self.enabled)
            except Exception as error:
                self.report({'ERROR'}, str(error))
                return {'CANCELLED'}
            return {'FINISHED'}

    bpy.utils.register_class(AD_OT_action_controls)
