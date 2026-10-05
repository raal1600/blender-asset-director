"""Finite real transition acceptance with artifacts, resource samples and scope.

No missing provider/GPU/native-desktop evidence is counted as a pass. Model/GPU
acceptance is a separate explicit invocation, never an ordinary CI skip/pass.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
from transition_resources import measured_run


def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--blender',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--node',default='node')
    p.add_argument('--playwright',type=Path,help='Absolute pinned Playwright ESM entry, with browser/video helper installed')
    p.add_argument('--chrome',type=Path)
    p.add_argument('--ffmpeg',type=Path)
    p.add_argument('--ffprobe',type=Path)
    p.add_argument('--codex',type=Path)
    p.add_argument('--repeat',type=int,default=2)
    p.add_argument('--device-memory-budget-mib',type=int,default=9216,
                   help='Device-wide observation budget, including display/client headroom; no allocation promise')
    args=p.parse_args()
    assert 1<=args.repeat<=5 and 1024<=args.device_memory_budget_mib<=65536
    assert args.blender.is_file() and args.output.is_absolute() and not args.output.exists()
    out=args.output;out.mkdir(parents=True)
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONIOENCODING='utf-8',BAD_CONFIG=str(out/'runtime.json'))
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT))
    source_hash=hashlib.sha256()
    for directory in ('src','launcher','tools'):
        for file in sorted((ROOT/directory).rglob('*')):
            if file.is_file() and file.suffix in {'.py','.mjs','.js','.json','.html','.css'} and not any(
                    part in {'node_modules','__pycache__','.deps'} for part in file.parts):
                source_hash.update(file.relative_to(ROOT).as_posix().encode());source_hash.update(file.read_bytes())
    report={'schema':'asset-director.transition-acceptance/1','commit':commit,'dirty':dirty,
            'source_sha256':source_hash.hexdigest(),'status':'RUNNING','checks':[],
            'device_memory_budget_mib':args.device_memory_budget_mib,
            'scope':{'deterministic':'NOT_VERIFIED','installed_client':'NOT_VERIFIED',
                     'native_windows_package':'NOT_VERIFIED','provider':'NOT_VERIFIED',
                     'gpu_inference':'NOT_VERIFIED','authored_contacts':'NOT_VERIFIED','retargeted_native':'NOT_VERIFIED',
                     'natural_locomotion_contacts':'NOT_VERIFIED',
                     'hosted_final_commit_ci':'NOT_VERIFIED'}}

    def run(name,command,timeout=900,expected=None,cwd=ROOT):
        data=measured_run(command,out/(name+'.log'),cwd=cwd,env=env,timeout=timeout)
        write(out/(name+'-resources.json'),data)
        ok=data['exit_code']==0 and not data['timed_out'] and data['observed_process_release']=='PASS'
        if expected:
            try:ok=ok and json.loads(Path(expected).read_text(encoding='utf-8'))['status']=='PASS'
            except (OSError,ValueError,KeyError):ok=False
        peak=data['peak_device_used_mib']
        memory='NOT_VERIFIED' if peak is None else 'PASS' if peak<=args.device_memory_budget_mib else 'FAIL'
        row={'id':name,'status':'PASS' if ok else 'FAIL','seconds':data['seconds'],
             'peak_host_resident_bytes':data['peak_host_resident_bytes'],'peak_device_used_mib':peak,
             'device_budget':memory,'observed_process_release':data['observed_process_release'],'resource_report':name+'-resources.json'}
        report['checks'].append(row);write(out/'ACCEPTANCE.json',report)
        print(json.dumps(row),flush=True)
        return ok

    def blender(script,*values):
        return [args.blender,'--background','--factory-startup','--disable-autoexec','--threads','2',
                '--python-exit-code','11','--python',ROOT/'tools'/script,'--',*values]

    def validate_cases(fixture,prefix=''):
        cases=json.loads((fixture/'RESULTS.json').read_text(encoding='utf-8'))['results']
        for index,case in enumerate(cases):
            name=prefix+str(index);fresh=out/('fresh-'+name)
            if run('fresh-'+name,blender('transition_reopen_check.py',fixture/'RESULTS.json',index,fresh),expected=fresh/'RESULTS.json'):
                run('glb-'+name,[args.node,ROOT/'tools/transition_glb_check.mjs',fresh],expected=fresh/'GLB-RESULTS.json')
                if args.ffmpeg:
                    run('movie-'+name,[args.ffmpeg,'-nostdin','-n','-v','error','-framerate',case['fps']/case.get('fps_base',1),
                        '-i',fresh/'frame-%04d.png','-c:v','libx264','-pix_fmt','yuv420p',fresh/'boundaries.mp4'],120)
        return cases

    def reproducibility(first,second,name):
        a=json.loads((first/'RESULTS.json').read_text(encoding='utf-8'))['results']
        b=json.loads((second/'RESULTS.json').read_text(encoding='utf-8'))['results']
        errors=[]
        def compare(x,y):
            if isinstance(x,dict):
                assert x.keys()==y.keys()
                for key in x: compare(x[key],y[key])
            elif isinstance(x,list):
                assert len(x)==len(y)
                for left,right in zip(x,y):compare(left,right)
            elif isinstance(x,(int,float)):
                errors.append(abs(x-y))
            else:assert x==y
        assert len(a)==len(b)
        for left,right in zip(a,b):
            assert left.get('name')==right.get('name')
            assert left['fps']==right['fps'] and left['stitch_timestamps']==right['stitch_timestamps']
            compare(left['samples'],right['samples'])
        maximum=max(errors,default=0.)
        row={'id':name,'status':'PASS' if maximum<=1e-6 else 'FAIL','device_budget':'NOT_APPLICABLE',
             'max_component_difference':maximum,'tolerance':1e-6,'compared_components':len(errors)}
        report['checks'].append(row);write(out/'ACCEPTANCE.json',report)

    try:
        run('portable',[sys.executable,ROOT/'tools/run_checks.py','--offline'],1200)
        run('launcher',[args.node,'--test'],600,cwd=ROOT/'launcher')
        fixture=out/'continuity'
        if run('continuity',blender('stitch_continuity_fixture.py',fixture),expected=fixture/'RESULTS.json'):
            cases=validate_cases(fixture)
            for iteration in range(1,args.repeat):
                target=out/('repeat-'+str(iteration))
                if run('repeat-'+str(iteration),blender('stitch_continuity_fixture.py',target),expected=target/'RESULTS.json'):
                    reproducibility(fixture,target,'reproducibility-'+str(iteration))
            sampling=out/'sampling'
            if run('sampling',blender('viewer_sampling_fixture.py',cases[4]['result'],sampling),expected=sampling/'RESULTS.json'):
                for name in ('fractional','nonzero','mapped'):
                    run('sampling-'+name,[args.node,ROOT/'tools/transition_glb_check.mjs',sampling/name],expected=sampling/name/'GLB-RESULTS.json')
            report['scope']['deterministic']='PASS' if all(c['status']=='PASS' for c in report['checks']) else 'FAIL'
        else:
            report['scope']['deterministic']='FAIL'
        contacts=out/'contacts';contact_start=len(report['checks'])
        if run('contacts',blender('contact_transition_fixture.py',contacts),expected=contacts/'RESULTS.json'):
            validate_cases(contacts,'contact-')
            repeated=out/'contacts-repeat'
            if args.repeat>1 and run('contacts-repeat',blender('contact_transition_fixture.py',repeated),expected=repeated/'RESULTS.json'):
                reproducibility(contacts,repeated,'contacts-reproducibility')
        report['scope']['authored_contacts']='PASS' if all(c['status']=='PASS' for c in report['checks'][contact_start:]) else 'FAIL'
        retarget=out/'retarget';library=out/'retarget-library';retarget_start=len(report['checks'])
        if run('retarget-backend',[sys.executable,'-m','asset_director','--library',library,'backend-install']):
            if run('retarget',blender('retarget_transition_fixture.py',retarget,library),expected=retarget/'RESULTS.json'):
                validate_cases(retarget,'retarget-')
        report['scope']['retargeted_native']='PASS' if all(c['status']=='PASS' for c in report['checks'][retarget_start:]) else 'FAIL'
        source=out/'browser-fixture'
        if args.playwright:
            assert args.ffmpeg and args.ffprobe and args.codex, 'Installed client acceptance requires explicit ffmpeg, ffprobe and codex executable paths'
            if run('browser-fixture',blender('motion_stitch_fixture.py',source),expected=source/'RESULTS.json'):
                from create_workbench_studio import create
                studio=out/'InstalledStudio'
                create(studio,str(args.blender),sys.executable,str(args.codex),source_commit=commit,
                       ffmpeg=str(args.ffmpeg),ffprobe=str(args.ffprobe))
                command=[args.node,ROOT/'tools/motion_stitch_browser_check.mjs',out/'client',source,
                         sys.executable,args.blender,args.playwright,args.chrome or '',studio]
                passed=run('installed-client',command,1200,expected=out/'client/RESULTS.json')
                report['scope']['installed_client']='PASS' if passed else 'FAIL'
                cancellation=[args.node,ROOT/'tools/action_cancel_browser_check.mjs',out/'cancellation',source,
                              sys.executable,args.blender,args.playwright,args.chrome or '',studio]
                run('client-cancellation',cancellation,600,expected=out/'cancellation/RESULTS.json')
        # Scoped success is intentionally distinct from full task acceptance.
        report['status']='FAIL' if any(c['status']=='FAIL' or c['device_budget']=='FAIL' for c in report['checks']) else 'SCOPED_PASS'
        report['full_acceptance']='NOT_VERIFIED'
    except Exception as exc:
        report['status']='FAIL';report['error']=repr(exc)
    finally:
        write(out/'ACCEPTANCE.json',report)
    return 1 if report['status']=='FAIL' else 0


if __name__=='__main__':
    raise SystemExit(main())
