"""Deterministic rig matching and numerical motion diagnostics (no inference models)."""
from __future__ import annotations
import math
import re
from .core import digest, require

ROLE_NAMES = {
    "root": {"root", "rootmotion", "armature"}, "hips": {"hips", "pelvis"},
    "spine": {"spine", "spine01", "spine1"}, "head": {"head"}, "neck": {"neck", "neck01"},
}
for side, long_side in (("l", "left"), ("r", "right")):
    for role, aliases in {"thigh": ["thigh", "upleg", "upperleg"], "calf": ["calf", "leg", "lowerleg", "shin"],
                          "foot": ["foot", "ankle"], "toe": ["toe", "toebase", "ball"],
                          "upperarm": ["upperarm", "arm"], "forearm": ["forearm", "lowerarm"],
                          "hand": ["hand", "wrist"], "shoulder": ["shoulder", "clavicle"]}.items():
        ROLE_NAMES[role + "_" + side] = {x for alias in aliases for x in (alias + side, side + alias, long_side + alias, alias + long_side)}
REQUIRED = {"hips", "spine", "head", *[r + "_" + s for r in ("thigh", "calf", "foot", "upperarm", "forearm", "hand") for s in ("l", "r")]}

def norm_bone(name: str) -> str:
    name = name.rsplit(":", 1)[-1]
    if name.startswith("DEF-"): name = name[4:]
    return re.sub("[^a-z0-9]", "", name.lower())

def identify_roles(bones: list[dict]) -> dict:
    assigned, ambiguous = {}, {}
    for role, aliases in ROLE_NAMES.items():
        matches = [b["name"] for b in bones if norm_bone(b["name"]) in aliases]
        if len(matches) == 1: assigned[role] = matches[0]
        elif matches: ambiguous[role] = sorted(matches)
    return {"roles": assigned, "ambiguous": ambiguous, "missing": sorted(REQUIRED - assigned.keys()), "evidence": "name aliases; hierarchy/geometry still require validation"}

def rig_fingerprint(bones: list[dict], object_scale=(1, 1, 1)) -> str:
    return digest({"bones": sorted([{k: b[k] for k in ("name", "parent", "rest")} for b in bones], key=lambda b: b["name"]),
                   "scale": [round(float(v), 6) for v in object_scale]})

def mapping_plan(source: dict, target: dict) -> dict:
    s, t = source["roles"], target["roles"]
    missing = sorted(REQUIRED - (set(s) & set(t)))
    pairs = {s[r]: t[r] for r in sorted(set(s) & set(t))}
    duplicate = len(set(pairs.values())) != len(pairs)
    status = "MAPPING_REVIEW_REQUIRED" if missing or duplicate or source.get("ambiguous") or target.get("ambiguous") else "RETARGETABLE"
    if not target.get("skinned_vertices", 0): status = "NEEDS_RIGGING"
    if source.get("fingerprint") == target.get("fingerprint") and status == "RETARGETABLE": status = "DIRECT_ACTION_COMPATIBLE"
    return {"status": status, "pairs": pairs, "missing_roles": missing, "requires_rest_alignment_check": True,
            "source_fingerprint": source.get("fingerprint"), "target_fingerprint": target.get("fingerprint")}

def vec_distance(a, b): return math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))

def frame_convert(frame: float, source_fps: float, target_fps: float, source_start=0, target_start=0) -> float:
    require(all(math.isfinite(v) for v in (frame, source_fps, target_fps, source_start, target_start)) and source_fps > 0 and target_fps > 0,
            "INVALID_TIMING", "Frame rates must be finite and positive")
    return target_start + (frame-source_start) * target_fps / source_fps

def quality(samples: list[dict], height: float, fps: float, *, ground_z: float | None = None, sole_offsets: dict | None = None) -> dict:
    require(0 < height < 1e7 and math.isfinite(height) and 0 < fps <= 240, "INVALID_SCALE", "Invalid anatomical height or FPS")
    require(2 <= len(samples) <= 10000, "INVALID_MOTION", "Need at least two bounded motion samples")
    times = [s["frame"] / fps for s in samples]
    require(all(b > a for a, b in zip(times, times[1:])), "INVALID_MOTION", "Frames must increase")
    series = {k: [s[k] for s in samples] for k in ("root", "hips", "foot_l", "foot_r") if all(k in s for s in samples)}
    for values in series.values():
        require(all(len(v) == 3 and all(math.isfinite(x) for x in v) for v in values), "NONFINITE_MOTION", "Invalid evaluated pose coordinate")
    roots = series.get("root")
    root_displacement = vec_distance(roots[0], roots[-1]) if roots else None
    root_jump = max((vec_distance(a, b) for a, b in zip(roots, roots[1:])), default=0) / height if roots else None
    contacts = {}
    relative_movement = []
    for role in ("foot_l", "foot_r"):
        if role not in series: continue
        values = series[role]
        minimum = min(v[2] for v in values)
        intervals, current = [], []
        for i, v in enumerate(values):
            vz = 0 if i == 0 else abs(v[2]-values[i-1][2]) / (times[i]-times[i-1])
            possible = v[2] <= minimum + 0.035*height and vz <= 0.25*height
            if possible: current.append(i)
            elif current:
                if len(current) >= 3: intervals.append(current)
                current = []
        if len(current) >= 3: intervals.append(current)
        drifts = [max(vec_distance(values[i], values[j]) for j in indices) / height for indices in intervals for i in indices[:1]]
        penetration = None
        if ground_z is not None and sole_offsets and role in sole_offsets:
            penetration = max(0, max(ground_z - (v[2] - sole_offsets[role]) for v in values)) / height
        contacts[role] = {"method": "low ankle height/vertical speed heuristic, not confirmed sole contacts", "intervals": [[samples[x[0]]["frame"], samples[x[-1]]["frame"]] for x in intervals],
                          "max_stance_drift_height_ratio": max(drifts) if drifts else None,
                          "penetration_height_ratio": penetration,
                          "status": "WARNING" if drifts and max(drifts) > .01 else "NOT_MEASURED" if not drifts else "NO_THRESHOLD_WARNING"}
        if roots:
            rel = [[x-y for x,y in zip(v,r)] for v,r in zip(values,roots)]
            relative_movement.append(max(vec_distance(rel[0], v) for v in rel) / height)
    limb_motion = max(relative_movement) if relative_movement else None
    warnings = []
    if limb_motion is None: warnings.append("LIMB_MOTION_UNKNOWN")
    elif limb_motion < .001: warnings.append("NO_NONTRIVIAL_LIMB_MOTION")
    if root_jump is not None and root_jump > .15: warnings.append("ROOT_DISCONTINUITY")
    if any(c["status"] == "WARNING" for c in contacts.values()): warnings.append("POSSIBLE_FOOT_SLIDING")
    return {"frames_measured": len(samples), "duration_seconds": times[-1] - times[0],
            "root_displacement": root_displacement, "root_max_step_height_ratio": root_jump,
            "root_motion": "UNKNOWN" if root_displacement is None else "MEASURED_TRAVEL" if root_displacement > .01*height else "LOW_DISPLACEMENT_NOT_PROOF_OF_IN_PLACE",
            "limb_relative_motion_height_ratio": limb_motion, "contacts": contacts, "warnings": warnings,
            "loop_seam_position_height_ratio": {k: vec_distance(v[0], v[-1])/height for k,v in series.items()},
            "status": "WARNINGS" if warnings else "NO_NUMERIC_WARNINGS", "visual_acceptance": "PENDING",
            "not_measured": ["artistic naturalness", "cloth penetration", "weapon grip", "sole penetration unless calibrated"]}
