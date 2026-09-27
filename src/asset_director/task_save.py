"""Explicit Save handoff for a dedicated editing copy, never recovery autosaves.

Installed after initialization's own save. Only successful saves to the exact
working path are recorded. No background/timer save and no approval is made.
The launcher freezes the last saved bytes only after the owned process stops.
"""
import json
import os
import time
from pathlib import Path
from uuid import uuid4
from .core import Library, atomic_json, file_hash, load_json, require, within

MODE = "explicit-save-v1"


def session_file(task):
    return within(Path(task["projectDirectory"]), "Docs/Workbench/" + task["id"] + "-save-session.json")


def save_file(task):
    return within(Path(task["projectDirectory"]), "Docs/Workbench/" + task["id"] + "-explicit-save.json")


def install(task, initialized):
    import bpy
    from . import license_policy as lp
    from .scene_ops import scene_audit
    project = initialized["project"]
    working = within(project, task["workingScene"])
    session_path, receipt_path = session_file(task), save_file(task)
    require(not session_path.exists() and not receipt_path.exists(), "OUTPUT_EXISTS", "Editing session already exists")
    identity = dict(schema=1, taskId=task["id"], projectId=task["projectId"], sceneId=task["sceneId"],
                    processId=os.getpid(), stage=task["stage"], mode=MODE)
    session = dict(identity, state="READY", initial_sha256=file_hash(working), workingScene=task["workingScene"])
    atomic_json(session_path, session)
    pending = {"target": None, "grants": None}

    def matches(filename):
        return (isinstance(filename, str) and bool(filename) and Path(filename).resolve() == working
                and bool(bpy.data.filepath) and Path(bpy.data.filepath).resolve() == working)

    def failed(message):
        pending["target"] = None
        session.update(state="SAVE_FAILED", message=str(message)[:1000])
        atomic_json(session_path, session)

    def before(filename):
        pending["target"] = None
        if not matches(filename) or session["state"] == "DISCONNECTED":
            return
        try:
            embedded = json.loads(bpy.context.scene.get(lp.SCENE_KEY, "[]"))
            require(isinstance(embedded, list), "LICENSE_SCOPE_MISMATCH", "Invalid scene lineage")
            grants = sorted(set(initialized["baseline"]) | set(embedded))
            with Library(task["library"]) as lib:
                lp.dependencies(lib, grants)
            pending.update(target=str(working), grants=grants)
            session.update(state="SAVING", message=None)
            atomic_json(session_path, session)
        except Exception as exc:
            # A handler cannot cancel Blender's Save; refuse collection instead.
            failed(exc)

    def after(filename):
        if pending["target"] != str(working) or not matches(filename):
            return
        pending["target"] = None
        try:
            before_hash = file_hash(working)
            audit = scene_audit()
            with Library(task["library"]) as lib:
                lp.retain_derivation(lib, working, pending["grants"])
            require(file_hash(working) == before_hash, "SAVE_CHANGED", "Saved working file changed during observation")
            record = dict(identity, saveId=str(uuid4()), path=task["workingScene"], sha256=before_hash,
                          size=working.stat().st_size, audit=audit, saved_at=time.time(),
                          human_acceptance="PENDING", source="blender-explicit-save")
            # Preserve small immutable observations, not another .blend per save.
            history = within(project, "Docs/Workbench/" + task["id"] + "-save-" + record["saveId"] + ".json")
            atomic_json(history, record)
            atomic_json(receipt_path, record)
            session.update(state="SAVED", message=None)
            atomic_json(session_path, session)
        except Exception as exc:
            failed(exc)

    def post_fail(filename):
        if pending["target"] == str(working):
            failed("Blender could not save the editing copy. Inspect the retained working file before continuing.")

    def disconnect(_filename):
        pending["target"] = None
        session.update(state="DISCONNECTED", message="Another file was opened; automatic return is paused.")
        atomic_json(session_path, session)

    bpy.app.handlers.save_pre.append(before)
    bpy.app.handlers.save_post.append(after)
    bpy.app.handlers.save_post_fail.append(post_fail)
    bpy.app.handlers.load_pre.append(disconnect)
    return dict(before=before, after=after, failed=post_fail, disconnect=disconnect)


def save_and_return(task):
    import bpy
    working = within(Path(task["projectDirectory"]), task["workingScene"])
    require(bool(bpy.data.filepath) and Path(bpy.data.filepath).resolve() == working,
            "TASK_CONTEXT_CHANGED", "Return to the Director editing copy before saving")
    result = bpy.ops.wm.save_as_mainfile(filepath=str(working), check_existing=False)
    require("FINISHED" in result, "SAVE_FAILED", "Blender did not finish saving; this window stays open")
    record = load_json(save_file(task))
    require(record["sha256"] == file_hash(working) and load_json(session_file(task))["state"] == "SAVED",
            "SAVE_FAILED", "Save handoff is incomplete; inspect the task before closing")
    # This is the user-invoked return command in this dedicated process only.
    # Ordinary X / Save / Don't Save remain Blender's normal native behavior.
    bpy.ops.wm.quit_blender()
