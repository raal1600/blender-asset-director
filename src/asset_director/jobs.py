"""Durable, versioned jobs and bounded isolated Blender execution."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import threading
import time
from .core import Asset, DirectorError, Library, SCHEMA, atomic_json, canonical, digest, fields, file_hash, load_json, require, rights, tokens, within
from . import camera_plan
from . import look_contract

OPS = {
    "stage-floor": {"size", "location", "color", "grid_color", "tile_size", "roughness"},
    "inspect": set(),
    "scene-audit": set(),
    "camera-fit": {"subjects", "frames", "direction", "lens_mm", "sensor_width_mm", "margin", "projection"},
    "camera-check": {"subjects", "frames", "camera", "margin", "sample", "targets", "occlusion"},
    "camera-plan": set(camera_plan.TOP_LEVEL),
    "look-audit": set(),
    "light-adjust": {"lights"},
    "world-adjust": set(look_contract.WORLD_FIELDS),
    "look-adjust": set(look_contract.LOOK_FIELDS),
    "light-rig": {"subjects", "lights"},
    "index": {"max_clips", "sample"},
    "import": {"collection", "selection"},
    "retarget": {"target_object", "source_object", "action", "slot", "mapping", "alignment", "pose_space", "start", "end", "source_fps", "target_fps", "allow_unskinned_fixture"},
    "assemble": {"target_object", "clips", "fps", "controller_speed", "direction", "terrain_object", "travel_frames"},
    "qa": {"target_object", "start", "end", "terrain_object", "sole_offsets"},
    "preview": {"frames", "width", "height", "samples", "target_object", "stage"},
}
MUTATIONS = {"stage-floor", "import", "retarget", "assemble", "preview", "camera-fit", "camera-plan",
             "light-adjust", "world-adjust", "look-adjust", "light-rig"}
TARGET_REQUIRED = {"stage-floor", "retarget", "assemble", "qa", "preview", "scene-audit", "camera-fit", "camera-check",
                   "camera-plan", "look-audit", "light-adjust", "world-adjust", "look-adjust", "light-rig"}


def implementation_hash():
    return digest({p.name: file_hash(p) for p in sorted(Path(__file__).parent.glob("*.py"))})


def prepare(lib: Library, operation: str, input_file: str | None = None, asset_id: str | None = None, options=None) -> dict:
    require(operation in OPS, "UNKNOWN_OPERATION", "Unknown Blender operation")
    options = options or {}
    fields(options, OPS[operation])
    if operation == "assemble":
        from .motion_timing import validate_assembly
        validate_assembly(options)
    if operation == "stage-floor":
        from .floor_contract import validate
        validate(options)
    if operation == "retarget" and "pose_space" in options:
        from .pose_contract import validate
        validate(options["pose_space"])
        require(options.get("mapping") and options.get("alignment"), "MAPPING_REVIEW_REQUIRED",
                "Evaluated pose transfer requires explicit mapping and reference alignment")
    # Reject an invalid camera plan on portable Python: no Blender process, no
    # file write and no partial scene mutation for a contract that cannot execute.
    if operation == "camera-plan":
        camera_plan.validate(options)
    # Same rule for look development: validate explicit values before Blender runs.
    elif operation == "light-adjust":
        look_contract.validate_light_adjust(options)
    elif operation == "world-adjust":
        look_contract.validate_world_adjust(options)
    elif operation == "look-adjust":
        look_contract.validate_look_adjust(options)
    require(not options.get("allow_unskinned_fixture"), "FIXTURE_ONLY", "Unskinned fixture override is not available to production jobs")
    inputs = []
    if input_file:
        path = Path(input_file).expanduser().resolve()
        require(path.is_file() and path.suffix.lower() in {".blend", ".glb", ".gltf", ".fbx", ".bvh", ".obj"}, "INVALID_INPUT", "Input must be an existing supported Blender/asset file")
        inputs.append({"role": "target", "path": str(path), "sha256": file_hash(path), "size": path.stat().st_size})
    asset = lib.get(asset_id) if asset_id else None
    source_files = []
    if asset:
        require(asset.local_files, "ASSET_NOT_ACQUIRED", "Acquire/intake the source first")
        if operation in {"import", "retarget"}:
            policy = rights(asset)
            require(policy["eligible"], "BLOCKED_POLICY", "; ".join(policy["reasons"]))
        for f in asset.local_files: lib.verify_file(f)
        source_files = asset.local_files
        if asset.kind == "animation" and operation == "retarget":
            options.setdefault("action", asset.metadata.get("action"))
            if asset.metadata.get("slot") is not None: options.setdefault("slot", asset.metadata["slot"])
            if asset.metadata.get("source_object"): options.setdefault("source_object", asset.metadata["source_object"])
            if asset.metadata.get("fps"):
                require("source_fps" not in options or options["source_fps"] == asset.metadata["fps"],
                        "SOURCE_TIMEBASE_MISMATCH", "Do not override indexed timebase to change speed; use assemble playback_speed")
                options.setdefault("source_fps", asset.metadata["fps"])
    if operation in TARGET_REQUIRED:
        require(inputs, "TARGET_REQUIRED", "Operation requires a specific saved working/target file")
    if operation in {"import", "retarget"}: require(source_files, "SOURCE_REQUIRED", "Operation requires an acquired asset ID")
    # No terminal strings, scripts, network endpoints, or model-provided output paths.
    specification = {"schema_version": SCHEMA, "operation": operation, "inputs": inputs, "asset_id": asset_id,
                     "source_files": source_files, "source_file": asset.metadata.get("file") if asset else None, "options": options, "implementation": implementation_hash()}
    jid = "j_" + digest(specification)[:24]
    path = lib.root / "jobs" / jid / "job.json"
    if path.exists():
        previous = load_json(path)
        require(previous["specification"] == specification, "JOB_CONFLICT", "Conflicting job specification")
        return previous
    job = {"id": jid, "specification": specification, "state": "PLANNED", "created_at": time.time(), "library": str(lib.root),
           "outputs": [], "last_error": None}
    atomic_json(path, job)
    return job


def read_job(lib: Library, jid: str) -> tuple[dict, Path]:
    require(jid.startswith("j_") and len(jid) == 26 and all(c in "0123456789abcdef" for c in jid[2:]), "INVALID_JOB", "Invalid job ID")
    path = lib.root / "jobs" / jid / "job.json"
    require(path.is_file(), "JOB_NOT_FOUND", "Unknown job")
    job = load_json(path)
    require(job["id"] == jid and "j_" + digest(job["specification"])[:24] == jid and Path(job["library"]).resolve() == lib.root,
            "INVALID_JOB", "Job identity/library mismatch")
    require(job["specification"]["implementation"] == implementation_hash(), "STALE_IMPLEMENTATION", "Code changed; prepare a new job")
    fields(job["specification"]["options"], OPS[job["specification"]["operation"]])
    for f in job["specification"]["inputs"]:
        p = Path(f["path"])
        require(p.is_file() and p.stat().st_size == f["size"] and file_hash(p) == f["sha256"], "STALE_INPUT", "Target input changed; prepare a new job")
    for f in job["specification"]["source_files"]: lib.verify_file(f)
    return job, path


def child_environment() -> dict:
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "HOME", "USERPROFILE", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "LD_LIBRARY_PATH"}
    return {k:v for k,v in os.environ.items() if k.upper() in allowed}


def run(lib: Library, jid: str, blender: str, timeout=360) -> dict:
    require(5 <= timeout <= 900, "RESOURCE_LIMIT", "Timeout must be 5..900 seconds")
    executable = Path(blender).expanduser().resolve()
    require(executable.is_file(), "BLENDER_NOT_FOUND", "Provide the actual Blender executable path")
    job, path = read_job(lib, jid)
    if job["state"] == "SUCCEEDED":
        for output in job["outputs"]: lib.verify_file(output)
        return job
    require(job["state"] == "PLANNED", "JOB_NOT_RUNNABLE", "Failed/interrupted jobs retain evidence; use job-retry explicitly")
    with lib.lock("run-" + jid):
        job["state"] = "RUNNING"; job["started_at"] = time.time(); atomic_json(path, job)
        runner = Path(__file__).parent / "worker.py"
        args = [str(executable), "--background", "--factory-startup", "--disable-autoexec", "--threads", "2", "--python-exit-code", "11", "--python", str(runner), "--", str(path)]
        log = path.parent / "worker.log"
        try:
            with log.open("wb") as out:
                process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=child_environment(), cwd=path.parent, shell=False)
                overflow = threading.Event()
                def drain():
                    count = 0
                    while True:
                        block = process.stdout.read(4096)
                        if not block: break
                        count += len(block)
                        if count <= 2*1024**2: out.write(block)
                        else:
                            overflow.set(); process.kill(); break
                reader = threading.Thread(target=drain, daemon=True); reader.start()
                try: code = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(); raise DirectorError("BLENDER_TIMEOUT", "Blender worker deadline exceeded")
                except BaseException:
                    process.kill(); process.wait(timeout=10); raise
                finally:
                    reader.join(timeout=10)
                    process.stdout.close()
                require(not overflow.is_set(), "LOG_LIMIT", "Blender output exceeded the log limit")
            result_path = path.parent / "result.json"
            result = load_json(result_path) if result_path.exists() else None
            require(code == 0 and result and result.get("status") == "OK", (result or {}).get("code", "BLENDER_FAILED"), (result or {}).get("message", "Blender worker failed; inspect its local log"))
            # Detect unexpected disk modifications as well as stale jobs.
            read_job(lib, jid)
            outputs = []
            for p in sorted(path.parent.iterdir()):
                if p.name in {"job.json", "worker.log"} or not p.is_file(): continue
                outputs.append({"path": p.relative_to(lib.root).as_posix(), "size": p.stat().st_size, "sha256": file_hash(p)})
            job.update(state="SUCCEEDED", outputs=outputs, summary=result.get("summary", {}), finished_at=time.time())
        except DirectorError as exc:
            job.update(state="FAILED", last_error=exc.as_dict(), finished_at=time.time())
            atomic_json(path, job); raise
        except BaseException:
            job.update(state="INTERRUPTED", finished_at=time.time()); atomic_json(path, job); raise
        atomic_json(path, job)
        return job


def retry(lib: Library, jid: str) -> dict:
    job, path = read_job(lib, jid)
    require(job["state"] in {"FAILED", "INTERRUPTED"}, "INVALID_STATE", "Only failed/interrupted jobs may be retried")
    # Preserve failure evidence; never erase existing source or final projects.
    history = path.parent / f"attempt-{int(time.time()*1000)}"
    history.mkdir()
    for p in list(path.parent.iterdir()):
        if p.is_file(): p.replace(history / p.name)
    job.update(state="PLANNED", outputs=[], last_error=None)
    atomic_json(path, job); return job


def index_result(lib: Library, asset_id: str, jid: str) -> dict:
    a = lib.get(asset_id)
    job, path = read_job(lib, jid)
    require(job["state"] == "SUCCEEDED" and job["specification"]["operation"] == "index", "INDEX_NOT_READY", "Need a successful index job")
    report = load_json(path.parent / "result.json")
    clips = report.get("data", {}).get("clips", [])
    added = []
    for clip in clips:
        sf = clip["file"]
        require(any(f["sha256"] == sf["sha256"] and f["path"] == sf["path"] for f in a.local_files), "INDEX_SOURCE_MISMATCH", "Index result refers to a different asset")
        family = re_clip_name(clip["action"])
        sid = digest([a.id, sf["sha256"], clip["action"], clip.get("slot"), clip["source_object"]])
        record = Asset(a.provider, "clip-" + sid, clip["action"], "animation", a.source_url, a.license_id, a.license_url, a.author,
                       a.price, True, [Path(sf["path"]).suffix.lower()], sorted(tokens(clip["action"])), a.evidence,
                       # Include sidecar dependencies, not only the primary glTF.
                       local_files=a.local_files,
                       metadata={**clip, "parent_asset": a.id, "motion_family": digest([a.id, family]),
                                 "family_match": "name-grouped format variants; not proof of identical motion", "tag_origin": "filename inference", "visual_review": "PENDING"})
        lib.put(record); added.append(record.id)
    a.metadata["indexed_clips"] = added; a.metadata["index_job"] = jid
    lib.put(a)
    return {"status": "INDEXED", "clips": len(added), "motion_families": len({lib.get(i).metadata["motion_family"] for i in added}), "ids": added}


def re_clip_name(name):
    import re
    return re.sub(r"[^a-z0-9]", "", name.split("|")[-1].lower())
