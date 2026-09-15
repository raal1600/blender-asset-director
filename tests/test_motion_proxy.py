"""Pure regressions for accidental controller/helper surfaces (no bpy/network)."""
import copy
import unittest
from asset_director.core import DirectorError
from asset_director.motion_proxy import anatomy_graph, VISUAL_SCHEMA
from test_motion_foundation import skeleton


class AnatomyGraphTests(unittest.TestCase):
    def setUp(self):
        self.source = skeleton()

    def test_root_is_not_a_visible_body_landmark_or_segment(self):
        graph = anatomy_graph(self.source)
        self.assertIn('root', graph['excluded_bones'])
        self.assertNotIn('root', [v['bone'] for v in graph['landmarks']])
        self.assertFalse(any('root' in (s['start_bone'], s['end_bone']) for s in graph['segments']))
        self.assertFalse(graph['terminal_display_tails_used'])

    def test_no_tails_can_create_terminal_surface(self):
        before = anatomy_graph(self.source)
        for j in self.source['joints']:
            j['tail'] = [j['head'][i] + 500*(j['tail'][i]-j['head'][i]) for i in range(3)]
        self.assertEqual(before, anatomy_graph(self.source))

    def test_unmapped_upper_body_leaf_does_not_become_a_capsule(self):
        self.source['joints'].append({'name': 'decorative_leaf', 'parent': 'head',
                                     'head': [8, 4, 2], 'tail': [8, 40, 2], 'rotation': [1, 0, 0, 0]})
        graph = anatomy_graph(self.source)
        self.assertIn('decorative_leaf', graph['excluded_bones'])
        self.assertNotIn('decorative_leaf', [v['bone'] for v in graph['landmarks']])

    def test_declared_nonanatomical_role_is_still_not_a_body_part(self):
        self.source['roles']['motion_controller'] = self.source['roles'].pop('root')
        graph = anatomy_graph(self.source)
        self.assertIn('motion_controller', graph['excluded_roles'])
        self.assertIn('root', graph['excluded_bones'])

    def test_helpers_between_landmarks_are_skipped_not_deleted(self):
        helper = {'name': 'spine_helper', 'parent': 'spine', 'head': [2, 5, 6],
                  'tail': [2, 6, 6], 'rotation': [1, 0, 0, 0]}
        self.source['joints'].insert(3, helper)
        next(j for j in self.source['joints'] if j['name'] == 'head')['parent'] = 'spine_helper'
        original = copy.deepcopy(self.source)
        graph = anatomy_graph(self.source)
        link = next(s for s in graph['segments'] if s['end_role'] == 'head')
        self.assertEqual(link['start_role'], 'spine')
        self.assertEqual(link['skipped_helpers'], ['spine_helper'])
        self.assertEqual(self.source, original)

    def test_roles_not_raw_names_choose_visible_anatomy(self):
        rename = {j['name']: f'ObservedNode-{i}' for i, j in enumerate(self.source['joints'])}
        for j in self.source['joints']:
            j['name'] = rename[j['name']]
            j['parent'] = rename[j['parent']] if j['parent'] else None
        self.source['roles'] = {r: rename[n] for r, n in self.source['roles'].items()}
        graph = anatomy_graph(self.source)
        self.assertIn(rename['root'], graph['excluded_bones'])
        self.assertEqual(len(graph['landmarks']), len(rename)-1)

    def test_hips_required_instead_of_guessing_from_controller(self):
        del self.source['roles']['hips']
        with self.assertRaises(DirectorError) as e:
            anatomy_graph(self.source)
        self.assertEqual(e.exception.code, 'PROXY_ANATOMY_REVIEW_REQUIRED')

    def test_anatomy_outside_pelvis_subtree_is_refused(self):
        next(j for j in self.source['joints'] if j['name'] == 'head')['parent'] = 'root'
        with self.assertRaises(DirectorError): anatomy_graph(self.source)

    def test_coincident_landmarks_are_reported_without_zero_length_capsules(self):
        head = next(j for j in self.source['joints'] if j['name'] == 'head')
        head['head'] = [0, .2, 0]; head['tail'] = [0, .6, 0]
        graph = anatomy_graph(self.source)
        self.assertTrue(any(s['end_role'] == 'head' for s in graph['coincident_links']))
        self.assertFalse(any(s['end_role'] == 'head' for s in graph['segments']))

    def test_anatomy_graph_is_deterministic_and_nonmutating(self):
        original = copy.deepcopy(self.source)
        graph = anatomy_graph(self.source)
        self.assertEqual(graph, anatomy_graph(self.source))
        self.assertEqual(graph['schema'], VISUAL_SCHEMA)
        self.assertEqual(original, self.source)

    def test_anatomy_does_not_require_every_optional_role(self):
        graph = anatomy_graph(self.source)
        self.assertNotIn('neck', [n['role'] for n in graph['landmarks']])
        self.assertTrue(any(s['start_role'] == 'spine' and s['end_role'] == 'head' for s in graph['segments']))

    def test_one_landmark_is_not_sufficient_for_body_geometry(self):
        self.source['roles'] = {'hips': 'hips'}
        with self.assertRaises(DirectorError): anatomy_graph(self.source)


if __name__ == '__main__': unittest.main()
