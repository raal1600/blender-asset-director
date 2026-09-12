"""Real Blender multi-scene regression; simple geometry, not artistic samples."""
import json
from pathlib import Path
import sys
import bpy
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from asset_director import scene_ops, jobs
from asset_director.core import Library, file_hash, atomic_json
from asset_director.worker import execute

out=Path(sys.argv[sys.argv.index('--')+1]).resolve(); out.mkdir(parents=True,exist_ok=True)
checks=[]
cases=[('product',(16,9),(.02,.05,.12),(17,-30,2),'PERSP'),
       ('environment',(9,16),(200,300,30),(-900,80,-12),'PERSP'),
       ('interior',(1,1),(12,8,4),(2,5,0),'ORTHO'),
       ('abstract',(21,9),(1,8,.3),(0,0,300),'PERSP')]
for title,aspect,scale,location,projection in cases:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(); obj=bpy.context.object; obj.name='unrelated_名称.087'
    obj.scale=scale; obj.location=location
    scene=bpy.context.scene; scene.render.resolution_x=aspect[0]*64; scene.render.resolution_y=aspect[1]*64
    scene.render.fps=30
    world=bpy.data.worlds.new('ExistingWorld'); world.use_nodes=True; scene.world=world
    existing=bpy.data.objects.new('untouched_light',bpy.data.lights.new('untouched_light','POINT'))
    existing.data.energy=12.34; scene.collection.objects.link(existing)
    bpy.context.view_layer.update()
    before_matrix=scene_ops.flatten(obj.matrix_world)
    old_energy=existing.data.energy
    observed=scene_ops.scene_audit(); assert not any(o['type']=='ARMATURE' for o in observed['objects'])
    result=scene_ops.camera_fit({'subjects':[obj.name],'frames':[1],'lens_mm':57,'direction':[.4,-1,.25],'projection':projection},title)
    assert result['all_fit'],result
    scene_ops.light_rig({'subjects':[obj.name],'lights':[{'type':'AREA','energy':50,'offset':[1,-1,1],'color':[1,1,1],'size_ratio':2}]},title)
    assert scene.world==world and existing.data.energy==old_energy
    assert scene_ops.flatten(obj.matrix_world)==before_matrix
    scene.frame_set(7)
    check=scene_ops.camera_check({'subjects':[obj.name],'camera':result['camera'],'frames':[1,3,7]})
    assert check['all_fit'] and scene.frame_current==7
    checks.append({'case':title,'projection':projection,'aspect':aspect,'fit':True,'original_preserved':True})
# Check sampled animated bounds, using neither a required rig nor a fixed 240-frame duration.
obj.location.x+=50; obj.keyframe_insert('location',frame=1)
obj.location.x+=50; obj.keyframe_insert('location',frame=36)
result=scene_ops.camera_fit({'subjects':[obj.name],'frames':[1,18,36],'lens_mm':40,'direction':[0,-1,1]},'animated')
assert result['all_fit']; checks.append({'case':'animated_bounds','fit':True})
# Exercise the real worker: the former preview branch incorrectly required an armature.
scene.render.resolution_x=64; scene.render.resolution_y=64
original=out/'source.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(original)); baseline=file_hash(original)
with Library(out/'library') as lib:
    job=jobs.prepare(lib,'preview',str(original),options={'frames':[1],'width':64,'height':64,'samples':1})
    summary=execute(lib.root/'jobs'/job['id']/'job.json')
    assert summary['operation']=='preview'
    assert (lib.root/'jobs'/job['id']/'preview_0001.png').stat().st_size>0
    assert file_hash(original)==baseline
checks.append({'case':'rig_free_preview_worker','render':'CPU 64x64 1 sample','original_hash_unchanged':True})
report={'status':'PASS','blender_version':bpy.app.version_string,'checks':checks,
        'notice':'Synthetic geometric regression cases; not realistic artwork, film quality, or user-scene acceptance.'}
atomic_json(out/'studio_report.json',report); print(json.dumps(report))
