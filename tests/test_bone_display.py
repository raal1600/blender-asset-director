import tempfile
import unittest
from pathlib import Path
from asset_director import jobs, bone_display_contract as contract
from asset_director.core import DirectorError, Library


class BoneDisplayContracts(unittest.TestCase):
    def options(self):
        return dict(target_object='ReviewedRig',target_fingerprint='a'*64,display_type='OCTAHEDRAL',
                    show_custom_shapes=False,show_in_front=True)

    def test_explicit_styles_and_optional_visibility(self):
        for style in ('OCTAHEDRAL','STICK'):
            contract.validate('bone-display',self.options()|{'display_type':style})
            contract.validate('bone-display',self.options()|{'visible_bones':['ObservedJoint'],'hide_widget_objects':['ObservedWidget']})

    def test_required_review_fields(self):
        for key in self.options():
            value=self.options();value.pop(key)
            with self.subTest(key=key),self.assertRaises(DirectorError):contract.validate('bone-display',value)

    def test_invalid_or_unbounded_display_requests(self):
        for patch in ({'show_custom_shapes':0},{'show_in_front':'true'},{'display_type':'SPHERES'},
                      {'target_fingerprint':'bad'},{'target_object':''},{'visible_bones':[]},
                      {'visible_bones':['a','a']},{'visible_bones':['b'+str(i) for i in range(4097)]},
                      {'hide_widget_objects':['x','x']},{'hide_widget_objects':['b'+str(i) for i in range(257)]},
                      {'delete_objects':['x']}):
            with self.subTest(patch=patch),self.assertRaises(DirectorError):contract.validate('bone-display',self.options()|patch)

    def test_audit_is_read_only_and_requires_target(self):
        contract.validate('bone-display-audit',{'target_object':'Rig'})
        self.assertNotIn('bone-display-audit',jobs.MUTATIONS)
        self.assertIn('bone-display',jobs.MUTATIONS)
        with self.assertRaises(DirectorError):contract.validate('bone-display-audit',{'target_object':'Rig','show_custom_shapes':False})

    def test_invalid_requests_create_no_jobs(self):
        with tempfile.TemporaryDirectory() as tmp, Library(Path(tmp)/'library') as lib:
            with self.assertRaises(DirectorError):jobs.prepare(lib,'bone-display',options=self.options()|{'show_custom_shapes':1})
            self.assertFalse(list((lib.root/'jobs').iterdir()))

    def test_registered_jobs_require_saved_input(self):
        with tempfile.TemporaryDirectory() as tmp, Library(Path(tmp)/'library') as lib:
            for op,options in [('bone-display-audit',{'target_object':'Rig'}),('bone-display',self.options())]:
                with self.assertRaises(DirectorError) as caught:jobs.prepare(lib,op,options=options)
                self.assertEqual(caught.exception.code,'TARGET_REQUIRED')


if __name__ == '__main__':unittest.main()
