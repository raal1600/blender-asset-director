"""Portable explicit render-device contract. CPU is the legacy default."""
from .core import fields, require

def selection(options):
    value = options.get("render_device", {"backend": "CPU"})
    fields(value, {"backend", "id"}, {"backend"})
    require(value["backend"] in ("CPU", "OPTIX"), "INVALID_SCHEMA", "Choose CPU or an observed OptiX device")
    if value["backend"] == "CPU":
        require(set(value) == {"backend"}, "INVALID_SCHEMA", "CPU selection has no GPU identity")
    else:
        identity = value.get("id")
        require(isinstance(identity, str) and 0 < len(identity) <= 512 and
                all(ord(c) >= 32 for c in identity), "INVALID_SCHEMA", "Choose an exact observed GPU identity")
    return dict(value)

def require_observed(selected, audit):
    if selected["backend"] == "CPU":
        return
    matches = [d for d in audit.get("render_devices", [])
               if d.get("backend") == selected["backend"] and d.get("id") == selected["id"]]
    require(len(matches) == 1, "RENDER_DEVICE_UNAVAILABLE",
            "Selected GPU was not observed in readiness; check devices again or explicitly choose CPU")
