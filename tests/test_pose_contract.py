import copy
import unittest
from asset_director.core import DirectorError
from asset_director.pose_contract import validate


class PoseContractTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(rotation=[1,0,0,0,1,0,0,0,1], translation_bone='pelvis',
                           translation_scale=1.8, target_origin=[0,0,1])

    def test_proper_rotation(self):
        self.config['rotation'] = [0,-1,0,1,0,0,0,0,1]
        validate(self.config)

    def test_rejects_reflection_shear_and_nonfinite(self):
        for rotation in [[-1,0,0,0,1,0,0,0,1], [1,.1,0,0,1,0,0,0,1], [float('nan')]*9]:
            with self.subTest(rotation=rotation), self.assertRaises(DirectorError):
                validate({**self.config, 'rotation':rotation})

    def test_rejects_unbounded_translation_and_missing_anchor(self):
        for key,value in [('translation_scale',0), ('translation_scale',float('inf')),
                          ('translation_bone',''), ('target_origin',[0,0]), ('unexpected',True)]:
            with self.subTest(key=key,value=value), self.assertRaises(DirectorError):
                validate({**self.config,key:value})

    def test_job_rejects_before_writing(self):
        import tempfile
        from pathlib import Path
        from asset_director.core import Library
        from asset_director.jobs import prepare
        with tempfile.TemporaryDirectory() as directory, Library(directory) as lib:
            with self.assertRaises(DirectorError):
                prepare(lib,'retarget',options={'pose_space':self.config})
            self.assertEqual(list((Path(directory)/'jobs').iterdir()), [])
