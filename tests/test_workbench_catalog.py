"""Portable catalog/import contracts, not Blender execution evidence."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from asset_director.core import Asset, Library, DirectorError, file_hash
from asset_director import jobs
from asset_director.workbench_catalog import catalog


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
    def test_query_and_identity_bounds(self):
        for args in [{'limit':51},{'offset':-1},{'limit':True},{'query':'a'*2001},{'asset_id':'../../outside'},{'verify':True}]:
            with self.subTest(args=args),self.assertRaises(DirectorError):catalog(self.lib,**args)

if __name__=='__main__':unittest.main()
