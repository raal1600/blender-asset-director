"""Real Blender subframe-export timebase and exception-restoration checks."""
from pathlib import Path
import json
import math
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from asset_director import viewer_export, viewer_sampling, action_layer
from asset_director.core import atomic_json,digest,file_hash
from transition_reopen_check import evaluate


source,output=sys.argv[sys.argv.index('--')+1:]
source=Path(source);out=Path(output);out.mkdir(parents=True,exist_ok=False)
original=file_hash(source);checks=[]

def settings(scene):
    r=scene.render
    return [scene.frame_start,scene.frame_end,scene.frame_current,scene.frame_subframe,
            r.fps,r.fps_base,r.frame_map_old,r.frame_map_new]

try:
    for name,start,end,fps,base,old,new in [('fractional',1,100,30,1.001,100,100),
                                         ('nonzero',7,100,60,1.,100,100),
                                         ('mapped',1,100,30,1.,200,100)]:
        bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
        scene=bpy.context.scene;scene.frame_start=start;scene.frame_end=end
        assert [scene.frame_start,scene.frame_end]==[start,end], 'Requested scene frame range was clamped'
        scene.render.fps=fps;scene.render.fps_base=base
        scene.render.frame_map_old=old;scene.render.frame_map_new=new
        scene['asset_director_preview_only']=True
        rig=scene.objects['Canonical native rig']
        samples=[evaluate(rig,f) for f in [start,start+.125,23,24.875,25,25.125,25.25,28,28.125,end]]
        scene.frame_set(17,subframe=.375)
        before=settings(scene);actions={a.name:digest(action_layer.channels(a)) for a in bpy.data.actions}
        folder=out/name;folder.mkdir()
        export=viewer_export.export(folder/'accepted.glb',{'takes':[],'checkpoint':True,'preview_profile':'action-playback-v1'})
        assert settings(scene)==before,'Exporter did not restore exact scene settings'
        assert actions=={a.name:digest(action_layer.channels(a)) for a in bpy.data.actions}
        assert abs(export['playback']['duration']-(end-start)/(fps/base))<1e-6
        atomic_json(folder/'RESULTS.json',{'status':'PASS','samples':samples,'rig':rig.name,'height_m':2.,
                    'frame_range':[start,end],'fps':fps/base,'export':export,'source_sha256':original})
        checks.append(name+' exact timing/settings/native Action preservation')
    try:
        with viewer_sampling.evaluated_sampling(scene,4):
            assert settings(scene)!=before
            raise RuntimeError('injected exporter failure')
    except RuntimeError as error:
        assert str(error)=='injected exporter failure'
    assert settings(scene)==before
    assert file_hash(source)==original
    checks.append('exception restores scene frame, subframe, range, fps and original time remapping')
    atomic_json(out/'RESULTS.json',{'status':'PASS','checks':checks})
except Exception as error:
    atomic_json(out/'RESULTS.json',{'status':'FAIL','checks':checks,'error':repr(error)})
    raise
