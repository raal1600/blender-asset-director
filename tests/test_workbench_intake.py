"""Policy refusals occur before any native preparation or catalog mutation."""
import copy
import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from asset_director.workbench_intake import validate_evidence
from asset_director.core import DirectorError
from asset_director.core import Library, atomic_json
from asset_director.intake import intake
from asset_director.workbench_catalog import describe, validate_import


class PreparationRights(unittest.TestCase):
    def setUp(self):
        self.evidence = dict(title='Generated fixture', kind='model', source_url='https://example.invalid/generated',
                             license_id='CC0-1.0', license_url='https://example.invalid/terms', author='Fixture generator',
                             price=0, attested=True, tags=['environment'])

    def test_explicit_supported_evidence_is_not_altered(self):
        before = copy.deepcopy(self.evidence)
        validate_evidence(self.evidence)
        self.assertEqual(before, self.evidence)

    def test_incomplete_custom_paid_credentials_or_false_claim_refused(self):
        for changes in ({'attested':False}, {'attested':'true'}, {'license_id':'UNKNOWN'}, {'price':2},
                        {'price':False}, {'kind':'animation'}, {'author':''}, {'source_url':'file:///secret'},
                        {'source_url':'https://user:password@example.invalid'}, {'license_url':''}, {'unexpected':'field'}):
            with self.subTest(changes=changes), self.assertRaises(DirectorError):
                validate_evidence({**self.evidence, **changes})

    def test_intake_existing_check_and_publication_share_the_cross_process_lease(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);source=root/'model.obj';source.write_text('v 0 0 0\n')
            evidence=root/'evidence.json';atomic_json(evidence,self.evidence)
            with Library(root/'library') as lib:
                lock=lib.lock;get=lib.get;put=lib.put;active=set()
                @contextmanager
                def tracked_lock(name):
                    with lock(name):
                        active.add(name)
                        try:yield
                        finally:active.remove(name)
                def checked_get(aid):
                    self.assertIn('intake-catalog',active);return get(aid)
                def checked_put(asset):
                    self.assertIn('intake-catalog',active);return put(asset)
                lib.lock=tracked_lock;lib.get=checked_get;lib.put=checked_put
                first=intake(lib,str(source),str(evidence),preserve_existing=True)
                self.assertEqual(first['status'],'INTAKEN')
                second=intake(lib,str(source),str(evidence),preserve_existing=True)
                self.assertEqual(second['status'],'ALREADY_INTAKEN')

    def test_preparation_does_not_enable_unchecked_models_in_the_same_package(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);source=root/'originals';source.mkdir()
            (source/'selected.blend').write_bytes(b'Synthetic metadata fixture, not a Blender test')
            (source/'unchecked.blend').write_bytes(b'Second synthetic metadata fixture')
            evidence=root/'evidence.json';atomic_json(evidence,self.evidence)
            with Library(root/'library') as lib:
                result=intake(lib,str(source),str(evidence),preserve_existing=True,prepared_member='selected.blend')
                asset=lib.get(result['asset_id']);view=describe(lib,asset,verify=True)
                self.assertEqual(len(view['models']),1)
                self.assertTrue(view['models'][0].endswith('/selected.blend'))
                validate_import(lib,asset,{'file':view['models'][0]})
                for options in ({},{'file':next(f['path'] for f in asset.local_files if f['path'].endswith('/unchecked.blend'))}):
                    with self.assertRaises(DirectorError):validate_import(lib,asset,options)


if __name__ == '__main__':
    unittest.main()
