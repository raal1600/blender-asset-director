"""Dedicated human-editing Blender process. Never attaches to another GUI.

A fixed JSON task opens a working copy, selects an existing workspace/targets,
and provides one explicit checkpoint operator. No socket, second MCP server,
script argument, installation, or saved user-preference changes are introduced.
"""
from pathlib import Path
import json
import re
import sys
from .core import Library, atomic_json, fields, file_hash, load_json, require, within

STAGES = {"world": "Layout", "action": "Animation", "shots": "Layout", "light": "Shading", "render": "Rendering"}
TASK_FIELDS = {"schema", "id", "projectId", "sceneId", "stage", "projectDirectory", "library", "input", "workingScene", "checkpointScene", "returnFile", "targets", "camera", "frame", "action", "state", "startedAt", "processId", "selectedSources", "frameRange"}


def validate(task):
    fields(task, TASK_FIELDS, TASK_FIELDS - {"processId", "frameRange"})
    require(task["schema"] == 1 and task["stage"] in STAGES, "INVALID_TASK", "Unknown task schema or stage")
    for key, prefix in (("id", "task_"), ("projectId", "prj_"), ("sceneId", "sc_")):
        require(isinstance(task[key], str) and re.fullmatch(prefix + r"[0-9a-f-]{36}", task[key]),
                "INVALID_TASK", "Invalid task identity")
    require(isinstance(task["targets"], list) and len(task["targets"]) <= 64 and
            all(isinstance(n, str) and 0 < len(n) <= 255 for n in task["targets"]),
            "INVALID_TASK", "Invalid observed targets")
    require(task["camera"] is None or isinstance(task["camera"], str) and 0 < len(task["camera"]) <= 255 and not any(c in task["camera"] for c in "\r\n\0"), "INVALID_TASK", "Invalid camera")
    require(task["frame"] is None or type(task["frame"]) is int and -100000 <= task["frame"] <= 100000,
            "INVALID_TASK", "Invalid frame")
    frame_range = task.get("frameRange")
    require(frame_range is None or isinstance(frame_range, list) and len(frame_range) == 2 and
            all(type(f) is int for f in frame_range) and -100000 <= frame_range[0] <= frame_range[1] <= 100000
            and frame_range[1] - frame_range[0] < 360, "INVALID_TASK", "Invalid task playback range")
    require(task["action"] == "workbench-edit", "INVALID_TASK", "Unknown task operation")
    require(isinstance(task["projectDirectory"], str) and Path(task["projectDirectory"]).is_absolute(),
            "INVALID_TASK", "Expected an absolute project directory")
    require(isinstance(task["library"], str) and Path(task["library"]).is_absolute(),
            "INVALID_TASK", "Expected an absolute configured library")
    require(isinstance(task["selectedSources"], list) and len(task["selectedSources"]) <= 20000,
            "INVALID_TASK", "Invalid selected sources")
    for source in task["selectedSources"]:
        fields(source, {"sourceId", "version", "path"}, {"sourceId", "version", "path"})
        require(isinstance(source["sourceId"], str) and re.fullmatch(r"src_[0-9a-f-]{36}", source["sourceId"]) and
                isinstance(source["version"], str) and re.fullmatch(r"[0-9a-f]{64}", source["version"]) and
                isinstance(source["path"], str) and Path(source["path"]).is_absolute(),
                "INVALID_TASK", "Invalid selected source reference")
    project = Path(task["projectDirectory"]).resolve()
    owner = load_json(project / "project.json")
    require(owner.get("id") == task["projectId"] and owner.get("owner") == "asset-director-launcher",
            "PROJECT_MISMATCH", "Task belongs to another project")
    for key in ("workingScene", "checkpointScene"):
        name = task[key]
        require(isinstance(name, str) and name.startswith("Scenes/") and name.endswith(".blend") and name.count("/") == 1,
                "INVALID_TASK", "Working files must be directly inside project Scenes")
        within(project, name)
    require(task["workingScene"] != task["checkpointScene"], "INVALID_TASK", "Checkpoint must be a different file")
    require(task["returnFile"] == "Docs/Workbench/" + task["id"] + "-return.json",
            "INVALID_TASK", "Unexpected checkpoint receipt path")
    within(project, task["returnFile"])
    if task["input"] is not None:
        fields(task["input"], {"path", "sha256"}, {"path", "sha256"})
        source = within(project, task["input"]["path"])
        require(source.is_file() and source.suffix == ".blend" and source.parent == (project / "Scenes").resolve(),
                "INVALID_TASK", "Input must be a saved project scene")
        require(file_hash(source) == task["input"]["sha256"], "STALE_INPUT", "Checkpoint changed before task launch")
        require(source not in {within(project, task["workingScene"]), within(project, task["checkpointScene"])},
                "ORIGINAL_OVERWRITE", "Task output must not overwrite its input")
    return project


def initialize(task):
    import bpy
    from . import license_policy as lp
    project = validate(task)
    require(not within(project, task["checkpointScene"]).exists(),
            "OUTPUT_EXISTS", "Task checkpoint already exists; do not overwrite")
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    working = within(project, task["workingScene"])
    if bpy.app.background:
        require(not working.exists(), "OUTPUT_EXISTS", "Task working file already exists")
        if task["input"]:
            bpy.ops.wm.open_mainfile(filepath=str(within(project, task["input"]["path"])), load_ui=False, use_scripts=False)
        else:
            bpy.ops.wm.read_factory_settings(use_empty=True)
    elif task["input"]:
        # The launcher copied and verified the frozen input before starting this
        # dedicated GUI. Loading on the CLI avoids invalidating a live timer's UI
        # context. The original is never opened as the mutable GUI file.
        require(working.is_file() and file_hash(working) == task["input"]["sha256"],
                "STALE_INPUT", "Expected an unchanged launcher-created working copy")
        require(bool(bpy.data.filepath) and Path(bpy.data.filepath).resolve() == working,
                "TASK_CONTEXT_CHANGED", "Launch this task with its verified working copy")
    else:
        require(not working.exists() and not bpy.data.filepath,
                "TASK_CONTEXT_CHANGED", "New tasks require an unused factory-startup window")
        # This process was just created without a file. Remove only its factory
        # objects; never reload windowing data or touch another Blender process.
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
    from .task_window import task_window
    window = task_window()
    if window:
        # File load can clear context.window even in a visible interactive process.
        with bpy.context.temp_override(window=window):
            return configure(task, project)
    return configure(task, project)


def configure(task, project):
    import bpy
    from . import license_policy as lp
    with Library(task["library"]) as lib:
        baseline = lp.derivation(lib, task["input"]["sha256"]) if task["input"] else []
        embedded = json.loads(bpy.context.scene.get(lp.SCENE_KEY, "[]"))
        require(isinstance(embedded, list) and set(embedded) <= set(baseline),
                "LICENSE_SCOPE_MISMATCH", "Use the library that owns this checkpoint's restricted lineage")
    configured = False
    window = bpy.context.window
    if window and not bpy.app.background:
        workspace = (bpy.data.workspaces.get("Asset Director - " + task["stage"].title()) or
                     bpy.data.workspaces.get(STAGES[task["stage"]]))
        if workspace:
            window.workspace = workspace
            workspace.name = "Asset Director - " + task["stage"].title()
            configured = True
    scene = bpy.context.scene
    if task.get("frameRange"):
        start, end = task["frameRange"]
        require(scene.frame_start <= start <= end <= scene.frame_end, "TARGET_CHANGED", "Shot range leaves the saved scene")
        scene.frame_preview_start, scene.frame_preview_end = start, end
        scene.use_preview_range = True
        require([scene.frame_preview_start, scene.frame_preview_end] == [start, end],
                "INVALID_TASK", "Blender did not retain the requested playback range")
    for name in task["targets"]:
        require(scene.objects.get(name) is not None, "TARGET_CHANGED", "Observed target is no longer in this scene: " + name)
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for name in task["targets"]:
        obj = scene.objects[name]
        require(obj.name in bpy.context.view_layer.objects, "TARGET_HIDDEN", "Target is not in the active view layer")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
    if task["camera"]:
        camera = scene.objects.get(task["camera"])
        require(camera is not None and camera.type == "CAMERA", "CAMERA_REQUIRED", "Requested camera is missing")
        scene.camera = camera
    if task["frame"] is not None:
        scene.frame_set(task["frame"])
    if task["camera"]:
        scene.camera = camera  # Preserve the requested camera after timeline markers.
    active = bpy.context.view_layer.objects.active
    if task["stage"] == "action" and active and active.type == "ARMATURE":
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode="POSE")
    if window and scene.camera and task["stage"] in {"shots", "light"}:
        for area in window.screen.areas:
            if area.type == "VIEW_3D" and area.spaces.active.region_3d:
                area.spaces.active.region_3d.view_perspective = "CAMERA"
    bpy.ops.wm.save_as_mainfile(filepath=str(within(project, task["workingScene"])), check_existing=False, relative_remap=True)
    with Library(task["library"]) as lib:
        lp.retain_derivation(lib, within(project, task["workingScene"]), baseline)
    return {"project": project, "baseline": baseline, "gui_configured": configured}


def checkpoint(task, initialized):
    import bpy
    from . import license_policy as lp
    from .scene_ops import scene_audit
    project = initialized["project"]
    validate(task)
    require(Path(bpy.data.filepath).resolve() == within(project, task["workingScene"]),
            "TASK_CONTEXT_CHANGED", "This window is no longer editing the task working copy")
    target, receipt = within(project, task["checkpointScene"]), within(project, task["returnFile"])
    require(not target.exists() and not receipt.exists(), "CHECKPOINT_EXISTS", "This task already returned a checkpoint")
    embedded = json.loads(bpy.context.scene.get(lp.SCENE_KEY, "[]"))
    require(isinstance(embedded, list), "LICENSE_SCOPE_MISMATCH", "Invalid scene lineage")
    grants = sorted(set(initialized["baseline"]) | set(embedded))
    with Library(task["library"]) as lib:
        lp.dependencies(lib, grants)
        if grants:
            bpy.context.scene[lp.SCENE_KEY] = json.dumps(grants)
        # Copy keeps this GUI on its mutable working file, never the checkpoint.
        bpy.ops.wm.save_as_mainfile(filepath=str(target), check_existing=False, copy=True, relative_remap=False)
        lp.retain_derivation(lib, target, grants)
    record = {"schema": 1, "taskId": task["id"], "projectId": task["projectId"], "sceneId": task["sceneId"],
              "stage": task["stage"], "path": task["checkpointScene"], "sha256": file_hash(target),
              "size": target.stat().st_size, "audit": scene_audit(), "gui_configured": initialized["gui_configured"],
              "human_acceptance": "PENDING", "source": "blender-checkpoint-operator"}
    atomic_json(receipt, record)
    return record


def main(filename):
    import bpy
    task = load_json(Path(filename))
    project = validate(task)
    require(Path(filename).resolve() == within(project, "Runs/" + task["id"] + ".json"),
            "INVALID_TASK", "Task must come from its project Runs directory")
    status_file = within(project, "Docs/Workbench/" + task["id"] + "-status.json")
    try:
        state = initialize(task)
    except BaseException as exc:
        atomic_json(status_file, {"taskId": task["id"], "projectId": task["projectId"],
                                  "sceneId": task["sceneId"], "state": "FAILED", "message": str(exc)[:2000]})
        raise

    class AD_OT_checkpoint(bpy.types.Operator):
        bl_idname = "asset_director.save_checkpoint"
        bl_label = "Save checkpoint and return to launcher"
        bl_description = "Save a new review candidate; your working copy stays open and the original is preserved"

        @classmethod
        def poll(cls, context):
            return not within(project, task["returnFile"]).exists()

        def execute(self, context):
            try:
                checkpoint(task, state)
            except Exception as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            self.report({"INFO"}, "Checkpoint saved. Return to the same launcher scene and collect it for review.")
            return {"FINISHED"}

    class AD_PT_task(bpy.types.Panel):
        bl_label = "Asset Director task"
        bl_idname = "AD_PT_task"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Asset Director"

        def draw(self, context):
            layout = self.layout
            layout.label(text="Activity: " + task["stage"].title())
            layout.label(text="Task: " + task["id"][5:13])
            layout.label(text="Your original checkpoint is preserved.")
            layout.operator(AD_OT_checkpoint.bl_idname)
            if task["selectedSources"]:
                layout.separator()
                layout.label(text="Selected sources (not imported):")
                for source in task["selectedSources"][:20]:
                    layout.label(text=Path(source["path"]).name)
                    layout.label(text=source["path"])
                layout.label(text="Use normal File > Import / Append, or the reviewed specialist.")
                layout.label(text="Keep source originals unchanged.")
            if within(project, task["returnFile"]).exists():
                layout.label(text="Saved. Collect the checkpoint in the launcher.")
                layout.label(text="Further edits here are not automatically collected.")

    bpy.utils.register_class(AD_OT_checkpoint)
    bpy.utils.register_class(AD_PT_task)
    # Search (F3) can find the operator in every workspace, not only VIEW_3D.
    atomic_json(status_file, {"taskId": task["id"], "projectId": task["projectId"], "sceneId": task["sceneId"],
                              "state": "READY", "gui_configured": state["gui_configured"],
                              "working_file": bpy.data.filepath, "workspace": bpy.context.window.workspace.name if bpy.context.window else None})
    print("ASSET_DIRECTOR_TASK_READY " + task["id"], flush=True)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    require(len(args) == 1, "INVALID_TASK", "Expected one launcher-created task manifest")
    main(args[0])
