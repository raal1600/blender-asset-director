"""Collision labels are candidates, never a substitute for source identity."""
import unittest
from asset_director.worker import re_original

class ActionLabelTests(unittest.TestCase):
    def test_embedded_owner_suffix(self):
        self.assertEqual(re_original('Armature.001|mixamo.com|Layer0'),'Armature|mixamo.com|Layer0')
    def test_terminal_action_suffix(self):
        self.assertEqual(re_original('OtherTake.002'),'OtherTake')
    def test_both_collision_sites(self):
        self.assertEqual(re_original('Armature.012|mixamo.com|Layer0.003'),'Armature|mixamo.com|Layer0')
    def test_no_collision_preserves_label(self):
        for name in ('Armature|mixamo.com|Layer0','Dance1','Run.2','Root|Version.002|Layer0',''):
            self.assertEqual(re_original(name),name)
    def test_large_blender_suffix(self):
        self.assertEqual(re_original('Armature.1000|Take'),'Armature|Take')
    def test_normalization_cannot_resolve_ambiguous_imports(self):
        names=['Armature.001|Take','Armature.002|Take']
        matches=[n for n in names if re_original(n)==re_original('Armature|Take')]
        self.assertEqual(len(matches),2)  # existing require(len(matches)==1) must refuse
    def test_other_take_not_accepted(self):
        self.assertNotEqual(re_original('Armature.001|Take A'),re_original('Armature|Take B'))

if __name__=='__main__':unittest.main()
