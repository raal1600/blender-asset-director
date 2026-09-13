"""Portable camera-plan contract and projection math (no Blender import).

The host model authors creative intent as explicit values: frame checkpoints,
camera placement, an aim definition, and the normalized screen position the aim
point should occupy. This module validates that contract and provides the pure
math needed to solve it. It never invents a shot, a lens, a duration, a frame
rate, a genre or a camera name.

Execution, keyframing and authoritative projection checks live in scene_ops,
which imports Blender. Keeping the contract here lets `job-prepare` reject an
invalid plan on ordinary Python, without launching Blender or touching a file.
"""
from __future__ import annotations
import math
from .core import fields, require, text

MODES = {"create", "adapt"}
PROJECTIONS = {"PERSP"}
SENSOR_FITS = {"AUTO", "HORIZONTAL", "VERTICAL"}
ROTATION_MODES = {"QUATERNION", "XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"}
INTERPOLATION_TYPES = {"BEZIER", "LINEAR", "CONSTANT"}
EASINGS = {"AUTO", "EASE_IN", "EASE_OUT", "EASE_IN_OUT"}
HANDLE_TYPES = {"AUTO_CLAMPED", "AUTO", "VECTOR", "FREE", "ALIGNED"}
EXTRAPOLATIONS = {"CONSTANT", "LINEAR"}
EXISTING_ANIMATION = {"preserve", "clear"}
CONSTRAINT_POLICIES = {"mute", "keep"}

MAX_CHECKPOINTS = 32
MAX_SUBJECTS = 128
FRAME_LIMIT = 100000
MAGNITUDE_LIMIT = 1e6

TOP_LEVEL = {"mode", "camera", "name", "subjects", "lens_mm", "sensor_width_mm", "sensor_height_mm", "sensor_fit",
             "projection", "rotation_mode", "keyframes", "interpolation", "frame_range", "fps",
             "constraints", "existing_animation", "set_scene_camera", "dof", "roll_deg"}
KEYFRAME_FIELDS = {"frame", "aim", "position", "direction", "distance", "fit", "lens_mm",
                   "screen", "roll_deg", "dof"}
AIM_FIELDS = {"subject", "bounds", "point"}
FIT_FIELDS = {"margin"}
DOF_FIELDS = {"use_dof", "focus_object", "focus_distance"}
INTERPOLATION_FIELDS = {"type", "easing", "handle_left", "handle_right", "extrapolation"}


def triple(value, *, code="INVALID_SCHEMA", message="Provide three finite numbers", limit=MAGNITUDE_LIMIT):
    require(isinstance(value, list) and len(value) == 3
            and all(type(v) in (int, float) and math.isfinite(float(v)) and abs(float(v)) <= limit for v in value),
            code, message)
    return [float(v) for v in value]


def number(value, *, code="INVALID_SCHEMA", message="Provide a finite number", low=None, high=None):
    require(type(value) in (int, float) and math.isfinite(float(value)), code, message)
    value = float(value)
    if low is not None:
        require(value >= low, code, message)
    if high is not None:
        require(value <= high, code, message)
    return value


def screen_target(value, *, default=(0.5, 0.5)):
    """Normalized screen position of the aim point: x right, y up, 0..1 each."""
    if value is None:
        return list(default)
    require(isinstance(value, list) and len(value) == 2
            and all(type(v) in (int, float) and math.isfinite(float(v)) for v in value)
            and all(0.0 <= float(v) <= 1.0 for v in value),
            "SCREEN_TARGET_INVALID", "Screen target must be two normalized values in 0..1")
    return [float(value[0]), float(value[1])]


def validate(options) -> dict:
    """Validate a host-authored camera plan and return normalized explicit values."""
    fields(options, TOP_LEVEL, {"keyframes"})
    mode = options.get("mode", "create")
    require(mode in MODES, "INVALID_SCHEMA", "mode must be create or adapt")
    projection = options.get("projection", "PERSP")
    require(projection in PROJECTIONS, "UNSUPPORTED_PROJECTION",
            "camera-plan authors perspective cameras; use camera-fit for orthographic framing")
    sensor_fit = options.get("sensor_fit", "AUTO")
    require(sensor_fit in SENSOR_FITS, "INVALID_SCHEMA", "Unknown sensor_fit")
    rotation_mode = options.get("rotation_mode")
    require(rotation_mode is None or rotation_mode in ROTATION_MODES, "INVALID_SCHEMA", "Unknown rotation_mode")
    camera = options.get("camera")
    name = options.get("name")
    if mode == "adapt":
        require(isinstance(camera, str) and camera.strip(), "CAMERA_REQUIRED",
                "Adapting requires the observed camera object name")
        require(name is None, "INVALID_SCHEMA", "adapt edits the named camera; do not pass name")
    else:
        require(camera is None, "INVALID_SCHEMA", "create must not pass camera; it authors a new one")
        require(name is None or (isinstance(name, str) and name.strip()), "INVALID_SCHEMA", "Invalid camera name")
    subjects = options.get("subjects", [])
    require(isinstance(subjects, list) and 1 <= len(subjects) <= MAX_SUBJECTS
            and all(isinstance(s, str) and s.strip() for s in subjects)
            and len(set(subjects)) == len(subjects), "SUBJECTS_REQUIRED",
            "Provide one or more observed geometry names used for bounds and aim")
    lens = options.get("lens_mm")
    if lens is not None:
        lens = number(lens, code="LENS_REQUIRED", message="Choose an explicit lens", low=1.0, high=1000.0)
    sensor = number(options.get("sensor_width_mm", 36.0), code="INVALID_SCHEMA",
                    message="Invalid sensor width", low=1.0, high=100.0)
    sensor_height = number(options.get("sensor_height_mm", 24.0), code="INVALID_SCHEMA",
                           message="Invalid sensor height", low=1.0, high=100.0)
    roll = options.get("roll_deg")
    if roll is not None:
        roll = number(roll, code="INVALID_SCHEMA", message="Invalid roll", low=-180.0, high=180.0)
    constraints = options.get("constraints", "mute")
    require(constraints in CONSTRAINT_POLICIES, "INVALID_SCHEMA", "constraints must be mute or keep")
    existing = options.get("existing_animation", "preserve")
    require(existing in EXISTING_ANIMATION, "INVALID_SCHEMA", "existing_animation must be preserve or clear")
    set_camera = options.get("set_scene_camera", True)
    require(isinstance(set_camera, bool), "INVALID_SCHEMA", "set_scene_camera must be a boolean")
    fps = options.get("fps")
    if fps is not None:
        fps = number(fps, code="INVALID_SCHEMA", message="Invalid fps", low=1.0, high=1000.0)
    frame_range = options.get("frame_range")
    if frame_range is not None:
        require(isinstance(frame_range, list) and len(frame_range) == 2
                and all(type(f) is int for f in frame_range), "INVALID_SCHEMA", "Invalid frame range")
        start, end = frame_range
        require(-FRAME_LIMIT <= start <= end <= FRAME_LIMIT and (end - start) <= FRAME_LIMIT,
                "INVALID_TIMEBASE", "Frame range must be ordered and bounded")
        frame_range = [start, end]
    keyframes = options.get("keyframes")
    require(isinstance(keyframes, list) and 1 <= len(keyframes) <= MAX_CHECKPOINTS, "RESOURCE_LIMIT",
            "Provide one to %d explicit frame checkpoints" % MAX_CHECKPOINTS)
    normalized = []
    previous = None
    for item in keyframes:
        fields(item, KEYFRAME_FIELDS, {"frame", "aim"})
        frame = item["frame"]
        require(type(frame) is int and -FRAME_LIMIT <= frame <= FRAME_LIMIT, "INVALID_TIMEBASE",
                "Frame checkpoints must be bounded integers")
        require(previous is None or frame > previous, "INVALID_TIMEBASE", "Frame checkpoints must strictly increase")
        previous = frame
        aim = resolve_aim(item["aim"])
        has_position = "position" in item
        has_direction = "direction" in item
        require(has_position != has_direction, "PLACEMENT_REQUIRED",
                "Each checkpoint needs exactly one of position or direction")
        entry = {"frame": frame, "aim": aim, "screen": screen_target(item.get("screen"))}
        if has_position:
            entry["position"] = triple(item["position"], message="Camera position must be three finite numbers")
        else:
            direction = triple(item["direction"], message="Camera direction must be three finite numbers")
            require(math.sqrt(sum(v * v for v in direction)) > 1e-9, "DIRECTION_REQUIRED", "Zero camera direction")
            entry["direction"] = direction
            has_distance = "distance" in item
            has_fit = "fit" in item
            require(has_distance != has_fit, "PLACEMENT_REQUIRED",
                    "A direction checkpoint needs exactly one of distance or fit")
            if has_distance:
                entry["distance"] = number(item["distance"], code="INVALID_SCHEMA",
                                           message="Distance must be positive", low=1e-6, high=MAGNITUDE_LIMIT)
            else:
                fields(item["fit"], FIT_FIELDS, {"margin"})
                entry["fit"] = {"margin": number(item["fit"]["margin"], code="INVALID_SCHEMA",
                                                 message="Fit margin must satisfy 0 <= margin < 0.45",
                                                 low=0.0, high=0.4499999)}
        if "lens_mm" in item:
            entry["lens_mm"] = number(item["lens_mm"], code="LENS_REQUIRED", message="Invalid checkpoint lens",
                                      low=1.0, high=1000.0)
        if "roll_deg" in item:
            entry["roll_deg"] = number(item["roll_deg"], code="INVALID_SCHEMA", message="Invalid roll",
                                       low=-180.0, high=180.0)
        if "dof" in item:
            entry["dof"] = validate_dof(item["dof"])
        require(lens is not None or "lens_mm" in entry, "LENS_REQUIRED",
                "Choose an explicit lens, per checkpoint or for the whole plan")
        normalized.append(entry)
    return {"mode": mode, "camera": camera, "name": name, "subjects": list(subjects),
            "lens_mm": lens, "sensor_width_mm": sensor, "sensor_height_mm": sensor_height,
            "sensor_fit": sensor_fit, "projection": projection,
            "rotation_mode": rotation_mode, "keyframes": normalized,
            "interpolation": validate_interpolation(options.get("interpolation")),
            "frame_range": frame_range, "fps": fps, "constraints": constraints,
            "existing_animation": existing, "set_scene_camera": set_camera,
            "dof": validate_dof(options["dof"]) if "dof" in options else None,
            "roll_deg": roll}


def resolve_aim(value) -> dict:
    require(isinstance(value, dict), "AIM_REQUIRED", "Aim must be an object")
    fields(value, AIM_FIELDS)
    if "point" in value:
        require("subject" not in value and "bounds" not in value, "INVALID_SCHEMA",
                "Aim is either an observed subject or an explicit world point")
        return {"point": triple(value["point"], message="Aim point must be three finite numbers")}
    require(isinstance(value.get("subject"), str) and value["subject"].strip(), "AIM_REQUIRED",
            "Aim needs an observed subject name or an explicit point")
    aim = {"subject": value["subject"], "bounds": [0.5, 0.5, 0.5]}
    if "bounds" in value:
        bounds = value["bounds"]
        require(isinstance(bounds, list) and len(bounds) == 3
                and all(type(v) in (int, float) and math.isfinite(float(v)) and 0.0 <= float(v) <= 1.0
                        for v in bounds),
                "INVALID_SCHEMA", "Aim bounds fractions must be three values in 0..1")
        aim["bounds"] = [float(v) for v in bounds]
    return aim


def validate_dof(value) -> dict:
    require(isinstance(value, dict), "INVALID_SCHEMA", "dof must be an object")
    fields(value, DOF_FIELDS)
    out = {}
    if "use_dof" in value:
        require(isinstance(value["use_dof"], bool), "INVALID_SCHEMA", "use_dof must be a boolean")
        out["use_dof"] = value["use_dof"]
    if "focus_object" in value:
        target = value["focus_object"]
        if target is not None:
            require(isinstance(target, str) and target.strip(), "INVALID_SCHEMA", "focus_object must be a name")
        out["focus_object"] = target
    if "focus_distance" in value:
        out["focus_distance"] = number(value["focus_distance"], code="INVALID_SCHEMA",
                                        message="focus_distance must be positive", low=1e-6, high=MAGNITUDE_LIMIT)
    return out


def validate_interpolation(value) -> dict:
    out = {"type": "BEZIER", "easing": "AUTO", "handle_left": "AUTO_CLAMPED",
           "handle_right": "AUTO_CLAMPED", "extrapolation": "CONSTANT"}
    if value is None:
        return out
    require(isinstance(value, dict), "INVALID_SCHEMA", "interpolation must be an object")
    fields(value, INTERPOLATION_FIELDS)
    checks = (("type", INTERPOLATION_TYPES), ("easing", EASINGS), ("handle_left", HANDLE_TYPES),
              ("handle_right", HANDLE_TYPES), ("extrapolation", EXTRAPOLATIONS))
    for key, allowed in checks:
        if key in value:
            require(value[key] in allowed, "INVALID_SCHEMA", "Unknown interpolation " + key)
            out[key] = value[key]
    return out


def sensor_extents(sensor_width_mm, sensor_height_mm, sensor_fit, resolution, pixel_aspect=(1.0, 1.0)):
    """Effective sensor width/height in millimetres for the actual render format.

    This mirrors Blender's own camera framing, verified against Camera.view_frame
    on Blender 5.2.1: AUTO applies the declared sensor width to the larger image
    dimension, HORIZONTAL pins that width to the image width, and VERTICAL pins
    the declared sensor height to the image height (the other axis follows the
    aspect). Pixel aspect is included because a non-square pixel changes the
    projected field of view. A wrong rule here would silently miss every screen
    target, so the Blender fixture checks the solved framing for each fit mode.
    """
    width, height = float(resolution[0]), float(resolution[1])
    pixel_x, pixel_y = float(pixel_aspect[0]), float(pixel_aspect[1])
    require(width > 0 and height > 0 and pixel_x > 0 and pixel_y > 0, "INVALID_SCHEMA", "Invalid render format")
    sensor_w, sensor_h = float(sensor_width_mm), float(sensor_height_mm)
    effective_w = width * pixel_x
    effective_h = height * pixel_y
    if sensor_fit == "HORIZONTAL":
        return sensor_w, sensor_w * effective_h / effective_w
    if sensor_fit == "VERTICAL":
        return sensor_h * effective_w / effective_h, sensor_h
    if effective_w >= effective_h:
        return sensor_w, sensor_w * effective_h / effective_w
    return sensor_w * effective_w / effective_h, sensor_w


def half_angles(lens_mm, sensor_w_mm, sensor_h_mm):
    require(lens_mm > 0, "LENS_REQUIRED", "Lens must be positive")
    return math.atan(sensor_w_mm / (2.0 * lens_mm)), math.atan(sensor_h_mm / (2.0 * lens_mm))


def screen_angles(half_h, half_v, screen):
    """Yaw and pitch that place an on-axis aim point at a normalized screen target.

    A point on the camera axis projects to (0.5, 0.5). Yawing the camera by psi
    and pitching it by beta moves that point to
        x = 0.5 + 0.5 * tan(psi) / (cos(beta) * tan(half_h))
        y = 0.5 - 0.5 * tan(beta) / tan(half_v)
    which this inverts exactly, so the solve is deterministic rather than a search.
    """
    target_x, target_y = float(screen[0]), float(screen[1])
    beta = math.atan(-2.0 * (target_y - 0.5) * math.tan(half_v))
    psi = math.atan(2.0 * (target_x - 0.5) * math.tan(half_h) * math.cos(beta))
    return psi, beta


def project_point(point, eye, forward, right, up, half_h, half_v):
    """Pure pinhole projection matching Blender's convention (x right, y up, 0..1)."""
    delta = [point[i] - eye[i] for i in range(3)]
    depth = sum(delta[i] * forward[i] for i in range(3))
    require(depth > 1e-9, "POINT_BEHIND_CAMERA", "Subject point is not in front of the camera")
    x_c = sum(delta[i] * right[i] for i in range(3))
    y_c = sum(delta[i] * up[i] for i in range(3))
    return (0.5 + 0.5 * (x_c / depth) / math.tan(half_h),
            0.5 + 0.5 * (y_c / depth) / math.tan(half_v),
            depth)


def screen_error(achieved, target):
    """Largest normalized-axis deviation between an achieved and intended screen position."""
    return max(abs(float(achieved[0]) - float(target[0])), abs(float(achieved[1]) - float(target[1])))


def bisect_threshold(fits, low, high, *, iterations=48, growth=2.0, limit=1e9):
    """Smallest accepted value of a monotone predicate over [low, high].

    Used for the bounded distance solve so the search itself stays portable and
    testable; the caller supplies the real projection predicate.
    """
    require(callable(fits), "INVALID_SCHEMA", "Predicate must be callable")
    require(high > low > 0, "INVALID_SCHEMA", "Invalid search interval")
    for _ in range(iterations):
        if fits(high):
            break
        high *= growth
        require(high <= limit, "FIT_UNREACHABLE", "Cannot frame the subject within the bounded search")
    else:
        raise AssertionError("unreachable")
    for _ in range(iterations):
        middle = (low + high) / 2.0
        if fits(middle):
            high = middle
        else:
            low = middle
    return high
