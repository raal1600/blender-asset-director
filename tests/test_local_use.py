"""Synthetic declarations only; never human licensing or live asset evidence."""
import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from asset_director.core import Library, DirectorError, atomic_json, digest, rights
from asset_director.intake import intake
from asset_director.local_use import validate, job_binding
from asset_director.workbench_intake import validate_evidence
from asset_director import jobs


def confirmation():
    return {'policy':'local-project-use-v1', 'confirmed':True, 'source_id':'src_'+'a'*36,
            'source_version':'b'*64, 'member':'model.blend', 'project_id':'prj_'+'c'*36,
            'confirmed_at':'2026-09-21T12:00:00Z'}


def evidence():
    return {'title':'Synthetic fixture', 'kind':'model', 'source_url':'', 'license_id':'UNKNOWN',
            'license_url':'', 'author':'', 'price':0, 'attested':True, 'tags':['environment'],
            'local_confirmation':confirmation()}


class LocalUse(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'originals';self.source.mkdir()
        (self.source/'model.blend').write_bytes(b'Synthetic policy bytes; not a Blender execution test')
        self.evidence_file=self.root/'evidence.json';atomic_json(self.evidence_file,evidence())
        self.lib=Library(self.root/'catalog');self.addCleanup(self.lib.close)

    def prepare(self):
        return self.lib.get(intake(self.lib,str(self.source),str(self.evidence_file),
                           preserve_existing=True,prepared_member='model.blend')['asset_id'])

    def test_exact_confirmation_does_not_invent_a_license_or_author(self):
        before=evidence();validate_evidence(before);self.assertEqual(before,evidence())
        a=self.prepare();gate=rights(a,lib=self.lib)
        self.assertTrue(gate['eligible']);self.assertEqual(a.license_id,'UNKNOWN')
        self.assertEqual((a.author,a.source_url,a.license_url),('','',''))
        self.assertEqual(gate['basis'],'USER_CONFIRMED_LOCAL_USE')
        self.assertEqual(gate['model_training'],'NOT_AUTHORIZED')
        self.assertFalse(rights(a,lib=self.lib,purpose='raw_redistribution')['eligible'])
        del a.metadata['local_use_confirmation']
        self.assertFalse(rights(a,lib=self.lib)['eligible'],'Unknown licenses do not become globally permitted')

    def test_false_scope_paid_or_invented_metadata_refused_before_intake(self):
        for change in ({'confirmed':False},{'confirmed':'true'},{'policy':'all-future-files'},
                       {'member':'../secret.blend'},{'source_version':'invalid'},
                       {'confirmed_at':'yesterday'},{'confirmed_at':'2026-09-21'}, {'future_files':True}):
            e=evidence();e['local_confirmation'].update(change)
            with self.subTest(change=change),self.assertRaises(DirectorError):validate_evidence(e)
        for change in ({'author':'Guessed creator'},{'license_id':'CC0-1.0'},{'price':2}, {'attested':False},
                       {'source_url':'https://invented.invalid'}, {'license_url':'https://invented.invalid'}):
            with self.subTest(change=change),self.assertRaises(DirectorError):validate_evidence({**evidence(),**change})
        with self.assertRaises(DirectorError):intake(self.lib,str(self.source),str(self.evidence_file),prepared_member='model.blend')
        with self.assertRaises(DirectorError):intake(self.lib,str(self.source),str(self.evidence_file),preserve_existing=True,prepared_member='other.blend')
        self.assertEqual(self.lib.all(),[]);self.assertEqual(list((self.lib.root/'incoming').iterdir()),[])

    def test_request_must_match_the_confirmed_version_and_member(self):
        request={'id':confirmation()['source_id'],'version':'b'*64,'file':'model.blend'}
        validate(confirmation(),request)
        for change in ({'id':'src_'+'d'*36},{'version':'e'*64},{'file':'other.blend'}):
            with self.subTest(change=change),self.assertRaises(DirectorError):validate(confirmation(),{**request,**change})

    def test_existing_reviewed_or_blocked_catalog_evidence_is_preserved(self):
        a=self.prepare();del a.metadata['local_use_confirmation'];a.author='Retained reviewer'
        self.lib.put(a);before=a.to_dict()
        self.assertFalse(rights(a,lib=self.lib)['eligible'])
        after=self.prepare();self.assertEqual(before,after.to_dict())
        self.assertFalse(rights(after,lib=self.lib)['eligible'])

    def test_tampered_confirmation_and_conflicting_restricted_grant_fail_closed(self):
        original=self.prepare()
        for change in ({'scope':'public-redistribution'},{'prepared_member':None},{'files_sha256':'0'*64}, {'id':'lc_'+'0'*64}):
            a=copy.deepcopy(original);a.metadata['local_use_confirmation'].update(change)
            self.assertFalse(rights(a,lib=self.lib)['eligible'])
        for change in ({'license_grant':'old-restricted-grant'},{'local_motion':{'provider_hint':'mixamo'}}):
            a=copy.deepcopy(original);a.metadata.update(change);self.assertFalse(rights(a,lib=self.lib)['eligible'])
        for bad in (None,False,[],{'bad':'record'}):
            a=copy.deepcopy(original);a.metadata['local_use_confirmation']=bad
            self.assertFalse(rights(a,lib=self.lib)['eligible'])

    def test_native_job_binds_exact_confirmation_and_refuses_later_metadata_change(self):
        a=self.prepare();job=jobs.prepare(self.lib,'asset-contents',asset_id=a.id,options={'file':a.metadata['prepared_member']})
        self.assertEqual(job['specification']['local_use'],job_binding(a));jobs.read_job(self.lib,job['id'])
        record=a.metadata['local_use_confirmation'];record['confirmation']['confirmed_at']='2026-09-22T12:00:00Z'
        record['id']='lc_'+digest({k:v for k,v in record.items() if k!='id'});self.lib.put(a)
        self.assertTrue(rights(a,lib=self.lib)['eligible'])
        with self.assertRaises(DirectorError):jobs.read_job(self.lib,job['id'])


if __name__=='__main__':unittest.main()
