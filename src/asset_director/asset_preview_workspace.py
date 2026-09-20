"""Explicit preview-only Blender UI. No network, checkpoint or project mutation."""
from pathlib import Path
import sys
import math
import json
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from asset_director.core import load_json, file_hash, require
from asset_director import blender_ops as ops

args = sys.argv[sys.argv.index('--')+1:]
require(len(args) == 1, 'INVALID_PREVIEW', 'Expected one private preview receipt')
receipt_file = Path(args[0]).resolve()
receipt = load_json(receipt_file)
require(receipt.get('state') in {'READY', 'OPENED'} and receipt.get('schema') == 'asset-director.asset-preview/1',
        'INVALID_PREVIEW', 'Preview preparation did not succeed')
expected = (receipt_file.parent / receipt['blend']['path']).resolve()
require(Path(bpy.data.filepath).resolve() == expected and file_hash(expected) == receipt['blend']['sha256']
        and bpy.context.scene.get('asset_director_preview_only') is True,
        'STALE_PREVIEW', 'Open only the exact prepared preview copy')
takes = receipt['data']['takes']


class ADPREVIEW_OT_frame(bpy.types.Operator):
    bl_idname = 'asset_director_preview.frame'
    bl_label = 'Frame asset'

    def execute(self, context):
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    region = next(r for r in area.regions if r.type == 'WINDOW')
                    with context.temp_override(window=window, area=area, region=region):
                        bpy.ops.view3d.view_all(center=False)
        return {'FINISHED'}


class ADPREVIEW_OT_take(bpy.types.Operator):
    bl_idname = 'asset_director_preview.take'
    bl_label = 'Inspect native take'
    index: bpy.props.IntProperty(min=0)

    def execute(self, context):
        if self.index >= len(takes): return {'CANCELLED'}
        t = takes[self.index]
        obj, action = bpy.data.objects.get(t['object']), bpy.data.actions.get(t['action'])
        if not obj or not action:
            self.report({'ERROR'}, 'Preview was edited; reopen a fresh copy to inspect this take')
            return {'CANCELLED'}
        if context.screen.is_animation_playing: bpy.ops.screen.animation_cancel(restore_frame=False)
        ops.assign(obj, action, t['slot'])
        for track in obj.animation_data.nla_tracks: track.mute = True
        context.scene.frame_start = math.floor(t['start'])
        context.scene.frame_end = math.ceil(t['end'])
        context.scene.frame_set(context.scene.frame_start)
        context.scene['ad_preview_take'] = t['action']
        return {'FINISHED'}


class ADPREVIEW_PT_info(bpy.types.Panel):
    bl_label = 'Asset Director - PREVIEW COPY'
    bl_idname = 'ADPREVIEW_PT_info'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Asset preview'

    def draw(self, context):
        layout = self.layout
        layout.label(text=receipt['title'][:100], icon='INFO')
        layout.label(text='Inspection only - scene unchanged.')
        layout.label(text='Orbit with middle mouse; zoom with wheel.')
        layout.operator('asset_director_preview.frame', icon='VIEWZOOM')
        layout.label(text='%.3g fps - native source pairing' % receipt['data']['fps'])
        if takes:
            box = layout.box()
            box.label(text='Observed native takes (%d)' % len(takes))
            box.label(text='Choose a take, then press Play.')
            for index, take in enumerate(takes):
                op = box.operator('asset_director_preview.take', text=take['action'])
                op.index = index
        else:
            layout.label(text='No verified rig takes were found.')
            layout.label(text='Inspect other motion in the timeline.')
        layout.operator('screen.animation_play', text='Pause' if context.screen.is_animation_playing else 'Play / pause', icon='PLAY')
        layout.label(text='Check timing and contacts in the timeline.')
        layout.separator()
        layout.label(text='Return to Director to add the asset.')
        layout.label(text='Close with X. Originals stay unchanged.')
        layout.label(text='Source version: ' + receipt['source_version'][:16])


for cls in (ADPREVIEW_OT_frame, ADPREVIEW_OT_take, ADPREVIEW_PT_info):
    bpy.utils.register_class(cls)


initialization = {'framed': False, 'attempts': 0}


def ready():
    initialization['attempts'] += 1
    panels = []
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                space.show_region_ui = True
                space.shading.type = 'SOLID'
                space.shading.color_type = 'MATERIAL'
                area.tag_redraw()
                panels.extend((window, area, r) for r in area.regions if r.type == 'UI')
    if not initialization['framed']:
        bpy.ops.asset_director_preview.frame()
        initialization['framed'] = True
    # Blender populates sidebar categories only after the region has drawn.
    # Do not report readiness while our controls remain hidden on the Item tab.
    selected = bool(panels)
    for window, area, region in panels:
        try:
            with bpy.context.temp_override(window=window, area=area, region=region):
                region.active_panel_category = 'Asset preview'
                selected = selected and region.active_panel_category == 'Asset preview'
        except (AttributeError, TypeError, ValueError, RuntimeError):
            selected = False
    if not selected:
        if initialization['attempts'] < 20:
            return 0.2
        from asset_director.core import atomic_json
        atomic_json(receipt_file.parent / 'window-failure.json', {
            'state': 'FAILED', 'code': 'PREVIEW_UI_NOT_READY',
            'message': 'The Asset preview sidebar could not be activated.'})
        return None
    # Positive GUI initialization evidence, not proof of visual/temporal approval.
    from asset_director.core import atomic_json
    atomic_json(receipt_file.parent / 'window-ready.json', {
        'schema': 'asset-director.asset-preview-window/1', 'source_id': receipt['source_id'],
        'source_version': receipt['source_version'], 'blend_sha256': receipt['blend']['sha256'],
        'pid': __import__('os').getpid(), 'state': 'READY', 'panel': 'Asset preview',
        'human_review': 'PENDING'})
    return None

bpy.app.timers.register(ready, first_interval=0.5)
