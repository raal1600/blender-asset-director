"""Start the dedicated GUI task after Blender's event loop is ready.

Use only the validated task's diagnostic path. Startup failures stay visible;
no reload of another process, preferences save or protocol server is introduced.
"""
from contextlib import redirect_stdout, redirect_stderr
import io
from pathlib import Path
import traceback
from .core import atomic_json, load_json, require, within


class BoundedLog(io.TextIOBase):
    def __init__(self, path, limit=1024 * 1024):
        self.stream = None
        self.stream = Path(path).open('x', encoding='utf-8')
        self.remaining = limit

    def write(self, message):
        text = str(message)
        # Bound diagnostic characters; no uncontrolled exception/output dump.
        if self.remaining:
            portion = text[:self.remaining]
            self.stream.write(portion); self.stream.flush()
            self.remaining -= len(portion)
        return len(text)

    def flush(self):
        if self.stream:
            self.stream.flush()

    def close(self):
        if not self.closed:
            super().close()
            if self.stream:
                self.stream.close()


def start(filename):
    import bpy
    from .task_workspace import validate, main
    from .task_feedback import install, observation
    task = load_json(Path(filename)); project = validate(task)
    require(Path(filename).resolve() == within(project, 'Runs/' + task['id'] + '.json'),
            'INVALID_TASK', 'Task must come from its project Runs directory')
    status = within(project, 'Docs/Workbench/' + task['id'] + '-status.json')
    log = within(project, 'Docs/Workbench/' + task['id'] + '-startup.log')
    identity = dict(taskId=task['id'], projectId=task['projectId'], sceneId=task['sceneId'])
    atomic_json(status, dict(identity, state='STARTING'))

    def prepare():
        try:
            with BoundedLog(log) as stream, redirect_stdout(stream), redirect_stderr(stream):
                try:
                    print('Workspaces:', [w.name for w in bpy.data.workspaces])
                    print('Normal windows:', len(bpy.context.window_manager.windows))
                    main(filename)
                    install(filename)
                    print('Task observation:', observation(task, load_json(status)['gui_configured']))
                except Exception:
                    traceback.print_exc()
                    raise
        except Exception as exc:
            atomic_json(status, dict(identity, state='FAILED', message=str(exc)[:2000]))
        return None

    if bpy.app.background:
        prepare()
    else:
        # File/workspace operators from startup --python can run before the
        # initial native window becomes a valid editor context.
        bpy.app.timers.register(prepare, first_interval=0.2, persistent=True)
