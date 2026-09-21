"""Portable catalog/import contracts, not Blender execution evidence."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from asset_director.core import Asset, Library, DirectorError, file_hash
from asset_director import jobs
from asset_director.workbench_catalog import catalog, production_catalog_ids


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.lib=Library(Path(self.temp.name)/'library');self.addCleanup(self.lib.close)
        self.source=self.lib.root/'incoming'/'model.blend'
        self.source.write_bytes(b'BLENDER synthetic contract fixture, not a valid Blender scene')
        self.asset=Asset('local','fixture-source','Example character','model','https://example.invalid/source',
                         'CC0-1.0','https://example.invalid/license','Synthetic fixture',0,True,['.blend'],[],
                         'user_attested',[{'path':'incoming/model.blend','sha256':file_hash(self.source),'size':self.source.stat().st_size}])
        self.lib.put(self.asset)
    def test_search_paging_is_explicit_and_selection_is_not_import(self):
        page=catalog(self.lib,'character',0,1)
        self.assertEqual(page['total'],1);self.assertIsNone(page['next_offset'])
        item=page['items'][0];self.assertFalse(item['verified']);self.assertEqual(item['models'],['incoming/model.blend'])
        self.assertNotIn('in_scene',item);self.assertEqual(catalog(self.lib,'missing')['total'],0)
        self.assertEqual(catalog(self.lib,offset=1)['items'],[])
    def test_selection_verifies_bytes_and_metadata_refresh_does_not_change_pin(self):
        before=catalog(self.lib,asset_id=self.asset.id,verify=True)
        self.asset.checked_at+=1;self.lib.put(self.asset)
        self.assertEqual(catalog(self.lib,asset_id=self.asset.id)['version'],before['version'])
        self.source.write_bytes(b'changed')
        with self.assertRaisesRegex(DirectorError,'Input missing or changed'):catalog(self.lib,asset_id=self.asset.id,verify=True)
    def test_rights_changes_change_pinned_identity(self):
        before=catalog(self.lib,asset_id=self.asset.id)
        self.asset.license_id='UNKNOWN';self.lib.put(self.asset)
        after=catalog(self.lib,asset_id=self.asset.id)
        self.assertNotEqual(before['version'],after['version']);self.assertFalse(after['policy']['eligible'])
    def test_explicit_import_file_and_collections_reject_unowned_or_duplicate_inputs(self):
        job=jobs.prepare(self.lib,'import',asset_id=self.asset.id,options={'file':'incoming/model.blend','selection':['Set']})
        self.assertEqual(job['specification']['options']['selection'],['Set'])
        for patch in [{'file':'../../outside.blend'},{'file':'incoming/other.blend'}, {'selection':['Set','Set']}, {'selection':[]},{'selection':'all'},{'script':'print(1)'}]:
            with self.subTest(patch=patch),self.assertRaises(DirectorError):jobs.prepare(self.lib,'import',asset_id=self.asset.id,options=patch)
    def test_collection_inspection_is_source_only_and_does_not_create_mutable_output(self):
        job=jobs.prepare(self.lib,'asset-contents',asset_id=self.asset.id,options={'file':'incoming/model.blend'})
        self.assertEqual(job['specification']['inputs'],[]);self.assertNotIn('asset-contents',jobs.MUTATIONS)
        self.assertFalse((self.lib.root/'jobs'/job['id']/'result.blend').exists())
        with self.assertRaises(DirectorError):jobs.prepare(self.lib,'asset-contents',str(self.source),self.asset.id,{'file':'incoming/model.blend'})
    def test_catalog_metadata_is_not_import_authorization(self):
        self.asset.evidence='unverified';self.lib.put(self.asset)
        item=catalog(self.lib,asset_id=self.asset.id,verify=True)
        self.assertTrue(item['verified']);self.assertFalse(item['policy']['eligible'])
        with self.assertRaises(DirectorError):jobs.prepare(self.lib,'import',asset_id=self.asset.id,options={'file':'incoming/model.blend','selection':['Set']})
    def test_kind_groups_filter_before_pagination_without_rewriting_catalog(self):
        from dataclasses import replace
        for i in range(60):
            self.lib.put(replace(self.asset, source_id='scope-'+str(i), title='Scoped '+str(i),
                                 kind=['model','pack','animation','material','hdri'][i % 5]))
        before=[a.to_dict() for a in self.lib.all()]
        world=catalog(self.lib,kinds=['model','pack'])
        self.assertEqual(world['total'],25);self.assertEqual(len(world['items']),24)
        self.assertEqual(len(catalog(self.lib,kinds=['model','pack'],offset=24)['items']),1)
        self.assertTrue(all(a['kind'] in {'model','pack'} for a in world['items']))
        self.assertEqual(catalog(self.lib,kinds=['animation'])['total'],12)
        self.assertEqual(catalog(self.lib,kinds=['material','hdri'])['total'],24)
        self.assertEqual(catalog(self.lib,kinds=['model','pack'],kind='animation')['total'],0)
        self.assertEqual([a.to_dict() for a in self.lib.all()],before)
        for kinds in [[],['wrong'],['model','model'],'model',[{}],True]:
            with self.subTest(kinds=kinds),self.assertRaises(DirectorError):catalog(self.lib,kinds=kinds)
    def test_query_and_identity_bounds(self):
        for args in [{'limit':51},{'offset':-1},{'limit':True},{'query':'a'*2001},{'asset_id':'../../outside'},{'verify':True}]:
            with self.subTest(args=args),self.assertRaises(DirectorError):catalog(self.lib,**args)

    def test_production_exclusion_precedes_count_and_paging_and_retains_source_versions(self):
        from dataclasses import replace
        for i in range(60):
            self.lib.put(replace(self.asset, source_id='exclude-'+str(i), title='Library '+str(i).zfill(3)))
        before=[a.to_dict() for a in self.lib.all()]
        rows=catalog(self.lib,limit=50)['items']
        excluded=[a['id'] for a in rows[:25]]
        first=catalog(self.lib,exclude_ids=excluded)
        self.assertEqual(first['total'],36);self.assertEqual(len(first['items']),24)
        self.assertFalse(set(excluded)&{a['id'] for a in first['items']})
        last=catalog(self.lib,exclude_ids=excluded,offset=9999)
        self.assertEqual(last['offset'],24);self.assertEqual(len(last['items']),12);self.assertIsNone(last['next_offset'])
        self.assertEqual(catalog(self.lib,exclude_ids=excluded,query='character')['total'],0)
        self.assertEqual([a.to_dict() for a in self.lib.all()],before)
        self.asset.license_id='UNKNOWN';self.lib.put(self.asset)
        self.assertEqual(catalog(self.lib,exclude_ids=excluded,query='character')['total'],0)
        self.assertEqual(catalog(self.lib,query='character')['total'],1)
        for bad in ['all',[{}],['../other'],[self.asset.id]*2,[self.asset.id]*2001]:
            with self.subTest(bad=bad),self.assertRaises(DirectorError):catalog(self.lib,exclude_ids=bad)

    def test_project_exclusion_reads_only_valid_retained_pins_and_does_not_verify_changed_sources(self):
        import json
        file=Path(self.temp.name)/'project.json'
        pin=catalog(self.lib,asset_id=self.asset.id)
        project={'owner':'asset-director-launcher','workbench':{'catalogPins':[{'id':pin['id'],'version':pin['version']}]}}
        file.write_text(json.dumps(project));before=file.read_bytes()
        self.source.write_bytes(b'changed original for explicit stale-source test')
        self.assertEqual(production_catalog_ids(file),[self.asset.id]);self.assertEqual(file.read_bytes(),before)
        for value in [{},[],{'owner':'other'},dict(project,workbench={'catalogPins':[{'id':'bad','version':'v'}]})]:
            file.write_text(json.dumps(value))
            with self.subTest(value=value),self.assertRaises(DirectorError):production_catalog_ids(file)


    def test_inspection_scope_partitions_project_owned_jobs_and_refuses_arbitrary_strings(self):
        import uuid
        options={'file':'incoming/model.blend','request_scope':'prj_'+str(uuid.uuid4())+':sc_'+str(uuid.uuid4())}
        first=jobs.prepare(self.lib,'asset-contents',asset_id=self.asset.id,options=options)
        options['request_scope']='prj_'+str(uuid.uuid4())+':sc_'+str(uuid.uuid4())
        second=jobs.prepare(self.lib,'asset-contents',asset_id=self.asset.id,options=options)
        self.assertNotEqual(first['id'],second['id'])
        for scope in [None,42,{},'../../unrelated','python evil.py']:
            options['request_scope']=scope
            with self.subTest(scope=scope),self.assertRaises(DirectorError):
                jobs.prepare(self.lib,'asset-contents',asset_id=self.asset.id,options=options)

if __name__=='__main__':unittest.main()
