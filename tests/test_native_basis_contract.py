"""Label-only changes may reuse defaults; motion/dependency changes may not."""
import copy
import unittest
from asset_director.native_basis_contract import equivalent_inputs, source_content


class NativeBasisContractTests(unittest.TestCase):
    def setUp(self):
        self.inputs = {'unit': 1, 'rest': ['reviewed'], 'sources': [
            {'action': 'one', 'slot': 'OBSlot', 'channels': 'a' * 64, 'range': [1, 24]},
            {'action': 'two', 'slot': 'OBSlot', 'channels': 'b' * 64, 'range': [1, 30]}]}

    def test_rename_and_reordering_preserve_content(self):
        changed = copy.deepcopy(self.inputs)
        changed['sources'][0]['action'] = 'unrelated label'
        changed['sources'].reverse()
        self.assertTrue(equivalent_inputs(self.inputs, changed))

    def test_motion_binding_contact_and_rig_changes_refuse(self):
        for key, value in [('channels', 'c' * 64), ('slot', 'different'),
                           ('range', [2, 24]), ('contact_annotations_sha256', 'd' * 64)]:
            changed = copy.deepcopy(self.inputs)
            changed['sources'][0][key] = value
            self.assertFalse(equivalent_inputs(self.inputs, changed), key)
        changed = copy.deepcopy(self.inputs)
        changed['unit'] = .01
        self.assertFalse(equivalent_inputs(self.inputs, changed))

    def test_duplicate_bindings_are_counted_not_collapsed(self):
        changed = copy.deepcopy(self.inputs)
        changed['sources'].append(dict(changed['sources'][0], action='duplicate'))
        self.assertFalse(equivalent_inputs(self.inputs, changed))
        self.assertEqual(len(source_content(changed['sources'])), 3)


if __name__ == '__main__':
    unittest.main()
