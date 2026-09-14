"""Display-only changes in an isolated result; never edit anatomy or animation."""
import bpy
from .core import require
from . import bone_display_contract as contract


def target(options):
    obj = bpy.data.objects.get(options['target_object'])
    require(obj is not None and obj.type == 'ARMATURE', 'TARGET_REQUIRED', 'Choose an observed armature')
    require(len(obj.data.bones) <= 4096, 'RESOURCE_LIMIT', 'Too many bones for bounded display review')
    return obj


def audit(obj):
    assignments = {p.name:p.custom_shape.name for p in obj.pose.bones if p.custom_shape}
    widgets = []
    for name in sorted(set(assignments.values())):
        shape = bpy.data.objects[name]
        users = sorted(o.name for o in bpy.data.objects if o.type == 'ARMATURE' and
                       any(p.custom_shape == shape for p in o.pose.bones))
        widgets.append({'name':name, 'type':shape.type, 'rig_users':users,
                        'hide_render':shape.hide_render, 'hide_viewport':shape.hide_viewport,
                        'hidden_in_view_layer':shape.hide_get() if shape.name in bpy.context.view_layer.objects else None})
    return {'target_object':obj.name, 'display_type':obj.data.display_type,
            'show_custom_shapes':obj.data.show_bone_custom_shapes, 'show_in_front':obj.show_in_front,
            'custom_shape_assignments':assignments,
            'custom_shapes_override_standard_style':bool(assignments) and obj.data.show_bone_custom_shapes,
            'per_bone_display_overrides':{b.name:b.display_type for b in obj.data.bones if b.display_type != 'ARMATURE_DEFINED'},
            'visible_bones':[b.name for b in obj.data.bones if not b.hide],
            'widget_objects':widgets,
            'visual_acceptance':'PENDING',
            'notice':'Configured display evidence, not a viewport screenshot. Widget visibility flags do not prove rendered visibility.'}


def inspect(options):
    contract.validate('bone-display-audit', options)
    obj=target(options)
    from .blender_ops import rig_report
    return audit(obj) | {'target_fingerprint':rig_report(obj)['fingerprint'], 'read_only':True}


def apply(options):
    contract.validate('bone-display', options)
    obj=target(options)
    from .blender_ops import rig_report
    fingerprint=rig_report(obj)['fingerprint']
    require(fingerprint == options['target_fingerprint'], 'STALE_TARGET', 'Rig changed since display review')
    require(not obj.library and not obj.data.library and not obj.override_library and not obj.data.override_library,
            'DISPLAY_TARGET_READ_ONLY', 'Linked/override rigs need a separate ownership review')
    require(obj.data.users == 1, 'SHARED_ARMATURE_DATA', 'Display changes would affect another armature object')
    visible=options.get('visible_bones')
    require(visible is None or set(visible) <= set(obj.data.bones.keys()), 'UNKNOWN_BONE', 'Display list names absent bones')
    before=audit(obj)
    widgets={p.custom_shape.name:p.custom_shape for p in obj.pose.bones if p.custom_shape}
    hiding=[]
    # Validate every widget before making any display change. No general mesh
    # hide/delete channel, and no guess based on a sphere-like name.
    for name in options.get('hide_widget_objects', []):
        require(name in widgets, 'NOT_TARGET_WIDGET', 'Object is not an observed custom shape of this rig')
        shape=widgets[name]
        require(not shape.library and not shape.override_library and shape.name in bpy.context.view_layer.objects,
                'DISPLAY_TARGET_READ_ONLY', 'Widget is not local in the current view layer')
        require(not any(m.type == 'ARMATURE' for m in shape.modifiers), 'SKINNED_WIDGET_REVIEW', 'Refusing to hide a skinned mesh as a widget')
        require(not any(o != obj and o.type == 'ARMATURE' and any(p.custom_shape == shape for p in o.pose.bones)
                        for o in bpy.data.objects), 'SHARED_WIDGET_REVIEW', 'Widget is shared with another rig')
        hiding.append(shape)
    obj.data.display_type=options['display_type']
    obj.data.show_bone_custom_shapes=options['show_custom_shapes']
    obj.show_in_front=options['show_in_front']
    for bone in obj.data.bones:
        bone.display_type='ARMATURE_DEFINED'
        if visible is not None: bone.hide=bone.name not in visible
    for shape in hiding:
        shape.hide_set(True)
        shape.hide_render=True
    after=audit(obj)
    require(rig_report(obj)['fingerprint'] == fingerprint and
            after['custom_shape_assignments'] == before['custom_shape_assignments'],
            'DISPLAY_ISOLATION_VIOLATION', 'Rig rest data or custom shape references changed')
    return {'before':before, 'after':after, 'target_fingerprint':fingerprint,
            'hidden_widget_objects':[o.name for o in hiding], 'custom_shape_references_preserved':True,
            'rest_fingerprint_preserved':True, 'visual_acceptance':'PENDING',
            'scope':'Armature display, bone visibility and explicitly reviewed widget visibility only; no viewport/playback control'}
