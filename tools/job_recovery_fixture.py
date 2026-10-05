"""Real Blender executor death, child release, interrupted-job recovery and retry."""
if not __debug__:raise RuntimeError('Optimized Python disables acceptance assertions')
from pathlib import Path
import os,sys,time,subprocess,json
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.dont_write_bytecode=True
from asset_director import jobs
from asset_director.core import Library,atomic_json,load_json,file_hash,DirectorError
from asset_director.execution_resources import gpu_lease
from asset_director.process_state import stopped
args=sys.argv[sys.argv.index('--')+1:];out=Path(args[0]).resolve()
if len(args)==3 and args[1]=='--executor':
    with Library(out/'library') as lib:jobs.run(lib,args[2],bpy.app.binary_path,timeout=60)
    raise SystemExit(0)
assert len(args)==1 and not out.exists();out.mkdir(parents=True)
report={'status':'FAIL','checks':[]};owner=None;worker=None
try:
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.mesh.primitive_cube_add();source=out/'synthetic.blend';bpy.ops.wm.save_as_mainfile(filepath=str(source));source_hash=file_hash(source)
    with Library(out/'library') as lib:
        job=jobs.prepare(lib,'preview',str(source),options={'stage':True,'target_object':'Cube','frames':[1],'width':64,'height':64,'samples':1});directory=lib.root/'jobs'/job['id'];marker=directory/'worker-ownership.json'
        command=[bpy.app.binary_path,'--background','--factory-startup','--disable-autoexec','--threads','2','--python-exit-code','11','--python',str(Path(__file__).resolve()),'--',str(out),'--executor',job['id']]
        with gpu_lease(),(out/'executor.log').open('wb') as log:
            owner=subprocess.Popen(command,stdout=log,stderr=log)
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                if marker.exists():
                    worker=load_json(marker)
                    if worker.get('state')=='WATCHING_EXECUTOR':break
                assert owner.poll() is None,'Executor exited before real Blender was ready';time.sleep(.02)
            assert worker and worker.get('state')=='WATCHING_EXECUTOR';assert not stopped(worker)
            try:jobs.recover(lib,job['id'],confirmed=True)
            except DirectorError as e:assert e.code in {'RESOURCE_QUEUE_TIMEOUT','JOB_STILL_RUNNING'}
            else:raise AssertionError('Recovered a live native worker')
            report['checks'].append('Live executor and real Blender worker cannot be recovered')
            before=time.monotonic();owner.kill();owner.wait(timeout=10)
            while not stopped(worker) and time.monotonic()-before<5:time.sleep(.02)
            assert stopped(worker),'Real Blender child outlived its owned executor'
            report['child_release_seconds']=time.monotonic()-before
        retained=load_json(directory/'job.json');assert retained['state']=='RUNNING' and not retained['outputs']
        recovered=jobs.recover(lib,job['id'],confirmed=True);assert recovered['state']=='INTERRUPTED' and not recovered['outputs']
        assert not (lib.root/('.run-'+job['id']+'.lock')).exists();assert (directory/'worker.log').is_file();assert (directory/'recovery.json').is_file()
        jobs.retry(lib,job['id']);assert list(directory.glob('attempt-*/recovery.json'))
        complete=jobs.run(lib,job['id'],bpy.app.binary_path,timeout=60);assert complete['state']=='SUCCEEDED';assert file_hash(source)==source_hash
        report['checks'].extend(['Executor death releases real Blender within five seconds','Stopped execution is marked INTERRUPTED with all evidence retained and no accepted output','Explicit retry archives the failure and actually succeeds in a new Blender process','Original generated source unchanged'])
        report.update(status='PASS',job_id=job['id'],source_sha256=source_hash,blender=bpy.app.version_string)
finally:
    if owner and owner.poll() is None:owner.kill();owner.wait(timeout=10)
    if worker and not stopped(worker):os.kill(worker['pid'],__import__('signal').SIGTERM)
    atomic_json(out/'RESULTS.json',report)
print(json.dumps(report))
