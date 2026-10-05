"""Real optional-provider acceptance, separate from ordinary offline checks.

Creates clearly synthetic G1 Actions, samples them through Blender, runs the
actual pinned model, bakes candidate motion, saves/reopens and renders/exports.
This proves provider/Blender integration, not final seamless/contact quality.
"""
from pathlib import Path
import argparse
import copy
import json
import math
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from asset_director.core import DirectorError, atomic_json, digest, load_json, require


def blender_stage(stage, output):
    import bpy
    from mathutils import Quaternion, Vector
    from asset_director.motion_bricks_blender import _basis, apply_candidate, evaluated_poses, make_request
    skeleton = load_json(output / "skeleton.json"); names = skeleton["joint_names"]
    if stage == "prepare":
        bpy.ops.wm.read_factory_settings(use_empty=True)
        armature = bpy.data.armatures.new("Synthetic G1 verified rest")
        rig = bpy.data.objects.new("Synthetic G1", armature); bpy.context.collection.objects.link(rig)
        bpy.context.view_layer.objects.active = rig; rig.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT"); basis = _basis()
        for i, name in enumerate(names):
            bone = armature.edit_bones.new(name); bone.head = basis @ Vector(skeleton["neutral_joints"][i])
            bone.tail = bone.head + Vector((0, 0, .04))
            if skeleton["parents"][i] >= 0:
                bone.parent = armature.edit_bones[names[skeleton["parents"][i]]]
        bpy.ops.object.mode_set(mode="OBJECT")
        scene = bpy.context.scene; scene.render.fps = 30; scene.render.fps_base = 1
        rig.animation_data_create()
        for label, travelling in (("Synthetic idle source", False), ("Synthetic walk target", True)):
            action = bpy.data.actions.new(label); action.use_fake_user = True; rig.animation_data.action = action
            for f in range(1, 33):
                for i, name in enumerate(names):
                    pose = rig.pose.bones[name]; pose.rotation_mode = "QUATERNION"
                    pose.location = (0,0,0); pose.rotation_quaternion = (1,0,0,0); pose.scale = (1,1,1)
                    if i == 0:
                        root = Vector((0, .80, .6 + f*.014 if travelling else 0))
                        pose.location = rig.data.bones[name].matrix_local.to_3x3().inverted() @ (basis.to_3x3() @ root)
                    elif i in (1,8) and travelling:
                        pose.rotation_quaternion = Quaternion((1,0,0), .1 * math.sin(f*.2) * (1 if i==1 else -1))
                    rotation_path = "rotation_quaternion"
                    if i == 21:
                        pose.rotation_mode = "XYZ"; pose.rotation_euler = (.02*math.sin(f*.1),0,0)
                        rotation_path = "rotation_euler"
                    for field in ("location", rotation_path, "scale"):
                        pose.keyframe_insert(field, frame=f, group=name)
        source = bpy.data.actions["Synthetic idle source"]; target = bpy.data.actions["Synthetic walk target"]
        request = make_request(rig, skeleton, source, target, 29, 1, frames=40, seed=1234)
        atomic_json(output / "request.json", request)
        preserved = {a.name: digest(evaluated_poses(rig, skeleton, list(range(1,33)), a)) for a in (source, target)}
        atomic_json(output / "source-action-hashes.json", preserved)
        bpy.ops.wm.save_as_mainfile(filepath=str(output / "synthetic-source.blend"))
        return
    bpy.ops.wm.open_mainfile(filepath=str(output / ("synthetic-source.blend" if stage == "bake" else "provider-candidate.blend")))
    rig = bpy.data.objects["Synthetic G1"]
    request = load_json(output / "request.json"); result = load_json(output / "result.json")
    if stage == "bake":
        action = apply_candidate(rig, request, result, name="MotionBricks real generated candidate")
    else:
        action = bpy.data.actions["MotionBricks real generated candidate"]
    poses = evaluated_poses(rig, skeleton, list(range(1, result["frames"]+1)), action)
    root_error = max(math.dist(a,b) for a,b in zip(poses["roots"], result["roots"]))
    angle_error = 0.
    for actual_frame, expected_frame in zip(poses["local_xyzw"], result["local_xyzw"]):
        for actual, expected in zip(actual_frame, expected_frame):
            dot = abs(sum(a*b for a,b in zip(actual,expected))) / math.sqrt(sum(v*v for v in actual)*sum(v*v for v in expected))
            angle_error = max(angle_error, math.degrees(2*math.acos(min(1., dot))))
    preserved = load_json(output / "source-action-hashes.json")
    for name, expected in preserved.items():
        require(digest(evaluated_poses(rig, skeleton, list(range(1,33)), bpy.data.actions[name])) == expected,
                "FIXTURE_SOURCE_CHANGED", f"Source Action changed: {name}")
    metrics = {"stage": stage, "root_error_m": root_error, "local_rotation_error_degrees": angle_error,
               "frames": result["frames"], "source_actions_preserved": True, "request_hash": result["request_hash"]}
    atomic_json(output / (stage + "-metrics.json"), metrics)
    require(root_error <= 1e-5 and angle_error <= .05, "FIXTURE_POSE_PARITY", str(metrics))
    scene = bpy.context.scene; scene.frame_start=1; scene.frame_end=result["frames"]
    if stage == "bake":
        # One simple rigidly skinned octahedron per joint; generated fixture only.
        verts, faces, groups = [], [], []
        for i, position in enumerate(skeleton["neutral_joints"]):
            head = _basis() @ Vector(position); first=len(verts)
            for offset in ((.025,0,0),(-.025,0,0),(0,.025,0),(0,-.025,0),(0,0,.025),(0,0,-.025)):
                verts.append(tuple(head+Vector(offset))); groups.append(i)
            faces.extend(tuple(first+j for j in face) for face in ((0,2,4),(2,1,4),(1,3,4),(3,0,4),(2,0,5),(1,2,5),(3,1,5),(0,3,5)))
        # Skin every limb edge to its parent joint, preserving model FK geometry.
        for i,parent in enumerate(skeleton["parents"]):
            if parent < 0: continue
            start=_basis() @ Vector(skeleton["neutral_joints"][parent])
            end=_basis() @ Vector(skeleton["neutral_joints"][i]); direction=end-start
            if direction.length < 1e-6: continue
            direction.normalize(); axis=Vector((0,0,1)) if abs(direction.z)<.9 else Vector((1,0,0))
            u=direction.cross(axis).normalized();v=direction.cross(u).normalized();first=len(verts)
            for point in (start,end):
                for k in range(8):
                    verts.append(tuple(point+.012*(u*math.cos(k*math.tau/8)+v*math.sin(k*math.tau/8))))
                    groups.append(parent)
            for k in range(8):faces.append((first+k,first+(k+1)%8,first+8+(k+1)%8,first+8+k))
        mesh=bpy.data.meshes.new("Synthetic markers mesh");mesh.from_pydata(verts,[],faces)
        skin=bpy.data.objects.new("Synthetic G1 skinned markers",mesh);bpy.context.collection.objects.link(skin)
        for i,name in enumerate(names):
            group=skin.vertex_groups.new(name=name);group.add([j for j,v in enumerate(groups) if v==i],1,"REPLACE")
        modifier=skin.modifiers.new("Exact G1 skin","ARMATURE");modifier.object=rig;skin.parent=rig
        bpy.ops.object.camera_add(location=(2.8,-3.0,1.6)); camera=bpy.context.object
        camera.rotation_euler=(Vector((0,-.35,.65))-camera.location).to_track_quat('-Z','Y').to_euler();scene.camera=camera
        scene.render.engine="BLENDER_WORKBENCH";scene.render.resolution_x=640;scene.render.resolution_y=480
        scene.render.resolution_percentage=100;scene.render.image_settings.file_format="PNG"
        scene.display.shading.light="STUDIO";scene.display.shading.color_type="SINGLE";scene.display.shading.single_color=(.2,.65,.95)
        scene.display.shading.background_type="WORLD";scene.world=bpy.data.worlds.new("Fixture world");scene.world.color=(.03,.04,.06)
        bpy.ops.wm.save_as_mainfile(filepath=str(output / "provider-candidate.blend"))
        args={"filepath":str(output/"provider-candidate.glb"),"export_format":"GLB","export_animations":True}
        if "export_animation_mode" in bpy.ops.export_scene.gltf.get_rna_type().properties.keys(): args["export_animation_mode"]="SCENE"
        bpy.ops.export_scene.gltf(**args)
    else:
        for frame in (1,2,3,4,result["frames"]-3,result["frames"]-2,result["frames"]-1,result["frames"]):
            scene.frame_set(frame);scene.render.filepath=str(output/f"candidate-frame-{frame:03d}.png")
            bpy.ops.render.render(write_still=True)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",type=Path);p.add_argument("--blender",type=Path)
    p.add_argument("--output",type=Path,required=True);p.add_argument("--stage",choices=("prepare","bake","reopen"))
    a=p.parse_args(argv);output=a.output.resolve();output.mkdir(parents=True,exist_ok=True)
    if a.stage:
        blender_stage(a.stage,output);return 0
    from asset_director.motion_bricks_provider import execute
    config=load_json(a.config);discovery=execute(config);atomic_json(output/"skeleton.json",discovery["skeleton"])
    def stage(name):
        command=[str(a.blender),"--background","--factory-startup","--python",str(Path(__file__).resolve()),"--",
                 "--output",str(output),"--stage",name]
        r=subprocess.run(command,capture_output=True,text=True,timeout=180,
                         creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        (output/(name+".log")).write_text(r.stdout+"\n"+r.stderr,encoding="utf-8")
        require(r.returncode==0 and "Traceback (most recent call last)" not in r.stdout+r.stderr,
                "FIXTURE_BLENDER_FAILED",f"Blender {name} failed; inspect {output/(name+'.log')}")
    stage("prepare");request=load_json(output/"request.json")
    result=execute(config,request);atomic_json(output/"result.json",result)
    repeated=execute(config,request);atomic_json(output/"repeated-result.json",repeated)
    require(result["roots"]==repeated["roots"] and result["local_xyzw"]==repeated["local_xyzw"],
            "FIXTURE_NONDETERMINISTIC","Same backend/seed did not reproduce")
    altered=copy.deepcopy(request)
    for root in altered["target"]["roots"]:root[2]+=.2
    influenced=execute(config,altered);atomic_json(output/"altered-target-result.json",influenced)
    require(influenced["roots"]!=result["roots"] or influenced["local_xyzw"]!=result["local_xyzw"],
            "FIXTURE_UNUSED_TARGET","Target boundary did not influence real inference")
    stage("bake");stage("reopen")
    failures={}
    for name,changed,cancel in (("host_budget",{**config,"host_memory_budget_mib":64},None),
                               ("timeout",{**config,"timeout_seconds":.01},None),
                               ("cancelled",config,lambda:True)):
        try:execute(changed,request,cancelled=cancel)
        except DirectorError as exc:failures[name]=exc.code
        else:raise RuntimeError(f"Expected {name} failure")
    require(failures=={"host_budget":"MOTION_BRICKS_RESOURCE_EXHAUSTED","timeout":"MOTION_BRICKS_TIMEOUT",
                      "cancelled":"MOTION_BRICKS_CANCELLED"},"FIXTURE_FAILURE_HANDLING",str(failures))
    # Cancellation while queued and after an actual native subprocess starts.
    import threading
    from asset_director.motion_bricks_provider import _job_lock, _memory_mib
    held=threading.Event();release=threading.Event()
    def hold_queue():
        with _job_lock(lambda:None):
            held.set();release.wait(10)
    holder=threading.Thread(target=hold_queue);holder.start();held.wait(5)
    began=time.monotonic()
    try:
        try:execute(config,request,cancelled=lambda:time.monotonic()-began>.1)
        except DirectorError as exc:failures["queued_cancel"]=exc.code
    finally:release.set();holder.join(5)
    started=[]
    def progress(event):
        if event["stage"]=="running":started.append((time.monotonic(),event["worker_pid"]))
    try:execute(config,request,progress=progress,cancelled=lambda:bool(started) and (_memory_mib(started[0][1]) or 0)>100)
    except DirectorError as exc:failures["running_cancel"]=exc.code
    require(failures.get("queued_cancel")==failures.get("running_cancel")=="MOTION_BRICKS_CANCELLED",
            "FIXTURE_CANCELLATION",str(failures))
    # Successful model reload after forced termination proves lock/restart recovery.
    recovered=execute(config,request)
    require(recovered["roots"]==result["roots"] and recovered["local_xyzw"]==result["local_xyzw"],
            "FIXTURE_RECOVERY","Post-cancellation rerun differs")
    atomic_json(output/"recovered-result.json",recovered)
    summary={"status":"PASS_PROVIDER_AND_BLENDER_PARITY", "full_application_journey":"NOT_TESTED_BY_THIS_FIXTURE",
             "seam_contact_quality":"NOT_ACCEPTED_BY_THIS_FIXTURE", "repeatability":"EXACT_SAME_BACKEND",
             "target_influence":"CONFIRMED", "failure_cases":failures,
             "resources":[r["resource_measurements"] for r in (discovery,result,repeated,influenced,recovered)],
             "blender_bake":load_json(output/"bake-metrics.json"),"blender_reopen":load_json(output/"reopen-metrics.json")}
    atomic_json(output/"summary.json",summary);print(json.dumps(summary));return 0


if __name__=="__main__":
    arguments=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else None
    raise SystemExit(main(arguments))
