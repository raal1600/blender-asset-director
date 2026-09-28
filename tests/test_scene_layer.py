import copy
import tempfile
import unittest
from pathlib import Path
from asset_director import scene_layer_contract as contract, jobs
from asset_director.core import DirectorError, Library


class SceneLayerContracts(unittest.TestCase):
    def test_copy_inventory_does_not_change_semantic_layer_fingerprint(self):
        state = {'scene': {'camera': 'Wide', 'preview_dependencies': {'mode': 'ALL_PINNED'}},
                 'cameras': [{'lens': 50}], 'look': {'energy': 100}, 'preserved': 'original'}
        expected = contract.fingerprint(state)
        changed = copy.deepcopy(state)
        changed['scene']['preview_dependencies'] = {'mode': 'EXACT_ABSOLUTE_FILES', 'source_sha256': 'a'*64, 'paths': []}
        self.assertEqual(contract.fingerprint(changed), expected)
        del changed['scene']['preview_dependencies']
        self.assertEqual(contract.fingerprint(changed), expected)
        for key, value in [('cameras', [{'lens': 35}]), ('look', {'energy': 150}), ('preserved', 'changed'),
                           ('scene', {'camera': 'Close'})]:
            self.assertNotEqual(contract.fingerprint(changed | {key: value}), expected)

    def request(self):
        return {'version': contract.VERSION, 'layer': 'shots', 'audit_sha256': 'a'*64,
                'operations': [{'operation': 'camera-fit', 'name': 'Wide', 'options':
                    {'subjects': ['Observed mesh'], 'frames': [1, 9], 'direction': [1, -2, 1], 'lens_mm': 50}}]}

    def test_explicit_camera_and_lighting_contracts(self):
        request = self.request();self.assertEqual(contract.validate(request), request)
        value = request | {'layer': 'light', 'operations': [
            {'operation': 'light-adjust', 'options': {'lights': [{'name': 'Key', 'energy': 200}]}},
            {'operation': 'world-adjust', 'options': {'strength': .2}},
            {'operation': 'look-adjust', 'options': {'exposure': .5}},
            {'operation': 'light-rig', 'options': {'subjects': ['Observed mesh'], 'lights': [
                {'type': 'AREA', 'energy': 100, 'offset': [1, 2, 1], 'color': [1, 1, 1]}]}}]}
        self.assertEqual(contract.validate(value), value)

    def test_refuses_unknown_cross_layer_and_oversized_operations(self):
        for patch in [{'version': 'new'}, {'layer': 'world'}, {'audit_sha256': 'no'}, {'script': 'no'},
                      {'operations': []}, {'operations': self.request()['operations']*2}, {'layer': 'light'}]:
            with self.subTest(patch=patch), self.assertRaises(DirectorError):contract.validate(self.request() | patch)
        for patch in [{'frames': [True]}, {'frames': [1]*33}, {'direction': [0, 0, 0]}, {'lens_mm': float('nan')},
                      {'subjects': ['same', 'same']}, {'projection': 'PANO'}, {'margin': .5}, {'script': 'no'}]:
            value = self.request();value['operations'][0]['options'].update(patch)
            with self.subTest(patch=patch), self.assertRaises(DirectorError):contract.validate(value)

    def test_camera_plan_cannot_change_action_timebase_or_discard_animation(self):
        value = self.request();value['operations'] = [{'operation': 'camera-plan', 'options': {
            'mode': 'create', 'name': 'Close', 'subjects': ['Observed mesh'], 'lens_mm': 50,
            'keyframes': [{'frame': 1, 'aim': {'subject': 'Observed mesh'}, 'position': [1, -3, 2]}]}}]
        contract.validate(value)
        for patch in [{'fps': 60}, {'frame_range': [1, 99]}, {'existing_animation': 'clear'}, {'name': 'x'*64}]:
            bad = copy.deepcopy(value);bad['operations'][0]['options'].update(patch)
            with self.assertRaises(DirectorError):contract.validate(bad)

    def test_native_scene_only_and_read_only_audit(self):
        with tempfile.TemporaryDirectory() as temporary, Library(Path(temporary)/'library') as lib:
            for op, options in [('scene-layer-audit', {'layer': 'shots'}), ('scene-layer-edit', self.request())]:
                for filename, asset in [(None, None), ('source.glb', None), ('source.blend', 'a_'+'1'*24)]:
                    with self.assertRaises(DirectorError) as error:jobs.prepare(lib, op, input_file=filename, asset_id=asset, options=options)
                    self.assertEqual(error.exception.code, 'TARGET_REQUIRED')
            self.assertFalse(list((lib.root/'jobs').iterdir()))
        self.assertIn('scene-layer-edit', jobs.MUTATIONS);self.assertNotIn('scene-layer-audit', jobs.MUTATIONS)


if __name__ == '__main__':unittest.main()
