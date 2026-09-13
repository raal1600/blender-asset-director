"""Portable lighting/look contracts (no Blender import).

The host model decides artistic intent; this module only validates explicit
values. Anything that depends on the running Blender version - enum membership
for view transforms, looks and light shapes, the presence of light exposure or
white balance, and Blender's own hard property limits - is checked at execution
time in scene_ops, not guessed here.

There are no genre presets: no "cinematic", "sunset" or "hero" keyword path
exists, and no scene name is special-cased.
"""
from __future__ import annotations
import math
from .core import fields, require, text

LIGHT_TYPES = {"POINT", "AREA", "SUN", "SPOT"}
MAX_LIGHTS_PER_REQUEST = 32

# property -> light types it is meaningful for. Everything else is rejected by
# type instead of being silently stored and ignored by Blender.
LIGHT_PROPERTIES = {
    "energy": LIGHT_TYPES,
    "color": LIGHT_TYPES,
    "exposure": LIGHT_TYPES,
    "use_temperature": LIGHT_TYPES,
    "temperature": LIGHT_TYPES,
    "normalize": LIGHT_TYPES,
    "use_shadow": LIGHT_TYPES,
    "use_soft_falloff": LIGHT_TYPES,
    "cutoff_distance": LIGHT_TYPES,
    "size": {"AREA"},
    "size_y": {"AREA"},
    "shape": {"AREA"},
    "angle_deg": {"SUN"},
    "spot_size_deg": {"SPOT"},
    "spot_blend": {"SPOT"},
    "shadow_soft_size": {"POINT", "SPOT"},
    "location": LIGHT_TYPES,
    "rotation_euler_deg": LIGHT_TYPES,
    "rotation_quaternion": LIGHT_TYPES,
    "hide_render": LIGHT_TYPES,
}
BOOLEAN_LIGHT_PROPERTIES = {"use_temperature", "normalize", "use_shadow", "use_soft_falloff", "hide_render"}
VECTOR_LIGHT_PROPERTIES = {"color", "location", "rotation_euler_deg"}
QUATERNION_LIGHT_PROPERTY = "rotation_quaternion"

# Portable first gate; execution re-checks Blender's own hard limits when the
# running version exposes them.
LIGHT_RANGES = {"energy": (0.0, 1e6), "exposure": (-100.0, 100.0), "temperature": (100.0, 100000.0),
                "size": (0.0, 1e5), "size_y": (0.0, 1e5), "angle_deg": (0.0, 180.0),
                "spot_size_deg": (0.1, 180.0), "spot_blend": (0.0, 1.0), "shadow_soft_size": (0.0, 1e5),
                "cutoff_distance": (0.0, 1e5)}
AREA_SHAPES_REQUIRING_SIZE_Y = {"RECTANGLE", "ELLIPSE"}

WORLD_FIELDS = {"strength", "color"}
LOOK_FIELDS = {"exposure", "gamma", "view_transform", "look", "display_device", "use_white_balance",
               "white_balance_temperature", "white_balance_tint"}
LOOK_RANGES = {"exposure": (-100.0, 100.0), "gamma": (1e-3, 100.0),
               "white_balance_temperature": (100.0, 100000.0), "white_balance_tint": (-1000.0, 1000.0)}
LOOK_BOOLEAN_FIELDS = {"use_white_balance"}
LOOK_TEXT_FIELDS = {"view_transform", "look", "display_device"}


def finite(value, *, code="INVALID_SCHEMA", message="Provide a finite number", low=None, high=None):
    require(type(value) in (int, float) and math.isfinite(float(value)), code, message)
    value = float(value)
    if low is not None:
        require(value >= low, code, message)
    if high is not None:
        require(value <= high, code, message)
    return value


def vector3(value, *, code="INVALID_SCHEMA", message="Provide three finite numbers", low=None, high=None):
    require(isinstance(value, list) and len(value) == 3
            and all(type(v) in (int, float) and math.isfinite(float(v)) for v in value), code, message)
    for v in value:
        if low is not None:
            require(float(v) >= low, code, message)
        if high is not None:
            require(float(v) <= high, code, message)
    return [float(v) for v in value]


def validate_light_adjust(options) -> dict:
    """Normalize an 'adapt these observed lights' request."""
    fields(options, {"lights"}, {"lights"})
    entries = options["lights"]
    require(isinstance(entries, list) and 1 <= len(entries) <= MAX_LIGHTS_PER_REQUEST, "RESOURCE_LIMIT",
            "Provide one to %d light entries" % MAX_LIGHTS_PER_REQUEST)
    normalized = []
    seen = set()
    for entry in entries:
        require(isinstance(entry, dict), "INVALID_SCHEMA", "Each light entry must be an object")
        fields(entry, {"name"} | set(LIGHT_PROPERTIES), {"name"})
        name = text(entry["name"], 1000)
        require(name.strip(), "LIGHT_REQUIRED", "Each light entry needs an observed light name")
        require(name not in seen, "INVALID_SCHEMA", "Duplicate light entry")
        seen.add(name)
        changes = {key: value for key, value in entry.items() if key != "name"}
        require(changes, "LIGHT_CHANGE_REQUIRED", "Each light entry needs at least one property to change")
        for key, value in changes.items():
            if key in BOOLEAN_LIGHT_PROPERTIES:
                require(isinstance(value, bool), "INVALID_SCHEMA", key + " must be a boolean")
            elif key == QUATERNION_LIGHT_PROPERTY:
                require(isinstance(value, list) and len(value) == 4
                        and all(type(v) in (int, float) and math.isfinite(float(v)) for v in value),
                        "INVALID_SCHEMA", "rotation_quaternion must be four finite numbers")
                changes[key] = [float(v) for v in value]
            elif key in VECTOR_LIGHT_PROPERTIES:
                low, high = (0.0, 1.0) if key == "color" else (None, None)
                changes[key] = vector3(value, message=key + " must be three finite numbers", low=low, high=high)
            elif key == "shape":
                changes[key] = text(value, 100)
                require(changes[key].strip(), "INVALID_SCHEMA", "shape must be a nonempty name")
            else:
                low, high = LIGHT_RANGES.get(key, (None, None))
                changes[key] = finite(value, message="Invalid " + key, low=low, high=high)
        normalized.append({"name": name, "changes": changes})
    return {"lights": normalized}


def validate_world_adjust(options) -> dict:
    """Normalize bounded edits to the active world's background."""
    fields(options, WORLD_FIELDS, set())
    require(options, "INVALID_SCHEMA", "Provide at least one world setting")
    normalized = {}
    if "strength" in options:
        normalized["strength"] = finite(options["strength"], message="Invalid world strength", low=0.0, high=1e6)
    if "color" in options:
        normalized["color"] = vector3(options["color"], message="World color must be three finite numbers (RGB)",
                                      low=0.0, high=1.0)
    return normalized


def validate_look_adjust(options) -> dict:
    """Normalize explicit scene view/colour-management values."""
    fields(options, LOOK_FIELDS, set())
    require(options, "INVALID_SCHEMA", "Provide at least one look setting")
    normalized = {}
    for key, value in options.items():
        if key in LOOK_BOOLEAN_FIELDS:
            require(isinstance(value, bool), "INVALID_SCHEMA", key + " must be a boolean")
            normalized[key] = value
        elif key in LOOK_TEXT_FIELDS:
            normalized[key] = text(value, 200)
            require(normalized[key].strip(), "INVALID_SCHEMA", key + " must be a nonempty name")
        else:
            low, high = LOOK_RANGES[key]
            normalized[key] = finite(value, message="Invalid " + key, low=low, high=high)
    return normalized


def light_properties_for_type(light_type: str) -> list[str]:
    """Properties this contract considers meaningful for a Blender light type."""
    return sorted(key for key, types in LIGHT_PROPERTIES.items() if light_type in types)


def unsupported_properties(light_type: str, keys) -> list[str]:
    return sorted(key for key in keys if light_type not in LIGHT_PROPERTIES.get(key, set()))
