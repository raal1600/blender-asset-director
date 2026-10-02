import copy
import math
import tempfile
import unittest
from pathlib import Path
from asset_director import jobs, world_transform_contract as contract
from asset_director.core import DirectorError, Library


IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
INSTANCE = 'instance_01234567-89ab-cdef-0123-456789abcdef'


class WorldTransformContractTests(unittest.TestCase):
    def options(self):
        return {'version': contract.VERSION, 'transforms': [
            {'instance': INSTANCE, 'expected_matrix': IDENTITY.copy(), 'matrix': IDENTITY.copy()}]}

    def test_positive_uniform_rotation_translation(self):
        value = self.options()
        value['transforms'][0]['matrix'] = [0, -2, 0, 10, 2, 0, 0, -3, 0, 0, 2, 4, 0, 0, 0, 1]
        self.assertEqual(contract.validate(value), value)

    def test_no_shear_reflection_nonuniform_scale_or_unbounded_values(self):
        for index, number in [(0, -1), (0, 2), (0, 0), (1, .1), (3, 1e6 + 1),
                              (12, .001), (15, 0), (3, math.nan), (3, math.inf), (3, True), (3, '2')]:
            for key in ('matrix', 'expected_matrix'):
                value = self.options()
                value['transforms'][0][key][index] = number
                with self.subTest(index=index, number=number, key=key), self.assertRaises(DirectorError):
                    contract.validate(value)

    def test_unknown_missing_and_duplicate_targets_refuse(self):
        variants = [None, {}, {'version': contract.VERSION, 'transforms': []},
                    self.options() | {'version': 'new-version'}, self.options() | {'script': 'no'}]
        for patch in ({'instance': 'Rig'}, {'matrix': IDENTITY[:-1]}, {'expected_matrix': None}, {'file': 'arbitrary'}):
            value = self.options(); value['transforms'][0].update(patch); variants.append(value)
        duplicate = self.options(); duplicate['transforms'] *= 2; variants.append(duplicate)
        for key in ('instance', 'matrix', 'expected_matrix'):
            value = self.options(); del value['transforms'][0][key]; variants.append(value)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(DirectorError):
                contract.validate(value)

    def test_instance_limit_and_validation_before_job_write(self):
        value = self.options()
        value['transforms'] = [dict(copy.deepcopy(value['transforms'][0]),
                                    instance=f'instance_{i:08x}-89ab-cdef-0123-456789abcdef') for i in range(64)]
        contract.validate(value)
        value['transforms'].append(dict(copy.deepcopy(value['transforms'][0]), instance='instance_ffffffff-89ab-cdef-0123-456789abcdef'))
        with tempfile.TemporaryDirectory() as tmp, Library(Path(tmp) / 'library') as lib:
            with self.assertRaises(DirectorError):
                jobs.prepare(lib, 'world-transform', options=value)
            self.assertFalse(list((lib.root / 'jobs').iterdir()))
            for op, options in [('world-transform', self.options()), ('world-placement-audit', {})]:
                with self.assertRaises(DirectorError) as caught:
                    jobs.prepare(lib, op, options=options)
                self.assertEqual(caught.exception.code, 'TARGET_REQUIRED')

    def test_requires_native_scene_and_no_asset_id(self):
        with tempfile.TemporaryDirectory() as tmp, Library(Path(tmp) / 'library') as lib:
            for filename, asset in [('model.glb', None), ('scene.blend', 'a_' + '1' * 24)]:
                with self.assertRaises(DirectorError) as caught:
                    jobs.prepare(lib, 'world-transform', input_file=filename, asset_id=asset, options=self.options())
                self.assertEqual(caught.exception.code, 'TARGET_REQUIRED')
        self.assertIn('world-transform', jobs.MUTATIONS)
        self.assertNotIn('world-placement-audit', jobs.MUTATIONS)


if __name__ == '__main__':
    unittest.main()
