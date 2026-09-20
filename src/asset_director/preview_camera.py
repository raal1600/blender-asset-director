"""Explicit-camera previews inside an isolated worker; legacy requests unchanged."""
from .core import require


def validate(options):
    if "camera" in options:
        name = options["camera"]
        require(isinstance(name, str) and 0 < len(name) <= 255 and not any(c in name for c in "\r\n\0"),
                "CAMERA_REQUIRED", "Choose an observed camera name")
        require(not options.get("stage"), "INVALID_SCHEMA", "Do not combine an observed camera with temporary staging")


def render_previews(directory, options):
    from . import blender_ops
    if "camera" not in options:
        return blender_ops.render_previews(directory, options)
    import bpy
    from .render_sequence_blender import audit
    validate(options)
    scene = bpy.context.scene
    camera = scene.objects.get(options["camera"])
    require(camera is not None and camera.type == "CAMERA", "CAMERA_REQUIRED", "The requested camera is missing")
    before = audit()
    require(not before["blockers"], "RENDER_BLOCKED", "; ".join(before["blockers"]))
    original = scene.camera
    bindings = [(m, m.camera) for m in scene.timeline_markers if m.camera]
    try:
        for marker, _ in bindings:
            marker.camera = None
        scene.camera = camera
        result = blender_ops.render_previews(directory, options)
        after = audit()
        require(after["dependencies"] == before["dependencies"] and not after["blockers"],
                "STALE_RENDER_DEPENDENCIES", "Preview dependencies changed during rendering")
        require(scene.camera == camera, "CAMERA_CHANGED", "Preview did not preserve the requested camera")
    finally:
        for marker, bound in bindings:
            marker.camera = bound
        scene.camera = original
    require(scene.camera == original and all(m.camera == bound for m, bound in bindings),
            "PREVIEW_SETTINGS_NOT_RESTORED", "Camera or timeline bindings were not restored")
    return {**result, "camera": camera.name, "frames": options.get("frames", [1]),
            "scene_camera_restored": True, "timeline_camera_bindings_restored": True}
