import copy
import math
import unittest
from asset_director.motion_bricks_calibration import SCHEMA,validate,plane_summary
from asset_director.core import DirectorError


class HingeCalibrationTests(unittest.TestCase):
    def evidence(self):
        return {'schema':SCHEMA,'rest_identity':'a'*64,'mapping_sha256':'b'*64,'source_action_sha256':'c'*64,
                'source_slot_identifier':'OBObserved','source_fps':30,'source_range':[1,32],'reviewed':True,
                'observations':{side:[{'frame':i+1,'bend_degrees':25,'normal_world_rest':[0.,0.,sign]} for i in range(12)]
                                for side,sign in [('left',-1.),('right',1.)]}}
    def test_reviewed_consistent_planes_are_derived_from_actual_signed_observations(self):
        value=self.evidence();before=copy.deepcopy(value);result=validate(value,'a'*64,'b'*64)
        self.assertEqual(result['left']['normal_world_rest'],[0.,0.,-1.]);self.assertEqual(result['right']['samples'],12)
        self.assertEqual(value,before)
    def test_review_is_required_and_rest_mapping_timebase_are_bound(self):
        for key,value in [('reviewed',False),('rest_identity','changed'),('mapping_sha256','changed'),('source_fps',0),('source_action_sha256','label'),('source_slot_identifier','')]:
            with self.subTest(key=key),self.assertRaises(DirectorError):validate(self.evidence()|{key:value},'a'*64,'b'*64)
        evidence=self.evidence();evidence['source_range']=[3,32]
        with self.assertRaises(DirectorError):validate(evidence,'a'*64,'b'*64)
    def test_inconsistent_or_singular_evidence_cannot_be_approved_with_a_flag(self):
        rows=self.evidence()['observations']['left']
        for patch in [{'bend_degrees':0},{'normal_world_rest':[0,0,0]},{'normal_world_rest':[0,float('nan'),-1]},{'frame':0}]:
            values=copy.deepcopy(rows);values[5].update(patch)
            with self.subTest(patch=patch),self.assertRaises(DirectorError):plane_summary(values)
        values=copy.deepcopy(rows);values[5]['normal_world_rest']=[0,math.sin(.3),-math.cos(.3)]
        with self.assertRaisesRegex(DirectorError,'more than 5 degrees'):plane_summary(values)
        with self.assertRaises(DirectorError):plane_summary(rows[:7])
