"""Cross-scene contracts: fixture genres are test data, never runtime recipes."""
import json
from pathlib import Path
import tempfile
import unittest
from asset_director.core import DirectorError, digest, file_hash, plan
from asset_director.studio import compile_plan, validate_handoff, validate_review, ROLES


def audit(names=('opaque_name_9','some_other_object'), kind='MESH', fps=30):
    return {'objects':[{'name':n,'type':kind} for n in names], 'fps':fps, 'resolution':[900,1600]}


def brief(names=('opaque_name_9',), capabilities=('camera',)):
    return {'schema_version':1,'goal':'Respect the supplied brief and assets','deliverable':'scene',
            'capabilities':list(capabilities),'targets':{'subject':list(names)},'requirements':[]}


class StudioCase(unittest.TestCase):
    def test_plain_prompt_never_fabricates_scene(self):
        for p in ('A desert sentinel walks','A perfume bottle on a plinth','A quiet interior','A logo reveal','Une forêt enneigée','مجسم تجريدي'):
            with self.subTest(prompt=p):
                r=plan(p)
                self.assertEqual(r['goal'],p); self.assertEqual(r['targets'],{}); self.assertEqual(r['requirements'],[])
                self.assertEqual(r['shots'],[]); self.assertEqual(r['status'],'HOST_INTERPRETATION_REQUIRED')
    def test_empty_prompt_rejected(self):
        with self.assertRaises(DirectorError): plan(' ')
    def test_product_needs_no_performer(self):
        p=compile_plan(brief(capabilities=('camera','lighting','materials')),audit())
        self.assertNotIn('performance',[r['name'] for r in p['roles']]); self.assertEqual(p['gap_queries'],[])
    def test_environment_needs_no_character(self):
        p=compile_plan(brief(capabilities=('set','camera')),audit())
        self.assertNotIn('performance',[r['name'] for r in p['roles']]); self.assertEqual(p['limitations'],[])
    def test_material_repair_skips_camera(self):
        p=compile_plan(brief(capabilities=('materials',)),audit())
        self.assertEqual([r['name'] for r in p['roles']],['director-producer','lighting-lookdev','continuity-qa'])
    def test_abstract_animation_routes_performance_without_rig_gate(self):
        p=compile_plan(brief(capabilities=('object-motion','graphics')),audit())
        self.assertIn('performance',[r['name'] for r in p['roles']]); self.assertEqual(p['limitations'],[])
    def test_character_motion_reports_missing_rig(self):
        p=compile_plan(brief(capabilities=('character-motion',)),audit())
        self.assertIn('RIG_ASSESSMENT_REQUIRED',p['limitations'][0])
    def test_armature_presence_is_not_skinning_proof(self):
        p=compile_plan(brief(capabilities=('character-motion',)),audit(kind='ARMATURE'))
        self.assertEqual(p['status'],'CONTRACT_VALIDATED_NOT_EXECUTED'); self.assertEqual(p['visual_acceptance'],'PENDING')
    def test_default_preserve_is_observed_not_hero(self):
        self.assertEqual(compile_plan(brief(),audit())['preserve'],['opaque_name_9','some_other_object'])
    def test_unknown_target_fails(self):
        with self.assertRaises(DirectorError): compile_plan(brief(('guessed_hero',)),audit())
    def test_arbitrary_unicode_names(self):
        p=compile_plan(brief(('瓶_β.091',)),audit(('瓶_β.091',)))
        self.assertEqual(p['targets']['subject'],['瓶_β.091'])
    def test_no_required_naming_prefix(self):
        for name in ('Cube.087','ship cargo','0042','混合 объект'):
            with self.subTest(name=name): compile_plan(brief((name,)),audit((name,)))
    def test_no_required_origin_units_or_aspect(self):
        a=audit(); a.update(units={'system':'METRIC','scale_length':.01},resolution=[1000,1000])
        self.assertEqual(compile_plan(brief(),a)['fps'],30)
    def test_only_missing_assets_generate_queries(self):
        b=brief(capabilities=('assets',)); b['requirements']=[
            {'id':'keep','kind':'model','state':'reuse','refs':['opaque_name_9'],'evidence':['User supplied this subject']},
            {'id':'missing','kind':'material','state':'missing','query':'brushed ceramic','refs':[],'evidence':['No suitable material observed']},
            {'id':'unclear','kind':'other','state':'uncertain','refs':[],'evidence':['Needs closer inspection']}]
        p=compile_plan(b,audit())
        self.assertEqual([q['query'] for q in p['gap_queries']],['brushed ceramic'])
        self.assertEqual(p['blocked_requirements'][0]['reason'],'ASSESSMENT_REQUIRED')
    def test_missing_needs_scout_capability(self):
        b=brief(); b['requirements']=[{'id':'x','kind':'model','state':'missing','query':'prop','refs':[],'evidence':['needed']}]
        with self.assertRaises(DirectorError): compile_plan(b,audit())
    def test_existing_not_falsely_absent(self):
        b=brief(capabilities=('assets',)); b['requirements']=[{'id':'x','kind':'model','state':'missing','query':'prop','refs':['opaque_name_9'],'evidence':['wrong style']}]
        with self.assertRaises(DirectorError): compile_plan(b,audit())
    def test_reuse_needs_observed_references(self):
        b=brief(); b['requirements']=[{'id':'x','kind':'model','state':'reuse','refs':[],'evidence':['claimed']}]
        with self.assertRaises(DirectorError): compile_plan(b,audit())
    def test_assessment_needs_evidence(self):
        b=brief(); b['requirements']=[{'id':'x','kind':'model','state':'reuse','refs':['opaque_name_9'],'evidence':[]}]
        with self.assertRaises(DirectorError): compile_plan(b,audit())
    def test_nonvisual_work_does_not_start_sound(self):
        self.assertNotIn('sound',compile_plan(brief(),audit())['capabilities'])
    def test_audio_planning_limit_explicit(self):
        self.assertIn('planning-only',compile_plan(brief(capabilities=('sound',)),audit())['limitations'][0])
    def test_shot_timebase_not_fixed(self):
        b=brief(); b['shots']=[{'id':'s1','purpose':'Read the subject','frames':[42,65],'targets':['subject']}]
        p=compile_plan(b,audit(fps=23.976)); self.assertEqual(p['fps'],23.976); self.assertEqual(p['shots'][0]['frames'],[42,65])
    def test_still_does_not_invent_shots(self):
        b=brief(); b['deliverable']='still'; self.assertEqual(compile_plan(b,audit())['shots'],[])
    def test_invalid_fps(self):
        b=brief(); b['shots']=[{'id':'s1','purpose':'read','frames':[1,2],'targets':['subject']}]
        for fps in (None,0,-1,float('nan'),True):
            with self.subTest(fps=fps),self.assertRaises(DirectorError): compile_plan(b,audit(fps=fps))
    def test_budget_cannot_escalate(self):
        for budget in ({'preview_frames':9},{'repair_passes':3},{'paid_assets':1},{'local_ai':True},{'heavy_gpu_render':True}):
            b=brief(); b['budget']=budget
            with self.subTest(budget=budget),self.assertRaises(DirectorError): compile_plan(b,audit())
    def test_unsupported_capability(self):
        with self.assertRaises(DirectorError): compile_plan(brief(capabilities=('invent-everything',)),audit())
    def test_schema_typo_rejected(self):
        b=brief(); b['targtes']={}
        with self.assertRaises(DirectorError): compile_plan(b,audit())
    def test_duplicate_names_rejected(self):
        with self.assertRaises(DirectorError): compile_plan(brief(),audit(('opaque_name_9','opaque_name_9')))
    def test_plan_reproducible(self):
        self.assertEqual(compile_plan(brief(),audit()),compile_plan(brief(),audit()))
    def test_changed_scene_changes_plan(self):
        self.assertNotEqual(compile_plan(brief(),audit())['plan_id'],compile_plan(brief(),audit(fps=60))['plan_id'])
    def proposal(self,p):
        return {'plan_id':p['plan_id'],'audit_revision':p['audit_revision'],'role':'cinematography','capability':'camera','subjects':['opaque_name_9'],'reason':'Frame the requested subject'}
    def test_handoff_validated_not_executed(self):
        p=compile_plan(brief(),audit())
        self.assertEqual(validate_handoff(p,self.proposal(p),audit())['status'],'HANDOFF_VALIDATED_NOT_EXECUTED')
    def test_stale_handoff_rejected(self):
        p=compile_plan(brief(),audit())
        with self.assertRaises(DirectorError): validate_handoff(p,self.proposal(p),audit(fps=60))
    def test_reviewer_cannot_own_camera_change(self):
        p=compile_plan(brief(),audit()); q=self.proposal(p); q['role']='continuity-qa'
        with self.assertRaises(DirectorError): validate_handoff(p,q,audit())
    def test_change_outside_target_scope_rejected(self):
        p=compile_plan(brief(),audit()); q=self.proposal(p); q['subjects']=['some_other_object']
        with self.assertRaises(DirectorError): validate_handoff(p,q,audit())
    def test_visual_pass_requires_images_and_capability(self):
        r={'audit_revision':digest(audit()),'technical':'UNTESTED','visual':'PASS','evidence':[],'findings':[]}
        for vision in (True,False):
            with self.subTest(vision=vision),self.assertRaises(DirectorError): validate_review(r,audit(),vision_available=vision)
    def test_stale_review(self):
        r={'audit_revision':digest(audit()),'technical':'UNTESTED','visual':'PENDING','evidence':[],'findings':[]}
        with self.assertRaises(DirectorError): validate_review(r,audit(fps=60))
    def test_review_does_not_claim_human_acceptance(self):
        r={'audit_revision':digest(audit()),'technical':'UNTESTED','visual':'PENDING','evidence':[],'findings':[]}
        self.assertEqual(validate_review(r,audit())['human_acceptance'],'NOT_ESTABLISHED')
    def test_evidence_file_changed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'evidence.json'; p.write_text('{}'); h=file_hash(p); p.write_text('[]')
            r={'audit_revision':digest(audit()),'technical':'PASS','visual':'PENDING','evidence':[{'path':str(p),'sha256':h}],'findings':[]}
            with self.assertRaises(DirectorError): validate_review(r,audit())
    def test_actual_technical_report(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'evidence.json'; p.write_text('{}')
            r={'audit_revision':digest(audit()),'technical':'PASS','visual':'PENDING','evidence':[{'path':str(p),'sha256':file_hash(p)}],'findings':[]}
            self.assertEqual(validate_review(r,audit())['technical'],'PASS')
    def test_role_files_present_and_routed(self):
        root=Path(__file__).parents[1]/'skills/blender-asset-director'
        for name in ROLES: self.assertTrue((root/'references/roles'/f'{name}.md').is_file())
    def test_runtime_contains_no_benchmark_filename(self):
        root=Path(__file__).parents[1]/'src/asset_director'
        for name in ('studio.py','scene_ops.py'):
            self.assertNotIn('Desert Warrior.blend',(root/name).read_text(encoding='utf-8'))

if __name__=='__main__': unittest.main()
