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
    from .task_window import task_window
    window = task_window()
    scene = window.scene if window else bpy.context.scene
    active = (window.view_layer if window else bpy.context.view_layer).objects.active
    returned = within(root, task['returnFile']).is_file()
    return dict(taskId=task['id'], projectId=task['projectId'], sceneId=task['sceneId'],
                state='CHECKPOINT_SAVED' if returned else 'READY' if matches else 'CONTEXT_CHANGED',
                observed_at=time.time(), processId=os.getpid(), expected_file=matches,
                dirty=bool(bpy.data.is_dirty) if matches else None, gui_configured=configured,
                workspace=window.workspace.name if window and matches else None,
                active_object=active.name if matches and active else None,
                frame=scene.frame_current if matches else None,
                checkpoint_available=returned,
                areas=[dict(type=a.type, x=a.x, y=a.y, width=a.width, height=a.height)
                       for a in window.screen.areas] if window and matches else [])


CHECKPOINT_LABEL = 'Save checkpoint and return to launcher'


def register_checkpoint_menus(types):
    """Give F3 a canonical menu entry without changing user preferences.

    F3 searches menu entries. The abbreviated direct header button alone is not
    the canonical operator search label; retain both access paths.
    """
    def menu_entry(self, context):
        self.layout.operator('asset_director.save_checkpoint', text=CHECKPOINT_LABEL)

    def quick_button(self, context):
        self.layout.operator('asset_director.save_checkpoint', text='Save checkpoint & return')

    types.TOPBAR_MT_file.append(menu_entry)
    types.TOPBAR_MT_editor_menus.append(quick_button)


def install(filename):
    """Call after task_workspace.main initialized and registered the real operator."""
    import bpy
    task = load_json(Path(filename))
    status = within(Path(task['projectDirectory']), 'Docs/Workbench/' + task['id'] + '-status.json')
    configured = load_json(status)['gui_configured']
    print('Feedback: status read', flush=True)

    print('Feedback: registering File menu and topbar', flush=True)
    register_checkpoint_menus(bpy.types)
    print('Feedback: topbar registered', flush=True)
    from .task_window import task_window
    window = task_window()
    print('Feedback: window resolved', flush=True)
    if window:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.show_region_ui = True

    def heartbeat():
        try:
            atomic_json(status, observation(task, configured))
        except Exception as exc:
            # A stale timestamp is unavailable, not proof that the task is live.
            print('ASSET_DIRECTOR_STATUS_UNAVAILABLE ' + type(exc).__name__, flush=True)
        return 1.0

    print('Feedback: regions configured', flush=True)
    heartbeat()
    print('Feedback: initial observation saved', flush=True)
    bpy.app.timers.register(heartbeat, first_interval=1.0, persistent=True)
