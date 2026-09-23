"""Device discovery/configuration only inside isolated Blender workers.

Never save preferences; no auto backend switch or CPU fallback for a GPU request.
OptiX mode uses OptiX denoising when the source enables denoising.
"""
import bpy
from .core import require
from .render_devices import selection, require_observed

def discover():
    devices = [{"backend": "CPU", "id": "CPU", "name": "CPU (2 threads)"}]
    warnings = []
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        supported = {entry[0] for entry in prefs.get_device_types(bpy.context)}
        if "OPTIX" in supported:
            observed = prefs.get_devices_for_type("OPTIX")
            devices.extend({"backend": "OPTIX", "id": d.id, "name": d.name}
                           for d in observed if d.type == "OPTIX")
    except Exception as exc:
        warnings.append("OptiX device detection unavailable (" + type(exc).__name__ +
                        "); CPU remains available. No render was started.")
    return sorted(devices, key=lambda d: (d["backend"], d["id"])), warnings

def configure(options, approved):
    require(bpy.app.background, "BACKGROUND_REQUIRED", "Render devices are configured only in isolated workers")
    selected = selection(options)
    require_observed(selected, approved)
    scene = bpy.context.scene
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 2
    if selected["backend"] == "CPU":
        scene.cycles.device = "CPU"
        if hasattr(scene.cycles, "denoising_use_gpu"):
            scene.cycles.denoising_use_gpu = False
        require(not scene.cycles.use_denoising or scene.cycles.denoiser != "OPTIX",
                "RENDER_DEVICE_UNAVAILABLE", "Source requests OptiX denoising; explicitly choose GPU or review source settings")
        name = "CPU (2 threads)"
    else:
        devices, _ = discover()
        require_observed(selected, {"render_devices": devices})
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        # Disable CPU/hybrid and every non-selected GPU in this unsaved process.
        for device in prefs.devices:
            device.use = device.type == "OPTIX" and device.id == selected["id"]
        active = [d for d in prefs.devices if d.use]
        require(len(active) == 1 and active[0].id == selected["id"] and active[0].type == "OPTIX",
                "RENDER_DEVICE_UNAVAILABLE", "Exact GPU could not be enabled; CPU fallback is not authorized")
        name = active[0].name
        scene.cycles.device = "GPU"
        if scene.cycles.use_denoising:
            scene.cycles.denoiser = "OPTIX"
            if hasattr(scene.cycles, "denoising_use_gpu"):
                scene.cycles.denoising_use_gpu = True
    return evidence(selected, name)

def evidence(selected, name):
    scene = bpy.context.scene
    expected = "CPU" if selected["backend"] == "CPU" else "GPU"
    require(scene.cycles.device == expected, "RENDER_DEVICE_CHANGED", "Render device changed during execution")
    if expected == "GPU":
        prefs = bpy.context.preferences.addons["cycles"].preferences
        active = [d for d in prefs.devices if d.use]
        require(prefs.compute_device_type == "OPTIX" and len(active) == 1 and
                active[0].type == "OPTIX" and active[0].id == selected["id"],
                "RENDER_DEVICE_CHANGED", "Selected GPU configuration changed")
    return {"backend": selected["backend"], "id": selected.get("id", "CPU"), "name": name,
            "cycles_device": scene.cycles.device, "cpu_threads": 2,
            "denoising": {"enabled": bool(scene.cycles.use_denoising),
                          "method": scene.cycles.denoiser if scene.cycles.use_denoising else None},
            "fallback": False, "blender_version": bpy.app.version_string,
            "evidence_scope": "Configured isolated Cycles device plus successful frame execution; not hardware utilization telemetry"}
