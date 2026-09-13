"""Real Blender lighting/look-development regression.

Synthetic scenes with unrelated object, light and world names, several light
types, varied engines, aspects and exposure values. This is technical evidence
for contract behaviour and preservation invariants - not artistic judgement.
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
LIBRARY = OUT / "look-library"
CHECKS = []


def require(condition, name, **detail):
    if not condition:
        raise AssertionError(name + ": " + json.dumps(detail, default=str))
    CHECKS.append({"check": name, **detail})


def rejection(callable_, name, expected, **kw):
    try:
        callable_()
    except DirectorError as exc:
        require(exc.code == expected, name, expected=expected, code=exc.code)
        return
    raise AssertionError(name + ": expected " + expected + " but the call succeeded")


def scene_with_lights(names_types, resolution=(1600, 900), engine="CYCLES", exposure=0.0, fps=30):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.engine = engine
    scene.render.fps, scene.render.fps_base = fps, 1.0
    scene.view_settings.exposure = exposure
    created = []
    for name, kind in names_types:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        created.append(obj)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    prop = bpy.context.object
    prop.name = "unrelated prop"
    return scene, created, prop


def simple_world(name="plain sky world", strength=0.5, color=(0.2, 0.2, 0.2)):
    world = bpy.data.worlds.new(name)
    world.use_nodes = True
    node = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    node.inputs["Color"].default_value = (color[0], color[1], color[2], 1.0)
    node.inputs["Strength"].default_value = strength
    bpy.context.scene.world = world
    return world


def raster_engine():
    """A valid non-Cycles engine for this Blender version (the identifier changed in 5.x)."""
    identifiers = [item.identifier for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
        if candidate in identifiers:
            return candidate
    return "CYCLES"


def complex_world(name="gradient sky world"):
    world = bpy.data.worlds.new(name)
    world.use_nodes = True
    sky = world.node_tree.nodes.new("ShaderNodeTexSky")
    node = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    # A direct link keeps this valid across versions; the extra unconnected node
    # keeps the graph visibly non-trivial for the "do not rewrite it" assertions.
    world.node_tree.nodes.new("ShaderNodeMix")
    world.node_tree.links.new(sky.outputs["Color"], node.inputs["Color"])
    bpy.context.scene.world = world
    return world


def run_job(operation, source, options):
    with Library(LIBRARY) as lib:
        job = jobs.prepare(lib, operation, str(source), options=options)
        directory = lib.root / "jobs" / job["id"]
        execute(directory / "job.json")
        report = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    return job["id"], directory, report["data"]


def reload_result(directory):
    bpy.ops.wm.open_mainfile(filepath=str(directory / "result.blend"), load_ui=False, use_scripts=False)
    return bpy.context.scene


def snapshot_of(loaded_scene):
    return scene_ops.look_state()


def case_adapt_lights():
    """Adapt existing lights across unrelated names, types, engines and aspects."""
    cases = [("key light rig", [("key light rig", "POINT"), ("broad fill 02", "AREA")], (1600, 900), "CYCLES"),
             ("sun rig", [("sun rig", "SUN"), ("practical spot", "SPOT")], (900, 1600), raster_engine())]
    for label, lights, resolution, engine in cases:
        scene, created, _ = scene_with_lights(lights, resolution=resolution, engine=engine)
        simple_world()
        source = OUT / (label.replace(" ", "_") + "_source.blend")
        bpy.ops.wm.save_as_mainfile(filepath=str(source))
        baseline = file_hash(source)
        request = {"lights": []}
        if any(kind == "POINT" for _, kind in lights):
            request["lights"].append({"name": "key light rig", "energy": 250.0, "color": [1.0, 0.8, 0.6],
                                      "location": [2.0, -3.0, 4.0], "shadow_soft_size": 0.35})
            request["lights"].append({"name": "broad fill 02", "energy": 40.0, "size": 2.5,
                                      "rotation_euler_deg": [10.0, 0.0, 45.0]})
        else:
            request["lights"].append({"name": "sun rig", "angle_deg": 3.0, "use_shadow": False,
                                      "energy": 3.5})
            request["lights"].append({"name": "practical spot", "spot_size_deg": 30.0, "spot_blend": 0.5,
                                      "energy": 120.0})
        _, directory, data = run_job("light-adjust", source, request)
        requested = {(entry["name"], key) for entry in request["lights"] for key in entry if key != "name"}
        differences = {(item["light"], item["property"]) for item in data["differences"]}
        require(differences == requested, "adapt_lights_changed_only_requested", case=label,
                changed=sorted(differences), requested=sorted(requested))
        require(data["unrelated_lights_unchanged"] and data["materials_unchanged"],
                "adapt_lights_isolation", case=label)
        require(data["classification"] == "ADAPT", "adapt_lights_classification", case=label)
        require("before_snapshot" in data and "after_snapshot" in data, "adapt_lights_snapshot", case=label)
        for item in data["applied"]:
            measured = item["applied"]
            want = item["requested"]
            if isinstance(want, list):
                ok = all(abs(float(measured[i]) - float(want[i])) <= 1e-3 for i in range(3))
            elif isinstance(want, float):
                ok = abs(float(measured) - float(want)) <= max(1e-3, abs(float(want)) * 1e-6)
            else:
                ok = measured == want
            require(ok, "adapt_lights_value_applied", case=label, property=item["property"],
                    requested=want, applied=measured)
        require(data["before_snapshot"]["lights"] != data["after_snapshot"]["lights"],
                "adapt_lights_snapshot_differs", case=label)
        require(data["before_snapshot"]["materials"] == data["after_snapshot"]["materials"]
                and data["before_snapshot"]["engine"] == data["after_snapshot"]["engine"],
                "adapt_lights_engine_and_materials_stable", case=label)
        require(file_hash(source) == baseline, "adapt_lights_source_preserved", case=label)
        reload_result(directory)
        reloaded = scene_ops.light_state(bpy.data.objects[request["lights"][0]["name"]])
        first = request["lights"][0]
        key = next(k for k in first if k != "name")
        require(reloaded.get(key) is not None, "adapt_lights_persisted_in_saved_file", case=label, key=key)


def case_additive_light():
    """The existing additive capability reports CREATE evidence and its inventory."""
    scene, created, prop = scene_with_lights([("existing practical", "POINT")], engine="CYCLES")
    simple_world()
    source = OUT / "additive_source.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    _, _, data = run_job("light-rig", source, {
        "subjects": ["unrelated prop"],
        "lights": [{"type": "AREA", "energy": 55.0, "offset": [1.0, -1.0, 1.0], "color": [1.0, 0.9, 0.8],
                    "size_ratio": 1.5}]})
    require(data["classification"] == "CREATE" and len(data["created_lights"]) == 1, "additive_light_created")
    names = {light["name"] for light in data["lights_after"]}
    require("existing practical" in names and all(name in names for name in data["created_lights"]),
            "additive_light_inventory", names=sorted(names))
    require(data["existing_lights_preserved"] and data["existing_world_preserved"],
            "additive_light_preserves_existing")


def case_rejections():
    """Unsupported combinations fail loudly instead of being silently ignored."""
    scene, created, _ = scene_with_lights([("sun rig", "SUN"), ("area rig", "AREA"), ("point rig", "POINT")])
    simple_world()
    rejection(lambda: scene_ops.light_adjust({"lights": [{"name": "sun rig", "size": 2.0}]}, "fixture"),
              "reject_size_on_sun", "LIGHT_PROPERTY_UNSUPPORTED")
    rejection(lambda: scene_ops.light_adjust({"lights": [{"name": "area rig", "angle_deg": 2.0}]}, "fixture"),
              "reject_angle_on_area", "LIGHT_PROPERTY_UNSUPPORTED")
    rejection(lambda: scene_ops.light_adjust({"lights": [{"name": "point rig", "spot_size_deg": 20.0}]}, "fixture"),
              "reject_spot_size_on_point", "LIGHT_PROPERTY_UNSUPPORTED")
    rejection(lambda: scene_ops.light_adjust({"lights": [{"name": "point rig", "temperature": 4000.0}]}, "fixture"),
              "reject_temperature_without_flag", "LIGHT_PROPERTY_UNSUPPORTED")
    rejection(lambda: scene_ops.light_adjust({"lights": [{"name": "area rig", "size_y": 1.0}]}, "fixture"),
              "reject_size_y_on_square_area", "LIGHT_PROPERTY_UNSUPPORTED")
    rejection(lambda: scene_ops.light_adjust({"lights": [{"name": "missing lamp", "energy": 1.0}]}, "fixture"),
              "reject_unknown_light", "LIGHT_NOT_FOUND")
    created[0].rotation_mode = "QUATERNION"
    rejection(lambda: scene_ops.light_adjust({"lights": [{"name": "sun rig", "rotation_euler_deg": [1, 2, 3]}]},
                                             "fixture"),
              "reject_euler_on_quaternion_light", "LIGHT_ROTATION_MODE")
    require(scene_ops.light_state(bpy.data.objects["sun rig"])["energy"] == 10.0,
            "rejections_left_light_untouched")


def case_look_adjust():
    """Exposure, gamma and colour-management edits with runtime value validation."""
    scene, created, _ = scene_with_lights([("practical one", "POINT")], engine="CYCLES", exposure=-0.25)
    simple_world()
    availability = scene_ops.look_settings_state(scene)[1]
    source = OUT / "look_source.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    _, directory, data = run_job("look-adjust", source, {"exposure": 0.45, "gamma": 1.05})
    require(abs(data["color_management_after"]["exposure"] - 0.45) <= 1e-5
            and abs(data["color_management_after"]["gamma"] - 1.05) <= 1e-5,
            "look_adjust_applied", after=data["color_management_after"])
    require(data["materials_unchanged"] and data["lights_unchanged"] and data["world_unchanged"],
            "look_adjust_isolation")
    require(data["color_management_before"]["exposure"] == -0.25, "look_adjust_snapshot_before",
            exposure=data["color_management_before"]["exposure"])
    rejection(lambda: scene_ops.look_adjust({"view_transform": "NotARealTransform"}, "fixture"),
              "reject_invalid_view_transform", "LOOK_VALUE_REJECTED")
    rejection(lambda: scene_ops.look_adjust({"exposure": 500.0}, "fixture"), "reject_out_of_range_exposure",
              "INVALID_SCHEMA")
    # Discover a valid alternative transform from the running Blender instead of assuming one.
    # The job reloaded the source file, so re-acquire the live scene.
    view = bpy.context.scene.view_settings
    original = view.view_transform
    chosen = None
    for candidate in ("Standard", "Filmic", "AgX", "Khronos PBR Neutral", "Raw"):
        try:
            view.view_transform = candidate
        except (TypeError, ValueError):
            continue
        if view.view_transform == candidate and candidate != original:
            chosen = candidate
            view.view_transform = original
            break
    if chosen:
        _, _, transform_data = run_job("look-adjust", source, {"view_transform": chosen})
        require(transform_data["color_management_after"]["view_transform"] == chosen,
                "look_adjust_view_transform_applied", chosen=chosen)
    else:
        require(True, "look_adjust_view_transform_skipped_no_alternative",
                note="this Blender exposes a single view transform")
    if all(availability.get(field) for field in ("use_white_balance", "white_balance_temperature",
                                                  "white_balance_tint")):
        _, _, wb = run_job("look-adjust", source,
                           {"use_white_balance": True, "white_balance_temperature": 5200.0,
                            "white_balance_tint": 8.0})
        after = wb["color_management_after"]
        require(after["use_white_balance"] is True and abs(after["white_balance_temperature"] - 5200.0) <= 1e-3
                and abs(after["white_balance_tint"] - 8.0) <= 1e-3, "look_adjust_white_balance", after=after)
    else:
        require(True, "look_adjust_white_balance_unavailable", note="not exposed by this Blender")


def case_world_adjust():
    """Safe world edits, graded refusal for linked inputs, and no graph rewriting."""
    scene, created, _ = scene_with_lights([("practical one", "POINT")])
    world = simple_world(strength=0.5, color=(0.2, 0.2, 0.2))
    source = OUT / "world_source.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    _, directory, data = run_job("world-adjust", source, {"strength": 0.35, "color": [0.6, 0.4, 0.25]})
    after = data["world_after"]
    require(abs(after["background_strength"] - 0.35) <= 1e-5, "world_strength_applied", after=after)
    require(all(abs(after["background_color"][i] - [0.6, 0.4, 0.25][i]) <= 1e-5 for i in range(3)),
            "world_color_applied", after=after)
    require(data["lights_unchanged"] and data["materials_unchanged"], "world_adjust_isolation")
    require(data["before_snapshot"]["world"] != data["after_snapshot"]["world"], "world_snapshot_differs")
    # A linked Background color must be refused with the graph left intact.
    complex_source = OUT / "world_complex_source.blend"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene, created, prop = scene_with_lights([("practical one", "POINT")])
    complex_world()
    before_types = sorted(n.type for n in scene.world.node_tree.nodes)
    bpy.ops.wm.save_as_mainfile(filepath=str(complex_source))
    rejection(lambda: scene_ops.world_adjust({"color": [1.0, 1.0, 1.0]}, "fixture"),
              "reject_linked_world_color", "WORLD_COLOR_LINKED")
    require(sorted(n.type for n in scene.world.node_tree.nodes) == before_types,
            "linked_world_graph_intact", before=before_types,
            after=sorted(n.type for n in scene.world.node_tree.nodes))
    _, _, strength_data = run_job("world-adjust", complex_source, {"strength": 0.7})
    require(abs(strength_data["world_after"]["background_strength"] - 0.7) <= 1e-5,
            "linked_world_strength_still_allowed", after=strength_data["world_after"])
    require(strength_data["world_after"]["color_linked"] is True,
            "linked_world_color_still_linked_after_strength_edit")
    # Two Background nodes cannot be edited deterministically.
    two_source = OUT / "world_two_backgrounds_source.blend"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene, created, prop = scene_with_lights([("practical one", "POINT")])
    double = bpy.data.worlds.new("double world")
    double.use_nodes = True
    double.node_tree.nodes.new("ShaderNodeBackground")
    scene.world = double
    bpy.ops.wm.save_as_mainfile(filepath=str(two_source))
    rejection(lambda: scene_ops.world_adjust({"strength": 0.5}, "fixture"),
              "reject_ambiguous_world_graph", "WORLD_GRAPH_UNSUPPORTED")
    # Plain (non-node) world colour: only reachable where the running Blender lets
    # use_nodes be disabled. Blender 5.x always keeps world nodes, so this branch is
    # reported rather than asserted when it is unavailable.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene, created, prop = scene_with_lights([("practical one", "POINT")])
    plain = bpy.data.worlds.new("plain colour world")
    plain.use_nodes = False
    plain.color = (0.1, 0.1, 0.1)
    scene.world = plain
    if bool(getattr(plain, "use_nodes", True)):
        require(True, "world_color_path_not_reachable_this_version",
                note="this Blender always uses world nodes; the plain colour path is covered where it exists")
    else:
        plain_source = OUT / "world_color_source.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(plain_source))
        _, _, plain_data = run_job("world-adjust", plain_source, {"color": [0.3, 0.35, 0.4]})
        require(plain_data["world_after"]["mode"] == "world_color", "world_color_mode",
                after=plain_data["world_after"])
        require(all(abs(plain_data["world_after"]["color"][i] - [0.3, 0.35, 0.4][i]) <= 1e-5 for i in range(3)),
                "world_color_applied_on_plain_world", after=plain_data["world_after"])
        rejection(lambda: scene_ops.world_adjust({"strength": 0.5}, "fixture"),
                  "reject_strength_without_node_background", "WORLD_STRENGTH_UNSUPPORTED")
    _ = directory


def case_look_audit_evidence():
    """The read-only audit reports what exists and what is safely editable."""
    scene, created, prop = scene_with_lights([("audit point", "POINT"), ("audit area", "AREA")])
    simple_world()
    source = OUT / "audit_source.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    _, _, data = run_job("look-audit", source, {})
    state = data["state"]
    require(set(state["lights"][0]) >= {"name", "type", "energy", "color", "hide_render", "use_shadow"},
            "look_audit_light_properties", properties=sorted(state["lights"][0]))
    require(state["world"]["mode"] == "background_node" and "strength" in state["world"]["supported_edits"],
            "look_audit_world_supported_edits", world=state["world"])
    require("exposure" in state["color_management"] and "view_transform" in state["color_management"],
            "look_audit_color_management")
    require(isinstance(state["materials"]["count"], int) and data["materials_are_read_only"],
            "look_audit_materials_read_only")
    require(data["editable"]["lights"] == ["audit area", "audit point"], "look_audit_editable_lights",
            editable=data["editable"]["lights"])
    require(data["visual_acceptance"] == "PENDING", "look_audit_visual_pending")


def case_preview_restoration_after_look():
    """Look-development previews must still restore production render settings."""
    scene, created, prop = scene_with_lights([("preview practical", "POINT")], resolution=(1280, 720), engine="CYCLES")
    simple_world()
    camera_data = bpy.data.cameras.new("fixture camera")
    camera = bpy.data.objects.new("fixture camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0.0, -6.0, 1.5)
    camera.rotation_euler = (math.radians(80.0), 0.0, 0.0)
    scene.camera = camera
    scene.render.resolution_percentage = 65
    scene.cycles.samples = 23
    scene.render.image_settings.file_format = "JPEG"
    scene.render.filepath = "//delivery/look_"
    scene.frame_set(7)
    source = OUT / "look_preview_source.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    _, look_dir, _ = run_job("look-adjust", source, {"exposure": 0.3})
    look_result = look_dir / "result.blend"
    _, preview_dir, preview = run_job("preview", look_result, {"frames": [3], "width": 128, "height": 96,
                                                              "samples": 1})
    require(preview["production_settings_restored"] and preview["delivery_master"] is False,
            "look_preview_settings_restored_flag")
    require(preview["production_settings"]["resolution"] == [1280, 720]
            and preview["production_settings"]["samples"] == 23
            and preview["production_settings"]["resolution_percentage"] == 65,
            "look_preview_records_production_settings", recorded=preview["production_settings"])
    reload_result(preview_dir)
    scene = bpy.context.scene
    require([scene.render.resolution_x, scene.render.resolution_y] == [1280, 720]
            and scene.render.resolution_percentage == 65 and scene.cycles.samples == 23
            and scene.render.image_settings.file_format == "JPEG",
            "look_preview_saved_settings_are_production",
            resolution=[scene.render.resolution_x, scene.render.resolution_y],
            percentage=scene.render.resolution_percentage, samples=scene.cycles.samples)
    require((preview_dir / "preview_0003.png").stat().st_size > 0, "look_preview_image_written")


def main():
    case_adapt_lights()
    case_additive_light()
    case_rejections()
    case_look_adjust()
    case_world_adjust()
    case_look_audit_evidence()
    case_preview_restoration_after_look()
    report = {"status": "PASS", "blender_version": bpy.app.version_string, "checks": CHECKS,
              "check_count": len(CHECKS),
              "notice": "Synthetic lighting/look fixtures with unrelated names; technical evidence only, "
                        "not artistic acceptance."}
    atomic_json(OUT / "look_report.json", report)
    print(json.dumps({"status": "PASS", "checks": len(CHECKS), "blender": bpy.app.version_string}))


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        atomic_json(OUT / "look_report.json",
                    {"status": "FAIL", "blender_version": bpy.app.version_string, "checks": CHECKS,
                     "error": type(exc).__name__ + ": " + str(exc)[:2000]})
        raise
