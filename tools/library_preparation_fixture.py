"""Real Blender local-package preparation, dependency refusal and collection import.

Generated fixtures and scripted evidence only; never a user's source or approval.
"""
from pathlib import Path
import json
import sys
import bpy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from asset_director.core import Library, atomic_json, file_hash, digest, DirectorError, load_json
from asset_director.workbench_intake import run
from asset_director import jobs

out=Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(parents=True,exist_ok=False)
source=out/'originals';source.mkdir()
checks=[]
report={'status':'RUNNING','kind':'synthetic-native-package-preparation','decisions':'SCRIPTED_FIXTURE_EVIDENCE_NOT_HUMAN_APPROVAL','checks':checks}
def check(value,name):
    if not value:raise AssertionError(name)
    checks.append(name)

def request(name,member):
    attempt=out/name;attempt.mkdir()
    records=[{'path':p.name,'sha256':file_hash(p),'size':p.stat().st_size} for p in sorted(source.iterdir()) if p.is_file()]
    data={'schema':'asset-director.asset-preview/1','source_kind':'source','id':'synthetic-native-package',
          'title':'Synthetic environment','version':digest(records),'root':str(source),'file':member,'files':records}
    atomic_json(attempt/'request.json',data)
    return attempt,data

try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=.5);bpy.context.object.name='ExistingSyntheticSubject'
    baseline=out/'baseline.blend';bpy.ops.wm.save_as_mainfile(filepath=str(baseline))
    baseline_hash=file_hash(baseline)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_plane_add(size=3,location=(3,0,0));obj=bpy.context.object;obj.name='SyntheticEnvironmentMesh'
    collection=bpy.data.collections.new('SyntheticEnvironment');bpy.context.scene.collection.children.link(collection)
    for owner in list(obj.users_collection):owner.objects.unlink(obj)
    collection.objects.link(obj)
    image=bpy.data.images.new('RecordedTexture',width=4,height=4)
    image.pixels=[.2,.5,.1,1]*16;image.filepath_raw=str(source/'texture.png');image.file_format='PNG';image.save()
    material=bpy.data.materials.new('SyntheticTextureMaterial');material.use_nodes=True
    texture=material.node_tree.nodes.new('ShaderNodeTexImage');texture.image=image
    material.node_tree.links.new(texture.outputs['Color'],material.node_tree.nodes.get('Principled BSDF').inputs['Base Color']);obj.data.materials.append(material)
    bpy.ops.wm.save_as_mainfile(filepath=str(source/'environment.blend'))
    image.filepath='//texture.png';bpy.ops.wm.save_as_mainfile(filepath=str(source/'environment.blend'))
    evidence=out/'synthetic-evidence.json'
    atomic_json(evidence,dict(title='Synthetic environment',kind='model',source_url='https://example.invalid/generated-native-package',
                license_id='CC0-1.0',license_url='https://example.invalid/synthetic-terms',author='Synthetic fixture generator',price=0,attested=True,tags=['environment']))
    with Library(out/'catalog') as lib:
        attempt,source_request=request('valid-attempt','environment.blend')
        prepared=run(lib,attempt/'request.json',evidence,bpy.app.binary_path)
        check(prepared['state']=='READY' and prepared['asset']['subcategory']['id']=='environment','real native preparation with recorded relative texture')
        check(not prepared['scene_imported'] and not prepared['production_use_approved'],'preparation never imports a scene or approves use')
        contents=jobs.prepare(lib,'asset-contents',asset_id=prepared['asset_id'],options={'file':prepared['file']})
        contents=jobs.run(lib,contents['id'],bpy.app.binary_path,timeout=180)
        data=load_json(lib.root/'jobs'/contents['id']/'result.json')['data']
        check(contents['state']=='SUCCEEDED' and 'SyntheticEnvironment' in data['collections'],'observed native collection names, not guessed mappings')
        imported=jobs.prepare(lib,'import',asset_id=prepared['asset_id'],input_file=str(baseline),options={'file':prepared['file'],'selection':['SyntheticEnvironment'],'collection':'Synthetic imported environment'})
        imported=jobs.run(lib,imported['id'],bpy.app.binary_path,timeout=180)
        data=load_json(lib.root/'jobs'/imported['id']/'result.json')['data']
        check(imported['state']=='SUCCEEDED' and {o['name'] for o in data['scene_audit']['objects']} >= {'ExistingSyntheticSubject','SyntheticEnvironmentMesh'},'real bounded collection import preserves existing world')
        check(all(file_hash(source/f['path'])==f['sha256'] for f in source_request['files']) and file_hash(baseline)==baseline_hash,'original package, texture and previous world bytes unchanged')
        # This separate source deliberately references a missing texture.
        image.filepath='//missing-texture.png';bpy.ops.wm.save_as_mainfile(filepath=str(source/'broken.blend'))
        bad,_=request('missing-dependency-attempt','broken.blend');count=len(lib.all())
        try:run(lib,bad/'request.json',evidence,bpy.app.binary_path)
        except DirectorError:pass
        else:raise AssertionError('Missing dependency was accepted')
        check(load_json(bad/'intake-receipt.json')['state']=='FAILED' and len(lib.all())==count,'missing dependency fails before catalog publication and preserves failed attempt')
        report.update(status='PASS',asset_id=prepared['asset_id'],asset_version=prepared['asset_version'],import_job=imported['id'],blender=bpy.app.version_string)
except BaseException as error:
    report.update(status='FAIL',error=str(error));raise
finally:atomic_json(out/'report.json',report)
print(json.dumps(report))
