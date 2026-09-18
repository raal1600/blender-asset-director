"""Blender-only read-only readiness and bounded CPU sequence rendering."""
from fractions import Fraction
from pathlib import Path
import bpy
from .core import file_hash, require
from .render_sequence import readiness, validate


def dependencies():
    """Conservative initial scope: files, packed images, keyed/NLA animation.

Unknown cache/sequence inputs fail closed rather than producing apparently
reproducible but unpinned films. All paths here come from observed Blender data.
    """
    files, blockers = {}, []
    for collection in (bpy.data.images, bpy.data.fonts, bpy.data.libraries):
        for item in collection:
            if getattr(item, "packed_file", None) or getattr(item, "packed_files", None):
                continue
            if getattr(item, "source", None) in {"SEQUENCE", "MOVIE", "TILED"}:
                blockers.append("Sequence/movie/UDIM image needs a dedicated dependency adapter: " + item.name)
                continue
            name = getattr(item, "filepath", "")
            if not name or name == "<builtin>":
                continue
            filename = Path(bpy.path.abspath(name, library=getattr(item, "library", None))).resolve()
            if not filename.is_file():
                blockers.append("Missing external dependency: " + item.name)
                continue
            require(len(files) < 2048, "RESOURCE_LIMIT", "Too many external render dependencies")
            stat = filename.stat()
            require(stat.st_size <= 2 * 1024**3, "RESOURCE_LIMIT", "External dependency exceeds 2 GiB")
            files[str(filename)] = {"path": str(filename), "size": stat.st_size, "sha256": file_hash(filename)}
    if len(bpy.data.cache_files) or len(bpy.data.volumes) or len(bpy.data.movieclips):
        blockers.append("External simulation/volume/movie caches are outside the first render adapter")
    for obj in bpy.context.scene.objects:
        if len(obj.particle_systems) or any(m.type in {"FLUID", "CLOTH", "SOFT_BODY", "DYNAMIC_PAINT"} for m in obj.modifiers):
            blockers.append("Simulation cache review required: " + obj.name)
    if bpy.context.scene.rigidbody_world:
        blockers.append("Rigid-body cache review required")
    require(sum(f["size"] for f in files.values()) <= 4 * 1024**3,
            "RESOURCE_LIMIT", "External render inputs exceed 4 GiB")
    # Geometry-node simulations and baked geometry require their own dependency
    # adapter. Refuse them rather than implying random-access reproducibility.
    for tree in bpy.data.node_groups:
        if any(n.bl_idname in {"GeometryNodeSimulationInput", "GeometryNodeSimulationOutput", "GeometryNodeBake"} for n in tree.nodes):
            blockers.append("Geometry-node simulation/bake review required: " + tree.name)
    return sorted(files.values(), key=lambda f: f["path"]), sorted(set(blockers))


def audit():
    scene = bpy.context.scene
    external, blockers = dependencies()
    fps = Fraction(scene.render.fps, 1) / Fraction(str(scene.render.fps_base)).limit_denominator(100000)
    require(1 <= fps <= 240, "INVALID_FPS", "Saved scene FPS must be between 1 and 240")
    if getattr(bpy.app, "autoexec_fail", False):
        blockers.append("Scene requires disabled script/driver execution; bake or review it separately")
    if scene.render.use_multiview:
        blockers.append("Multiview output is outside this single-view render adapter")
    if scene.render.pixel_aspect_x != scene.render.pixel_aspect_y:
        blockers.append("Non-square pixels need an explicit delivery adapter")
    # A sequencer or arbitrary compositor can write unrelated File Output paths.
    if scene.sequence_editor and scene.render.use_sequencer:
        blockers.append("Render source scenes, not a scene with an active sequencer")
    if (getattr(scene, "use_nodes", False) or getattr(scene, "compositing_node_group", None)) and scene.render.use_compositing:
        blockers.append("Compositor output requires a separately reviewed adapter")
    return {"kind": "RENDER_READINESS", "frame_range": [scene.frame_start, scene.frame_end],
            "fps": {"numerator": fps.numerator, "denominator": fps.denominator},
            "cameras": sorted(o.name for o in scene.objects if o.type == "CAMERA"),
            "camera": scene.camera.name if scene.camera else None,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
            "samples": int(scene.cycles.samples), "dependencies": external,
            "blockers": sorted(set(blockers)), "engine": "CYCLES_CPU",
            "human_acceptance": "NOT_EVALUATED", "sound": "NOT_RENDERED"}


def render(lib, spec, directory):
    options = spec["options"]
    count = validate(options)
    before = audit()
    approved, _ = readiness(lib, options["readiness_job"], spec["inputs"][0]["path"])
    require(before == approved, "STALE_READINESS", "Scene or external dependencies changed after readiness review")
    require(not before["blockers"], "RENDER_BLOCKED", "; ".join(before["blockers"]))
    scene = bpy.context.scene
    camera = scene.objects.get(options["camera"])
    require(camera is not None and camera.type == "CAMERA", "CAMERA_REQUIRED", "Observed camera is missing")
    # This isolated worker never saves its disposable scene. Suspend camera
    # markers so rendering cannot re-evaluate a different camera after frame_set.
    for marker in scene.timeline_markers:
        marker.camera = None
    scene.camera = camera
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = options["samples"]
    scene.cycles.use_adaptive_sampling = False
    scene.render.resolution_x, scene.render.resolution_y = options["width"], options["height"]
    scene.render.resolution_percentage = 100
    scene.render.use_border = False
    scene.render.use_crop_to_border = False
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    frames = []
    for index, frame in enumerate(range(options["start"], options["end"] + 1), 1):
        filename = "frame_%06d.png" % index
        output = directory / filename
        require(not output.exists(), "OUTPUT_EXISTS", "Retry through job-retry, never overwrite render evidence")
        scene.frame_set(frame)
        scene.camera = camera  # Timeline camera markers must not retarget this shot.
        scene.render.filepath = str(output)
        bpy.ops.render.render(write_still=True)
        require(output.is_file(), "RENDER_FAILED", "Blender did not write the requested frame")
        frames.append({"frame": frame, "file": filename})
    after, blockers = dependencies()
    require(after == before["dependencies"] and not blockers,
            "STALE_RENDER_DEPENDENCIES", "External inputs changed during rendering; output is not accepted")
    return {"kind": "RENDERED_FRAME_SEQUENCE", "delivery_master": False,
            "width": options["width"], "height": options["height"], "fps": before["fps"],
            "frame_count": count, "frames": frames, "camera": camera.name,
            "source_sha256": spec["inputs"][0]["sha256"], "dependencies": after,
            "engine": "CYCLES_CPU", "samples": options["samples"],
            "human_acceptance": "PENDING", "audio": "NONE"}
