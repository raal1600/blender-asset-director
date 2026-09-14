"""Regressions from the first real-source 0.6-dev acceptance."""
import copy
import unittest
from asset_director.motion_body import body_profile
from asset_director.motion_morph import inclusive_scene_end, morph_skeleton
from asset_director.core import digest


def decorative_skeleton():
    # The anatomical landmarks are JOINT HEADS. Tails intentionally point away
    # from child heads to reproduce imported rigs whose Blender display bones are
    # disconnected/decorative rather than connected anatomical segments.
    joints=[
      {'name':'root','parent':None,'head':[0,0,0],'tail':[0,0.55,0],'rotation':[1,0,0,0]},
      {'name':'hips','parent':'root','head':[0,0.1,0],'tail':[0.25,0.1,0],'rotation':[1,0,0,0]},
      {'name':'thigh.L','parent':'hips','head':[.12,.1,0],'tail':[.12,.1,.27],'rotation':[1,0,0,0]},
      {'name':'shin.L','parent':'thigh.L','head':[.12,-.35,0],'tail':[.4,-.35,0],'rotation':[1,0,0,0]},
      {'name':'foot.L','parent':'shin.L','head':[.12,-.78,0],'tail':[.12,-.9,.18],'rotation':[1,0,0,0]},
      {'name':'thigh.R','parent':'hips','head':[-.12,.1,0],'tail':[-.12,.1,.27],'rotation':[1,0,0,0]},
      {'name':'shin.R','parent':'thigh.R','head':[-.12,-.35,0],'tail':[-.4,-.35,0],'rotation':[1,0,0,0]},
      {'name':'foot.R','parent':'shin.R','head':[-.12,-.78,0],'tail':[-.12,-.9,.18],'rotation':[1,0,0,0]},
    ]
    # Orientations need only be proper unit quaternions for this pure morphology
    # regression; Blender creates its own rest matrices in the integration test.
    roles={'root':'root','hips':'hips','thigh_l':'thigh.L','calf_l':'shin.L','foot_l':'foot.L',
           'thigh_r':'thigh.R','calf_r':'shin.R','foot_r':'foot.R'}
    sk={'joints':joints,'roles':roles,'source_fingerprint':digest(joints)}
    return sk


class MorphologyRegressionTests(unittest.TestCase):
    def test_semantic_chain_scaling_ignores_decorative_tails(self):
        source=decorative_skeleton()
        before=body_profile(source)
        fitted=morph_skeleton(source,{'thigh_l':.7,'calf_l':.7,'thigh_r':.7,'calf_r':.7})
        after=body_profile(fitted)
        self.assertAlmostEqual(after['chains']['leg_l']['length_m']/before['chains']['leg_l']['length_m'],.7,places=7)
        self.assertAlmostEqual(after['chains']['leg_r']['length_m']/before['chains']['leg_r']['length_m'],.7,places=7)
        # The source is immutable and its intentionally misleading tails stay so.
        self.assertEqual(source,decorative_skeleton())

    def test_child_heads_follow_parent_semantic_span_not_parent_tail(self):
        source=decorative_skeleton();fitted=morph_skeleton(source,{'thigh_l':.5})
        src={j['name']:j for j in source['joints']};dst={j['name']:j for j in fitted['joints']}
        original=[src['shin.L']['head'][i]-src['thigh.L']['head'][i] for i in range(3)]
        changed=[dst['shin.L']['head'][i]-dst['thigh.L']['head'][i] for i in range(3)]
        for a,b in zip(changed,original):self.assertAlmostEqual(a,b*.5,places=7)
        self.assertNotEqual(dst['shin.L']['head'],dst['thigh.L']['tail'])

    def test_fractional_final_key_gets_inclusive_scene_frame(self):
        end,exact=inclusive_scene_end(1,4.961,30)
        self.assertAlmostEqual(exact,149.83,places=7)
        self.assertEqual(end,150)

    def test_near_integer_endpoint_is_not_extended_an_extra_frame(self):
        end,exact=inclusive_scene_end(1,149/30+1e-9,30)
        self.assertAlmostEqual(exact,150.00000003,places=6)
        self.assertEqual(end,150)

    def test_true_fractional_endpoint_ceil_is_intentional(self):
        end,_=inclusive_scene_end(1,4.9667,30)
        self.assertEqual(end,151)


if __name__=='__main__':unittest.main()
