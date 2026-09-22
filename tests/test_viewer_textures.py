"""Portable budget evidence, separate from real Blender export tests."""
import copy
import unittest
from asset_director.core import DirectorError
from asset_director.viewer_textures import plan, MAX_PIXELS


def image(width, height, source='FILE'):
    return {'name': 'Synthetic texture', 'size': [width, height], 'source': source}


class ViewerTextureTests(unittest.TestCase):
    def test_large_aggregate_becomes_bounded_without_mutating_input(self):
        images = [image(4096, 4096) for _ in range(5)]
        before = copy.deepcopy(images)
        report = plan(images)
        self.assertGreater(report['source_pixels'], 64 * 1024**2)
        self.assertLessEqual(report['preview_pixels'], MAX_PIXELS)
        self.assertEqual(report['reduced_images'], 5)
        self.assertEqual(report['scope'], 'PREVIEW_ONLY')
        self.assertFalse(report['originals_changed'])
        self.assertEqual(images, before)

    def test_aspect_ratio_small_images_and_empty_buffers(self):
        report = plan([image(4096, 2048), image(32, 64), image(0, 0, 'VIEWER')])
        self.assertEqual([i['preview_size'] for i in report['images']], [[2048, 1024], [32, 64], [0, 0]])
        self.assertEqual(report['reduced_images'], 1)
        self.assertEqual(plan([])['preview_pixels'], 0)

    def test_source_bounds_and_unsupported_animation_fail_closed(self):
        for images in [[image(8193, 1)], [image(8192, 8192)] * 3, [image(1, 1)] * 129,
                       [image(-1, 2)], [image(0, 2)], [image(True, 1)],
                       *[[image(32, 32, kind)] for kind in ['MOVIE', 'SEQUENCE', 'TILED']]]:
            with self.subTest(images=images), self.assertRaises(DirectorError):
                plan(images)
