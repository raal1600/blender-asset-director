"""Unlike namespaces expose source/target anchor confusion without Blender."""
import copy
from pathlib import Path
import tempfile
import unittest
from asset_director.core import DirectorError, Library
from asset_director.pose_contract import validate_binding
from asset_director.jobs import prepare


class PoseBindingTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(rotation=[1,0,0,0,1,0,0,0,1], translation_bone='target:pelvis',
                           translation_scale=1, target_origin=[0,0,1])
        self.mapping = {'mixamorig:Hips': 'target:pelvis', 'mixamorig:Spine': 'target:spine'}

    def test_target_anchor_with_different_names_is_valid(self):
        before=copy.deepcopy((self.config,self.mapping))
        validate_binding(self.config,self.mapping)
        self.assertEqual((self.config,self.mapping),before)

    def test_source_name_is_not_a_target_name(self):
        with self.assertRaises(DirectorError) as caught:
            validate_binding({**self.config,'translation_bone':'mixamorig:Hips'},self.mapping)
        self.assertEqual(caught.exception.code,'INVALID_POSE_TRANSFER')
        self.assertIn('TARGET',str(caught.exception))

    def test_unknown_target_refused(self):
        with self.assertRaises(DirectorError):
            validate_binding({**self.config,'translation_bone':'target:other'},self.mapping)

    def test_non_mapping_and_invalid_names_refused(self):
        for mapping in (None, [], 'mapping', {}, {'a':None}, {'a':[]}, {'':'b'}, {'a':''}):
            with self.subTest(mapping=mapping),self.assertRaises(DirectorError):
                validate_binding(self.config,mapping)

    def test_duplicate_targets_are_not_invertible(self):
        with self.assertRaises(DirectorError):
            validate_binding(self.config,{'a':'target:pelvis','b':'target:pelvis'})

    def test_bounded_mapping(self):
        with self.assertRaises(DirectorError):
            validate_binding(self.config,{str(i):str(i) for i in range(257)})

    def test_prepare_refuses_source_anchor_before_files_or_jobs(self):
        # A path, asset or valid canonical record is not needed to discover this
        # bad binding: rejection must precede input resolution and job creation.
        with tempfile.TemporaryDirectory() as tmp, Library(tmp) as lib:
            options={'mapping':self.mapping,'alignment':{'target:pelvis':[1]*16},
                     'pose_space':{**self.config,'translation_bone':'mixamorig:Hips'}}
            for op in ('retarget','motion-retarget'):
                request=copy.deepcopy(options)
                if op=='motion-retarget':
                    request.update(motion_id='m_'+'a'*64,project_use='commercial',
                        target_object='Rig',target_fps=30,target_meters_per_unit=1,
                        expected_source_fingerprint='b'*64,expected_target_fingerprint='c'*64)
                with self.subTest(op=op),self.assertRaises(DirectorError) as caught:
                    prepare(lib,op,'does-not-exist.blend',options=request)
                self.assertEqual(caught.exception.code,'INVALID_POSE_TRANSFER')
            self.assertEqual(list((Path(tmp)/'jobs').iterdir()),[])


if __name__=='__main__':unittest.main()
