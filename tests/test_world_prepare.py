import copy
import tempfile
import unittest
from pathlib import Path
from asset_director import jobs, world_prepare_contract as contract
from asset_director.core import DirectorError, Library


class WorldPrepareContractTests(unittest.TestCase):
    def options(self):
        return {'version': contract.VERSION, 'audit_sha256': 'a' * 64,
                'groups': [{'asset_id': 'a_' + '1' * 24, 'import_job': 'j_' + '2' * 24}]}

    def test_exact_inspected_group(self):
        value = self.options()
        self.assertEqual(contract.validate(value), value)
        self.assertIn('world-prepare', jobs.MUTATIONS)
        self.assertNotIn('world-prepare-audit', jobs.MUTATIONS)

    def test_invalid_foreign_fields_and_identity_refuse(self):
        variants = [None, [], {}, self.options() | {'version': 'future'},
                    self.options() | {'audit_sha256': 'a' * 63}, self.options() | {'file': 'arbitrary'},
                    self.options() | {'groups': []}, self.options() | {'groups': 'automatic'}]
        for patch in ({'asset_id': ''}, {'asset_id': 'a' * 201}, {'asset_id': ['x']},
                      {'import_job': None}, {'import_job': 'control\n'}, {'asset_id': '\ud800'}, {'members': ['guessed']}):
            value = self.options(); value['groups'][0].update(patch); variants.append(value)
        value = self.options(); value['groups'] *= 2; variants.append(value)
        for key in ('version', 'audit_sha256', 'groups'):
            value = self.options(); del value[key]; variants.append(value)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(DirectorError):contract.validate(value)

    def test_group_bound_and_before_job_publication(self):
        value = self.options()
        value['groups'] = [{'asset_id': 'synthetic', 'import_job': str(i)} for i in range(64)]
        contract.validate(value)
        value['groups'].append({'asset_id': 'synthetic', 'import_job': '65'})
        with tempfile.TemporaryDirectory() as tmp, Library(Path(tmp) / 'library') as lib:
            with self.assertRaises(DirectorError):jobs.prepare(lib, 'world-prepare', options=value)
            self.assertFalse(list((lib.root / 'jobs').iterdir()))
            for operation, options in [('world-prepare', self.options()), ('world-prepare-audit', {})]:
                for filename, asset in [(None, None), ('model.glb', None), ('scene.blend', 'a_' + '1' * 24)]:
                    with self.subTest(operation=operation, filename=filename), self.assertRaises(DirectorError) as exc:
                        jobs.prepare(lib, operation, input_file=filename, asset_id=asset, options=copy.deepcopy(options))
                    self.assertEqual(exc.exception.code, 'TARGET_REQUIRED')
            self.assertFalse(list((lib.root / 'jobs').iterdir()))


if __name__ == '__main__':unittest.main()
