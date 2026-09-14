"""Portable regression cases: reviewed chains, contracts, samples and approvals."""
import copy
from pathlib import Path
import tempfile
import unittest
from asset_director.core import DirectorError, Library
from asset_director.motion import identify_roles, mapping_plan
from asset_director.skeleton_chains import finger_candidate
from asset_director import transfer_contract as tc
from asset_director.transfer_review import validate_review
from asset_director.contact_diagnostics import summarize
from asset_director.jobs import prepare


def chain(kind='def', side='l', finger='index'):
    names=(['DEF-hips','DEF-spine.001','DEF-spine.002','DEF-spine.003','DEF-hand.'+side]
           if kind=='def' else ['mixamorig:Hips','mixamorig:Spine','mixamorig:Spine1','mixamorig:Spine2',
                                'mixamorig:'+('Left' if side=='l' else 'Right')+'Hand'])
    result=[{'name':n,'parent':names[i-1] if i else None} for i,n in enumerate(names)]
    parent=names[-1]
    for i in (1,2,3):
        name=(f'DEF-f_{finger}.{i:02d}.{side.upper()}' if kind=='def' else
              f'mixamorig:{"Left" if side=="l" else "Right"}Hand{finger.title()}{i}')
        result.append({'name':name,'parent':parent});parent=name
    return result


def options():
    return dict(target_object='Character',source_meters_per_unit=1,target_meters_per_unit=1,
                target_fps=30,root_mode='morphology_scaled',facing={'mode':'anatomical'})


class ChainProposals(unittest.TestCase):
    def test_numbered_def_torso_distinct(self):
        r=identify_roles(chain());self.assertEqual([r['roles'][k] for k in ('spine','spine_mid','chest')],
            ['DEF-spine.001','DEF-spine.002','DEF-spine.003'])
    def test_finger_three_joints(self):
        r=identify_roles(chain());self.assertEqual(len(r['finger_chains']),1)
        self.assertEqual(r['roles']['index_2_l'],'DEF-f_index.02.L')
    def test_mixamo_fingers(self):
        for f in ('index','middle','ring','pinky','thumb'):
            for side in ('l','r'):
                with self.subTest(finger=f,side=side):
                    r=identify_roles(chain('mixamo',side,f));self.assertIn(f'{f}_3_{side}',r['roles'])
    def test_namespaces(self):
        b=chain()
        for bone in b:
            bone['name']='Imported:'+bone['name']
            if bone['parent']:bone['parent']='Imported:'+bone['parent']
        self.assertEqual(identify_roles(b)['roles']['spine'],'Imported:DEF-spine.001')
    def test_no_provider_identity_claim(self):
        self.assertFalse(identify_roles(chain())['torso_chain']['provider_identity_proven'])
    def test_number_gaps_not_collapsed(self):
        b=chain();b[2]['name']='DEF-spine.007';b[3]['parent']=b[2]['name']
        self.assertNotIn('spine',identify_roles(b)['roles'])
    def test_wrong_torso_order_blocked(self):
        b=chain();b[2]['parent']=b[0]['name'];self.assertIn('spine',identify_roles(b)['ambiguous'])
    def test_four_spines_not_three(self):
        b=chain();b.append({'name':'DEF-spine.004','parent':'DEF-spine.003'})
        self.assertIsNone(identify_roles(b)['torso_chain'])
    def test_finger_requires_hand_parent(self):
        b=chain();b[5]['parent']=b[0]['name'];r=identify_roles(b)
        self.assertNotIn('index_1_l',r['roles']);self.assertIn('index_chain_l',r['ambiguous'])
    def test_incomplete_chain_reported(self):
        r=identify_roles(chain()[:-1]);self.assertNotIn('index_1_l',r['roles'])
    def test_wrong_side_not_cross_mapped(self):
        b=chain();b[4]['name']='DEF-hand.r';b[5]['parent']='DEF-hand.r'
        self.assertFalse(identify_roles(b)['finger_chains'])
    def test_duplicate_finger_alias_blocked(self):
        b=chain()+[{'name':'Other:DEF-f_index.01.L','parent':'DEF-hand.l'}]
        self.assertIn('index_chain_l',identify_roles(b)['ambiguous'])
    def test_duplicate_bone_names_rejected(self):
        with self.assertRaises(DirectorError):identify_roles(chain()+[chain()[0]])
    def test_helpers_do_not_become_fingers(self):
        self.assertIsNone(finger_candidate('DEF-f_index.01.L.001'))
        self.assertIsNone(finger_candidate('MCH-f_index.01.L'))
    def test_asymmetry_not_invented(self):
        r=identify_roles(chain());self.assertNotIn('index_1_r',r['roles'])
        self.assertIn({'chain':'index_r','status':'ABSENT'},r['chain_notes'])
    def test_proposal_maps_distinct_fingers(self):
        source=identify_roles(chain('mixamo'));target=identify_roles(chain());target['skinned_vertices']=1
        p=mapping_plan(source,target)
        self.assertEqual(p['pairs']['mixamorig:LeftHandIndex2'],'DEF-f_index.02.L')
    def test_proposals_leave_input_unchanged(self):
        b=chain();old=copy.deepcopy(b);identify_roles(b);self.assertEqual(b,old)


class TransferContractTests(unittest.TestCase):
    def test_good_plan_nonmutating(self):
        o=options();old=copy.deepcopy(o);tc.plan(o);self.assertEqual(o,old)
    def test_no_scene_defaults(self):
        for key in options():
            o=options();del o[key]
            with self.subTest(key=key),self.assertRaises(DirectorError):tc.plan(o)
    def test_invalid_units(self):
        for value in (0,True,float('nan'),float('inf'),-1):
            o=options();o['source_meters_per_unit']=value
            with self.subTest(value=value),self.assertRaises(DirectorError):tc.plan(o)
    def test_explicit_facing(self):
        o=options();o['facing']=dict(mode='explicit',source_forward=[0,-1,0],target_forward=[1,0,0],evidence='Reviewed foot direction')
        tc.plan(o)
    def test_facing_evidence_required(self):
        o=options();o['facing']=dict(mode='explicit',source_forward=[0,-1,0],target_forward=[1,0,0],evidence='')
        with self.assertRaises(DirectorError):tc.plan(o)
    def test_facing_rejects_tilt(self):
        o=options();o['facing']=dict(mode='explicit',source_forward=[0,-1,.5],target_forward=[1,0,0],evidence='test')
        with self.assertRaises(DirectorError):tc.plan(o)
    def test_duplicate_role_target(self):
        o=options();o['target_roles']={'hips':'a','spine':'a'}
        with self.assertRaises(DirectorError):tc.plan(o)
    def test_bounded_sampling(self):
        for count in (1,258,True):
            o=options();o['check_count']=count
            with self.assertRaises(DirectorError):tc.plan(o)
    def test_review_exact_id_and_timezone(self):
        r=dict(plan_job_id='j_'+'a'*24,plan_id='tp_'+'b'*64,reviewer='test',reviewed_at='2026-09-14T12:00:00+02:00',approved=True)
        validate_review(r)
        for patch in ({'approved':False},{'approved':'yes'},{'reviewer':''},{'plan_id':'not-a-plan'},{'reviewed_at':'2026-09-14'}):
            with self.subTest(patch=patch),self.assertRaises(DirectorError):validate_review(r|patch)
    def test_bad_camera_before_paths_and_jobs(self):
        with tempfile.TemporaryDirectory() as tmp,Library(tmp) as lib:
            cases=[{'subjects':['mesh']},{'subjects':['mesh'],'camera':'Cam','frames':[1],'sample':{'start':1,'end':2,'count':2}},
                   {'subjects':['mesh'],'camera':'Cam','frames':[True]}, {'subjects':['mesh'],'camera':'Cam','occlusion':'yes'}]
            for c in cases:
                with self.subTest(c=c),self.assertRaises(DirectorError) as err:prepare(lib,'camera-check','missing.blend',options=c)
                self.assertNotEqual(err.exception.code,'INVALID_INPUT')
            self.assertEqual(list((Path(tmp)/'jobs').iterdir()),[])
    def test_camera_ray_budget_early(self):
        with self.assertRaises(DirectorError):tc.camera_check({'subjects':['a','b'],'camera':'Cam','frames':list(range(32)),'occlusion':True})
    def test_existing_camera_contract(self):
        tc.camera_check({'subjects':['mesh'],'camera':'Cam','sample':{'start':1,'end':2,'count':1}})
    def test_contact_fractional_checkpoints(self):
        self.assertEqual(tc.checkpoints({'sample':{'start':1,'end':2,'count':3}}),[1,1.5,2])
    def test_contact_overbudget_and_duplicate(self):
        for c in ({'frames':[1,1]}, {'sample':{'start':1,'end':2,'count':258}}, {'frames':[1],'sample':{}}):
            with self.assertRaises(DirectorError):tc.checkpoints(c)
    def test_alignment_rejects_invalid_matrices(self):
        eye=[1.,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
        tc.alignment({'target:hips':eye})
        for index,value in [(0,-1),(0,2),(4,.1),(15,0),(12,.1),(0,True),(0,float('nan'))]:
            changed=eye.copy();changed[index]=value
            with self.subTest(index=index,value=value),self.assertRaises(DirectorError):tc.alignment({'bone':changed})
    def test_alignment_bounded_and_not_script(self):
        for raw in ('bpy.ops...',[],{}, {'name':[1]*15}):
            with self.assertRaises(DirectorError):tc.alignment(raw)


class ContactEvidenceTests(unittest.TestCase):
    def sample(self,f,z,x=0):
        return {'frame':f,'time':f/30,'left':{'minimum_z':z,'centroid':[x,0,z]},'right':{'minimum_z':z,'centroid':[x,.1,z]}}
    def o(self):return {'ground_z':0,'meters_per_unit':1,'tolerance_m':.001,'near_ground_m':.02,'glide_speed_m_s':.05}
    def test_integer_pass_does_not_hide_subframe_penetration(self):
        r=summarize([self.sample(1,0),self.sample(1.5,-.01),self.sample(2,0)],self.o())
        self.assertTrue(r['extrema']['integer_frames']['penetration_within_tolerance'])
        self.assertFalse(r['extrema']['subframes']['penetration_within_tolerance'])
    def test_glide_not_locked_or_accepted(self):
        r=summarize([self.sample(1,0),self.sample(2,0,.1)],self.o())
        self.assertEqual(r['samples'][1]['left']['state'],'GLIDE_CANDIDATE')
        self.assertEqual(r['channels_changed'],[]);self.assertFalse(r['repair_applied'])
        self.assertEqual(r['performance'],'PENDING')
    def test_floating_airborne_not_inferred(self):
        r=summarize([self.sample(1,1),self.sample(2,1)],self.o())
        self.assertEqual(r['samples'][1]['left']['state'],'ABOVE_GROUND_UNCLASSIFIED')
    def test_meters_conversion(self):
        r=summarize([self.sample(1,-1)],self.o()|{'meters_per_unit':.01})
        self.assertAlmostEqual(r['extrema']['integer_frames']['max_penetration_m'],.01)
    def test_missing_subframes_not_pass(self):
        r=summarize([self.sample(1,0)],self.o())
        self.assertIsNone(r['extrema']['subframes']['penetration_within_tolerance'])
    def test_stationary_possible_not_confirmed(self):
        r=summarize([self.sample(1,0),self.sample(2,0)],self.o())
        self.assertEqual(r['samples'][1]['left']['state'],'PLANT_CANDIDATE')


if __name__=='__main__':unittest.main()
