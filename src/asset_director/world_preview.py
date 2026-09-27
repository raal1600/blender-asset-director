"""Frozen evaluated mesh derivative. Original rigs/data are restored afterwards."""
from contextlib import contextmanager
import bpy
from .core import require
from .world_placement import widgets


@contextmanager
def frozen_meshes(enabled):
    if not enabled:
        yield []
        return
    require(bpy.app.background and bpy.context.scene.get('asset_director_preview_only') is True,
            'PREVIEW_ONLY', 'Frozen geometry requires an isolated preview worker')
    scene = bpy.context.scene
    original = list(scene.objects)
    helpers = widgets(scene)
    require(not any(o.type == 'MESH' and (o.vertex_groups or any(m.type == 'ARMATURE' for m in o.modifiers)) for o in helpers),
            'WORLD_WIDGET_AMBIGUOUS', 'A rig shape is also skinned geometry; inspect in Blender')
    renderable = set()

    def visit(collection, hidden=False):
        hidden = hidden or collection.hide_render
        if not hidden:
            renderable.update(collection.objects)
        for child in collection.children:
            visit(child, hidden)
    visit(scene.collection)
    deps = bpy.context.evaluated_depsgraph_get()
    copies, flags, mapping = [], {}, []
    evaluated_vertices = 0
    try:
        # Evaluate all sources BEFORE hiding anything; never export a bind pose
        # as the user's current pose. No skin/action/bone channels in this view.
        for source in original:
            if (source.type != 'MESH' or source in helpers or source.hide_render
                    or source not in renderable or source.name not in bpy.context.view_layer.objects):
                continue
            evaluated = source.evaluated_get(deps)
            mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=deps)
            copy = bpy.data.objects.new('World preview - ' + source.name, mesh)
            copies.append((copy, mesh))
            evaluated_vertices += len(mesh.vertices)
            require(evaluated_vertices <= 2000000, 'RESOURCE_LIMIT',
                    'Evaluated geometry exceeds the two-million-vertex preview limit; inspect in Blender')
            copy.matrix_world = evaluated.matrix_world.copy()
            scene.collection.objects.link(copy)
            mapping.append({'source': source.name, 'node': copy.name})
        for source in original:
            if source.type in {'MESH', 'ARMATURE'} or source in helpers:
                flags[source] = source.hide_render
                source.hide_render = True
        bpy.context.view_layer.update()
        yield mapping
    finally:
        for source, value in flags.items():
            source.hide_render = value
        for copy, mesh in reversed(copies):
            bpy.data.objects.remove(copy, do_unlink=True)
            bpy.data.meshes.remove(mesh)
        bpy.context.view_layer.update()
