"""Regression boundaries found while completing the interrupted planning milestone."""
import copy
import unittest
from asset_director.core import DirectorError
from asset_director.motion import identify_roles, frame_convert, quality
from asset_director.contact_diagnostics import summarize
import test_transfer_planning as fixtures
chain = fixtures.chain


class ExtendedChainBoundaries(unittest.TestCase):
    def test_four_mixamo_spines_do_not_keep_previous_three_joint_shortcut(self):
        b=chain('mixamo')
        b.append({'name':'mixamorig:Spine3','parent':'mixamorig:Spine2'})
        result=identify_roles(b)
        self.assertIsNone(result['torso_chain'])
        self.assertTrue({'spine','spine_mid','chest'}.isdisjoint(result['roles']))
        self.assertIn('spine',result['ambiguous'])

    def test_four_finger_segments_require_review_in_both_families(self):
        for kind,last,name in (('mixamo','mixamorig:LeftHandIndex3','mixamorig:LeftHandIndex4'),
                               ('def','DEF-f_index.03.L','DEF-f_index.04.L')):
            with self.subTest(kind=kind):
                b=chain(kind)+[{'name':name,'parent':last}]
                result=identify_roles(b)
                self.assertFalse(result['finger_chains'])
                self.assertIn('index_chain_l',result['ambiguous'])
                self.assertNotIn('index_1_l',result['roles'])

    def test_shuffled_bone_storage_order_does_not_reorder_anatomy(self):
        b=chain('def'); original=identify_roles(b)
        self.assertEqual(original,identify_roles(list(reversed(b))))

    def test_namespaced_numbered_chain_duplicate_not_auto_selected(self):
        b=chain('mixamo')+[{'name':'Other:Spine1','parent':'mixamorig:Spine'}]
        result=identify_roles(b)
        self.assertIn('spine',result['ambiguous'])
        self.assertIsNone(result['torso_chain'])


class ContactCompletion(unittest.TestCase):
    def setUp(self):
        helper=fixtures.ContactEvidenceTests()
        self.samples=[helper.sample(1,0),helper.sample(1.5,-.01,.03),helper.sample(2,0,.06)]
        self.options=helper.o()

    def test_summary_does_not_modify_raw_measurements(self):
        before=copy.deepcopy(self.samples)
        first=summarize(self.samples,self.options)
        self.assertEqual(self.samples,before)
        self.assertEqual(first,summarize(self.samples,self.options))

    def test_separate_foot_metrics_preserve_subframe_extrema(self):
        result=summarize(self.samples,self.options)
        self.assertAlmostEqual(result['per_foot']['left']['minimum_clearance_m'],-.01)
        self.assertGreater(result['per_foot']['right']['maximum_horizontal_centroid_speed_m_s'],0)
        self.assertFalse(result['repair_applied'])

    def test_nonfinite_mesh_or_time_evidence_never_gets_pass(self):
        for where in ('centroid','minimum_z','time','frame'):
            with self.subTest(where=where),self.assertRaises(DirectorError):
                bad=copy.deepcopy(self.samples)
                if where=='centroid':bad[1]['left'][where][0]=float('nan')
                elif where=='minimum_z':bad[1]['left'][where]=float('inf')
                else:bad[1][where]=float('nan')
                summarize(bad,self.options)

    def test_unsorted_or_duplicate_frames_and_times_refused(self):
        for key in ('time','frame'):
            bad=copy.deepcopy(self.samples);bad[1][key]=bad[0][key]
            with self.assertRaises(DirectorError):summarize(bad,self.options)

    def test_invalid_calibration_refused(self):
        for patch in ({'meters_per_unit':0},{'ground_z':float('nan')},{'glide_speed_m_s':-1},
                      {'near_ground_m':0},{'tolerance_m':True}):
            with self.subTest(patch=patch),self.assertRaises(DirectorError):
                summarize(self.samples,self.options|patch)

    def test_unbounded_or_empty_arrays_refused(self):
        for values in ([],self.samples*100,None):
            with self.assertRaises(DirectorError):summarize(values,self.options)


class MatchedTimeRegression(unittest.TestCase):
    def test_missing_or_invalid_qa_scale_is_structured_error(self):
        for height, fps in ((None,30),(2,None),('2',30),(True,30),(2,True),(float('nan'),30),(2,float('inf'))):
            with self.subTest(height=height,fps=fps), self.assertRaises(DirectorError) as caught:
                quality([],height,fps)
            self.assertEqual(caught.exception.code,'INVALID_SCALE')

    def test_shifted_fbx_start_is_not_equal_frame_comparison(self):
        self.assertEqual(frame_convert(17,30,30,source_start=1,target_start=2),18)

    def test_elapsed_seconds_preserved_across_offsets_and_fps(self):
        for tfps in (24,25,30,60):
            for i in range(32):
                elapsed=i/30
                target=1+elapsed*tfps
                source=frame_convert(target,tfps,30,source_start=1,target_start=2)
                self.assertAlmostEqual((source-2)/30,elapsed)


if __name__=='__main__':unittest.main()
