"""Portable preview guards, not Blender or visual acceptance."""
from pathlib import Path
from tempfile import TemporaryDirectory
import copy
import unittest
from asset_director.core import Asset, Library, DirectorError, atomic_json, file_hash
from asset_director.asset_preview import snapshot
from asset_director.catalog_presentation import classification, reference_image
from asset_director.workbench_catalog import catalog
from asset_director import jobs


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'original';self.source.mkdir()
        self.file=self.source/'model.glb';self.file.write_bytes(b'synthetic contract bytes, not a real GLB')
        self.preview=self.root/'preview';self.preview.mkdir()
        self.request=self.preview/'request.json'
        self.data={'schema':'asset-director.asset-preview/1','id':'source-fixture','title':'Synthetic preview',
                   'version':'a'*64,'source_kind':'source','root':str(self.source),'file':'model.glb',
                   'files':[{'path':'model.glb','size':self.file.stat().st_size,'sha256':file_hash(self.file)}]}

    def run_snapshot(self,data=None):
        atomic_json(self.request,data or self.data)
        return snapshot(self.request)

    def test_copy_has_separate_library_unknown_rights_and_no_original_changes(self):
        before=file_hash(self.file);request,directory,asset=self.run_snapshot()
        self.assertEqual(file_hash(self.file),before)
        self.assertTrue(asset.metadata['preview_only']);self.assertEqual(asset.license_id,'UNKNOWN')
        self.assertEqual(file_hash(directory/asset.local_files[0]['path']),before)
        with Library(directory) as lib:
            job=jobs.prepare(lib,'asset-preview',asset_id=asset.id,options={'file':asset.local_files[0]['path']})
            self.assertEqual(job['specification']['inputs'],[])
            self.assertEqual(job['specification']['license_grants'],[])
        with self.assertRaisesRegex(DirectorError,'immutable'):self.run_snapshot()

    def test_changed_member_refused_before_snapshot_allocation(self):
        self.file.write_bytes(b'changed')
        with self.assertRaisesRegex(DirectorError,'Source changed'):self.run_snapshot()
        self.assertFalse((self.preview/'library').exists())

    def test_unknown_fields_paths_duplicate_names_budget_and_format_fail_closed(self):
        for change in [{'script':'evil'}, {'file':'../../model.glb'}, {'file':'model.zip'},
                       {'files':self.data['files']*2}, {'files':[dict(self.data['files'][0],size=513*1024*1024)]},
                       {'files':[dict(self.data['files'][0],path='../original/model.glb')],'file':'../original/model.glb'}]:
            data={**copy.deepcopy(self.data),**change}
            with self.subTest(change=change),self.assertRaises(DirectorError):self.run_snapshot(data)
            self.assertFalse((self.preview/'library').exists())

    def test_production_asset_cannot_use_preview_operation_as_an_import_bypass(self):
        with Library(self.root/'library') as lib:
            f=lib.root/'incoming/model.glb';f.write_bytes(b'fixture')
            asset=Asset('local','test','Fixture','model','',local_files=[{'path':'incoming/model.glb','size':7,'sha256':file_hash(f)}])
            lib.put(asset)
            with self.assertRaisesRegex(DirectorError,'separately copied'):jobs.prepare(lib,'asset-preview',asset_id=asset.id,options={'file':'incoming/model.glb'})

    def test_embedded_checkpoint_copies_only_exact_files_even_under_common_storage_root(self):
        data={**self.data,'root':str(self.root),'file':'original/model.glb','source_kind':'checkpoint',
              'files':[{**self.data['files'][0],'path':'original/model.glb'}]}
        atomic_json(self.request,data)
        _,directory,asset=snapshot(self.request,embedded=True)
        self.assertTrue(asset.metadata['preview_checkpoint'])
        self.assertEqual(asset.metadata['preview_original_root'],str(self.root.resolve()))
        self.assertEqual(file_hash(directory/asset.local_files[0]['path']),file_hash(self.file))
        with Library(directory) as lib:
            for value in [1,'true',None,[]]:
                with self.assertRaisesRegex(DirectorError,'boolean'):
                    jobs.prepare(lib,'asset-preview',asset_id=asset.id,options={'file':asset.local_files[0]['path'],'embedded':value})

    def test_embedded_mode_cannot_copy_from_its_own_attempt(self):
        file=self.preview/'model.glb';file.write_bytes(b'fixture')
        data={**self.data,'root':str(self.preview),'files':[{'path':'model.glb','size':file.stat().st_size,'sha256':file_hash(file)}]}
        atomic_json(self.request,data)
        with self.assertRaisesRegex(DirectorError,'own attempt'):snapshot(self.request,embedded=True)
        self.assertFalse((self.preview/'library').exists())

    def test_blend_checkpoint_uses_short_verified_copy_paths_and_exact_dependency_map(self):
        scene=self.source/'scene.blend';scene.write_bytes(b'synthetic checkpoint bytes')
        data={**self.data,'source_kind':'checkpoint','file':'scene.blend',
              'files':[{'path':'scene.blend','size':scene.stat().st_size,'sha256':file_hash(scene)},*self.data['files']]}
        atomic_json(self.request,data)
        _,directory,asset=snapshot(self.request,embedded=True)
        self.assertEqual(asset.metadata['preview_member'],'incoming/package/f0000.blend')
        self.assertEqual(asset.metadata['preview_source_map'],{'incoming/package/f0000.blend':'scene.blend','incoming/package/f0001.glb':'model.glb'})
        self.assertEqual(asset.metadata['preview_original_member'],'scene.blend')
        for record,original in zip(asset.local_files,data['files']):
            self.assertEqual(record['sha256'],original['sha256'])
            self.assertEqual(file_hash(directory/record['path']),file_hash(self.source/original['path']))
        self.assertEqual(scene.read_bytes(),b'synthetic checkpoint bytes')

    def test_taxonomy_is_factual_and_filters_before_paging_without_record_mutation(self):
        a=Asset('local','a','Character in marketing name','model','')
        self.assertEqual(classification(a)['id'],'model')
        a.tags=['rigged'];self.assertEqual(classification(a)['id'],'rigged-model')
        a.metadata['subcategory']='prop';self.assertEqual(classification(a)['id'],'prop')
        with Library(self.root/'taxonomy') as lib:
            f=lib.root/'incoming/model.glb';f.write_bytes(b'fixture')
            a.local_files=[{'path':'incoming/model.glb','size':7,'sha256':file_hash(f)}]
            for i in range(55):
                a.source_id=str(i);a.metadata={'subcategory':'character' if i%2 else 'environment'};lib.put(a)
            before=[a.to_dict() for a in lib.all()]
            self.assertEqual(catalog(lib,subcategory='character')['total'],27)
            self.assertEqual(len(catalog(lib,subcategory='character',offset=24)['items']),3)
            self.assertEqual([a.to_dict() for a in lib.all()],before)
            with self.assertRaises(DirectorError):catalog(lib,subcategory='invented')

    def test_catalog_blend_also_uses_short_exact_copy_paths_without_checkpoint_claim(self):
        scene=self.source/'scene.blend';scene.write_bytes(b'synthetic catalog bytes')
        data={**self.data,'source_kind':'catalog','file':'scene.blend',
              'files':[{'path':'scene.blend','size':scene.stat().st_size,'sha256':file_hash(scene)},*self.data['files']]}
        atomic_json(self.request,data)
        _,directory,asset=snapshot(self.request,embedded=True)
        self.assertFalse(asset.metadata['preview_checkpoint'])
        self.assertEqual(asset.metadata['preview_member'],'incoming/package/f0000.blend')
        self.assertEqual(asset.metadata['preview_source_map']['incoming/package/f0001.glb'],'model.glb')
        self.assertEqual(file_hash(directory/asset.metadata['preview_member']),file_hash(scene))

    def test_texture_maps_are_not_reference_thumbnails(self):
        for name in ['body_baseColor.png','textures/diffuse.jpg','atlas.png','image.png']:
            self.assertFalse(reference_image(name))
        for name in ['preview.png','source-thumbnail.jpg','screenshots/reference-01.jpeg']:
            self.assertTrue(reference_image(name))

    def test_display_label_is_version_bound_without_changing_catalog_identity(self):
        from asset_director.catalog_labels import read
        with Library(self.root/'labels-library') as lib:
            f=lib.root/'incoming/model.glb';f.write_bytes(b'fixture')
            a=Asset('local','label-fixture','Rigged asset','model','',local_files=[{'path':'incoming/model.glb','size':7,'sha256':file_hash(f)}])
            lib.put(a);before=catalog(lib,asset_id=a.id)
            label_file=self.root/'labels.json'
            atomic_json(label_file,{'schema':1,'labels':{a.id:{'version':before['version'],'subcategory':'character'}}})
            labels=read(label_file);after=catalog(lib,asset_id=a.id,labels=labels)
            self.assertEqual(after['version'],before['version']);self.assertEqual(after['subcategory']['id'],'character')
            self.assertEqual(catalog(lib,labels=labels,subcategory='character')['total'],1)
            a.title='New source version';lib.put(a)
            self.assertEqual(catalog(lib,asset_id=a.id,labels=labels)['subcategory']['id'],'model')
