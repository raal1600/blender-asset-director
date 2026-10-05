"""Mandatory real fresh-Blender / application GLB subframe regression.

Invoked by the existing Blender subsystem runner. Only generated CC0 fixtures.
Child processes have finite timeouts; no mocks stand in for Blender or GLTFLoader.
"""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import bpy
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from owned_process import OwnedCommand
from asset_director.core import atomic_json

out=Path(sys.argv[sys.argv.index('--')+1]);out.mkdir(parents=True,exist_ok=False)
report={'status':'FAIL','input_kind':'GENERATED_CC0','checks':[],'cases':[]}

def run(name,command):
    with (out/(name+'.log')).open('w',encoding='utf-8') as log:
        owned=OwnedCommand(command,cwd=ROOT,stdout=log,report=out/(name+'-guardian.json'),timeout=600)
        try:result=owned.wait(timeout=620)
        finally:owned.close()
    assert result['state']=='EXITED' and result['exit_code']==0,(name,result)

def blender(script,*args):
    return [bpy.app.binary_path,'--background','--factory-startup','--disable-autoexec','--threads','2',
            '--python-exit-code','11','--python',ROOT/'tools'/script,'--',*args]

try:
    node=shutil.which('node');assert node,'Real GLB parity requires Node.js (same client implementation)'
    for kind,script,index in [('continuity','stitch_continuity_fixture.py',4),('contacts','contact_transition_fixture.py',3)]:
        source=out/kind;run(kind,blender(script,source))
        generated=json.loads((source/'RESULTS.json').read_text(encoding='utf-8'))
        assert generated['status']=='PASS'
        if kind=='continuity':assert generated['results'][index]['fps']==60 and generated['results'][index]['extra_frames']==2
        else:assert generated['results'][index]['name']=='walk-run-body-turn'
        fresh=out/(kind+'-fresh');run(kind+'-reopen',blender('transition_reopen_check.py',source/'RESULTS.json',index,fresh))
        run(kind+'-glb',[node,ROOT/'tools/transition_glb_check.mjs',fresh])
        native=json.loads((fresh/'RESULTS.json').read_text(encoding='utf-8'))
        playback=json.loads((fresh/'GLB-RESULTS.json').read_text(encoding='utf-8'))
        assert native['status']==playback['status']=='PASS'
        assert native['export']['timebase']['subdivisions']==32
        assert max(r['position_m'] for r in playback['samples'])<=1e-4, 'Subframe preview exceeds original 0.1mm parity limit'
        report['cases'].append({'kind':kind,'native':{k:native[k] for k in ('status','checks','source_sha256','frame_range','fps','render_range','rendered')},'playback':playback})
        report['checks'].append(kind+' fresh process persistence, actual GLTFLoader integer/eighth-frame parity and rendered boundaries')
    report['status']='PASS'
except Exception as error:
    report['error']=repr(error)
    raise
finally:
    atomic_json(out/'RESULTS.json',report)
