"""Portable contract for explicitly authorized frame-sequence renders.

Separate from bounded preview artifacts. No inference of creative settings,
scene ownership, distribution rights, or human approval happens in this module.
"""
from pathlib import Path
from .core import fields, file_hash, load_json, require

FIELDS = {"readiness_job", "camera", "start", "end", "width", "height", "samples"}
MAX_FRAMES = 360
MAX_PIXEL_SAMPLES = 2_000_000_000


def validate(options):
    fields(options, FIELDS, FIELDS)
    require(isinstance(options["readiness_job"], str) and
            len(options["readiness_job"]) == 26 and options["readiness_job"].startswith("j_") and
            all(c in "0123456789abcdef" for c in options["readiness_job"][2:]),
            "INVALID_JOB", "Choose an existing render-readiness job")
    require(isinstance(options["camera"], str) and 0 < len(options["camera"]) <= 255 and
            not any(c in options["camera"] for c in "\r\n\0"),
            "CAMERA_REQUIRED", "Choose an observed scene camera")
    for key in ("start", "end", "width", "height", "samples"):
        require(type(options[key]) is int, "INVALID_SCHEMA", key + " must be an integer")
    count = options["end"] - options["start"] + 1
    require(-100000 <= options["start"] <= options["end"] <= 100000 and 1 <= count <= MAX_FRAMES,
            "RESOURCE_LIMIT", "Render one to 360 consecutive frames per authorized shot")
    require(16 <= options["width"] <= 1920 and 16 <= options["height"] <= 1080 and
            options["width"] % 2 == options["height"] % 2 == 0,
            "RESOURCE_LIMIT", "Use even dimensions from 16x16 through 1920x1080")
    require(1 <= options["samples"] <= 128, "RESOURCE_LIMIT", "Use one to 128 CPU samples")
    require(count * options["width"] * options["height"] * options["samples"] <= MAX_PIXEL_SAMPLES,
            "RESOURCE_LIMIT", "This shot exceeds the CPU work budget; reduce range, dimensions or samples")
    return count


def readiness(lib, job_id, input_file):
    from .jobs import read_job
    job, location = read_job(lib, job_id)
    require(job["state"] == "SUCCEEDED" and job["specification"]["operation"] == "render-readiness",
            "READINESS_REQUIRED", "Complete a read-only render-readiness job first")
    inputs = job["specification"]["inputs"]
    require(len(inputs) == 1 and input_file is not None and
            inputs[0]["sha256"] == file_hash(Path(input_file)),
            "STALE_READINESS", "Readiness evidence belongs to another saved scene revision")
    for output in job["outputs"]:
        lib.verify_file(output)
    record = next((o for o in job["outputs"] if o["path"] ==
                   (location.parent / "result.json").relative_to(lib.root).as_posix()), None)
    require(record is not None, "READINESS_REQUIRED", "Missing readiness result evidence")
    report = load_json(location.parent / "result.json")
    require(report.get("status") == "OK" and report.get("job_id") == job_id,
            "READINESS_REQUIRED", "Invalid readiness result")
    data = report["data"]
    require(data.get("kind") == "RENDER_READINESS", "READINESS_REQUIRED", "Unexpected readiness artifact")
    return data, record


def prepare(lib, options, input_file):
    validate(options)
    require(input_file is not None and Path(input_file).suffix.lower() == ".blend",
            "TARGET_REQUIRED", "Render a saved .blend checkpoint")
    audit, dependency = readiness(lib, options["readiness_job"], input_file)
    verify_external(audit)
    require(not audit["blockers"], "RENDER_BLOCKED", "; ".join(audit["blockers"]))
    require(options["camera"] in audit["cameras"], "CAMERA_REQUIRED", "Camera was not observed in this checkpoint")
    require(audit["frame_range"][0] <= options["start"] <= options["end"] <= audit["frame_range"][1],
            "INVALID_RANGE", "Shot range must be inside the saved scene range")
    return dependency


def verify_external(audit):
    """Recheck retained external inputs without loading or executing Blender."""
    total = 0
    for dependency in audit.get("dependencies", []):
        path = Path(dependency["path"])
        require(path.is_absolute() and path.is_file(), "STALE_RENDER_DEPENDENCIES", "External render input is missing")
        total += dependency["size"]
        require(total <= 4 * 1024**3, "RESOURCE_LIMIT", "External render inputs exceed the 4 GiB verification budget")
        require(path.stat().st_size == dependency["size"] and file_hash(path) == dependency["sha256"],
                "STALE_RENDER_DEPENDENCIES", "External render inputs changed after readiness review")
