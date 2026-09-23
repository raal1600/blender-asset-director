"""Actual isolated CPU/OptiX fixture. GPU runs require an explicit CLI flag.

Run in Blender background with -- OUT OPTIX. No existing library or preferences
are saved. Missing GPU is a failure, never a CPU pass.
"""
from pathlib import Path
import json,sys,time,uuid
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from asset_director import jobs
from asset_director.core import Library,atomic_json,file_hash,DirectorError
args=sys.argv[sys.argv.index('--')+1:]
out=Path(args[0]).resolve();backend=args[1] if len(args)>1 else 'CPU'
assert backend in {'CPU','OPTIX'}
assert not out.exists(),'Use a new unused fixture directory'
out.mkdir(parents=True)
checks=[]
def check(condition,name,**details):
    assert condition,name
    checks.append({'name':name,**details})
def report():
    atomic_json(out/'report.json',{'status':'RUNNING','backend':backend,'checks':checks})
report()
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.frame_start=1;scene.frame_end=48;scene.render.fps=24
scene.render.use_compositing=False;scene.render.use_sequencer=False
scene.cycles.use_denoising=True;scene.cycles.denoiser='OPENIMAGEDENOISE'
bpy.ops.mesh.primitive_cube_add()
cube=bpy.context.object
for frame,x in [(1,-.5),(48,.5)]:
    cube.location.x=x;cube.keyframe_insert(data_path='location',frame=frame)
camera=bpy.data.objects.new('Fixture camera',bpy.data.cameras.new('Fixture camera'))
scene.collection.objects.link(camera);camera.location=(5,-8,4)
camera.rotation_euler=(-camera.location).to_track_quat('-Z','Y').to_euler();scene.camera=camera
light=bpy.data.objects.new('Fixture key',bpy.data.lights.new('Fixture key','AREA'))
scene.collection.objects.link(light);light.location=(1,-4,6);light.data.energy=800;light.data.size=4
light.rotation_euler=(-light.location).to_track_quat('-Z','Y').to_euler()
scene.world=bpy.data.worlds.new('Fixture world');scene.world.use_nodes=True
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.15
source=out/'synthetic.blend';scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(source),check_existing=False)
original=file_hash(source)
with Library(out/'library') as lib:
    ready=jobs.prepare(lib,'render-readiness',str(source))
    ready=jobs.run(lib,ready['id'],bpy.app.binary_path,timeout=180)
    audit=json.loads((out/'library/jobs'/ready['id']/'result.json').read_text())['data']
    check(not audit['blockers'],'readiness',devices=audit['render_devices'])
    options={'readiness_job':ready['id'],'camera':camera.name,'start':1,'end':2,'width':320,'height':180,'samples':8}
    if backend=='OPTIX':
        found=[d for d in audit['render_devices'] if d['backend']=='OPTIX']
        check(len(found)==1,'one_explicit_gpu_required')
        options['render_device']={'backend':'OPTIX','id':found[0]['id']}
    try:
        jobs.prepare(lib,'render-frames',str(source),options={**options,'render_device':{'backend':'OPTIX','id':'deliberately-missing'}})
        raise AssertionError('Missing GPU was accepted')
    except DirectorError as exc:
        check(exc.code=='RENDER_DEVICE_UNAVAILABLE','missing_gpu_refused_without_cpu_fallback')
    durations=[]
    for label,patch in [('smoke',{}),('720p',{'width':1280,'height':720,'end':48} if backend=='OPTIX' else {'width':64,'height':64,'end':2})]:
        selected={**options,**patch};job=jobs.prepare(lib,'render-frames',str(source),options=selected)
        started=time.monotonic();job=jobs.run(lib,job['id'],bpy.app.binary_path,timeout=900)
        data=json.loads((out/'library/jobs'/job['id']/'result.json').read_text())['data']
        elapsed=time.monotonic()-started
        check(job['state']=='SUCCEEDED' and data['render_device']['backend']==backend and
              not data['render_device']['fallback'],label,job=job['id'],seconds=elapsed,device=data['render_device'],frames=data['frame_count'])
        check(file_hash(source)==original,label+'_source_unchanged')
        for f in job['outputs']:check(file_hash(lib.root/f['path'])==f['sha256'],label+'_output_hash',path=f['path'])
        durations.append({'label':label,'seconds':elapsed,'job':job['id'],'frames':data['frame_count']})
        report()
    bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
    check(bpy.context.scene.cycles.denoiser=='OPENIMAGEDENOISE','saved_denoiser_preserved')
    atomic_json(out/'report.json',{'status':'PASS','backend':backend,'source_sha256':original,'checks':checks,'timings':durations,
        'blender':bpy.app.version_string,'not_tested':['desktop UI','film encoding','human visual approval','global preference UI']})
print('RENDER_DEVICE_FIXTURE_PASS',json.dumps(durations))
