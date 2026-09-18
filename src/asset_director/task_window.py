"""Resolve a window only inside the separately launched task process.

Loading a .blend may clear context.window. Blender documents re-establishing it
from window_manager.windows with temp_override after loading. No OS-wide window
selection is performed here; multiple normal windows are deliberately ambiguous.
"""
from .core import require


def task_window():
    import bpy
    if bpy.app.background:
        return None
    windows = [w for w in bpy.context.window_manager.windows
               if w.screen and not getattr(w.screen, 'is_temporary', False)]
    require(len(windows) == 1, 'TASK_WINDOW_AMBIGUOUS',
            'Expected exactly one normal window in the dedicated task process')
    return windows[0]
