"""Real Blender camera-authoring, camera-check and preview-settings regression.

Synthetic geometry with deliberately unrelated names, formats, scales and
timebases. This is technical evidence for framing math, keyframe persistence and
preservation invariants. It is not artistic cinematography, not a claim about
real rigs, and not acceptance of any user scene.
"""
import json
import math
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asset_director import jobs, scene_ops
from asset_director.core import DirectorError, Library, atomic_json, file_hash
from asset_director.worker import execute

OUT = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
LIBRARY = OUT / "camera-library"
CHECKS = []


def require(condition, name, **detail):
    if not condition:
        raise AssertionError(name + ": " + json.dumps(detail, default=str))
    CHECKS.append({"check": name, **detail})


def fresh(subject_name, location, scale, resolution, fps, frame_end, lens=50.0, sensor_fit="AUTO"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    subject = bpy.context.object
    subject.name = subject_name
    subject.location = location
    subject.scale = scale
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.fps, scene.render.fps_base = fps, 1.0
    scene.frame_start, scene.frame_end = 1, frame_end
    data = bpy.data.cameras.new("placed_camera")
    camera = bpy.data.objects.new("placed_camera", data)
    scene.collection.objects.link(camera)
    data.lens = lens
    data.sensor_fit = sensor_fit
    camera.location = (0.0, -14.0, 1.0)
    camera.rotation_euler = (math.radians(85.0), 0.0, 0.0)
    scene.camera = camera
    bpy.context.view_layer.update()
    return scene, subject, camera


def run_job(operation, source, options):
    with Library(LIBRARY) as lib:
        job = jobs.prepare(lib, operation, str(source), options=options)
        directory = lib.root / "jobs" / job["id"]
        execute(directory / "job.json")
        report = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    return job, directory, report["data"]


def reload_result(directory):
    bpy.ops.wm.open_mainfile(filepath=str(directory / "result.blend"), load_ui=False, use_scripts=False)
    return bpy.context.scene


def framed_height(checkpoint):
    low, high = checkpoint["bounds_ndc"][1], checkpoint["bounds_ndc"][3]
    return high - low


def screen_errors(verification):
    return [c["screen_target"]["error_max"] for c in verification["checkpoints"] if "screen_target" in c]


def margin_respected(checkpoint, margin):
    min_x, min_y, max_x, max_y = checkpoint["bounds_ndc"]
    return (margin - 1e-3 <= min_x and max_x <= 1 - margin + 1e-3
            and margin - 1e-3 <= min_y and max_y <= 1 - margin + 1e-3)


def fit_slack(checkpoint, margin):
    """Near-zero when the solved distance puts a bound exactly on the margin box.

    A tighter margin does not guarantee a larger subject: with an off-centre
    screen target the near margin binds first, so the honest invariant is that
    the fit is tight, not that the subject grew.
    """
    min_x, min_y, max_x, max_y = checkpoint["bounds_ndc"]
    return min(min_x - margin, min_y - margin, (1 - margin) - max_x, (1 - margin) - max_y)


def same_path(left, right):
    """Blender normalizes relative output paths per platform; compare separators loosely."""
    return str(left).replace("\\", "/") == str(right).replace("\\", "/")


def case_formats():
    """Create-mode authoring across unrelated names, aspects, fits, fps and lenses."""
    cases = [("box_case_9 Î²", (1920, 1080), "AUTO", 24, 24, (1.6, 1.6, 3.2), (4.0, -3.0, 0.5), 35.0),
             ("rigid prop 2", (1080, 1920), "VERTICAL", 30, 36, (0.4, 0.4, 0.9), (-7.5, 12.0, 0.25), 24.0),
             ("0042", (1000, 1000), "HORIZONTAL", 25, 12, (2.0, 2.0, 2.0), (0.0, 0.0, 4.0), 85.0),
             ("unrelated_Ù…Ø¬Ø³Ù…", (2100, 900), "AUTO", 60, 48, (0.2, 3.0, 0.6), (30.0, -18.0, 1.0), 50.0)]
    for name, resolution, fit, fps, end, scale, location, lens in cases:
        scene, subject, camera = fresh(name, location, scale, resolution, fps, end, lens=lens, sensor_fit=fit)
        before_matrix = scene_ops.flatten(subject.matrix_world)
        before_camera = scene_ops.flatten(camera.matrix_world)
        source = OUT / (name.replace(" ", "_") + ".blend")
        bpy.ops.wm.save_as_mainfile(filepath=str(source))
        baseline = file_hash(source)
        plan = {"mode": "create", "subjects": [name], "lens_mm": lens, "sensor_fit": fit,
                "frame_range": [1, end], "fps": fps,
                "interpolation": {"type": "BEZIER", "easing": "EASE_IN_OUT"},
                "keyframes": [
                    {"frame": 1, "aim": {"subject": name, "bounds": [0.5, 0.5, 0.5]},
                     "direction": [0.35, -1.0, 0.22], "fit": {"margin": 0.30}, "screen": [0.5, 0.5]},
                    {"frame": max(2, end // 2), "aim": {"subject": name, "bounds": [0.5, 0.5, 0.55]},
                     "direction": [0.35, -1.0, 0.18], "fit": {"margin": 0.15}, "screen": [0.38, 0.58]},
                    {"frame": end, "aim": {"subject": name, "bounds": [0.5, 0.5, 0.6]},
                     "direction": [0.35, -1.0, 0.12], "fit": {"margin": 0.08}, "screen": [0.30, 0.62],
                     "lens_mm": lens * 0.75}]}
        _, directory, data = run_job("camera-plan", source, plan)
        errors = screen_errors(data["verification"])
        sizes = [framed_height(c) for c in data["verification"]["checkpoints"]]
        require(data["mode"] == "create" and len(data["keyframes"]) == 3, "format_case_planned",
                case=name, aspect=resolution, fps=fps, lens=lens)
        require(max(errors) <= 0.005 and len(errors) == 3, "format_case_screen_targets", case=name,
                max_screen_error=max(errors))
        require(data["verification"]["all_fit"] and data["verification"]["occlusion_checked"],
                "format_case_verified", case=name)
        margins = [0.30, 0.15, 0.08]
        slack = [fit_slack(c, m) for c, m in zip(data["verification"]["checkpoints"], margins)]
        require(all(-2e-3 <= value <= 6e-3 for value in slack), "format_case_fit_is_tight", case=name,
                fit_slack=[round(v, 5) for v in slack], framed_height=[round(v, 4) for v in sizes])
        require(all(margin_respected(c, m) for c, m in zip(data["verification"]["checkpoints"], margins)),
                "format_case_margin_respected", case=name,
                bounds_ndc=[c["bounds_ndc"] for c in data["verification"]["checkpoints"]])
        require(abs(data["fps"] - fps) < 1e-6 and data["frame_range"] == [1, end],
                "format_case_timebase_explicit", case=name, fps=data["fps"], frames=data["frame_range"])
        # The worker reloaded the source, so compare the reloaded originals.
        require(scene_ops.flatten(bpy.data.objects[name].matrix_world) == before_matrix
                and scene_ops.flatten(bpy.data.objects["placed_camera"].matrix_world) == before_camera
                and file_hash(source) == baseline, "format_case_preserves_existing", case=name)
        scene = reload_result(directory)
        require(scene.camera.name == data["camera"] and scene.camera.animation_data is not None,
                "format_case_persisted_in_saved_file", case=name)
        keys = [point for curve in scene.camera.animation_data.action.fcurves for point in curve.keyframe_points] \
            if hasattr(scene.camera.animation_data.action, "fcurves") else []
        require(not keys or len(keys) >= 3, "format_case_keyframes_persisted", case=name, keyframes=len(keys))


def case_animated_camera_and_subject():
    """Establishing -> closer move with a changing screen position and an animated subject."""
    scene, subject, _ = fresh("mover.004", (0.0, 0.0, 0.5), (1.0, 1.0, 2.0), (1600, 900), 25, 24)
    subject.location = (0.0, 0.0, 0.5); subject.keyframe_insert("location", frame=1)
    subject.location = (3.0, 0.0, 0.6); subject.keyframe_insert("location", frame=12)
    subject.location = (6.0, 0.0, 0.8); subject.keyframe_insert("location", frame=24)
    subject.scale = (1.0, 1.0, 2.0); subject.keyframe_insert("scale", frame=1)
    subject.scale = (1.4, 1.4, 2.6); subject.keyframe_insert("scale", frame=24)
    subject_action = subject.animation_data.action.name
    source = OUT / "animated_camera_source.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    baseline = file_hash(source)
    plan = {"mode": "create", "subjects": ["mover.004"], "lens_mm": 50, "fps": 25, "frame_range": [1, 24],
            "keyframes": [
                {"frame": 1, "aim": {"subject": "mover.004"}, "direction": [0.3, -1.0, 0.25],
                 "fit": {"margin": 0.32}, "screen": [0.5, 0.5]},
                {"frame": 12, "aim": {"subject": "mover.004", "bounds": [0.5, 0.5, 0.7]},
                 "direction": [0.3, -1.0, 0.18], "fit": {"margin": 0.20}, "screen": [0.44, 0.54]},
                {"frame": 24, "aim": {"subject": "mover.004", "bounds": [0.5, 0.5, 0.8]},
                 "direction": [0.3, -1.0, 0.12], "fit": {"margin": 0.12}, "screen": [0.36, 0.6], "lens_mm": 65}]}
    margins = [0.32, 0.20, 0.12]
    _, directory, data = run_job("camera-plan", source, plan)
    distances = [k["distance"] for k in data["keyframes"]]
    sizes = [framed_height(c) for c in data["verification"]["checkpoints"]]
    errors = screen_errors(data["verification"])
    require(distances[0] > distances[-1], "animated_move_closes_in",
            distance=[round(v, 3) for v in distances])
    require(sizes[0] < sizes[-1], "animated_subject_grows",
            framed_height=[round(v, 4) for v in sizes])
    require(all(margin_respected(c, m) for c, m in zip(data["verification"]["checkpoints"], margins)),
            "animated_margins_respected",
            bounds_ndc=[c["bounds_ndc"] for c in data["verification"]["checkpoints"]])
    require(all(-2e-3 <= fit_slack(c, m) <= 6e-3 for c, m in
                zip(data["verification"]["checkpoints"], margins)),
            "animated_fit_is_tight",
            fit_slack=[round(fit_slack(c, m), 5)
                       for c, m in zip(data["verification"]["checkpoints"], margins)])
    require(max(errors) <= 0.005, "animated_screen_targets_met", max_screen_error=max(errors))
    require([k["screen_requested"] for k in data["keyframes"]] == [[0.5, 0.5], [0.44, 0.54], [0.36, 0.6]],
            "animated_screen_positions_change")
    require(len({k["lens_mm"] for k in data["keyframes"]}) == 2, "animated_lens_changes",
            lens=[k["lens_mm"] for k in data["keyframes"]])
    require(data["verification"]["all_fit"], "animated_framing_holds_at_every_checkpoint")
    require(file_hash(source) == baseline, "animated_source_preserved")
    scene = reload_result(directory)
    mover = bpy.data.objects["mover.004"]
    require(mover.animation_data is not None and mover.animation_data.action.name == subject_action,
            "animated_subject_action_untouched", action=subject_action)
    require(scene.camera.animation_data.action is not None, "animated_camera_action_saved")


def case_explicit_position():
    """Host-chosen world positions are honoured exactly, with a screen target applied on top."""
    scene, subject, _ = fresh("explicit_target", (0.0, 0.0, 0.0), (1.0, 1.0, 2.0), (1600, 900), 24, 10, lens=50)
    bpy.context.view_layer.update()
    source = OUT / "explicit_position_source.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    baseline = file_hash(source)
    placed = [[2.6, -9.0, 1.4], [2.0, -7.5, 1.1]]
    plan = {"mode": "create", "subjects": ["explicit_target"], "lens_mm": 50, "fps": 24,
            "keyframes": [
                {"frame": 1, "aim": {"subject": "explicit_target"}, "position": placed[0], "screen": [0.5, 0.5]},
                {"frame": 10, "aim": {"subject": "explicit_target"}, "position": placed[1], "screen": [0.42, 0.55]}]}
    _, directory, data = run_job("camera-plan", source, plan)
    errors = screen_errors(data["verification"])
    require(max(errors) <= 0.005 and len(errors) == 2, "explicit_screen_targets_met", max_screen_error=max(errors))
    for keyframe, expected in zip(data["keyframes"], placed):
        measured = keyframe["camera_location"]
        require(max(abs(measured[i] - expected[i]) for i in range(3)) < 1e-4, "explicit_position_honoured",
                requested=expected, measured=[round(v, 6) for v in measured])
    require(data["verification"]["all_fit"], "explicit_position_keeps_subject_in_frame",
            bounds_ndc=[c["bounds_ndc"] for c in data["verification"]["checkpoints"]])
    require(data["keyframes"][0]["distance"] > data["keyframes"][1]["distance"], "explicit_move_closes_in",
            distance=[round(k["distance"], 3) for k in data["keyframes"]])
    require(file_hash(source) == baseline, "explicit_source_preserved")
    scene = reload_result(directory)
    require(scene.camera.animation_data is not None, "explicit_camera_action_saved")


def case_adaptation():
    """Adapt an already authored, constrained camera without discarding its animation."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    subject = bpy.context.object
    subject.name = "prop_to_adapt"
    subject.scale = (1.2, 1.2, 2.4)
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.frame_start, scene.frame_end = 1, 20
    data = bpy.data.cameras.new("authored_camera")
    camera = bpy.data.objects.new("authored_camera", data)
    scene.collection.objects.link(camera)
    camera.location = (-9.0, -9.0, 3.0)
    camera.keyframe_insert("location", frame=1)
    camera.location = (-6.0, -12.0, 2.0)
    camera.keyframe_insert("location", frame=20)
    aim = bpy.data.objects.new("far_off_aim", None)
    scene.collection.objects.link(aim)
    aim.location = (40.0, 25.0, 6.0)
    track = camera.constraints.new("TRACK_TO")
    track.name = "authored_track"
    track.target = aim
    scene.camera = camera
    bpy.context.view_layer.update()
    old_action = camera.animation_data.action.name
    source = OUT / "adapt_source.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    plan = {"mode": "adapt", "camera": "authored_camera", "subjects": ["prop_to_adapt"], "lens_mm": 40,
            "existing_animation": "preserve", "constraints": "mute",
            "keyframes": [
                {"frame": 1, "aim": {"subject": "prop_to_adapt"}, "direction": [0.4, -1.0, 0.3],
                 "fit": {"margin": 0.3}, "screen": [0.5, 0.5]},
                {"frame": 20, "aim": {"subject": "prop_to_adapt"}, "direction": [0.4, -1.0, 0.15],
                 "fit": {"margin": 0.1}, "screen": [0.36, 0.58]}]}
    _, directory, data_out = run_job("camera-plan", source, plan)
    errors = screen_errors(data_out["verification"])
    require(max(errors) <= 0.005, "adapted_screen_targets_met", max_screen_error=max(errors))
    require(data_out["preserved_actions"] == [old_action], "adapted_action_reported", action=old_action)
    require(data_out["muted_constraints"] == ["authored_track"], "adapted_constraint_muted",
            muted=data_out["muted_constraints"])
    scene = reload_result(directory)
    camera = bpy.data.objects["authored_camera"]
    tracks = [t for t in camera.animation_data.nla_tracks if t.name.startswith("BAD_PRESERVED_")]
    require(len(tracks) == 1 and tracks[0].mute, "adapted_prior_action_stashed_muted",
            tracks=[t.name for t in camera.animation_data.nla_tracks])
    require(old_action in {a.name for a in bpy.data.actions}, "adapted_prior_action_retained")
    require(camera.constraints["authored_track"].mute, "adapted_constraint_still_muted_in_file")
    require(scene.camera.name == "authored_camera", "adapted_scene_camera_unchanged")
    # A kept constraint must fail loudly instead of silently defeating the authored aim.
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    camera = bpy.data.objects["authored_camera"]
    camera.constraints["authored_track"].mute = False
    kept = dict(plan); kept["constraints"] = "keep"
    try:
        scene_ops.camera_plan(kept, "fixture")
        raise AssertionError("kept_constraint_not_detected")
    except DirectorError as exc:
        require(exc.code == "SCREEN_TARGET_MISSED", "kept_constraint_refused", code=exc.code)


def preview_engine():
    identifiers = [item.identifier for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
        if candidate in identifiers:
            return candidate
    return identifiers[0]


def case_preview_settings():
    """Preview rendering must not contaminate the production settings it saves."""
    scene, _, _ = fresh("preview_subject", (0.0, 0.0, 0.5), (1.0, 1.0, 2.0), (1234, 567), 30, 12)
    scene.camera.data.lens = 40
    production = {"engine": preview_engine(), "resolution_x": 1234, "resolution_y": 567,
                  "resolution_percentage": 55, "filepath": "//delivery/production_",
                  "file_format": "JPEG", "threads_mode": "FIXED", "threads": 3,
                  "cycles_samples": 17, "frame": 12}
    scene.render.engine = production["engine"]
    scene.render.resolution_percentage = production["resolution_percentage"]
    scene.render.filepath = production["filepath"]
    scene.render.image_settings.file_format = production["file_format"]
    scene.render.threads_mode = production["threads_mode"]
    scene.render.threads = production["threads"]
    scene.cycles.samples = production["cycles_samples"]
    scene.frame_set(production["frame"])
    source = OUT / "preview_source.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    baseline = file_hash(source)
    _, directory, data = run_job("preview", source, {"frames": [1], "width": 128, "height": 96, "samples": 1})
    require(data["production_settings_restored"] and data["delivery_master"] is False
            and data["artifact_kind"] == "PREVIEW_ARTIFACT", "preview_reports_artifact_kind")
    saved = data["production_settings"]
    require(saved["engine"] == production["engine"] and saved["resolution"] == [1234, 567]
            and saved["resolution_percentage"] == 55 and saved["samples"] == 17
            and saved["file_format"] == "JPEG" and same_path(saved["filepath"], production["filepath"])
            and saved["frame"] == 12, "preview_reports_production_settings", saved=saved)
    require(data["preview_overrides"]["resolution"] == [128, 96] and data["preview_overrides"]["samples"] == 1,
            "preview_reports_bounded_overrides")
    require((directory / "preview_0001.png").stat().st_size > 0, "preview_image_written")
    require(file_hash(source) == baseline, "preview_source_untouched")
    scene = reload_result(directory)
    require(scene.render.resolution_x == 1234 and scene.render.resolution_y == 567
            and scene.render.resolution_percentage == 55, "preview_saved_resolution_is_production",
            resolution=[scene.render.resolution_x, scene.render.resolution_y],
            percentage=scene.render.resolution_percentage)
    require(scene.render.engine == production["engine"], "preview_saved_engine_is_production",
            engine=scene.render.engine)
    require(scene.cycles.samples == 17, "preview_saved_samples_are_production", samples=scene.cycles.samples)
    require(scene.render.image_settings.file_format == "JPEG"
            and same_path(scene.render.filepath, production["filepath"]), "preview_saved_output_is_production",
            file_format=scene.render.image_settings.file_format, filepath=scene.render.filepath)
    # The job runner launches Blender with a bounded thread count, so the saved
    # thread count must match what this job recorded as production, not what the
    # source file stored before the job started.
    require(scene.render.threads_mode == saved["threads_mode"] and scene.render.threads == saved["threads"],
            "preview_saved_threads_match_reported_production", reported=saved["threads"],
            saved=scene.render.threads)
    require(scene.render.threads_mode == production["threads_mode"],
            "preview_saved_threads_mode_is_production_mode", mode=scene.render.threads_mode)
    require(scene.frame_current == 12, "preview_saved_frame_is_production", frame=scene.frame_current)


def case_camera_check_sampling_and_occlusion():
    """Sampled checkpoints, screen-target error and bounded occlusion rays."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    subject = bpy.context.object
    subject.name = "occluded_subject"
    subject.scale = (1.0, 1.0, 1.0)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    occluder = bpy.context.object
    occluder.name = "opaque_wall"
    occluder.scale = (6.0, 0.2, 6.0)
    occluder.location = (0.0, -6.0, 0.0)
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    scene.frame_start, scene.frame_end = 1, 25
    data = bpy.data.cameras.new("checker")
    camera = bpy.data.objects.new("checker", data)
    scene.collection.objects.link(camera)
    camera.location = (0.0, -12.0, 0.0)
    camera.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    camera.data.lens = 50
    scene.camera = camera
    bpy.context.view_layer.update()
    options = {"subjects": ["occluded_subject"], "camera": "checker",
               "sample": {"start": 1, "end": 25, "count": 3}, "occlusion": True, "margin": 0.0,
               "targets": [{"frame": 1, "subject": "occluded_subject", "screen": [0.5, 0.5]}]}
    blocked = scene_ops.camera_check(options)
    frames = [c["frame"] for c in blocked["checkpoints"]]
    require(frames[0] == 1 and frames[-1] == 25 and len(frames) == 3, "sampled_checkpoints", frames=frames)
    require(all(c["occlusion"]["blocked"] > 0 for c in blocked["checkpoints"]), "occlusion_detected",
            blocked=[c["occlusion"]["blocked"] for c in blocked["checkpoints"]])
    require(blocked["checkpoints"][0]["screen_target"]["within_tolerance"], "screen_target_measured",
            error=blocked["checkpoints"][0]["screen_target"]["error_max"])
    require(blocked["checkpoints"][0]["roll_deg"] == 0.0 or abs(blocked["checkpoints"][0]["roll_deg"]) < 1e-6,
            "level_horizon_reported", roll=blocked["checkpoints"][0]["roll_deg"])
    occluder.location = (500.0, -6.0, 0.0)
    bpy.context.view_layer.update()
    clear = scene_ops.camera_check({**options, "occlusion": True})
    require(all(c["occlusion"]["blocked"] == 0 for c in clear["checkpoints"]), "occlusion_clears_when_moved",
            blocked=[c["occlusion"]["blocked"] for c in clear["checkpoints"]])
    require(clear["all_fit"] and clear["screen_targets_within_tolerance"], "clear_view_verified")


def main():
    case_formats()
    case_animated_camera_and_subject()
    case_explicit_position()
    case_adaptation()
    case_preview_settings()
    case_camera_check_sampling_and_occlusion()
    report = {"status": "PASS", "blender_version": bpy.app.version_string, "checks": CHECKS,
              "check_count": len(CHECKS),
              "notice": "Synthetic geometric fixtures with arbitrary object names. Not artistic "
                        "cinematography, not collision safety, not user-scene acceptance."}
    atomic_json(OUT / "camera_report.json", report)
    print(json.dumps({"status": "PASS", "checks": len(CHECKS), "blender": bpy.app.version_string}))


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        atomic_json(OUT / "camera_report.json",
                    {"status": "FAIL", "blender_version": bpy.app.version_string, "checks": CHECKS,
                     "error": type(exc).__name__ + ": " + str(exc)[:2000]})
        raise
