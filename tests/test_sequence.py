"""Portable regression contracts. Executed by the Actions unit matrix."""
import copy
import math
from pathlib import Path
import tempfile
import unittest
from asset_director.core import DirectorError, Library
from asset_director import motion_timing as mt, sequence_contract as sc, sequence_math as sm
from asset_director import transfer_contract as tc, jobs
from asset_director.ground_sampling import correction_frames


def request():
    return dict(target_object='ObservedRig',clips=[{'job_id':'j_'+'1'*24},{'job_id':'j_'+'2'*24}],fps=30,
                meters_per_unit=1,joins=[dict(duration_seconds=.4,yaw_degrees=15,placement='continue_velocity',subdivisions=4)],
                budget=dict(max_duration_seconds=60,max_pose_samples=4096,max_created_keys=1500000,
                            max_contact_samples=512,max_mesh_evaluations=1000000),contact=None)


class LongTransferTests(unittest.TestCase):
    def test_default_does_not_silently_admit_long_take(self):
        with self.assertRaises(DirectorError):mt.bake_samples(1,1113,30,30)

    def test_full_native_range_explicit_budget(self):
        samples=mt.bake_samples(1,1113,30,30,1200)
        self.assertEqual(len(samples),1113);self.assertEqual(samples[-1],(1113.,1113))

    def test_full_long_take_other_fps_retains_fractional_endpoint(self):
        samples=mt.bake_samples(1,1113,30,24,1200)
        self.assertAlmostEqual(samples[-1][0],890.6);self.assertEqual(samples[-1][1],1113)
        self.assertEqual(len(samples),891)
        self.assertTrue(all(a[0]<b[0] and a[1]<b[1] for a,b in zip(samples,samples[1:])))

    def test_long_budget_absolute_bounds(self):
        for value in (0,7201,True,1.5,float('nan'),'1200'):
            with self.subTest(value=value),self.assertRaises(DirectorError):mt.bake_samples(1,32,30,30,value)
        with self.assertRaises(DirectorError):mt.bake_samples(1,10000,30,1,7200)

    def test_opt_in_field_survives_portable_contract(self):
        p=dict(target_object='Rig',source_meters_per_unit=1,target_meters_per_unit=1,target_fps=30,
               root_mode='morphology_scaled',facing={'mode':'anatomical'},max_output_intervals=1200)
        tc.plan(p)
        with self.assertRaises(DirectorError):tc.plan(p|{'max_output_intervals':True})

    def test_long_legacy_retarget_requires_review_before_input_resolution(self):
        with tempfile.TemporaryDirectory() as tmp,Library(tmp) as lib:
            with self.assertRaises(DirectorError) as c:
                jobs.prepare(lib,'retarget','missing.blend',options={'max_output_intervals':1200})
            self.assertEqual(c.exception.code,'TRANSFER_REVIEW_REQUIRED')
            self.assertEqual(list((lib.root/'jobs').iterdir()),[])

    def test_long_grounding_retains_separate_checkpoint_cap(self):
        frames=[float(f) for f in range(1,1114)]
        with self.assertRaises(DirectorError):correction_frames(frames)
        samples=correction_frames(frames,2,max_frames=1201)
        self.assertEqual(len(samples),2225);self.assertEqual(samples[-1],1113)
        with self.assertRaises(DirectorError):correction_frames(frames,4,max_frames=1201)


class SequenceContractTests(unittest.TestCase):
    def test_nonmutating_complete_contract(self):
        p=request();before=copy.deepcopy(p);sc.validate('sequence-plan',p);self.assertEqual(p,before)

    def test_duplicate_clip_does_not_repeat_travelling_motion(self):
        p=request();p['clips'][1]=p['clips'][0]
        with self.assertRaises(DirectorError):sc.validate('sequence-plan',p)

    def test_exact_ids_not_names(self):
        for value in ('Moonwalk','Armature|mixamo.com|Layer0','../jobs/foo',None):
            p=request();p['clips'][0]={'job_id':value}
            with self.subTest(value=value),self.assertRaises(DirectorError):sc.validate('sequence-plan',p)

    def test_full_clips_do_not_accept_hidden_crop_or_speed(self):
        for key,value in (('start',30),('playback_speed',2),('repeat',4)):
            p=request();p['clips'][0][key]=value
            with self.subTest(key=key),self.assertRaises(DirectorError):sc.validate('sequence-plan',p)

    def test_explicit_join_count(self):
        for joins in ([],[request()['joins'][0]]*2,None):
            p=request();p['joins']=joins
            with self.assertRaises(DirectorError):sc.validate('sequence-plan',p)

    def test_bounded_join_inputs(self):
        for key,values in {'duration_seconds':[0,3,True,float('nan')], 'yaw_degrees':[181,float('inf')],
                           'subdivisions':[0,9,True,1.5],'placement':['auto','lock_feet']}.items():
            for v in values:
                p=request();p['joins'][0][key]=v
                with self.subTest(key=key,value=v),self.assertRaises(DirectorError):sc.validate('sequence-plan',p)

    def test_budgets_do_not_disable_absolute_caps(self):
        for key,cap in sc.BUDGET_CAPS.items():
            for value in (cap+1,0,True,None):
                p=request();p['budget'][key]=value
                with self.subTest(key=key,value=value),self.assertRaises(DirectorError):sc.validate('sequence-plan',p)

    def test_no_contacts_is_unknown_not_missing_permission(self):
        sc.validate('sequence-plan',request())
        for value in ('auto',[],True):
            p=request();p['contact']=value
            with self.assertRaises(DirectorError):sc.validate('sequence-plan',p)

    def test_same_sequence_supports_three_different_clips(self):
        p=request();p['clips'].append({'job_id':'j_'+'3'*24});p['joins'].append(dict(p['joins'][0]))
        sc.validate('sequence-plan',p)

    def test_registry_and_no_input_early_refusal(self):
        self.assertTrue(set(sc.OPS)<=set(jobs.OPS));self.assertIn('sequence-execute',jobs.MUTATIONS)
        self.assertNotIn('sequence-plan',jobs.MUTATIONS);self.assertNotIn('sequence-check',jobs.MUTATIONS)
        with tempfile.TemporaryDirectory() as tmp,Library(tmp) as lib:
            with self.assertRaises(DirectorError):jobs.prepare(lib,'sequence-plan',options=request())
            self.assertEqual(list((lib.root/'jobs').iterdir()),[])

    def test_review_requires_actual_approval_and_offset(self):
        r=dict(plan_job_id='j_'+'1'*24,plan_id='sq_'+'2'*64,reviewer='host',reviewed_at='2026-09-15T00:00:00Z',approved=True)
        sc.validate_review(r)
        for key,v in [('approved',False),('approved','yes'),('reviewer',''),('reviewed_at','2026-09-15'),('plan_id','tp_'+'2'*64)]:
            with self.subTest(key=key),self.assertRaises(DirectorError):sc.validate_review(r|{key:v})


class BridgeMathTests(unittest.TestCase):
    def test_quintic_position_and_velocity_endpoints(self):
        a=[.2,1,-2];b=[3,-1,.3];va=[1,.4,-.3];vb=[-.2,.5,.1];T=.47;h=1e-6
        f=lambda u:sm.hermite(a,b,va,vb,T,u)
        for observed,expected in [(f(0),a),(f(1),b),
                                  (sm.mul(sm.sub(f(h),f(0)),1/(T*h)),va),
                                  (sm.mul(sm.sub(f(1),f(1-h)),1/(T*h)),vb)]:
            self.assertLess(sm.norm(sm.sub(observed,expected)),1e-5)

    def test_quaternion_endpoints_and_noncommuting_angular_velocities(self):
        a=sm.qexp([.2,-.3,.1]);b=sm.qexp([.4,.15,-.2]);wa=[.3,-.5,.2];wb=[-.4,.25,.6];T=.6;h=1e-6
        f=lambda u:sm.rotation_bridge(a,b,wa,wb,T,u)
        self.assertAlmostEqual(abs(sm.dot(f(0),a)),1,places=10);self.assertAlmostEqual(abs(sm.dot(f(1),b)),1,places=10)
        self.assertLess(sm.norm(sm.sub(sm.angular_velocity(f(0),f(h),T*h),wa)),1e-4)
        self.assertLess(sm.norm(sm.sub(sm.angular_velocity(f(1-h),f(1),T*h),wb)),1e-4)
        for u in (.1,.5,.9):self.assertAlmostEqual(sm.norm(f(u)),1,places=10)

    def test_quaternion_sign_does_not_create_long_spin(self):
        a=sm.qexp([.1,.2,.3]);b=sm.qexp([.6,-.1,.1])
        for u in (0,.25,.5,.75,1):
            q=sm.rotation_bridge(a,b,[0]*3,[0]*3,.5,u)
            flipped=sm.rotation_bridge(a,sm.mul(b,-1),[0]*3,[0]*3,.5,u)
            self.assertAlmostEqual(abs(sm.dot(q,flipped)),1,places=12)

    def test_pi_ambiguity_refused(self):
        with self.assertRaises(DirectorError):sm.rotation_bridge([1,0,0,0],sm.qexp([0,0,math.pi]),[0]*3,[0]*3,.5,.5)

    def test_exact_grid_fractional_endpoint_and_large_duration(self):
        values=sm.grid(32,44.39,.25,100)
        self.assertEqual(values[0],32);self.assertEqual(values[-1],44.39)
        self.assertEqual(len(values),len(set(values)))
        with self.assertRaises(DirectorError):sm.grid(1,1113,.25,100)

    def test_zero_and_sign_equivalent_rotation(self):
        self.assertLess(sm.norm(sm.qlog([-1,0,0,0])),1e-10)
        self.assertEqual(sm.qexp([0,0,0]),[1,0,0,0])

    def test_degenerate_quaternion_rejected(self):
        for q in ([0]*4,[float('nan'),0,0,0],[float('inf'),0,0,0]):
            with self.assertRaises(DirectorError):sm.unit(q)


if __name__=='__main__':unittest.main()
