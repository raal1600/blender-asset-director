"""Synthetic motion/rights/profile tests: no network, Blender or performer data."""
import copy
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from asset_director import motion_assets as ma, jobs, motion_contract
from asset_director.core import DirectorError, Library, digest, file_hash
from asset_director.motion_body import body_profile, build_profile, validate_profile
from asset_director.motion_review import contact_states, diagnostics, record_review
from asset_director.motion_scout import search


def skeleton(scale=1):
    specs=[('root',None,[0,0,0],[0,.1,0]),('hips','root',[0,.1,0],[0,.2,0]),
           ('spine','hips',[0,.2,0],[0,.5,0]),('head','spine',[0,.5,0],[0,.6,0])]
    for side,x in [('l',.1),('r',-.1)]:
        for role,parent,a,b in [('thigh','hips',.1,-.3),('calf','thigh',-.3,-.7),('foot','calf',-.7,-.8),
                ('upperarm','spine',.45,.25),('forearm','upperarm',.25,.05),('hand','forearm',.05,-.05)]:
            specs.append((role+'_'+side,parent if parent in ('hips','spine') else parent+'_'+side,[x,a,0],[x,b,0]))
    return {'joints':[{'name':n,'parent':p,'head':[v*scale for v in h],'tail':[v*scale for v in t],
                       'rotation':[1,0,0,0] if t[1]>h[1] else [0,1,0,0]} for n,p,h,t in specs],
        'roles':{n:n for n,*_ in specs},'source_fingerprint':digest([specs,scale])}


def example(lib,tmp,scale=1):
    terms=lib.root/'licenses/test.txt';terms.write_text('Synthetic fixture dedicated to CC0; not captured human motion.')
    evidence={'path':'licenses/test.txt','sha256':file_hash(terms),'size':terms.stat().st_size}
    sk=skeleton(scale);samples=[]
    for i in range(25):
        samples.append({'time':i/24,'positions':[[j['head'][0]+i*.001,*j['head'][1:]] for j in sk['joints']],
                        'rotations':[j['rotation'] for j in sk['joints']]})
    payload=Path(tmp)/'numeric.bin';p=ma.write_payload(payload,samples,len(sk['joints']))
    r={'schema':ma.SCHEMA,'source':{'provider':'local','source_id':'synthetic','source_url':'https://example.org/fixture',
        'raw_files':[{'sha256':'a'*64,'size':10}],'capture_method':'generated','capture_evidence':'Test generator, not human mocap'},
       'rights':{'license_id':'CC0-1.0','license_url':'https://creativecommons.org/publicdomain/zero/1.0/',
          'evidence':[evidence],'commercial':'allowed','adaptation':'allowed','raw_redistribution':'allowed','attribution':'Synthetic unit fixture'},
       'timing':{'duration_seconds':1,'sample_count':25,'source_frame_fps':24,'native_capture_fps':None,'sampling':'explicit_timestamps'},
       'coordinates':{'unit':'meter','up':'+Z','handedness':'right','source_to_canonical':[1,0,0,0,1,0,0,0,1],'meters_per_source_unit':1},
       'skeleton':sk,'payload':p,'semantics':{'title':'Synthetic Backslide','labels':['backslide'],'description':'Not actual dancing'},
       'lineage':[],'contact_annotations':[]}
    r['id']=ma.validate_record(r)
    return r,payload,samples


class MotionRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.lib=Library(Path(self.tmp.name)/'lib');self.addCleanup(self.lib.close)
        self.record,self.payload,self.samples=example(self.lib,self.tmp.name)
    def bad(self,record,code=None):
        record.pop('id',None)
        with self.assertRaises(DirectorError) as exc:ma.validate_record(record)
        if code:self.assertEqual(exc.exception.code,code)
    def test_roundtrip_time_and_values(self):
        decoded=ma.read_payload(self.payload,self.record)
        self.assertEqual([s['time'] for s in decoded],[s['time'] for s in self.samples])
        self.assertAlmostEqual(decoded[-1]['positions'][0][0],.024,places=7)
    def test_immutable_store_reuse(self):
        a=ma.store(self.lib,self.record,self.payload);b=ma.store(self.lib,self.record,self.payload)
        self.assertEqual(a['motion_id'],b['motion_id']);self.assertEqual(b['status'],'REUSED')
        self.assertEqual(len(list((self.lib.root/'motions').iterdir())),1)
    def test_unchanged_id_rejects_modified_record(self):
        self.record['semantics']['title']='changed'
        with self.assertRaises(DirectorError) as e:ma.validate_record(self.record)
        self.assertEqual(e.exception.code,'MOTION_HASH_MISMATCH')
    def test_corrupt_payload_rejected(self):
        self.payload.write_bytes(self.payload.read_bytes()+b'x')
        with self.assertRaises(DirectorError):ma.read_payload(self.payload,self.record)
    def test_corrupt_stored_evidence_rejected(self):
        ma.store(self.lib,self.record,self.payload);(self.lib.root/'licenses/test.txt').write_text('edited')
        with self.assertRaises(DirectorError):ma.load(self.lib,self.record['id'])
    def test_unknown_schema(self):
        self.record['schema']='asset-director.motion/99';self.bad(self.record,'MOTION_SCHEMA_VERSION')
    def test_cyclic_hierarchy(self):
        self.record['skeleton']['joints'][0]['parent']='head';self.bad(self.record,'INVALID_SKELETON')
    def test_two_roots(self):
        self.record['skeleton']['joints'][1]['parent']=None;self.bad(self.record,'INVALID_SKELETON')
    def test_duplicate_joint(self):
        self.record['skeleton']['joints'][1]['name']='root';self.bad(self.record,'INVALID_SKELETON')
    def test_roles_cannot_invent_joint(self):
        self.record['skeleton']['roles']['foot_l']='not observed';self.bad(self.record,'INVALID_SKELETON')
    def test_duplicate_role_binding(self):
        self.record['skeleton']['roles']['test']='root';self.bad(self.record,'INVALID_SKELETON')
    def test_rest_orientation_must_match_bone_direction(self):
        self.record['skeleton']['joints'][0]['rotation']=[0,1,0,0]
        self.bad(self.record,'INVALID_SKELETON')
    def test_sample_limit(self):
        self.record['timing']['sample_count']=10001;self.bad(self.record,'RESOURCE_LIMIT')
    def test_bad_quaternion(self):
        self.record['skeleton']['joints'][0]['rotation']=[2,0,0,0];self.bad(self.record)
    def test_reflection_rejected(self):
        self.record['coordinates']['source_to_canonical']=[-1,0,0,0,1,0,0,0,1];self.bad(self.record)
    def test_nan_rejected(self):
        self.record['timing']['duration_seconds']=float('nan');self.bad(self.record)
    def test_shape_lies_rejected(self):
        self.record['payload']['size']+=1;self.bad(self.record)
    def test_pickle_is_not_a_numeric_format(self):
        self.record['payload']['format']='pickle';self.bad(self.record)
    def test_credential_url_rejected(self):
        self.record['source']['source_url']='https://user:password@example.org/a';self.bad(self.record)
    def test_signed_url_not_stored(self):
        self.record['source']['source_url']='https://example.org/a?token=secret';self.bad(self.record)
    def test_capture_type_requires_evidence(self):
        self.record['source']['capture_evidence']='';self.bad(self.record,'CAPTURE_EVIDENCE_REQUIRED')
    def test_evidence_path_escape(self):
        self.record['rights']['evidence'][0]['path']='../secrets';self.bad(self.record,'UNSAFE_PATH')
    def test_contacts_cannot_overlap(self):
        a={'role':'foot_l','start':0,'end':.6,'state':'GLIDING','evidence':'test annotated'}
        self.record['contact_annotations']=[a,{**a,'start':.5,'end':1}];self.bad(self.record)
    def test_unknown_contact_role(self):
        self.record['contact_annotations']=[{'role':'fake','start':0,'end':1,'state':'PLANTED','evidence':'x'}];self.bad(self.record)
    def test_unknown_project_cannot_pass(self):
        self.assertFalse(ma.rights_gate(self.record['source'],self.record['rights'],'unknown')['eligible'])
    def test_research_provider_blocks_commercial_flag_override(self):
        for provider in ('gvhmr','amass','babel','humanml3d'):
            self.assertFalse(ma.rights_gate({'provider':provider},self.record['rights'],'commercial')['eligible'])
    def test_no_adaptation_permission(self):
        self.record['rights']['adaptation']='unknown'
        self.assertFalse(ma.rights_gate(self.record['source'],self.record['rights'],'noncommercial')['eligible'])
    def test_nc_never_wins_commercial(self):
        self.record['rights']['license_id']='CC-BY-NC-4.0'
        self.assertFalse(ma.rights_gate(self.record['source'],self.record['rights'],'commercial')['eligible'])
    def test_local_search_offline_and_no_rewrite(self):
        ma.store(self.lib,self.record,self.payload)
        path=self.lib.root/'motions'/self.record['id']/'record.json';before=path.stat().st_mtime_ns
        with patch('asset_director.motion_scout.Providers',side_effect=AssertionError('network used')):
            found=search(self.lib,'moonwalking','commercial')
        self.assertEqual(found['results'][0]['id'],self.record['id']);self.assertEqual(path.stat().st_mtime_ns,before)
    def test_empty_library_keeps_discovery_routes(self):
        result=search(self.lib,'clapping','commercial')
        self.assertEqual(result['decision'],'CONTINUE_APPROVED_DISCOVERY')
        self.assertIn('cmu',[r['provider'] for r in result['discovery_tasks']])
    def test_network_failure_is_unknown_not_no_assets(self):
        with patch('asset_director.motion_scout.Providers.search',side_effect=DirectorError('NETWORK_ERROR','failed')):
            result=search(self.lib,'dance','commercial',remote=True)
        self.assertTrue(all(x.get('results')=='UNKNOWN_NOT_ZERO' for x in result['sources'] if x['provider']!='local'))
    def test_review_cannot_approve_stills(self):
        ma.store(self.lib,self.record,self.payload)
        review={'motion_id':self.record['id'],'decision':'ACCEPT','reviewer':'image_model','evidence_kind':'stills',
                'artifacts':self.record['rights']['evidence'],'notes':'Example, not approval'}
        with self.assertRaises(DirectorError) as e:record_review(self.lib,review)
        self.assertEqual(e.exception.code,'TEMPORAL_EVIDENCE_REQUIRED')
    def test_review_cannot_approve_metrics(self):
        ma.store(self.lib,self.record,self.payload)
        review={'motion_id':self.record['id'],'decision':'ACCEPT','reviewer':'human','evidence_kind':'metrics',
                'artifacts':self.record['rights']['evidence'],'notes':'Example'}
        with self.assertRaises(DirectorError):record_review(self.lib,review)
    def test_review_allows_uncertain_and_is_idempotent(self):
        ma.store(self.lib,self.record,self.payload)
        review={'motion_id':self.record['id'],'decision':'UNCERTAIN','reviewer':'image_model','evidence_kind':'stills',
                'artifacts':self.record['rights']['evidence'],'notes':'Cannot judge temporal motion from a still'}
        self.assertEqual(record_review(self.lib,review)['review_id'],record_review(self.lib,review)['review_id'])
    def test_explicit_motion_id_is_hashed_into_job(self):
        ma.store(self.lib,self.record,self.payload)
        baseline=Path(self.tmp.name)/'fixture.blend';baseline.write_bytes(b'fixture')
        j=jobs.prepare(self.lib,'clay-proxy',str(baseline),options={'motion_id':self.record['id'],'project_use':'commercial'})
        self.assertEqual(len(j['specification']['source_files']),3);self.assertIn('clay-proxy',jobs.MUTATIONS)
    def test_clay_requires_a_working_target(self):
        ma.store(self.lib,self.record,self.payload)
        with self.assertRaises(DirectorError) as e:jobs.prepare(self.lib,'clay-proxy',options={'motion_id':self.record['id'],'project_use':'commercial'})
        self.assertEqual(e.exception.code,'TARGET_REQUIRED')
    def test_read_job_catches_numeric_tampering(self):
        ma.store(self.lib,self.record,self.payload)
        j=jobs.prepare(self.lib,'motion-source',options={'motion_id':self.record['id'],'project_use':'commercial','fps':24})
        p=self.lib.root/'motions'/self.record['id']/'motion.bin';p.write_bytes(b'x'*p.stat().st_size)
        with self.assertRaises(DirectorError):jobs.read_job(self.lib,j['id'])
    def test_source_only_refuses_input_file(self):
        with self.assertRaises(DirectorError) as e:jobs.prepare(self.lib,'motion-source','anything.blend',options={'motion_id':self.record['id'],'project_use':'commercial','fps':24})
        self.assertEqual(e.exception.code,'SOURCE_ONLY_OPERATION')


class BodyAndContactTests(unittest.TestCase):
    def test_leg_ratio(self):
        p=build_profile(skeleton(),skeleton(.75));self.assertAlmostEqual(p['suggested_translation_scale_xyz'][0],.75)
        self.assertEqual(p['status'],'ALIGNMENT_REVIEW_REQUIRED')
    def test_profile_stability(self):
        self.assertEqual(build_profile(skeleton(),skeleton(.75)),build_profile(skeleton(),skeleton(.75)))
    def test_profile_detects_stale_pair(self):
        p=build_profile(skeleton(),skeleton(.75))
        with self.assertRaises(DirectorError):validate_profile(p,target_fingerprint='a'*64)
    def test_profile_detects_modified_settings(self):
        p=build_profile(skeleton(),skeleton(.75));p['suggested_translation_scale_xyz'][0]=2
        with self.assertRaises(DirectorError):validate_profile(p)
    def test_world_distance_policy(self):
        self.assertEqual(build_profile(skeleton(),skeleton(.75),'preserve_world')['suggested_translation_scale_xyz'],[1,1,1])
    def test_missing_leg_refuses_automatic_scale(self):
        sk=skeleton();del sk['roles']['calf_l']
        with self.assertRaises(DirectorError):build_profile(sk,skeleton())
    def test_crossed_semantic_hierarchy_refused(self):
        sk=skeleton();sk['roles']['calf_l'],sk['roles']['calf_r']=sk['roles']['calf_r'],sk['roles']['calf_l']
        with self.assertRaises(DirectorError):body_profile(sk)
    def test_stationary_contact(self):
        result=contact_states([i*.1 for i in range(10)],[[0,0,0]]*10,ground_z=0,sole_offset=0)
        self.assertIn('PLANTED_CANDIDATE',result['state_counts']);self.assertEqual(result['intent'],'UNKNOWN')
    def test_glide_is_not_locked_or_certified_intentional(self):
        result=contact_states([i*.1 for i in range(10)],[[i*.1,0,0] for i in range(10)],ground_z=0,sole_offset=0)
        self.assertIn('GLIDING_CANDIDATE',result['state_counts']);self.assertFalse(result['automatic_pose_correction'])
    def test_jump_airborne(self):
        result=contact_states([i*.1 for i in range(10)],[[i*.1,0,.2] for i in range(10)],ground_z=0,sole_offset=0)
        self.assertEqual(result['state_counts']['AIRBORNE'],9)
    def test_hysteresis_threshold_validation(self):
        with self.assertRaises(DirectorError):contact_states([0,1],[[0,0,0]]*2,ground_z=0,sole_offset=0,thresholds={'contact_height_m':1})
    def test_time_must_increase(self):
        with self.assertRaises(DirectorError):contact_states([1,1],[[0,0,0]]*2,ground_z=0,sole_offset=0)
    def test_penetration_is_not_contact_certification(self):
        result=contact_states([i*.1 for i in range(10)],[[0,0,-.5]]*10,ground_z=0,sole_offset=0)
        self.assertNotIn('PLANTED_CANDIDATE',result['state_counts'])
    def test_root_axis_scale_no_double_scaling(self):
        from asset_director.pose_contract import validate
        config={'rotation':[1,0,0,0,1,0,0,0,1],'translation_bone':'hips','translation_scale':2,
                'translation_scale_xyz':[.7,.7,.8],'target_origin':[0,0,0]}
        with self.assertRaises(DirectorError):validate(config)
        config['translation_scale']=1;validate(config)
    def test_root_axis_scale_limits(self):
        from asset_director.pose_contract import validate
        config={'rotation':[1,0,0,0,1,0,0,0,1],'translation_bone':'hips','translation_scale':1,
                'translation_scale_xyz':[.1,1,1],'target_origin':[0,0,0]}
        with self.assertRaises(DirectorError):validate(config)
    def test_clay_rejects_extreme_lengths(self):
        with self.assertRaises(DirectorError):motion_contract.validate('clay-proxy',{'motion_id':'m_'+'a'*64,'project_use':'commercial','length_scales':{'calf_l':.01}})
    def test_command_injection_not_in_contract(self):
        with self.assertRaises(DirectorError):motion_contract.validate('motion-source',{'motion_id':'m_'+'a'*64,'project_use':'commercial','fps':24,'python':'delete everything'})
    def test_singular_source_rotation(self):
        with self.assertRaises(DirectorError):ma.rotation([0]*9)

if __name__=='__main__':unittest.main()
