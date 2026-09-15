"""Planning bounds are checked before launching a source/target job."""
import unittest
from asset_director.core import DirectorError
from asset_director.motion import identify_roles
from asset_director import transfer_contract as tc
from test_transfer_planning import options, chain

class TransferLimits(unittest.TestCase):
    def test_ground_cap_validated_before_scene_access(self):
        o=options();o['ground_contact']={'mesh':'Skin','vertex_groups':['FootL','FootR'],'height':0,'max_correction':.04}
        tc.plan(o)
        o['ground_contact']['max_correction']=-1
        with self.assertRaises(DirectorError):tc.plan(o)
    def test_source_key_budget_is_explicit_and_bounded(self):
        tc.plan(options())
        for count in (1, 500000, 650000, 1000000):
            tc.plan(options() | {'max_source_keys': count})
        for count in (0, -1, 1000001, True, 650000.0, '650000'):
            with self.subTest(count=count), self.assertRaises(DirectorError):
                tc.plan(options() | {'max_source_keys': count})
    def test_target_fps_matches_executor_bound(self):
        with self.assertRaises(DirectorError):tc.plan(options()|{'target_fps':121})
    def test_excerpt_pairs(self):
        tc.plan(options() | {'start':4.5,'end':10.0})
        for patch in ({'start':1},{'end':2},{'start':3,'end':1}):
            with self.assertRaises(DirectorError):tc.plan(options() | patch)
    def test_rig_inspection_does_not_inherit_stricter_planning_cap(self):
        bones=chain()+[{'name':f'Helper-{i}','parent':'DEF-hips'} for i in range(300)]
        report=identify_roles(bones)
        self.assertEqual(len(report['finger_chains']),1)
        self.assertEqual(len(report['unmapped_bones']),300)

if __name__=='__main__':unittest.main()
