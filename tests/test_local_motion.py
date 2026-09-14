"""Offline inbox/grant/torso regressions. Bytes and license evidence are synthetic."""
import copy
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from asset_director import jobs, local_motion as lm, license_policy as lp, motion_assets as ma
from asset_director.core import DirectorError, Library, atomic_json, file_hash, load_json, rights
from asset_director.motion import identify_roles
from asset_director.motion_scout import search
from test_motion_foundation import example


def stable(path, content=b'SYNTHETIC_NOT_FBX'):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
    t=time.time()-10;os.utime(path,(t,t));return path


def review_request(lib, future=False):
    evidence=[]
    for name,url in [('faq',lp.FAQ),('terms',lp.TERMS)]:
        p=lib.root/'licenses'/('synthetic-'+name+'.txt')
        if not p.exists():p.write_text('Synthetic evidence only; not actual Adobe terms or permission.')
        evidence.append({'url':url,'file':lp.file_ref(lib,p.relative_to(lib.root).as_posix())})
    return {'policy':lp.POLICY,'reviewer':'synthetic-test','reviewed_at':'2026-09-14T00:00:00Z',
            'official_downloads_attested':True,'terms_reviewed':True,'include_future_files':future,'evidence':evidence}


class LocalMotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name).resolve();self.folder=self.base/'source'/'Mixamo';self.folder.mkdir(parents=True)
        self.lib=Library(self.base/'catalog');self.addCleanup(self.lib.close)
        self.root=lm.add_root(self.lib,str(self.folder),'mixamo')['root'];self.source=stable(self.folder/'Moonwalk.fbx')
    def sync_asset(self):
        r=lm.sync(self.lib,self.root['id']);return self.lib.get(r['roots'][0]['assets'][0]['asset_id'])
    def approve(self,future=False):
        return lm.review_root(self.lib,self.root['id'],review_request(self.lib,future))['review_id']
    def test_registration_is_idempotent_and_not_approval(self):
        r=lm.add_root(self.lib,str(self.folder),'mixamo');self.assertEqual(r['status'],'REUSED')
        self.assertIsNone(r['root']['review_id']);self.assertEqual(len(lm.roots(self.lib)['roots']),1)
    def test_overlapping_roots_refused(self):
        for p in (self.folder,self.folder.parent,self.lib.root,self.base):
            with self.subTest(path=p),self.assertRaises(DirectorError):lm.add_root(self.lib,str(p),'unknown')
    def test_missing_directory_not_created(self):
        p=self.base/'absent'
        with self.assertRaises(OSError):lm.add_root(self.lib,str(p),'mixamo')
        self.assertFalse(p.exists())
    def test_original_and_repeat_catalog_bytes_unchanged(self):
        before=file_hash(self.source),self.source.stat().st_mtime_ns
        a=self.sync_asset();p=self.lib.root/'manifests'/(a.id+'.json');saved=p.read_bytes(),p.stat().st_mtime_ns
        self.assertEqual(self.sync_asset().to_dict(),a.to_dict())
        self.assertEqual((p.read_bytes(),p.stat().st_mtime_ns),saved)
        self.assertEqual((file_hash(self.source),self.source.stat().st_mtime_ns),before)
        self.assertEqual(list(self.folder.iterdir()),[self.source])
    def test_folder_named_mixamo_does_not_authorize_import(self):
        a=self.sync_asset();self.assertFalse(rights(a,lib=self.lib)['eligible'])
        self.assertEqual(lm.preflight(self.lib,a.id)['import'],'BLOCKED')
        with self.assertRaises(DirectorError) as e:jobs.prepare(self.lib,'import',asset_id=a.id)
        self.assertEqual(e.exception.code,'BLOCKED_POLICY')
    def test_changed_content_preserves_previous_asset(self):
        old=self.sync_asset();stable(self.source,b'NEW CONTENT');new=self.sync_asset()
        self.assertNotEqual(new.id,old.id);self.lib.verify_file(old.local_files[0]);self.assertEqual(len(self.lib.all()),2)
    def test_rename_dedup_and_alias(self):
        a=self.sync_asset();self.source.rename(self.folder/'Backslide.fbx');r=lm.sync(self.lib)
        self.assertEqual(len(self.lib.all()),1);self.assertEqual(r['roots'][0]['assets'][0]['asset_id'],a.id)
        self.assertEqual(self.lib.get(a.id).metadata['local_motion']['source_names'],['Backslide.fbx','Moonwalk.fbx'])
        self.assertIn('Moonwalk.fbx',r['roots'][0]['retained_missing_sources'])
        self.assertTrue(search(self.lib,'backslide','commercial')['results'])
    def test_duplicate_content_copies_once(self):
        stable(self.folder/'Another.fbx');lm.sync(self.lib);self.assertEqual(len(self.lib.all()),1)
        self.assertEqual(len(list((self.lib.root/'incoming').rglob('*.fbx'))),1)
    def test_deleted_source_keeps_verified_private_copy(self):
        a=self.sync_asset();self.source.unlink();r=lm.sync(self.lib);self.lib.verify_file(a.local_files[0])
        self.assertEqual(r['roots'][0]['retained_missing_sources'],['Moonwalk.fbx'])
    def test_offline_root_not_empty_success(self):
        self.sync_asset();self.folder.rename(self.base/'unmounted');r=lm.sync(self.lib)
        self.assertEqual(r['status'],'PARTIAL_OR_BLOCKED');self.assertEqual(r['roots'][0]['status'],'ROOT_UNAVAILABLE')
        self.assertEqual(r['roots'][0]['retained_missing_sources'],[])
    def test_growing_download_deferred(self):
        self.source.write_bytes(b'GROWING');r=lm.sync(self.lib)
        self.assertFalse(self.lib.all());self.assertEqual(r['roots'][0]['notes'][0]['status'],'SOURCE_UNSTABLE')
    def test_temporary_download_extension_ignored(self):
        stable(self.folder/'New.fbx.part');self.assertEqual(len(lm.scan(self.lib,self.root['id'])['files']),1)
    def test_missing_converters_and_package_intake_reported(self):
        for ext in ('.amc','.npz','.gltf','.blend'):stable(self.folder/('take'+ext))
        r=lm.scan(self.lib,self.root['id']);self.assertEqual(len(r['notes']),4);self.assertEqual(len(r['files']),1)
    def test_file_budget_partial_not_false_complete(self):
        stable(self.folder/'Second.fbx',b'DIFFERENT');r=lm.sync(self.lib,max_new_files=1)
        self.assertEqual(r['status'],'PARTIAL_OR_BLOCKED');self.assertEqual(len(self.lib.all()),1)
    def test_entry_limit(self):
        with patch.object(lm,'MAX_ENTRIES',0):r=lm.scan(self.lib,self.root['id'])
        self.assertEqual(r['status'],'RESOURCE_LIMIT');self.assertFalse(r['complete'])
    def test_depth_limit(self):
        stable(self.folder/'a'/'b'/'c'/'d'/'e'/'too-deep.fbx');r=lm.scan(self.lib,self.root['id'])
        self.assertEqual(r['status'],'RESOURCE_LIMIT')
    def test_symlink_not_followed(self):
        p=stable(self.base/'private.fbx',b'PRIVATE')
        try:(self.folder/'link.fbx').symlink_to(p)
        except OSError:self.skipTest('Account cannot create symlinks')
        r=lm.scan(self.lib,self.root['id']);self.assertIn('SOURCE_LINK_REFUSED',[n['status'] for n in r['notes']])
        self.assertEqual(len(r['files']),1)
    def test_reparse_point_refused_portably(self):
        original=Path.lstat
        def mock(p,*args,**kw):
            s=original(p,*args,**kw)
            if p!=self.source:return s
            from types import SimpleNamespace
            return SimpleNamespace(st_mode=s.st_mode,st_file_attributes=0x400)
        with patch.object(Path,'lstat',mock),self.assertRaises(DirectorError):lm.safe_path(self.source)
    def test_provenance_conflict_not_opportunistic_relicense(self):
        self.sync_asset();other=self.base/'Other';other.mkdir();stable(other/'same.fbx')
        lm.add_root(self.lib,str(other),'cmu');r=lm.sync(self.lib)
        self.assertEqual(r['roots'][1]['assets'][0]['status'],'PROVENANCE_CONFLICT')
    def test_corrupt_private_copy_not_overwritten(self):
        a=self.sync_asset();(self.lib.root/a.local_files[0]['path']).write_bytes(b'EDITED');r=lm.sync(self.lib)
        self.assertEqual(r['roots'][0]['assets'][0]['status'],'STALE_INPUT')
    def test_no_implicit_blender_or_network(self):
        with patch('asset_director.jobs.run',side_effect=AssertionError('worker')),patch('asset_director.motion_scout.Providers',side_effect=AssertionError('network')):
            a=self.sync_asset();r=search(self.lib,'moonwalk','commercial')
        self.assertEqual(r['results'][0]['id'],a.id)
    def test_index_needs_working_executable(self):
        with self.assertRaises(DirectorError):lm.sync(self.lib,index=True,blender='not-a-file')
    def test_project_use_allowed_standalone_blocked(self):
        self.approve();a=self.sync_asset();self.assertTrue(rights(a,lib=self.lib)['eligible'])
        self.assertFalse(rights(a,lib=self.lib,purpose='raw_redistribution')['eligible'])
    def test_review_is_current_hashes_unless_future_opted_in(self):
        self.approve();self.sync_asset();stable(self.folder/'New.fbx',b'NEW');r=lm.sync(self.lib)
        new=next(a for a in r['roots'][0]['assets'] if a['relative_path']=='New.fbx')
        self.assertEqual(new['readiness']['import'],'BLOCKED')
    def test_explicit_future_inbox_opt_in(self):
        self.approve(True);stable(self.folder/'New.fbx',b'NEW');r=lm.sync(self.lib)
        self.assertTrue(all(a['readiness']['policy']['eligible'] for a in r['roots'][0]['assets']))
    def test_missing_attestation(self):
        q=review_request(self.lib);q['official_downloads_attested']=False
        with self.assertRaises(DirectorError):lm.review_root(self.lib,self.root['id'],q)
        self.assertIsNone(lm.roots(self.lib)['roots'][0]['review_id'])
    def test_missing_terms(self):
        q=review_request(self.lib);q['evidence'].pop()
        with self.assertRaises(DirectorError):lm.review_root(self.lib,self.root['id'],q)
    def test_arbitrary_custom_profile_is_not_bypass(self):
        q=review_request(self.lib);q['policy']='allow-anything'
        with self.assertRaises(DirectorError):lm.review_root(self.lib,self.root['id'],q)
    def test_other_provider_cannot_adopt_mixamo_license(self):
        p=self.base/'CMU';p.mkdir();stable(p/'Other.fbx');r=lm.add_root(self.lib,str(p),'cmu')['root']
        with self.assertRaises(DirectorError):lm.review_root(self.lib,r['id'],review_request(self.lib))
    def test_revocation_blocks_prepared_and_completed_reuse(self):
        review=self.approve();a=self.sync_asset();j=jobs.prepare(self.lib,'import',asset_id=a.id)
        p=self.lib.root/'jobs'/j['id']/'job.json';j['state']='SUCCEEDED';atomic_json(p,j)
        lp.revoke(self.lib,review,'test')
        self.assertFalse(rights(a,lib=self.lib)['eligible'])
        with self.assertRaises(DirectorError) as e:jobs.read_job(self.lib,j['id'])
        self.assertEqual(e.exception.code,'LICENSE_REVOKED');self.assertTrue(self.source.exists())
    def test_review_tampering_detected(self):
        rid=self.approve();a=self.sync_asset();p=self.lib.root/'licenses/reviews'/(rid+'.json');r=load_json(p)
        r['include_future_files']=True;atomic_json(p,r);self.assertFalse(rights(a,lib=self.lib)['eligible'])
    def test_evidence_tampering_blocks_execution(self):
        self.approve();a=self.sync_asset();j=jobs.prepare(self.lib,'import',asset_id=a.id)
        (self.lib.root/'licenses/synthetic-terms.txt').write_text('changed')
        with self.assertRaises(DirectorError):jobs.read_job(self.lib,j['id'])
    def test_license_label_without_grant_is_blocked(self):
        a=self.sync_asset();a.license_id=lp.LICENSE;a.price=0;self.assertFalse(rights(a,lib=self.lib)['eligible'])
    def test_grant_for_other_bytes_blocked(self):
        self.approve();a=self.sync_asset();a.source_id='another';a.local_files=[]
        self.assertFalse(rights(a,lib=self.lib)['eligible'])
    def test_relabel_existing_grant_cc0_blocked(self):
        self.approve();a=self.sync_asset();a.license_id='CC0-1.0';self.assertFalse(rights(a,lib=self.lib)['eligible'])
    def test_drop_grant_and_relabel_known_mixamo_blocked(self):
        self.approve();a=self.sync_asset();a.metadata.pop('license_grant');a.license_id='CC0-1.0'
        self.assertFalse(rights(a,lib=self.lib)['eligible'])
    def test_native_pairing_needs_index(self):
        self.approve();a=self.sync_asset()
        with self.assertRaises(DirectorError) as e:jobs.prepare(self.lib,'native-clip',asset_id=a.id)
        self.assertEqual(e.exception.code,'INDEX_REQUIRED')
    def test_native_pairing_source_only(self):
        with self.assertRaises(DirectorError) as e:jobs.prepare(self.lib,'native-clip',str(self.source))
        self.assertEqual(e.exception.code,'SOURCE_ONLY_OPERATION')
    def test_working_scene_carries_grants_to_subsequent_jobs(self):
        self.approve();a=self.sync_asset();gid=a.metadata['license_grant'];p=stable(self.base/'derived.blend',b'DERIVED')
        lp.retain_derivation(self.lib,p,[gid]);j=jobs.prepare(self.lib,'inspect',str(p))
        self.assertEqual(j['specification']['license_grants'],[gid])
    def test_canonical_rights_bind_source_content(self):
        self.approve();a=self.sync_asset();r=lp.canonical_rights(self.lib,[a.metadata['license_grant']])
        source={'raw_files':[{k:f[k] for k in ('sha256','size')} for f in a.local_files]}
        lp.validate_motion_scope(self.lib,source,r);source['raw_files'][0]['sha256']='f'*64
        with self.assertRaises(DirectorError):lp.validate_motion_scope(self.lib,source,r)
    def test_restricted_motion_cannot_allow_raw_distribution(self):
        self.approve();a=self.sync_asset();r=lp.canonical_rights(self.lib,[a.metadata['license_grant']]);r['raw_redistribution']='allowed'
        self.assertFalse(ma.rights_gate({'provider':'mixamo'},r,'commercial',lib=self.lib)['eligible'])
    def test_canonical_roundtrip_and_revocation(self):
        rid=self.approve();a=self.sync_asset();r,payload,_=example(self.lib,self.base)
        r.pop('id');r['rights']=lp.canonical_rights(self.lib,[a.metadata['license_grant']]);r['source']['provider']='mixamo'
        r['source']['raw_files']=[{k:f[k] for k in ('sha256','size')} for f in a.local_files]
        saved=ma.store(self.lib,r,payload);loaded,_=ma.load(self.lib,saved['motion_id'])
        self.assertEqual(loaded['rights']['raw_redistribution'],'denied')
        lp.revoke(self.lib,rid,'test')
        with self.assertRaises(DirectorError):ma.load(self.lib,saved['motion_id'])
    def test_canonical_mixamo_cc0_without_grant_blocked(self):
        r,_,_=example(self.lib,self.base)
        self.assertFalse(ma.rights_gate({'provider':'mixamo'},r['rights'],'commercial',lib=self.lib)['eligible'])
    def test_unknown_not_allowed_by_noncommercial_flag(self):
        self.assertFalse(rights(self.sync_asset(),commercial=False,lib=self.lib)['eligible'])


class TorsoTests(unittest.TestCase):
    def chain(self,prefix='mixamorig:'):
        names=['Hips','Spine','Spine1','Spine2','Neck','Head']
        return [{'name':prefix+n,'parent':prefix+names[i-1] if i else None} for i,n in enumerate(names)]
    def test_distinct_namespaced_torso(self):
        r=identify_roles(self.chain());self.assertEqual(r['roles']['spine'],'mixamorig:Spine')
        self.assertEqual(r['roles']['spine_mid'],'mixamorig:Spine1');self.assertEqual(r['roles']['chest'],'mixamorig:Spine2')
        self.assertNotIn('spine',r['ambiguous'])
    def test_unnamespaced_chain(self):self.assertTrue(identify_roles(self.chain(''))['torso_chain'])
    def test_broken_chain_stays_ambiguous(self):
        b=self.chain();b[2]['parent']='mixamorig:Hips';r=identify_roles(b)
        self.assertIn('spine',r['ambiguous']);self.assertIsNone(r['torso_chain'])
    def test_duplicate_alias_not_arbitrary_choice(self):
        b=self.chain()+[{'name':'other:Spine','parent':'mixamorig:Hips'}]
        self.assertIn('spine',identify_roles(b)['ambiguous'])
    def test_missing_parent_evidence_not_verified(self):
        self.assertIsNone(identify_roles([{'name':b['name']} for b in self.chain()])['torso_chain'])
    def test_old_single_alias_compatible(self):
        self.assertEqual(identify_roles([{'name':'Spine1'}])['roles']['spine'],'Spine1')
