"""Assemble verified, reviewed render sequences into a new silent H.264 cut.

No Blender scene mutation, network, shell, implicit retiming, or raw asset export.
The launcher owns the user approval and project/scene selection. This adapter
checks exact frame evidence and the encoded result, not artistic acceptance.
"""
from fractions import Fraction
from pathlib import Path
import json
import re
import shutil
import subprocess
import time
from .core import DirectorError, atomic_json, digest, fields, file_hash, load_json, require, within

PLAN_FIELDS = {"schema", "id", "project_id", "clips"}
CLIP_FIELDS = {"scene_id", "job_id", "checkpoint_sha256"}


def validate_plan(plan):
    fields(plan, PLAN_FIELDS, PLAN_FIELDS)
    require(plan["schema"] == 1 and isinstance(plan["id"], str) and
            re.fullmatch(r"cut_[0-9a-f-]{36}", plan["id"]), "INVALID_FILM_PLAN", "Invalid cut identity")
    require(isinstance(plan["project_id"], str) and re.fullmatch(r"prj_[0-9a-f-]{36}", plan["project_id"]),
            "INVALID_FILM_PLAN", "Invalid project identity")
    require(isinstance(plan["clips"], list) and 1 <= len(plan["clips"]) <= 32,
            "RESOURCE_LIMIT", "Choose one to 32 reviewed shot renders")
    for clip in plan["clips"]:
        fields(clip, CLIP_FIELDS, CLIP_FIELDS)
        require(isinstance(clip["scene_id"], str) and re.fullmatch(r"sc_[0-9a-f-]{36}", clip["scene_id"]),
                "INVALID_FILM_PLAN", "Invalid scene identity")
        require(isinstance(clip["job_id"], str) and re.fullmatch(r"j_[a-f0-9]{24}", clip["job_id"]),
                "INVALID_JOB", "Invalid render job")
        require(isinstance(clip["checkpoint_sha256"], str) and re.fullmatch(r"[a-f0-9]{64}", clip["checkpoint_sha256"]),
                "INVALID_FILM_PLAN", "Invalid checkpoint hash")


def rendered_sequence(lib, job_id):
    from .jobs import read_job
    job, location = read_job(lib, job_id)
    require(job["state"] == "SUCCEEDED" and job["specification"]["operation"] == "render-frames",
            "RENDER_REQUIRED", "Only successful render-frames jobs can enter the film")
    by_name = {}
    for output in job["outputs"]:
        filename = lib.verify_file(output)
        require(filename.parent == location.parent, "INVALID_RENDER", "Render output leaves its job")
        by_name[filename.name] = (filename, output)
    require("result.json" in by_name, "INVALID_RENDER", "Missing render result")
    report = load_json(by_name["result.json"][0])
    require(report.get("status") == "OK" and report.get("job_id") == job_id,
            "INVALID_RENDER", "Wrong render result identity")
    data = report["data"]
    require(data.get("kind") == "RENDERED_FRAME_SEQUENCE", "INVALID_RENDER", "Preview artifacts are not shot renders")
    require(type(data["frame_count"]) is int and 1 <= data["frame_count"] <= 360 and
            len(data["frames"]) == data["frame_count"], "INVALID_RENDER", "Incomplete frame list")
    rate = data["fps"]
    require(type(rate["numerator"]) is int and type(rate["denominator"]) is int and
            rate["numerator"] > 0 and rate["denominator"] > 0,
            "INVALID_RENDER", "Invalid frame rate")
    fps = Fraction(rate["numerator"], rate["denominator"])
    require(1 <= fps <= 240, "INVALID_RENDER", "Unsupported frame rate")
    width, height = data["width"], data["height"]
    require(type(width) is int and type(height) is int and
            16 <= width <= 1920 and 16 <= height <= 1080 and width % 2 == height % 2 == 0,
            "INVALID_RENDER", "Invalid frame dimensions")
    frames = []
    for index, frame in enumerate(data["frames"], 1):
        name = "frame_%06d.png" % index
        require(frame["file"] == name and name in by_name, "INVALID_RENDER", "Missing or unordered frame")
        filename, record = by_name[name]
        with filename.open("rb") as stream:
            header = stream.read(24)
        require(header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR" and
                int.from_bytes(header[16:20], "big") == width and int.from_bytes(header[20:24], "big") == height,
                "INVALID_RENDER", "Frame is not the recorded PNG dimensions")
        frames.append((filename, record))
    require(data["source_sha256"] == job["specification"]["inputs"][0]["sha256"],
            "INVALID_RENDER", "Render checkpoint identity mismatch")
    return {"job": job, "data": data, "frames": frames, "fps": fps, "size": (width, height)}


def executable(filename, name):
    require(isinstance(filename, str) and Path(filename).is_absolute() and Path(filename).is_file(),
            "ENCODER_NOT_CONFIGURED", "Configure an absolute " + name + " executable path")
    return str(Path(filename).resolve())


def _run(args, timeout):
    from .jobs import child_environment
    result = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                            timeout=timeout, shell=False, env=child_environment())
    require(result.returncode == 0, "ENCODER_FAILED", result.stderr.decode("utf-8", "replace")[-4000:])
    require(len(result.stdout) <= 1024**2, "ENCODER_OUTPUT_LIMIT", "Encoder response exceeded 1 MiB")
    return result.stdout


def assemble(lib, plan, project_directory, ffmpeg, ffprobe):
    validate_plan(plan)
    encoder, probe = executable(ffmpeg, "FFmpeg"), executable(ffprobe, "FFprobe")
    project = Path(project_directory).resolve()
    owner = load_json(project / "project.json")
    require(owner.get("owner") == "asset-director-launcher" and owner.get("id") == plan["project_id"],
            "PROJECT_MISMATCH", "Film plan does not belong to this launcher project")
    sequences = [rendered_sequence(lib, clip["job_id"]) for clip in plan["clips"]]
    for clip, sequence in zip(plan["clips"], sequences):
        require(sequence["data"]["source_sha256"] == clip["checkpoint_sha256"],
                "STALE_FILM_PLAN", "A shot render belongs to another checkpoint")
        source = Path(sequence["job"]["specification"]["inputs"][0]["path"]).resolve()
        require(source.is_relative_to((project / "Scenes").resolve()), "PROJECT_MISMATCH", "Shot input belongs to another project")
        require(sequence["fps"] == sequences[0]["fps"] and sequence["size"] == sequences[0]["size"],
                "FILM_FORMAT_MISMATCH", "Use a common frame rate and dimensions; this adapter never silently retimes or rescales")
    total = sum(len(s["frames"]) for s in sequences)
    require(sum(record["size"] for sequence in sequences for _, record in sequence["frames"]) <= 4 * 1024**3,
            "RESOURCE_LIMIT", "Film staging exceeds the 4 GiB frame-copy budget")
    require(total <= 3600, "RESOURCE_LIMIT", "Initial film adapter supports at most 3600 output frames")
    directory = within(project, "Deliverables/" + plan["id"])
    directory.parent.mkdir(parents=True, exist_ok=True)
    require(not directory.exists(), "OUTPUT_EXISTS", "Cut output already exists; create a new cut revision")
    directory.mkdir()
    record = {"schema": 1, "kind": "FILM_EXPORT", "plan": plan, "plan_hash": digest(plan),
              "state": "RUNNING", "started_at": time.time(), "audio": "NONE", "human_acceptance": "PENDING"}
    receipt = directory / "manifest.json"
    atomic_json(receipt, record)
    try:
        staging = directory / "frames"
        staging.mkdir()
        provenance, index = [], 0
        for clip, sequence in zip(plan["clips"], sequences):
            start = index + 1
            for filename, evidence in sequence["frames"]:
                index += 1
                target = staging / ("frame_%06d.png" % index)
                shutil.copyfile(filename, target)
                require(file_hash(target) == evidence["sha256"], "STALE_RENDER", "A frame changed while assembling")
            provenance.append({**clip, "output_frames": [start, index], "frame_hashes": [f[1]["sha256"] for f in sequence["frames"]]})
        fps = sequences[0]["fps"]
        rate = str(fps.numerator) + "/" + str(fps.denominator)
        destination = directory / "film.mp4"
        _run([encoder, "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-framerate", rate,
              "-start_number", "1", "-i", str(staging / "frame_%06d.png"), "-frames:v", str(total),
              "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-threads", "2",
              "-movflags", "+faststart", str(destination)], 900)
        measured = json.loads(_run([probe, "-v", "error", "-count_frames", "-select_streams", "v:0",
                                   "-show_entries", "stream=codec_name,width,height,r_frame_rate,nb_read_frames,duration",
                                   "-of", "json", str(destination)], 120))
        streams = measured.get("streams", [])
        require(len(streams) == 1, "ENCODE_VALIDATION_FAILED", "Expected exactly one video stream")
        stream = streams[0]
        require(stream.get("codec_name") == "h264" and int(stream.get("nb_read_frames", 0)) == total and
                (stream.get("width"), stream.get("height")) == sequences[0]["size"] and
                Fraction(stream["r_frame_rate"]) == fps,
                "ENCODE_VALIDATION_FAILED", "Encoded video differs from the approved frame contract")
        require(abs(float(stream["duration"]) - total / float(fps)) <= 1 / float(fps),
                "ENCODE_VALIDATION_FAILED", "Encoded duration differs from the frame contract")
        _run([encoder, "-v", "error", "-nostdin", "-i", str(destination), "-map", "0:v:0", "-f", "null", "-"], 120)
        # Recheck source evidence after encoding as well, not just copied bytes.
        for clip in plan["clips"]:
            rendered_sequence(lib, clip["job_id"])
        record.update(state="SUCCEEDED", finished_at=time.time(), sources=provenance,
                      file="film.mp4", sha256=file_hash(destination), size=destination.stat().st_size,
                      frames=total, fps={"numerator": fps.numerator, "denominator": fps.denominator},
                      dimensions=list(sequences[0]["size"]), seconds=total / float(fps),
                      codec="h264", crf=18, encoder_sha256=file_hash(Path(encoder)),
                      encoder_version=_run([encoder, "-version"], 10).decode("utf-8", "replace").splitlines()[0],
                      measured=stream)
        atomic_json(receipt, record)
        shutil.rmtree(staging)  # Only this newly created cut's temporary frame copies.
        return record
    except BaseException as exc:
        record.update(state="FAILED", finished_at=time.time(), error=str(exc)[:4000])
        atomic_json(receipt, record)
        raise
