import dataclasses
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import stat

from asset_director.core import Asset, Library, DirectorError, rights, rank, plan, atomic_json, load_json, within, file_hash
from asset_director.acquire import check_url, safe_member, public_addresses, extract_zip, gltf_dependencies, download, HTTP
from asset_director.motion import identify_roles, mapping_plan, frame_convert, quality
from asset_director import jobs
from asset_director.providers import Providers, capabilities
from asset_director.intake import intake


def sample_asset(**kw):
    fields=dict(provider='fixture',source_id='test',title='Slow Armed Walk',kind='animation',source_url='https://example.com/model',
                license_id='CC0-1.0',license_url='https://creativecommons.org/publicdomain/zero/1.0/',author='Fixture',price=0,downloadable=True,
                formats=['.glb'],tags=['walk','armed','slow'],evidence='provider')
    fields.update(kw); return Asset(**fields)


class LibraryFixture:
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.lib=Library(self.root/'library')
    def tearDown(self): self.lib.close(); self.tmp.cleanup()
    def local_file(self,name='fixture.glb',content=b'fixture'):
        p=self.lib.root/'incoming'/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(content)
        return {'path':p.relative_to(self.lib.root).as_posix(),'size':len(content),'sha256':file_hash(p)}


class LibraryCase(LibraryFixture,unittest.TestCase):
    def test_manifest_roundtrip_and_rebuild(self):
        a=sample_asset(); self.lib.put(a)
        self.assertEqual(self.lib.get(a.id),a)
        self.lib.db.execute('DELETE FROM assets'); self.lib.db.commit()
        self.assertEqual(self.lib.rebuild(),1); self.assertEqual(self.lib.get(a.id).title,a.title)
    def test_hash_verification(self):
        f=self.local_file(); self.lib.verify_file(f)
        (self.lib.root/f['path']).write_bytes(b'corrupted')
        with self.assertRaises(DirectorError): self.lib.verify_file(f)
    def test_lock_exclusion(self):
        with self.lib.lock():
            with self.assertRaises(DirectorError):
                with self.lib.lock(): pass
        with self.lib.lock(): pass
    def test_unknown_version(self):
        self.lib.db.execute('PRAGMA user_version=99'); self.lib.db.commit()
        with self.assertRaises(DirectorError): Library(self.lib.root)
    def test_json_rejects_duplicates_and_nan(self):
        p=self.root/'bad.json'
        for data in ('{"a":1,"a":2}', '{"a":NaN}'):
            p.write_text(data)
            with self.assertRaises(DirectorError): load_json(p)
    def test_id_cannot_be_spoofed(self):
        a=sample_asset().to_dict(); a['id']='a_wrong'
        with self.assertRaises(DirectorError): Asset.from_dict(a)
    def test_path_escape(self):
        for name in ('../secret','C:/Windows','x\\..\\y','/etc/passwd'):
            with self.subTest(name=name),self.assertRaises(DirectorError): within(self.lib.root,name)
    def test_job_is_reproducible_and_code_bound(self):
        a=jobs.prepare(self.lib,'inspect'); b=jobs.prepare(self.lib,'inspect')
        self.assertEqual(a['id'],b['id'])
        with patch('asset_director.jobs.implementation_hash',return_value='changed'):
            with self.assertRaises(DirectorError): jobs.read_job(self.lib,a['id'])
    def test_job_input_mutation_rejected(self):
        p=self.root/'original.blend'; p.write_bytes(b'original')
        j=jobs.prepare(self.lib,'inspect',str(p)); p.write_bytes(b'new')
        with self.assertRaises(DirectorError): jobs.read_job(self.lib,j['id'])
    def test_job_unknown_options(self):
        with self.assertRaises(DirectorError): jobs.prepare(self.lib,'inspect',options={'execute':'bad'})
    def test_child_environment_drops_keys(self):
        with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'SECRET','SKETCHFAB_TOKEN':'SECRET','PATH':'/bin'}):
            env=jobs.child_environment(); self.assertNotIn('DEEPSEEK_API_KEY',env);self.assertNotIn('SKETCHFAB_TOKEN',env)
    def test_failed_retry_preserves_evidence(self):
        j=jobs.prepare(self.lib,'inspect'); p=self.lib.root/'jobs'/j['id']/'job.json'
        j['state']='FAILED'; atomic_json(p,j); (p.parent/'worker.log').write_text('failure')
        r=jobs.retry(self.lib,j['id']); self.assertEqual(r['state'],'PLANNED'); self.assertTrue(list(p.parent.glob('attempt-*/worker.log')))
    def test_original_intake_evidence_stays_unverified(self):
        p=self.root/'source.fbx';p.write_bytes(b'local')
        e=self.root/'evidence.json';atomic_json(e,{'title':'Original','kind':'model','source_url':'user supplied'})
        r=intake(self.lib,str(p),str(e));a=self.lib.get(r['asset_id']);self.assertFalse(rights(a)['eligible']);self.assertEqual(p.read_bytes(),b'local')
    def test_intake_explicit_license_and_idempotence(self):
        p=self.root/'source.fbx';p.write_bytes(b'local')
        e=self.root/'evidence.json';atomic_json(e,{'title':'Approved','kind':'model','source_url':'https://example.com','license_id':'CC0-1.0','license_url':'https://creativecommons.org/publicdomain/zero/1.0/','price':0,'attested':True})
        a=intake(self.lib,str(p),str(e)); b=intake(self.lib,str(p),str(e))
        self.assertEqual(a['asset_id'],b['asset_id']);self.assertTrue(rights(self.lib.get(a['asset_id']))['eligible'])
    def test_attribution_report(self):
        self.lib.put(sample_asset(license_id='CC-BY-4.0'))
        r=self.lib.export_report();self.assertEqual(r['assets'],1);self.assertTrue((self.lib.root/'reports'/'ATTRIBUTION.md').exists())


class PolicyCase(unittest.TestCase):
    def test_cc0_allowed(self): self.assertTrue(rights(sample_asset())['eligible'])
    def test_ccby_attribution_required(self): self.assertTrue(rights(sample_asset(license_id='CC-BY-4.0'))['attribution_required'])
    def test_restricted_or_unknown_licenses_rejected(self):
        for lid in ('UNKNOWN','CC-BY-NC-4.0','CC-BY-ND-4.0','Editorial','Royalty Free','GPL-3.0'):
            with self.subTest(license=lid): self.assertFalse(rights(sample_asset(license_id=lid))['eligible'])
    def test_missing_evidence_rejected(self): self.assertFalse(rights(sample_asset(evidence='unverified'))['eligible'])
    def test_unknown_price_rejected(self): self.assertFalse(rights(sample_asset(price=None))['eligible'])
    def test_paid_rejected(self): self.assertFalse(rights(sample_asset(price=1))['eligible'])
    def test_non_downloadable_rejected(self): self.assertFalse(rights(sample_asset(downloadable=False))['eligible'])
    def test_unsupported_format_rejected(self): self.assertFalse(rights(sample_asset(formats=['.uasset']))['eligible'])
    def test_rank_is_stable_and_explainable(self):
        a=sample_asset();b=sample_asset(source_id='run',title='Armed Run',tags=['run','armed'])
        ranked=rank('slow armed walk',[b,a]);self.assertEqual(ranked[0]['asset']['id'],a.id)
        self.assertIn('WRONG_MOTION_RUN_NOT_WALK',ranked[1]['policy']['reasons']);self.assertEqual(rank('slow armed walk',[b,a]),ranked)
    def test_plan_is_not_a_fabricated_catalog(self):
        p=plan('Warrior slowly walks over a dune and stops, vigilant')
        self.assertEqual(p['status'],'HOST_INTERPRETATION_REQUIRED');self.assertEqual(p['targets'],{});self.assertEqual(p['shots'],[])
    def test_nonfinite_asset_value_rejected(self):
        for v in (float('nan'),float('inf'),-1):
            with self.assertRaises(DirectorError): Asset.from_dict(sample_asset(price=v).to_dict())


class ArchiveCase(LibraryFixture,unittest.TestCase):
    def archive(self,entries):
        p=self.root/'pack.zip'
        with zipfile.ZipFile(p,'w') as z:
            for name,data in entries: z.writestr(name,data)
        return self.local_file('pack.zip',p.read_bytes())
    def test_safe_member_windows_rules(self):
        for name in ('../x','C:\\x','/root','folder/CON.txt','x/evil.exe:stream','folder./a','a//b','a/../b','a/NUL','a/\x00b'):
            with self.subTest(name=name),self.assertRaises(DirectorError):safe_member(name)
    def test_extract_preserves_structure_and_skips_code(self):
        f=self.archive([('dir/model.fbx',b'asset'),('dir/LICENSE.txt',b'rights'),('dir/run.py',b'bad')]);files=extract_zip(self.lib,f)
        self.assertEqual(len(files),2);self.assertEqual(extract_zip(self.lib,f),files)
    def test_archive_case_collision(self):
        f=self.archive([('Model.fbx',b'one'),('model.fbx',b'two')])
        with self.assertRaises(DirectorError):extract_zip(self.lib,f)
    def test_archive_parent_file_collision(self):
        f=self.archive([('x',b'file'),('x/model.fbx',b'two')])
        with self.assertRaises(DirectorError):extract_zip(self.lib,f)
    def test_archive_symlink_rejected(self):
        info=zipfile.ZipInfo('link.fbx');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
        f=self.archive([(info,b'../../secret')])
        with self.assertRaises(DirectorError):extract_zip(self.lib,f)
    def test_gltf_external_uri_rejected(self):
        p=self.root/'model.gltf';p.write_text(json.dumps({'asset':{'version':'2.0'},'buffers':[{'uri':'https://evil.test/data'}]}))
        with self.assertRaises(DirectorError):gltf_dependencies(p,self.root)
    def test_gltf_local_dependency(self):
        p=self.root/'model.gltf';(self.root/'mesh.bin').write_bytes(b'data');p.write_text(json.dumps({'buffers':[{'uri':'mesh.bin'}]}))
        gltf_dependencies(p,self.root)
    def test_gltf_missing_dependency(self):
        p=self.root/'model.gltf';p.write_text(json.dumps({'buffers':[{'uri':'missing.bin'}]}))
        with self.assertRaises(DirectorError):gltf_dependencies(p,self.root)


class NetworkCase(unittest.TestCase):
    def test_url_policy(self):
        for url in ('http://example.com/x','https://user:pass@example.com','https://example.com:8080/x','https://evil.com/x','https://example.com/x#fragment'):
            with self.subTest(url=url),self.assertRaises(DirectorError):check_url(url,{'example.com'})
        self.assertEqual(check_url('https://example.com/x?q=1',{'example.com'}),('example.com','/x?q=1'))
    def test_private_dns_rejected(self):
        for ip in ('127.0.0.1','10.0.0.1','169.254.169.254','::1'):
            with patch('socket.getaddrinfo',return_value=[(None,None,None,None,(ip,443))]):
                with self.assertRaises(DirectorError):public_addresses('example.com')
    def test_mixed_public_private_dns_rejected(self):
        with patch('socket.getaddrinfo',return_value=[(None,None,None,None,('1.1.1.1',443)),(None,None,None,None,('127.0.0.1',443))]):
            with self.assertRaises(DirectorError):public_addresses('example.com')
    def test_provider_states_honest(self):
        with patch.dict('os.environ',{},clear=True):
            p=capabilities();self.assertEqual(p['sketchfab']['download'],'AUTH_REQUIRED');self.assertEqual(p['mixamo']['search'],'MANUAL_ONLY')


class MotionCase(unittest.TestCase):
    def samples(self,moving_limbs=True):
        return [{'frame':i,'root':[i*.1,0,1],'hips':[i*.1,0,1],'foot_l':[i*.1+(math.sin(i)*.1 if moving_limbs else 0),0,.05], 'foot_r':[i*.1,0,.05]} for i in range(10)]
    def test_fps_conversion(self):self.assertAlmostEqual(frame_convert(31,30,24,source_start=1,target_start=1),25)
    def test_fps_invalid(self):
        with self.assertRaises(DirectorError):frame_convert(1,0,24)
    def test_alias_mapping(self):
        r=identify_roles([{'name':x} for x in ('mixamorig:Hips','mixamorig:LeftUpLeg','DEF-foot.R')]);self.assertEqual(r['roles']['hips'],'mixamorig:Hips');self.assertIn('foot_r',r['roles'])
    def test_alias_ambiguity(self):self.assertIn('hips',identify_roles([{'name':'hips'},{'name':'pelvis'}])['ambiguous'])
    def test_unskinned_target(self):
        r={'roles':{},'ambiguous':{},'fingerprint':'x'};self.assertEqual(mapping_plan(r,r)['status'],'NEEDS_RIGGING')
    def test_rigid_motion_not_gait(self):self.assertIn('NO_NONTRIVIAL_LIMB_MOTION',quality(self.samples(False),2,24)['warnings'])
    def test_limb_motion_detected(self):self.assertGreater(quality(self.samples(),2,24)['limb_relative_motion_height_ratio'],.01)
    def test_qa_does_not_claim_visual_acceptance(self):self.assertEqual(quality(self.samples(),2,24)['visual_acceptance'],'PENDING')
    def test_nan_motion_rejected(self):
        s=self.samples();s[0]['root'][0]=float('nan')
        with self.assertRaises(DirectorError):quality(s,2,24)
    def test_frames_must_increase(self):
        with self.assertRaises(DirectorError):quality(list(reversed(self.samples())),2,24)


class ProviderCase(LibraryFixture,unittest.TestCase):
    def test_local_result_not_fabricated(self):
        self.assertEqual(Providers(self.lib).search('local','walk')['results'],[])
        self.lib.put(sample_asset());self.assertEqual(len(Providers(self.lib).search('local','walk')['results']),1)
    def test_seed_is_pack_not_45_invented_clips(self):
        r=Providers(self.lib).search('quaternius','walk')['results'];self.assertEqual(len(r),1);self.assertIsNone(r[0]['asset']['metadata']['actual_clips']);self.assertEqual(r[0]['asset']['kind'],'pack')
    def test_manual_provider_returns_actionable_state(self):self.assertEqual(Providers(self.lib).search('mixamo','walk')['status'],'MANUAL_ONLY')
    def test_polyhaven_normalization_fixture(self):
        class Fake:
            def json(self,*a,**kw):return {'sand':{'name':'Sand','type':1,'tags':['sand'],'authors':{'A':'url'}}}
        r=Providers(self.lib,Fake()).search('polyhaven','sand','material');self.assertEqual(len(r['results']),1);self.assertTrue(r['results'][0]['policy']['eligible'])
    def test_ambient_v3_fixture(self):
        class Fake:
            def json(self,*a,**kw):return {'assets':[{'id':'Sand001','title':'Sand','type':'material','tags':['sand']}]}
        r=Providers(self.lib,Fake()).search('ambientcg','sand','material');self.assertEqual(len(r['results']),1)
    def test_search_schema_error_is_not_empty_success(self):
        class Fake:
            def json(self,*a,**kw):return {'oops':42}
        with self.assertRaises(DirectorError):Providers(self.lib,Fake()).search('ambientcg','sand')
    def test_offline_cache_label(self):
        p=Providers(self.lib);url='https://api.polyhaven.com/assets'
        from asset_director.core import digest
        atomic_json(self.lib.root/'cache'/(digest(url)+'.json'),{'at':0,'data':{'sand':{}}})
        with patch.object(p.http,'json',side_effect=DirectorError('NETWORK_UNAVAILABLE','offline')):
            self.assertEqual(p.cached(url,{'api.polyhaven.com'}),{'sand':{}});self.assertEqual(p.last_cache_state,'STALE_OFFLINE_CACHE')
            with self.assertRaises(DirectorError):p.cached(url,{'api.polyhaven.com'},refresh=True)

if __name__=='__main__':unittest.main()


class AcquisitionCase(LibraryFixture,unittest.TestCase):
    def test_download_checksum_and_reuse_receipt(self):
        import hashlib
        class Fake:
            def stream(self,*a,**kw):yield b'payload'
        sha=hashlib.sha256(b'payload').hexdigest()
        f=download(self.lib,'https://example.com/file','file.fbx',{'example.com'},checksum=sha,client=Fake())
        self.assertEqual(f['sha256'],sha);self.lib.verify_file(f)
    def test_failed_checksum_leaves_no_partial(self):
        class Fake:
            def stream(self,*a,**kw):yield b'payload'
        with self.assertRaises(DirectorError):download(self.lib,'https://example.com/file','file.fbx',{'example.com'},checksum='0'*64,client=Fake())
        self.assertFalse(list((self.lib.root/'downloads').glob('partial-*')))
        self.assertEqual(load_json(self.lib.root/'budget.json')['downloaded'],7)
    def test_budget_rejects_streamed_oversize(self):
        class Fake:
            def stream(self,*a,**kw):yield b'payload'
        atomic_json(self.lib.root/'budget.json',{'downloaded':0,'extracted':0,'max_download':3,'max_extract':100})
        with self.assertRaises(DirectorError):download(self.lib,'https://example.com/file','file.fbx',{'example.com'},client=Fake())
    def test_unknown_rights_cannot_be_imported(self):
        a=sample_asset(kind='model',license_id='UNKNOWN',local_files=[self.local_file()]);self.lib.put(a)
        with self.assertRaises(DirectorError):jobs.prepare(self.lib,'import',asset_id=a.id)
        # Indexing/inspection is distinct from approving reuse in a commercial project.
        self.assertEqual(jobs.prepare(self.lib,'index',asset_id=a.id)['state'],'PLANNED')
    def test_parent_relative_gltf_inside_package_allowed(self):
        (self.root/'models').mkdir();(self.root/'textures').mkdir();(self.root/'textures'/'color.png').write_bytes(b'image')
        p=self.root/'models'/'a.gltf';p.write_text(json.dumps({'images':[{'uri':'../textures/color.png'}]}))
        self.assertEqual(gltf_dependencies(p,self.root),['textures/color.png'])
    def test_parent_relative_gltf_outside_package_rejected(self):
        (self.root/'package').mkdir();(self.root/'private.png').write_bytes(b'private')
        p=self.root/'package'/'a.gltf';p.write_text(json.dumps({'images':[{'uri':'../private.png'}]}))
        with self.assertRaises(DirectorError):gltf_dependencies(p,self.root/'package')


class HttpFlowCase(unittest.TestCase):
    def run_flow(self,responses,hosts,auth=None):
        from contextlib import ExitStack
        captured=[]
        class Context:
            def wrap_socket(self,raw,**kwargs):return raw
        class Conn:
            def __init__(self,*args,**kwargs):self._context=Context();self.host=args[0]
            def request(self,method,path,headers):captured.append((self.host,headers))
            def getresponse(self):return responses.pop(0)
            def close(self):pass
        with ExitStack() as stack:
            stack.enter_context(patch('asset_director.acquire.public_addresses',return_value=['1.1.1.1']))
            stack.enter_context(patch('asset_director.acquire.socket.create_connection',return_value=object()))
            stack.enter_context(patch('asset_director.acquire.http.client.HTTPSConnection',Conn))
            output=HTTP().bytes('https://api.example.com/start',hosts,auth=auth)
        return output,captured
    def response(self,status,headers=None,body=b'ok'):
        import io
        class Response:
            def __init__(self):self.status=status;self.data=io.BytesIO(body)
            def getheader(self,name,default=None):return (headers or {}).get(name,default)
            def read(self,n):return self.data.read(n)
            def close(self):pass
        return Response()
    def test_cross_host_redirect_drops_authorization(self):
        out,calls=self.run_flow([self.response(302,{'Location':'https://cdn.example.com/file'}),self.response(200,{'Content-Length':'2'})],{'api.example.com','cdn.example.com'},('api.example.com','Token private'))
        self.assertEqual(out,b'ok');self.assertIn('Authorization',calls[0][1]);self.assertNotIn('Authorization',calls[1][1])
    def test_disallowed_redirect_is_blocked(self):
        with self.assertRaises(DirectorError):self.run_flow([self.response(302,{'Location':'https://evil.test/file'})],{'api.example.com'})
    def test_truncated_response_fails(self):
        with self.assertRaises(DirectorError):self.run_flow([self.response(200,{'Content-Length':'8'})],{'api.example.com'})
    def test_access_error_is_not_success(self):
        with self.assertRaises(DirectorError):self.run_flow([self.response(403)],{'api.example.com'})
