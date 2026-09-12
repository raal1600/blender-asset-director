"""No-auth live-provider + real-animation integration test, run by CI."""
from pathlib import Path
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from asset_director.core import Library, DirectorError, atomic_json, load_json
from asset_director.providers import Providers
from asset_director import backend,jobs


def main(blender,library,out):
    output=Path(out);output.mkdir(parents=True,exist_ok=True); results={}
    with Library(library) as lib:
        providers=Providers(lib)
        pack=providers.search('quaternius','animation')['results'][0]['asset']['id']
        results['quaternius_acquire']=providers.acquire(pack)
        j=jobs.prepare(lib,'index',asset_id=pack,options={'max_clips':256})
        jobs.run(lib,j['id'],blender,900)
        results['index']=jobs.index_result(lib,pack,j['id'])
        clips=[a for a in lib.all() if a.kind=='animation']
        assert clips and any('walk' in a.title.lower() for a in clips),[a.title for a in clips]
        results['actual_clip_names']=[a.title for a in clips]
        results['backend']=backend.install(lib)
        for provider,query,kind in [('polyhaven','desert','hdri'),('ambientcg','sand','material')]:
            r=providers.search(provider,query,kind,3,refresh=True)
            assert r['results'],r
            aid=r['results'][0]['asset']['id'];results[provider]=providers.acquire(aid)
            # Real material/HDRI Blender import; metadata alone is not integration success.
            imp=jobs.prepare(lib,'import',asset_id=aid)
            results[provider+'_import']=jobs.run(lib,imp['id'],blender,240)['summary']
        lib.export_report()
        # Select an actual motion name only after indexing the live Standard package.
        walks=[a for a in clips if 'walk' in a.title.lower() and a.metadata.get('qa',{}).get('limb_relative_motion_height_ratio',0)>.005]
        assert walks,'No usable source walking motion was measured'
        walk=sorted(walks,key=lambda a:(a.metadata['duration_seconds'],a.id))[0]
        atomic_json(output/'selected_clip.json',{'library':str(lib.root),'asset_id':walk.id})
    subprocess.run([blender,'--background','--factory-startup','--disable-autoexec','--threads','2','--python-exit-code','11','--python',str(ROOT/'tools'/'real_motion_test.py'),'--',str(output/'selected_clip.json'),str(output)],check=True,timeout=600)
    results['real_motion']=load_json(output/'real_motion_report.json')
    results['status']='PASS';results['blender']=blender
    atomic_json(output/'live_acceptance.json',results);print(json.dumps(results))

if __name__=='__main__':main(*sys.argv[1:])
