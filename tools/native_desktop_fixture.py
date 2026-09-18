"""Actual Windows EXE/Blender GUI round trip on a disposable desktop.

Scripted input is not human approval. No model, pre-existing studio or private
assets are used. Cleanup addresses only processes spawned by this fixture.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tools/ci')]
from create_workbench_studio import create
from native_desktop_contract import DESKTOP_CHECKS
from evidence import Evidence, digest, read, write


def wait(fn, label, seconds=80):
    end = time.monotonic()+seconds
    while time.monotonic()<end:
        try:
            value=fn()
            if value: return value
        except (OSError, ValueError, KeyError): pass
        time.sleep(.3)
    raise RuntimeError('Timed out: '+label)


class Journey:
    def __init__(self, blender, evidence):
        self.blender=str(Path(blender).resolve());self.e=evidence
        self.root=Path(tempfile.mkdtemp(prefix='ad-native-'))/'studio'
        self.children=[];self.task_pids=[];self.session=None

    def spawn(self,args,label):
        log=(self.e.directory/(label+'.log')).open('wb')
        try: p=subprocess.Popen([str(a) for a in args],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
        finally: log.close()
        self.children.append(p);return p

    def ui(self,pid,action,**values):
        args=['powershell','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',
              str(ROOT/'tools/native_desktop_ui.ps1'),'-ProcessIdentifier',str(pid),'-Action',action]
        for key,value in values.items():args.extend(['-'+key,str(value)])
        result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=25)
        if result.returncode: raise RuntimeError(result.stderr[-3000:])
        return json.loads(result.stdout) if action=='observe' else None

    def api(self,route,body=None):
        req=urllib.request.Request(self.session['origin']+'/api/'+route,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization':'Bearer '+self.session['token'],'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)

    def state(self):return self.api('workbench/state?projectId='+self.project['id'])

    def post(self,action,**body):
        return self.api('workbench/'+action,dict(projectId=self.project['id'],sceneId=self.scene_id,
            revision=self.state()['project']['revision'],**body))

    def start_host(self,label):
        settings=self.root/'SystemRuntime/UserData/Launcher';log=settings/'desktop.log'
        old=log.read_text().count('Desktop interface loaded successfully.') if log.exists() else 0
        self.host=self.spawn([self.exe],label)
        self.session=wait(lambda:read(settings/'session.json'),'new desktop session')
        self.e.secrets.append(self.session['token'])
        wait(lambda:log.read_text().count('Desktop interface loaded successfully.')>old,'new WebView2 navigation')

    def run(self):
        e=self.e
        with e.checkpoint('native_host_loaded') as check:
            create(self.root,self.blender,sys.executable,sys.executable,source_commit=e.report['commit'])
            launcher=self.root/'SystemRuntime/Launcher'
            for name in ('Asset Director.exe','Microsoft.Web.WebView2.Core.dll','Microsoft.Web.WebView2.WinForms.dll','WebView2Loader.dll'):
                shutil.copy2(ROOT/'launcher'/name,launcher/name)
            self.exe=launcher/'Asset Director.exe';self.start_host('desktop')
            assert self.api('session')['app']=='asset-director-launcher'
            self.ui(self.host.pid,'capture',Text='Asset Director',OutputPath=e.directory/'native-desktop.png')
            check['exe_sha256']=digest(self.exe)
        with e.checkpoint('second_launch_reused'):
            original=dict(self.session);assert self.spawn([self.exe],'second-launch').wait(timeout=15)==0
            assert read(self.root/'SystemRuntime/UserData/Launcher/session.json')==original
            assert any(w['visible'] for w in self.ui(self.host.pid,'observe')['windows'])
        with e.checkpoint('blender_task_focused') as check:
            self.project=self.api('projects/create',dict(name='Synthetic native acceptance',brief='Scripted editing and preservation; not artistic review.'))
            created=self.api('workbench/create',dict(projectId=self.project['id'],revision=self.project['revision'],name='Native scene'))
            self.scene_id=created['sceneId'];directory=Path(created['project']['directory']);seed=directory/'Scenes/native-input.blend'
            job=self.spawn([self.blender,'-b','--factory-startup','--disable-autoexec','--python-exit-code','1',
                '--python',ROOT/'tools/native_desktop_scene.py','--','seed',seed],'seed')
            assert job.wait(timeout=90)==0;original=digest(seed)
            self.post('import',sourceScene='Scenes/native-input.blend');self.post('keep-building')
            frozen=self.state()['project']['workbench']['scenes'][0]['checkpoints'][-1]
            sentinel_file=self.root/'sentinel.json'
            sentinel=self.spawn([self.blender,'--factory-startup','--disable-autoexec','--python',
                ROOT/'tools/native_desktop_scene.py','--','sentinel',sentinel_file],'sentinel')
            before=wait(lambda:read(sentinel_file),'unrelated unsaved scene');assert before['file']==''
            task=self.post('task-open',context={'targets':['NativeSubject']})['task'];self.task_pids.append(task['processId'])
            status_file=directory/('Docs/Workbench/'+task['id']+'-status.json')
            status=wait(lambda:(v if (v:=read(status_file)).get('expected_file') or v['state']=='FAILED' else None),'identified task')
            assert status['state']!='FAILED',status
            assert status['gui_configured'] and status['active_object']=='NativeSubject'
            self.ui(task['processId'],'capture',OutputPath=e.directory/'native-blender.png')
            check.update(workspace=status['workspace'],target=status['active_object'])
        with e.checkpoint('active_close_preserved'):
            self.ui(self.host.pid,'close',Text='Asset Director')
            wait(lambda:any(w['title']=='Work is still running' for w in self.ui(self.host.pid,'observe')['windows']),'active-work dialog')
            self.ui(self.host.pid,'button',Text='Keep running in tray')
            wait(lambda:not any(w['visible'] and w['title']=='Asset Director' for w in self.ui(self.host.pid,'observe')['windows']),'tray hiding')
            assert self.api('lifecycle')['busy'] and self.state()['locked']
            assert self.spawn([self.exe],'tray-restore').wait(timeout=15)==0
            wait(lambda:any(w['visible'] and w['title']=='Asset Director' for w in self.ui(self.host.pid,'observe')['windows']),'tray restore')
        with e.checkpoint('native_edit_checkpoint') as check:
            area=max((a for a in read(status_file)['areas'] if a['type']=='VIEW_3D'),key=lambda a:a['width']*a['height'])
            point=dict(X=area['x']+int(area['width']*.4),Y=area['y']+int(area['height']*.5))
            self.ui(task['processId'],'move',**point)
            wait(lambda:read(status_file).get('dirty'),'native edit dirty state')
            self.ui(task['processId'],'checkpoint',**point)
            returned=wait(lambda:read(directory/task['returnFile']),'native checkpoint receipt')
            obj=next(o for o in returned['audit']['objects'] if o['name']=='NativeSubject')
            assert abs(obj['matrix_world'][3]-1)<1e-5,obj['matrix_world']
            assert digest(seed)==original and digest(directory/frozen['path'])==frozen['sha256']
            assert returned['human_acceptance']=='PENDING'
            self.post('task-collect');after=self.state()['project']['workbench']['scenes'][0]
            assert after['current']==frozen['id'] and after['candidate'] and not self.state()['locked']
            write(e.directory/'native-checkpoint.json',returned);check.update(native_transform_x=1,candidate_only=True)
        with e.checkpoint('unrelated_unsaved_preserved'):
            latest=wait(lambda:(v if (v:=read(sentinel_file))['observed_at']>before['observed_at'] else None),'fresh sentinel observation')
            assert {k:v for k,v in latest.items() if k!='observed_at'}=={k:v for k,v in before.items() if k!='observed_at'}
            assert sentinel.poll() is None
        with e.checkpoint('idle_exit_stopped_server'):
            self.ui(self.host.pid,'close',Text='Asset Director');assert self.host.wait(timeout=30)==0
            wait(lambda:not (self.root/'SystemRuntime/UserData/Launcher/session.json').exists(),'server exit')
            assert sentinel.poll() is None
        with e.checkpoint('restart_resumed'):
            old_token=self.session['token'];self.start_host('restart')
            assert self.session['token']!=old_token
            resumed=self.state()['project']['workbench']['scenes'][0]
            assert resumed['current']==after['current'] and resumed['candidate']==after['candidate']
            self.ui(self.host.pid,'close',Text='Asset Director');assert self.host.wait(timeout=30)==0
        write(e.directory/'native-events.json',dict(checks=e.report['checks'],input='scripted native GUI + authenticated HTTP',
            human_acceptance='NOT_TESTED',authorized_codex='NOT_TESTED',private_assets='NOT_TESTED'))

    def cleanup(self):
        if self.session:
            try:self.api('stop',{})
            except Exception:pass
        for pid in self.task_pids:
            subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],capture_output=True,timeout=15)
        for p in self.children:
            if p.poll() is None:subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=15)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--blender',required=True);parser.add_argument('--evidence',required=True,type=Path)
    args=parser.parse_args()
    if sys.platform!='win32':raise RuntimeError('Windows desktop required; no emulated pass')
    evidence=Evidence(args.evidence,'desktop','native-roundtrip',platform='win32');journey=Journey(args.blender,evidence)
    try:journey.run();evidence.finish(DESKTOP_CHECKS)
    except Exception as exc:evidence.fail(exc);raise
    finally:journey.cleanup()

if __name__=='__main__':main()
