"""Entry point for background Blender. This file is reviewed code, not asset content."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asset_director.core import DirectorError, Library, atomic_json, file_hash, require, within
from asset_director.jobs import read_job


def package_root(lib, record):
    p = Path(record["path"]).parts
    return lib.root / p[0] / p[1] if len(p) > 2 else lib.root


def stage(target):
    import bpy
    from mathutils import Vector
    points = [target.matrix_world @ b.head_local for b in target.data.bones] if target.type == "ARMATURE" else [target.matrix_world @ Vector(c) for c in target.bound_box]
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    center = (low+high)/2; h = max(.1, high.z-low.z)
    camera_data = bpy.data.cameras.new("BAD_PREVIEW_CAMERA"); camera = bpy.data.objects.new(camera_data.name, camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = center + Vector((h*1.5, -h*3, h*.4))
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z','Y').to_euler(); camera_data.lens = 50
    bpy.context.scene.camera = camera
    light_data = bpy.data.lights.new("BAD_PREVIEW_KEY", "AREA"); light_data.energy = max(200, h*h*250); light_data.shape = "DISK"; light_data.size = h*2
    light = bpy.data.objects.new(light_data.name, light_data); bpy.context.scene.collection.objects.link(light)
    light.location = center + Vector((h, -h, h*2)); light.rotation_euler = (center-light.location).to_track_quat('-Z','Y').to_euler()
    if not bpy.context.scene.world: bpy.context.scene.world = bpy.data.worlds.new("BAD_PREVIEW_WORLD")
    bpy.context.scene.world.use_nodes = True
    bg = next(n for n in bpy.context.scene.world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (.15,.15,.15,1); bg.inputs["Strength"].default_value = .5


def execute(job_path, *, live=False):
    import bpy
    from asset_director import blender_ops as ops
    from asset_director import backend
    from asset_director import scene_ops
    from asset_director.motion import quality
    job_path = Path(job_path).resolve()
    with Library(job_path.parents[2]) as lib:
        job, actual = read_job(lib, job_path.parent.name)
        require(actual == job_path, "INVALID_JOB", "Job must be inside its registered library")
        spec = job["specification"]; op = spec["operation"]; options = spec["options"]
        directory = job_path.parent
        require(not live or op == "inspect", "LIVE_MUTATION_BLOCKED", "This version executes mutations in a separate working-file process; live MCP is read-only here")
        if live:
            expected = spec["inputs"][0]["path"] if spec["inputs"] else None
            require(expected and Path(bpy.data.filepath).resolve() == Path(expected).resolve(), "TARGET_CHANGED", "The open Blender file is not the job target")
            data = ops.inspect_scene()
        else:
            require(bpy.app.background, "BACKGROUND_REQUIRED", "Run this operation in an isolated background Blender process")
            bpy.context.preferences.filepaths.use_scripts_auto_execute = False
            if spec["inputs"]: ops.load_input(Path(spec["inputs"][0]["path"]))
            else: bpy.ops.wm.read_factory_settings(use_empty=True)
            files = spec["source_files"]
            if op == "inspect": data = ops.inspect_scene()
            elif op == "stage-floor":
                from asset_director.floor_stage import create
                data = create(options, job["id"])
            elif op == "scene-audit":
                data = scene_ops.scene_audit()
                data["source_file_sha256"] = spec["inputs"][0]["sha256"]
            elif op == "camera-fit": data = scene_ops.camera_fit(options, job["id"])
            elif op == "camera-plan": data = scene_ops.camera_plan(options, job["id"])
            elif op == "look-audit": data = scene_ops.look_audit()
            elif op == "light-adjust": data = scene_ops.light_adjust(options, job["id"])
            elif op == "world-adjust": data = scene_ops.world_adjust(options, job["id"])
            elif op == "look-adjust": data = scene_ops.look_adjust(options, job["id"])
            elif op == "camera-check": data = scene_ops.camera_check(options)
            elif op == "light-rig": data = scene_ops.light_rig(options, job["id"])
            elif op == "preview":
                if options.get("stage"):
                    target = bpy.context.scene.objects.get(options.get("target_object", ""))
                    require(target is not None, "TARGET_REQUIRED", "Explicit staging needs an observed target object")
                    stage(target)
                data = ops.render_previews(directory, options)
            elif op == "index":
                data = {"clips": [], "rigs": [], "unassigned_actions": [], "files_indexed": []}
                candidates = [f for f in files if Path(f["path"]).suffix.lower() in {".glb", ".gltf", ".fbx", ".bvh", ".blend"}]
                # Pick the highest fidelity self-contained interchange representation, retaining all files of that representation.
                for extension in (".glb", ".gltf", ".fbx", ".bvh", ".blend"):
                    subset = [f for f in candidates if Path(f["path"]).suffix.lower() == extension]
                    if subset: candidates = subset; break
                if not candidates and spec["inputs"]:
                    raise DirectorError("INTAKE_REQUIRED", "Register local files before per-clip indexing")
                require(candidates, "NO_ANIMATION_FILES", "No supported animation files in acquired package")
                require(len(candidates) <= 256, "RESOURCE_LIMIT", "Too many source files")
                for f in candidates:
                    report = ops.index_file(lib.verify_file(f), f, options, package_root(lib, f))
                    for key in ("clips", "rigs", "unassigned_actions"): data[key].extend(report[key])
                    data["files_indexed"].append(f["path"])
                data["blender_version"] = bpy.app.version_string
            elif op == "import":
                asset = lib.get(spec["asset_id"])
                collection = bpy.data.collections.new("BAD_" + job["id"]); bpy.context.scene.collection.children.link(collection)
                if asset.kind == "hdri":
                    p = next((lib.verify_file(f) for f in files if Path(f["path"]).suffix.lower() in {".hdr", ".exr"}), None)
                    require(p, "NO_HDRI", "Acquired asset has no HDRI")
                    world = bpy.data.worlds.new("BAD_"+job["id"]); world.use_nodes = True
                    env = world.node_tree.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(str(p))
                    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
                    world.node_tree.links.new(env.outputs["Color"], bg.inputs["Color"]); bpy.context.scene.world = world
                    data = {"world": world.name, "source": asset.id}
                elif asset.kind == "material":
                    material, maps = ops.create_material([lib.verify_file(f) for f in files])
                    material.use_fake_user = True
                    data = {"material": material.name, "maps": maps, "source": asset.id}
                else:
                    candidates = [f for f in files if Path(f["path"]).suffix.lower() in {".glb", ".gltf", ".fbx", ".obj", ".blend"}]
                    require(candidates, "NO_MODEL", "No supported mesh file")
                    f = sorted(candidates, key=lambda x: ({".glb":0,".gltf":1,".fbx":2,".obj":3,".blend":4}[Path(x["path"]).suffix.lower()],x["path"]))[0]
                    created = ops.import_file(lib.verify_file(f), package_root(lib,f), selection=options.get("selection"))
                    for obj in created:
                        for previous in list(obj.users_collection): previous.objects.unlink(obj)
                        collection.objects.link(obj); obj["bad_asset"] = asset.id; obj["bad_job"] = job["id"]
                    data = {"objects": [o.name for o in created], "source": asset.id}
            elif op == "retarget":
                target = bpy.data.objects.get(options.get("target_object", ""))
                require(target and target.type == "ARMATURE", "TARGET_REQUIRED", "Specify the target armature from an inspection report")
                f = spec.get("source_file")
                if not f:
                    primary = [x for x in files if Path(x["path"]).suffix.lower() in {".glb", ".gltf", ".fbx", ".bvh"}]
                    require(len(primary) == 1, "SOURCE_AMBIGUOUS", "Select an indexed clip, not an ambiguous archive")
                    f = primary[0]
                before_actions = set(bpy.data.actions)
                created = ops.import_file(lib.verify_file(f), package_root(lib,f))
                new_actions = set(bpy.data.actions) - before_actions
                rigs = [o for o in created if o.type == "ARMATURE"]
                selected_rigs = [o for o in rigs if o.name == options.get("source_object")]
                if not selected_rigs and len(rigs) == 1: selected_rigs = rigs
                require(len(selected_rigs) == 1, "SOURCE_AMBIGUOUS", "Cannot identify the source armature uniquely")
                source = selected_rigs[0]
                matches = [a for a in new_actions if a.name == options.get("action")]
                if not matches:
                    matches = [a for a in new_actions if re_original(a.name) == re_original(options.get("action", ""))]
                require(len(matches) == 1, "ACTION_AMBIGUOUS", "Choose the actual indexed source action")
                data = ops.retarget(source, target, matches[0], options.get("slot"), options, backend.verify(lib), job["id"])
                for o in created: bpy.data.objects.remove(o, do_unlink=True)
                for a in new_actions: bpy.data.actions.remove(a)
            elif op in {"assemble", "qa"}:
                name = options.get("target_object")
                target = bpy.data.objects.get(name) if name else None
                if not target:
                    rigs = [o for o in bpy.data.objects if o.type == "ARMATURE"]
                    require(len(rigs) == 1, "TARGET_AMBIGUOUS", "Specify target_object")
                    target = rigs[0]
                if op == "assemble": data = ops.assemble(target, options, job["id"])
                elif op == "qa":
                    report = ops.rig_report(target)
                    sampled = ops.samples_for(target, report, options.get("start", bpy.context.scene.frame_start), options.get("end", bpy.context.scene.frame_end), max_samples=361)
                    data = {"rig": report, "samples": sampled, "qa": quality(sampled, report["anatomical_height"], bpy.context.scene.render.fps/bpy.context.scene.render.fps_base)}
                    if options.get("terrain_object"):
                        data["terrain_qa"] = ops.terrain_quality(sampled,report["anatomical_height"],options["terrain_object"],options.get("sole_offsets"))
            else: raise DirectorError("UNKNOWN_OPERATION", "Unsupported operation")
            if op in {"stage-floor", "import", "retarget", "assemble", "preview", "camera-fit", "camera-plan",
                      "light-adjust", "world-adjust", "look-adjust", "light-rig"}:
                dest = directory / "result.blend"
                require(not any(Path(f["path"]).resolve() == dest for f in spec["inputs"]), "ORIGINAL_OVERWRITE", "Output must not be an original input")
                bpy.ops.wm.save_as_mainfile(filepath=str(dest), check_existing=False)
        summary = {"operation": op, "blender_version": bpy.app.version_string, "clips": len(data.get("clips", [])), "visual_acceptance": "PENDING"}
        atomic_json(directory / "result.json", {"status": "OK", "job_id": job["id"], "summary": summary, "data": data})
        return summary


def re_original(name):
    import re
    return re.sub(r"\.\d{3}$", "", name)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    if len(args) != 1: raise SystemExit("Expected one job.json argument")
    path = Path(args[0]).resolve()
    try:
        result = execute(path)
        print(__import__("json").dumps(result))
    except DirectorError as exc:
        atomic_json(path.parent/"result.json", exc.as_dict())
        print(exc.code + ": " + exc.message)
        raise SystemExit(11)
