"""Blender-only implementation. Import inside Blender, never ordinary system Python."""
from __future__ import annotations
import contextlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import bpy
from mathutils import Matrix, Vector, Quaternion
from .core import DirectorError, digest, file_hash, require
from .motion import identify_roles, rig_fingerprint, mapping_plan, quality
from .acquire import gltf_dependencies
from . import motion_timing


def flatten(m): return [round(float(x), 8) for row in m for x in row]
def vector(v): return [float(x) for x in v]


def curves(action, slot=None):
    """Use slots/channel bags for layered actions; legacy fallback only when present."""
    if getattr(action, "is_action_layered", False) or (hasattr(action, "layers") and len(action.layers)):
        result = []
        for layer in action.layers:
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", []):
                    if slot is None or bag.slot_handle == slot.handle: result.extend(bag.fcurves)
        return result
    return list(getattr(action, "fcurves", []))


def assign(obj, action, slot_id=None):
    obj.animation_data_create()
    obj.animation_data.action = action
    slots = list(getattr(action, "slots", []))
    if slots:
        selected = [s for s in slots if s.identifier == slot_id] if slot_id is not None else slots
        require(len(selected) == 1, "SLOT_AMBIGUOUS", "Choose the actual owner slot for this action")
        obj.animation_data.action_slot = selected[0]
    return obj.animation_data


def action_range(action, slot=None):
    times = [float(k.co.x) for c in curves(action, slot) for k in c.keyframe_points]
    require(times, "EMPTY_ACTION", "No keyed channels in selected action/slot")
    return min(times), max(times)


def rig_report(obj):
    require(obj.type == "ARMATURE", "NOT_ARMATURE", "Target is not an armature")
    bones = [{"name": b.name, "parent": b.parent.name if b.parent else None, "rest": flatten(b.matrix_local),
              "head": vector(b.head_local), "tail": vector(b.tail_local), "deform": b.use_deform} for b in obj.data.bones]
    roles = identify_roles(bones)
    if obj.get("bad_semantic_roles") is not None:
        raw = obj["bad_semantic_roles"]
        require(isinstance(raw, str) and len(raw) <= 65536, "MAPPING_REVIEW_REQUIRED", "Invalid semantic role record")
        try: declared = json.loads(raw)
        except (ValueError, TypeError): raise DirectorError("MAPPING_REVIEW_REQUIRED", "Invalid semantic role JSON")
        from .motion import REQUIRED
        require(isinstance(declared, dict) and len(declared) <= 256 and
                all(isinstance(k,str) and isinstance(v,str) and v in obj.data.bones for k,v in declared.items()) and
                len(set(declared.values())) == len(declared), "MAPPING_REVIEW_REQUIRED", "Semantic roles must be one-to-one observed bones")
        roles = {"roles": declared, "ambiguous": {}, "missing": sorted(REQUIRED-set(declared)),
                 "evidence": "explicit host-reviewed roles; anatomy still needs validation"}
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" and m.object == obj for m in o.modifiers)]
    weighted = 0
    for mesh in meshes:
        ids = {g.index for g in mesh.vertex_groups if g.name in obj.data.bones}
        require(len(mesh.data.vertices) <= 2_000_000, "RESOURCE_LIMIT", "Mesh exceeds inspection vertex limit")
        weighted += sum(any(g.group in ids and g.weight > 1e-5 for g in v.groups) for v in mesh.data.vertices)
    r = roles["roles"]
    height = None
    if all(k in r for k in ("head", "foot_l", "foot_r")):
        head = obj.matrix_world @ obj.data.bones[r["head"]].tail_local
        feet = sum((obj.matrix_world @ obj.data.bones[r[k]].head_local for k in ("foot_l", "foot_r")), Vector()) / 2
        height = (head-feet).length
    constrained = [p.name for p in obj.pose.bones if p.constraints]
    report = {"name": obj.name, "bone_count": len(bones), "bones": bones, **roles, "skinned_vertices": weighted,
              "meshes": [o.name for o in meshes], "anatomical_height": height,
              "scale": vector(obj.matrix_world.to_scale()), "fingerprint": rig_fingerprint(bones, obj.matrix_world.to_scale()),
              "constrained_bones": constrained, "drivers": len(obj.animation_data.drivers) if obj.animation_data else 0,
              "attachments": [{"name": o.name, "parent_type": o.parent_type, "bone": o.parent_bone} for o in bpy.data.objects if o.parent == obj and o not in meshes]}
    report["readiness"] = "NEEDS_RIGGING" if not weighted else "MAPPING_REVIEW_REQUIRED" if roles["missing"] or roles["ambiguous"] or constrained else "RETARGETABLE"
    return report


@contextlib.contextmanager
def restore_context():
    scene = bpy.context.scene
    frame, sub = scene.frame_current, scene.frame_subframe
    active = bpy.context.view_layer.objects.active
    selection = list(bpy.context.selected_objects)
    try: yield
    finally:
        scene.frame_set(frame, subframe=sub)
        for o in bpy.context.selected_objects: o.select_set(False)
        for o in selection:
            if o.name in bpy.context.view_layer.objects: o.select_set(True)
        if active and active.name in bpy.context.view_layer.objects: bpy.context.view_layer.objects.active = active


def inspect_scene():
    scene = bpy.context.scene
    require(len(bpy.data.objects) <= 10000, "RESOURCE_LIMIT", "Scene exceeds bounded inspection limit")
    with restore_context():
        rigs = [rig_report(o) for o in bpy.data.objects if o.type == "ARMATURE"]
        missing = []
        for image in bpy.data.images:
            if image.source == "FILE" and not image.packed_file and image.filepath:
                if not Path(bpy.path.abspath(image.filepath)).is_file(): missing.append(image.name)
        return {"blender_version": bpy.app.version_string, "filepath": bpy.data.filepath, "is_dirty": bpy.data.is_dirty,
                "objects": [{"name": o.name, "type": o.type, "parent": o.parent.name if o.parent else None,
                             "dimensions": vector(o.dimensions), "hide_render": o.hide_render} for o in bpy.data.objects],
                "rigs": rigs, "camera": scene.camera.name if scene.camera else None,
                "engine": scene.render.engine, "fps": scene.render.fps / scene.render.fps_base,
                "resolution": [scene.render.resolution_x, scene.render.resolution_y],
                "frame_range": [scene.frame_start, scene.frame_end], "missing_images": missing,
                "actions": [{"name": a.name, "slots": [s.identifier for s in getattr(a, "slots", [])]} for a in bpy.data.actions]}


def import_file(path: Path, package_root: Path, *, selection=None, frame_fps=None):
    path = path.resolve()
    before = set(bpy.data.objects)
    extension = path.suffix.lower()
    if extension in {".glb", ".gltf"}:
        gltf_dependencies(path, package_root)
        scene = bpy.context.scene
        saved = scene.render.fps, scene.render.fps_base
        try:
            if frame_fps is not None:
                require(motion_timing.number(frame_fps, 1, 240), "INVALID_TIMING", "Invalid glTF import timebase")
                scene.render.fps = int(frame_fps); scene.render.fps_base = int(frame_fps)/frame_fps
            bpy.ops.import_scene.gltf(filepath=str(path))
        finally:
            scene.render.fps, scene.render.fps_base = saved
    elif extension == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path), automatic_bone_orientation=False, use_custom_props=False, use_image_search=False)
    elif extension == ".obj": bpy.ops.wm.obj_import(filepath=str(path))
    elif extension == ".bvh": bpy.ops.import_anim.bvh(filepath=str(path))
    elif extension == ".blend":
        require(selection and isinstance(selection, list), "SELECTION_REQUIRED", "Appending a .blend requires explicit collection names")
        with bpy.data.libraries.load(str(path), link=False) as (source, target):
            require(set(selection) <= set(source.collections), "COLLECTION_MISSING", "Requested collection not present")
            target.collections = selection
        for c in target.collections:
            if c: bpy.context.scene.collection.children.link(c)
    else: raise DirectorError("FORMAT_UNSUPPORTED", "No reviewed Blender importer for this format")
    return sorted(set(bpy.data.objects)-before, key=lambda o:o.name)


def load_input(path: Path):
    if path.suffix.lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        import_file(path, path.parent)


def clip_bindings(objects):
    """Associate each action SLOT using actual bindings, then unique bone-path evidence."""
    rigs = [o for o in objects if o.type == "ARMATURE"]
    found = []
    unassigned = []
    for action in sorted(bpy.data.actions, key=lambda a:a.name):
        slots = list(getattr(action, "slots", [])) or [None]
        for slot in slots:
            cs = curves(action, slot)
            if not cs: continue
            owners = []
            for obj in rigs:
                ad = obj.animation_data
                if not ad: continue
                if ad.action == action and (slot is None or ad.action_slot == slot): owners.append(obj)
                for track in ad.nla_tracks:
                    for strip in track.strips:
                        if strip.action == action and (slot is None or getattr(strip, "action_slot", None) == slot): owners.append(obj)
            owners = list(dict.fromkeys(owners))
            evidence = "animation/NLA slot binding"
            if not owners:
                bone_names = set()
                for c in cs:
                    match = re.match(r'pose\.bones\[("(?:[^"\\]|\\.)*")\]', c.data_path)
                    if match: bone_names.add(json.loads(match.group(1)))
                if bone_names: owners = [o for o in rigs if bone_names <= set(o.pose.bones.keys())]
                evidence = "unique bone-path compatibility (inferred owner)"
            if len(owners) == 1:
                start, end = action_range(action, slot)
                found.append((owners[0], action, slot, start, end, evidence))
            else:
                unassigned.append({"action": action.name, "slot": slot.identifier if slot else None,
                                   "reason": "ambiguous or non-skeletal owner", "candidate_owners": [o.name for o in owners]})
    return found, unassigned


def samples_for(obj, report, start, end, *, max_samples=241):
    roles = report["roles"]
    require(end > start and end-start <= 10000, "INVALID_MOTION", "Invalid/oversized motion range")
    count = min(max_samples, math.ceil(end-start)+1)
    frames = [start+(end-start)*i/(count-1) for i in range(count)]
    source_root = roles.get("root") or roles.get("hips")
    results = []
    for f in frames:
        integer = math.floor(f)
        bpy.context.scene.frame_set(integer, subframe=f-integer)
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        item = {"frame": f, "root": vector(evaluated.matrix_world @ evaluated.pose.bones[source_root].head) if source_root else vector(evaluated.matrix_world.translation)}
        for role in ("hips", "foot_l", "foot_r"):
            if role in roles: item[role] = vector(evaluated.matrix_world @ evaluated.pose.bones[roles[role]].head)
        results.append(item)
    return results


def index_file(path: Path, file_record: dict, options: dict, package_root: Path | None = None):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.suffix.lower() == ".blend": load_input(path); objects = list(bpy.data.objects)
    else: objects = import_file(path, package_root or path.parent)
    bindings, unassigned = clip_bindings(objects)
    require(len(bindings) <= options.get("max_clips", 256), "RESOURCE_LIMIT", "Clip count exceeds configured index limit")
    reports = {o.name: rig_report(o) for o in objects if o.type == "ARMATURE"}
    clips = []
    for obj, action, slot, start, end, evidence in bindings:
        if end <= start: continue
        assign(obj, action, slot.identifier if slot else None)
        for track in obj.animation_data.nla_tracks: track.mute = True
        fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
        report = reports[obj.name]
        sampled = samples_for(obj, report, start, end)
        qa = quality(sampled, report["anatomical_height"], fps) if report["anatomical_height"] else {"status": "HEIGHT_UNKNOWN", "visual_acceptance": "PENDING"}
        clips.append({"file": file_record, "action": action.name, "slot": slot.identifier if slot else None,
                      "source_object": obj.name, "ownership_evidence": evidence, "frame_start": start, "frame_end": end,
                      "fps": fps, "duration_seconds": (end-start)/fps,
                      "timebase": {"frame_coordinate_fps": fps, "native_capture_fps": None,
                                   "playback_speed": 1, "source": "observed imported action in seconds; capture rate unknown"},
                      "skeleton_fingerprint": report["fingerprint"],
                      "roles": report["roles"], "curve_count": len(curves(action, slot)), "qa": qa,
                      "sampling": "full integer frames" if end-start <= 240 else "bounded subsample", "samples": sampled})
    return {"clips": clips, "rigs": list(reports.values()), "unassigned_actions": unassigned, "version": bpy.app.version_string}


def load_backend(root: Path):
    name = "_asset_director_mwni"
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, root/"__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    # Register only the data schema. Do not install panels, handlers, drivers, or preferences.
    require(not hasattr(bpy.types.Object, "retargeting_context"), "BACKEND_CONFLICT", "A different retargeting schema is already registered")
    for cls in module.context.classes: bpy.utils.register_class(cls)
    bpy.types.Object.retargeting_context = bpy.props.PointerProperty(type=module.context.Context)
    return module


def safe_mapping(source, target, explicit=None, alignment=None):
    sr, tr = rig_report(source), rig_report(target)
    proposal = mapping_plan(sr, tr)
    pairs = explicit or proposal["pairs"]
    require(isinstance(pairs, dict) and pairs and len(set(pairs.values())) == len(pairs), "MAPPING_REVIEW_REQUIRED", "Mapping must be one-to-one")
    require(all(s in source.pose.bones and t in target.pose.bones for s,t in pairs.items()), "MAPPING_REVIEW_REQUIRED", "Unknown bone in mapping")
    require(not proposal["missing_roles"] or explicit, "MAPPING_REVIEW_REQUIRED", "Required anatomical roles missing")
    require(tr["skinned_vertices"] > 0, "NEEDS_RIGGING", "Target has no verified skinning")
    require(not any(target.pose.bones[t].constraints for t in pairs.values()) and not tr["drivers"], "MAPPING_REVIEW_REQUIRED", "Constrained/control rigs require a reviewed custom mapping path")
    require(not any(source.pose.bones[s].constraints for s in pairs) and not sr["drivers"], "SOURCE_CONSTRAINTS_UNSUPPORTED", "Bake source constraints separately before using this adapter")
    for obj in (source, target):
        scale = obj.matrix_world.to_scale()
        require(min(scale) > 0 and max(scale)/min(scale) < 1.0001, "SCALE_REVIEW_REQUIRED", "Negative/nonuniform armature scales require review")
    mismatched = []
    for s,t in pairs.items():
        a = source.matrix_world.to_3x3() @ (source.data.bones[s].tail_local - source.data.bones[s].head_local)
        b = target.matrix_world.to_3x3() @ (target.data.bones[t].tail_local - target.data.bones[t].head_local)
        if a.length > 1e-8 and b.length > 1e-8 and a.angle(b) > math.radians(25): mismatched.append([s,t])
    require(not mismatched or alignment, "ALIGNMENT_REVIEW_REQUIRED", "Rest-pose directions differ; provide reviewed target pose-basis alignment matrices")
    return pairs, sr, tr


def retarget(source, target, action, slot_id, options, backend_root: Path, job_id: str):
    require(source != target, "INVALID_TARGET", "Source and target must differ")
    pairs, sr, tr = safe_mapping(source, target, options.get("mapping"), options.get("alignment"))
    backend = load_backend(backend_root)
    if target.animation_data:
        for track in target.animation_data.nla_tracks: track.mute = True
    assign(source, action, slot_id)
    for track in source.animation_data.nla_tracks: track.mute = True
    slot = source.animation_data.action_slot if hasattr(source.animation_data, "action_slot") else None
    start, end = action_range(action, slot)
    start, end = options.get("start", start), options.get("end", end)
    require(end > start, "EMPTY_ACTION", "Invalid source range")
    sfps = options.get("source_fps", bpy.context.scene.render.fps / bpy.context.scene.render.fps_base)
    tfps = options.get("target_fps", bpy.context.scene.render.fps / bpy.context.scene.render.fps_base)
    bake = motion_timing.bake_samples(start, end, sfps, tfps)
    n, last_frame = len(bake), bake[-1][0]
    for c in curves(action, slot):
        if c.data_path in {"location", "rotation_euler", "rotation_quaternion", "scale"}:
            ys = [k.co.y for k in c.keyframe_points]
            require(not ys or max(ys)-min(ys) < 1e-6, "SOURCE_OBJECT_MOTION_REVIEW", "Source object-level animation needs explicit root conversion; choose a baked skeletal variant")
    # Quiesce target evaluation before making an alignment pose. Existing actions are kept as datablocks.
    target.animation_data_create(); original_action = target.animation_data.action
    if original_action: original_action.use_fake_user = True
    target.animation_data.action = None
    for pb in target.pose.bones: pb.matrix_basis = Matrix.Identity(4)
    alignment = options.get("alignment") or {}
    for name, values in alignment.items():
        require(name in target.pose.bones and len(values) == 16 and all(math.isfinite(v) for v in values), "INVALID_ALIGNMENT", "Invalid alignment pose")
        target.pose.bones[name].matrix_basis = Matrix([values[i:i+4] for i in range(0,16,4)])
    bpy.context.view_layer.update()
    ctx = target.retargeting_context
    ctx.is_importing = True; ctx.source = source; ctx.target = target; ctx.mappings.clear()
    for s,t in pairs.items():
        m = ctx.mappings.add(); m.source = s; m.target = t
        m.rest = backend.util.matrix_to_list(target.pose.bones[t].matrix)
        m.offset = backend.util.matrix_to_list(target.pose.bones[t].matrix_basis)
    ctx.did_setup_empty_alignment = True
    intermediate = {m.target: backend.mapping.get_intermediate_bones(ctx, m) for m in ctx.mappings}
    pose_transfer = None
    ground_contact = None
    if "pose_space" in options:
        from .pose_transfer import PoseTransfer
        require(not sr["constrained_bones"] and not tr["constrained_bones"],
                "MAPPING_REVIEW_REQUIRED", "Evaluated pose transfer requires unconstrained source and target chains")
        pose_transfer = PoseTransfer(source, target, pairs, options["pose_space"])
        if 'ground_contact' in options['pose_space']:
            from .ground_contact import GroundContact
            ground_contact = GroundContact(target, options['pose_space']['translation_bone'],
                                           options['pose_space']['ground_contact'])
    new = bpy.data.actions.new(f"BAD_{job_id}_{action.name}")
    target.animation_data.action = new
    previous_q = {}
    # Invoke the upstream matrix transfer directly. No generated driver expressions are executed.
    for output_frame, f in bake:
        bpy.context.scene.frame_set(math.floor(f), subframe=f-math.floor(f))
        matrices = {}
        if pose_transfer:
            matrices = pose_transfer.matrices()
        else:
            for m in ctx.mappings:
                sb = source.pose.bones[m.source]
                loc, rot, _ = sb.matrix_basis.decompose()
                matrices[m.target] = backend.drivers.drive_bone_mat(target.name, m.target, list(loc) + list(rot), intermediate[m.target])
        for name, mat in matrices.items():
            pb = target.pose.bones[name]
            loc, q, _ = mat.decompose()
            if name in previous_q and q.dot(previous_q[name]) < 0: q.negate()
            previous_q[name] = q.copy()
            pb.rotation_mode = 'QUATERNION'; pb.location = loc; pb.rotation_quaternion = q
            # Like upstream loc/rotation drivers, do not apply the transfer matrix's unit scale to pose.scale.
            pb.scale = (1,1,1)
            pb.keyframe_insert("location", frame=output_frame, group=name)
            pb.keyframe_insert("rotation_quaternion", frame=output_frame, group=name)
    new.use_fake_user = True
    new["bad_job"] = job_id; new["bad_source_action"] = action.name; new["bad_source_fps"] = sfps; new["bad_target_fps"] = tfps
    new["bad_target_fingerprint"] = tr["fingerprint"]
    for c in curves(new, getattr(target.animation_data, "action_slot", None)):
        for k in c.keyframe_points: k.interpolation = "LINEAR"
    if ground_contact:
        ground_contact.correct([frame for frame, _ in bake])
    bpy.context.scene.render.fps = int(tfps); bpy.context.scene.render.fps_base = int(tfps) / tfps
    bpy.context.scene.frame_start = 1; bpy.context.scene.frame_end = max(1, math.floor(last_frame))
    bpy.context.scene.frame_set(1)
    after = rig_report(target)
    require(after["fingerprint"] == tr["fingerprint"], "REST_POSE_CHANGED", "Retarget unexpectedly changed the target rest data")
    samples = samples_for(target, after, 1, last_frame, max_samples=361)
    qa = quality(samples, after["anatomical_height"], tfps)
    new["bad_in_place_horizontal"] = motion_timing.horizontal_span(samples) < .02*after["anatomical_height"]
    # A genuine idle can have stationary feet. Assert pose-key motion separately,
    # but leave locomotion semantics to the clip/quality gate rather than faking a gait.
    ranges=[max(k.co.y for k in c.keyframe_points)-min(k.co.y for k in c.keyframe_points) for c in curves(new,getattr(target.animation_data,"action_slot",None)) if c.keyframe_points]
    require(ranges and max(ranges)>1e-6,"NO_POSE_MOTION","Transfer produced no measurable pose-channel movement")
    return {"action": new.name, "slot": getattr(target.animation_data.action_slot, "identifier", None), "mapping": pairs,
            "source": sr["name"], "target": tr["name"], "target_fingerprint": tr["fingerprint"],
            "source_fingerprint": sr["fingerprint"], "frames": n, "frame_range": [1, last_frame], "fps": tfps,
            "duration_seconds": (end-start)/sfps, "source_frame_coordinate_fps": sfps,
            "performance_acceptance": "NOT_EVALUATED", "temporal_visual_review": "REQUIRED",
            "qa": qa, "samples": samples,
            "ground_contact": ground_contact.report() if ground_contact else None,
            "backend": "evaluated world-pose transfer; explicit alignment and translation anchor" if pose_transfer else "Mwni 2.4.0 direct matrix-transfer adapter; no scripted drivers", "visual_acceptance": "PENDING"}


def assemble(target, options, job_id):
    """Conservative NLA assembly. No guessed gait speed or repeating embedded root travel."""
    motion_timing.validate_assembly(options)
    clips = options["clips"]
    target.animation_data_create()
    for track in target.animation_data.nla_tracks: track.mute = True
    target.animation_data.action = None
    tfps = options.get("fps", bpy.context.scene.render.fps / bpy.context.scene.render.fps_base)
    require(1 <= tfps <= 120, "INVALID_TIMING", "Invalid sequence FPS")
    fp = rig_report(target)["fingerprint"]
    strips = []
    for idx, item in enumerate(clips):
        require(set(item) <= {"action", "slot", "start", "source_fps", "playback_speed", "blend_in", "repeat"} and {"action", "start"} <= set(item), "INVALID_SEQUENCE", "Invalid clip fields")
        action = bpy.data.actions.get(item["action"])
        require(action and action.get("bad_target_fingerprint") == fp, "INCOMPATIBLE_ACTION", "Use a validated action baked for this exact rig")
        slots = [s for s in action.slots if s.identifier == item.get("slot")] if item.get("slot") else list(action.slots)
        require(len(slots) == 1, "SLOT_AMBIGUOUS", "Specify action slot")
        start, end = action_range(action, slots[0])
        sfps = action.get("bad_target_fps", item.get("source_fps", tfps))
        require("source_fps" not in item or abs(item["source_fps"]-sfps) < 1e-6,
                "SOURCE_TIMEBASE_MISMATCH", "source_fps must match baked metadata; use playback_speed for intentional retiming")
        speed_factor = item.get("playback_speed", 1)
        scale_factor = motion_timing.strip_scale(sfps, tfps, speed_factor)
        require(1 <= sfps <= 240 and 1 <= item["start"] <= 360, "INVALID_TIMING", "Invalid timeline timing")
        track = target.animation_data.nla_tracks.new(); track.name = f"BAD_{job_id}_{idx}"
        strip = track.strips.new(action.name, int(item["start"]), action)
        if hasattr(strip, "action_slot"): strip.action_slot = slots[0]
        strip.action_frame_start = start; strip.action_frame_end = end
        repeat = item.get("repeat", 1)
        require(type(repeat) is int and 1 <= repeat <= 8, "INVALID_SEQUENCE", "Repeat must be 1..8 complete cycles")
        if repeat > 1:
            require(action.get("bad_in_place_horizontal") is True, "ROOT_REPEAT_REVIEW", "Only verified horizontally in-place actions may repeat")
        strip.scale = scale_factor; strip.repeat = repeat
        strip.extrapolation = "NOTHING"; strip.blend_type = "REPLACE"; strip.use_auto_blend = False
        strip.blend_in = min(float(item.get("blend_in", 0)), (end-start)*scale_factor / 2)
        strips.append({"action": action.name, "start": strip.frame_start, "end": strip.frame_end,
                       "blend_in": strip.blend_in, "repeat": repeat, "source_frame_coordinate_fps": sfps,
                       "source_duration_seconds": (end-start)/sfps, "playback_speed": speed_factor,
                       "duration_seconds": (strip.frame_end-strip.frame_start)/tfps})
    require(max(s["end"] for s in strips) <= 361, "RESOURCE_LIMIT", "Sequence exceeds 361 frames")
    bpy.context.scene.render.fps = int(tfps); bpy.context.scene.render.fps_base = int(tfps)/tfps
    first, last = motion_timing.retained_range(strips)
    bpy.context.scene.frame_start = first; bpy.context.scene.frame_end = last
    report = rig_report(target)
    data = samples_for(target, report, first, last, max_samples=361)
    controller = None
    speed = options.get("controller_speed")
    if speed is not None:
        require(type(speed) in (int,float) and math.isfinite(speed) and 0 <= speed <= report["anatomical_height"]*4,
                "INVALID_SPEED", "Provide a calibrated speed in scene units per second")
        # Range, not only first/last displacement: a looping root can return to its origin.
        h = report["anatomical_height"]
        span = motion_timing.horizontal_span(data)
        require(span <= .02*h, "DOUBLE_ROOT_MOTION", "Embedded horizontal root travel conflicts with a path controller")
        direction = options.get("direction")
        require(isinstance(direction,list) and len(direction)==3 and all(math.isfinite(x) for x in direction), "INVALID_DIRECTION", "Specify a finite world-space direction vector")
        direction = Vector(direction)
        require(abs(direction.z) < 1e-6 and direction.length > 1e-6, "INVALID_DIRECTION", "Use a horizontal nonzero direction; terrain controls height")
        direction.normalize()
        interval = options.get("travel_frames")
        require(isinstance(interval,list) and len(interval)==2 and first <= interval[0] < interval[1] <= last,
                "INVALID_TIMING", "travel_frames must bound the moving portion, excluding the stationary idle")
        bpy.context.scene.frame_set(1)
        world = target.matrix_world.copy(); old_parent = target.parent
        require(old_parent is None, "PARENT_REVIEW_REQUIRED", "Path controller requires an unparented armature; review the existing character hierarchy first")
        require(not any(o.parent is None and any(c.target==target for c in o.constraints if hasattr(c,'target')) for o in bpy.data.objects if o!=target),
                "ATTACHMENT_REVIEW", "Constraint-based external attachments need review before controller travel")
        controller = bpy.data.objects.new("BAD_PATH_"+job_id, None)
        bpy.context.scene.collection.objects.link(controller)
        controller["bad_job"] = job_id
        target.parent = controller; target.matrix_world = world
        ray = terrain_sampler(options.get("terrain_object")) if options.get("terrain_object") else None
        origin = world.translation.copy()
        initial_ground = ray(origin)[0] if ray else 0
        previous_z = 0
        for frame in range(1, bpy.context.scene.frame_end+1):
            seconds = (min(max(frame,interval[0]),interval[1])-interval[0])/tfps
            delta = direction*speed*seconds
            if ray:
                z, normal = ray(origin+delta)
                require(normal.z >= math.cos(math.radians(20)), "TERRAIN_TOO_STEEP", "This baseline supports only gentle terrain; foot IK is not implemented")
                delta.z = z-initial_ground
                require(abs(delta.z-previous_z) <= h*.08, "TERRAIN_DISCONTINUITY", "Terrain step is too abrupt for this controller")
                previous_z = delta.z
            controller.location = delta
            controller.keyframe_insert("location",frame=frame)
        for curve in curves(controller.animation_data.action, getattr(controller.animation_data,"action_slot",None)):
            for k in curve.keyframe_points: k.interpolation="LINEAR"
        data = samples_for(target, report, first, last, max_samples=361)
    return {"strips":strips,"frame_range":[first,last],
            "endpoint_policy":"last integer inside active strips; no padded rest-pose frame",
            "performance_acceptance":"NOT_EVALUATED", "temporal_visual_review":"REQUIRED",
            "qa":quality(data,report["anatomical_height"],tfps),"samples":data,
            "root_owner":"single external controller + in-place skeletal motion" if controller else "existing baked skeletal motion",
            "controller":controller.name if controller else None, "terrain_following":"root-height only; no foot IK" if options.get("terrain_object") else "none",
            "transition_visual_review":"PENDING"}


def terrain_sampler(name):
    from mathutils.bvhtree import BVHTree
    terrain=bpy.data.objects.get(name)
    require(terrain and terrain.type=='MESH', "TERRAIN_NOT_FOUND", "Specify the existing terrain mesh by exact name")
    evaluated=terrain.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh()
    try:
        require(len(mesh.vertices)<=2000000,"RESOURCE_LIMIT","Terrain is too dense for bounded sampling")
        vertices=[evaluated.matrix_world@v.co for v in mesh.vertices]
        require(vertices,"EMPTY_TERRAIN","Terrain is empty")
        tree=BVHTree.FromPolygons(vertices,[tuple(p.vertices) for p in mesh.polygons])
        top=max(v.z for v in vertices)+1
        depth=top-min(v.z for v in vertices)+2
    finally: evaluated.to_mesh_clear()
    def ray(point):
        hit,normal,_,_=tree.ray_cast(Vector((point.x,point.y,top)),Vector((0,0,-1)),depth)
        require(hit is not None,"OUTSIDE_TERRAIN","Character route extends beyond the terrain")
        return hit.z,normal
    return ray


def terrain_quality(samples, height, name, sole_offsets=None):
    ray=terrain_sampler(name); offsets=sole_offsets or {}; results={}
    for role in ('foot_l','foot_r'):
        require(role in offsets and type(offsets[role]) in (int,float) and math.isfinite(offsets[role]) and 0<=offsets[role]<=height*.2,
                "SOLE_CALIBRATION_REQUIRED","Actual sole-to-ankle offsets are required for terrain penetration measurements")
        clearances=[]
        for s in samples:
            if role in s:
                p=Vector(s[role]); z,_=ray(p)
                clearances.append(p.z-offsets[role]-z)
        results[role]={"minimum_clearance":min(clearances) if clearances else None,
                       "penetration_height_ratio":max(0,-min(clearances))/height if clearances else None}
    return {"contacts":results,"method":"calibrated ankle-to-sole offset against the specified evaluated terrain mesh; not full mesh collision"}


def create_material(files):
    """Texture assignment by explicit map naming. Never treat DirectX normals as OpenGL."""
    selected = {}
    for path in files:
        name = path.name.lower()
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr"}: continue
        role = None
        for pattern, key in ((r"(?:_color|_diff|_albedo)", "color"), (r"(?:_roughness|_rough)", "roughness"), (r"(?:_normalgl|_nor_gl)", "normal"), (r"(?:_metalness|_metallic|_metal)", "metallic")):
            if re.search(pattern, name): role = key; break
        if role and role not in selected: selected[role] = path
    require("color" in selected, "MATERIAL_MAPS_REVIEW", "Cannot identify an explicit color map")
    mat = bpy.data.materials.new("BAD_" + selected["color"].stem); mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    for role, path in selected.items():
        node = mat.node_tree.nodes.new("ShaderNodeTexImage"); node.image = bpy.data.images.load(str(path), check_existing=True)
        node.image.colorspace_settings.name = "sRGB" if role == "color" else "Non-Color"
        if role == "normal":
            normal = mat.node_tree.nodes.new("ShaderNodeNormalMap")
            mat.node_tree.links.new(node.outputs["Color"], normal.inputs["Color"])
            mat.node_tree.links.new(normal.outputs["Normal"], bsdf.inputs["Normal"])
        else: mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs[{"color":"Base Color", "roughness":"Roughness", "metallic":"Metallic"}[role]])
    return mat, {k: v.name for k,v in selected.items()}


def render_settings_snapshot(scene):
    """Every production render setting a preview temporarily overrides."""
    render = scene.render
    cycles = getattr(scene, "cycles", None)
    return {"engine": render.engine, "resolution_x": render.resolution_x, "resolution_y": render.resolution_y,
            "resolution_percentage": render.resolution_percentage, "filepath": render.filepath,
            "file_format": render.image_settings.file_format, "threads_mode": render.threads_mode,
            "threads": render.threads, "frame": scene.frame_current, "subframe": scene.frame_subframe,
            "cycles_device": getattr(cycles, "device", None), "cycles_samples": getattr(cycles, "samples", None)}


def apply_render_settings(scene, values):
    render = scene.render
    cycles = getattr(scene, "cycles", None)
    render.engine = values["engine"]
    render.resolution_x = values["resolution_x"]
    render.resolution_y = values["resolution_y"]
    render.resolution_percentage = values["resolution_percentage"]
    render.filepath = values["filepath"]
    render.image_settings.file_format = values["file_format"]
    render.threads_mode = values["threads_mode"]
    render.threads = values["threads"]
    if cycles is not None and values["cycles_samples"] is not None:
        cycles.samples = values["cycles_samples"]
    if cycles is not None and values["cycles_device"] is not None:
        cycles.device = values["cycles_device"]
    scene.frame_set(values["frame"], subframe=values["subframe"])


@contextlib.contextmanager
def preserved_render_settings(scene):
    """Run bounded preview overrides and always restore the project's own settings.

    A preview is an isolated artifact, not a delivery master. The worker saves a
    .blend after this operation, so leaving preview resolution/samples/engine in
    the scene would silently degrade any file a host mistook for the master.
    """
    before = render_settings_snapshot(scene)
    try:
        yield before
    finally:
        apply_render_settings(scene, before)


def render_previews(directory: Path, options):
    frames = options.get("frames", [1])
    width, height, samples = options.get("width", 320), options.get("height", 320), options.get("samples", 8)
    require(isinstance(frames, list) and 1 <= len(frames) <= 8 and all(type(f) is int and 0 <= f <= 10000 for f in frames), "RESOURCE_LIMIT", "At most eight bounded preview frames")
    require(64 <= width <= 960 and 64 <= height <= 540 and 1 <= samples <= 32, "RESOURCE_LIMIT", "Preview size/sample limit")
    scene = bpy.context.scene
    require(scene.camera is not None, "CAMERA_REQUIRED", "Provide a camera before rendering previews")
    outputs = []
    with preserved_render_settings(scene) as production:
        scene.render.engine = "CYCLES"; scene.cycles.device = "CPU"; scene.cycles.samples = samples
        scene.render.threads_mode = "FIXED"; scene.render.threads = 2
        scene.render.resolution_x = width; scene.render.resolution_y = height; scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        for frame in frames:
            scene.frame_set(frame); path = directory / f"preview_{frame:04d}.png"
            scene.render.filepath = str(path); bpy.ops.render.render(write_still=True)
            require(path.is_file() and path.stat().st_size > 0, "RENDER_FAILED", "Preview image missing")
            outputs.append(path.name)
    restored = render_settings_snapshot(scene)
    require(restored == production, "PREVIEW_SETTINGS_NOT_RESTORED",
            "Preview overrides were not restored; refusing to report a contaminated result")
    return {"files": outputs, "engine": "CYCLES_CPU", "samples": samples, "visual_acceptance": "PENDING",
            "artifact_kind": "PREVIEW_ARTIFACT", "delivery_master": False,
            "preview_overrides": {"resolution": [width, height], "resolution_percentage": 100, "samples": samples,
                                  "engine": "CYCLES", "device": "CPU", "threads": 2, "file_format": "PNG"},
            "production_settings": {"engine": production["engine"],
                                    "resolution": [production["resolution_x"], production["resolution_y"]],
                                    "resolution_percentage": production["resolution_percentage"],
                                    "samples": production["cycles_samples"], "file_format": production["file_format"],
                                    "filepath": production["filepath"], "frame": production["frame"],
                                    "threads_mode": production["threads_mode"], "threads": production["threads"]},
            "production_settings_restored": True}
