import unittest
from asset_director.core import DirectorError
from asset_director.ground_sampling import correction_frames
from asset_director.pose_contract import validate


class GroundSamplingTests(unittest.TestCase):
    def test_default_preserves_bake_times(self):
        self.assertEqual(correction_frames([1.,2.,2.4]),[1.,2.,2.4])

    def test_fractional_endpoint_and_intervals(self):
        times=correction_frames([1.,2.,2.4],4)
        self.assertEqual(len(times),9)
        self.assertEqual(times[:5],[1.,1.25,1.5,1.75,2.])
        self.assertEqual(times[-1],2.4)
        self.assertEqual(len(set(times)),len(times))
        self.assertTrue(all(a<b for a,b in zip(times,times[1:])))

    def test_maximum_budget_is_finite(self):
        self.assertEqual(len(correction_frames(list(range(361)),8)),2881)

    def test_bad_sampling_rejected(self):
        for d in (0,9,True,2.5,'2'):
            with self.subTest(d=d),self.assertRaises(DirectorError):correction_frames([1,2],d)
        for times in ([1,1],[2,1],[1,float('nan')],[1],list(range(362))):
            with self.subTest(times=times[:3]),self.assertRaises(DirectorError):correction_frames(times,2)

    def test_contract_validates_before_blender(self):
        base=dict(rotation=[1,0,0,0,1,0,0,0,1],translation_bone='hips',translation_scale=1,target_origin=[0,0,0])
        ground=dict(mesh='skin',vertex_groups=['sole'],height=0,max_correction=.02,subdivisions=4)
        validate({**base,'ground_contact':ground})
        for d in (True,0,9,1.1):
            with self.assertRaises(DirectorError):validate({**base,'ground_contact':{**ground,'subdivisions':d}})
