"""UI feedback for one explicitly opened task; no new socket or MCP server.

The heartbeat proves only what this helper observes. It is not OS visibility,
external write exclusion, creative approval, or ownership of another window.
"""
import os
import time
from pathlib import Path
from .core import atomic_json, load_json, within


def observation(task, configured):
    import bpy
    root = Path(task['projectDirectory']).resolve()
    matches = bool(bpy.data.filepath) and Path(bpy.data.filepath).resolve() == within(root, task['workingScene'])
    window = bpy.context.window
    scene = bpy.context.scene
    returned = within(root, task['returnFile']).is_file()
    return dict(taskId=task['id'], projectId=task['projectId'], sceneId=task['sceneId'],
                state='CHECKPOINT_SAVED' if returned else 'READY' if matches else 'CONTEXT_CHANGED',
                observed_at=time.time(), processId=os.getpid(), expected_file=matches,
                dirty=bool(bpy.data.is_dirty) if matches else None, gui_configured=configured,
                workspace=window.workspace.name if window and matches else None,
                active_object=bpy.context.object.name if matches and bpy.context.object else None,
                frame=scene.frame_current if matches else None,
                checkpoint_available=returned,
                areas=[dict(type=a.type, x=a.x, y=a.y, width=a.width, height=a.height)
                       for a in window.screen.areas] if window and matches else [])


def install(filename):
    """Call after task_workspace.main initialized and registered the real operator."""
    import bpy
    task = load_json(Path(filename))
    status = within(Path(task['projectDirectory']), 'Docs/Workbench/' + task['id'] + '-status.json')
    configured = load_json(status)['gui_configured']

    def draw(self, context):
        self.layout.operator('asset_director.save_checkpoint', text='Save checkpoint & return')

    bpy.types.TOPBAR_MT_editor_menus.append(draw)
    if bpy.context.window:
        for area in bpy.context.window.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.show_region_ui = True

    def heartbeat():
        try:
            atomic_json(status, observation(task, configured))
        except Exception as exc:
            # A stale timestamp is unavailable, not proof that the task is live.
            print('ASSET_DIRECTOR_STATUS_UNAVAILABLE ' + type(exc).__name__, flush=True)
        return 1.0

    heartbeat()
    bpy.app.timers.register(heartbeat, first_interval=1.0, persistent=True)
