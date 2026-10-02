import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path
from asset_director import shot_view_contract, viewer_timebase
from asset_director.core import DirectorError


class ShotViewTests(unittest.TestCase):
    def test_saved_shot_identity_is_bounded_and_not_an_edit(self):
        value = {'version': 'shot-view-v1', 'id': 'shot_'+'1'*8+'-'+'1'*4+'-'+'1'*4+'-'+'1'*4+'-'+'1'*12,
                 'revision': 1, 'name': 'Observed shot', 'camera': 'Observed camera', 'start': 5, 'end': 9}
        self.assertEqual(shot_view_contract.validate(value), value)
        for patch in [{'script': 'no'}, {'revision': True}, {'id': 'foreign'}, {'version': 'future'},
                      {'start': 1.5}, {'end': 365}, {'end': 4}, {'camera': ''}, {'name': 'no\n'}]:
            with self.subTest(patch=patch), self.assertRaises(DirectorError):shot_view_contract.validate(value | patch)

    def glb(self, times, interpolation='LINEAR'):
        binary = struct.pack('<'+'f'*len(times), *times)
        data = {'asset': {'version': '2.0'}, 'buffers': [{'byteLength': len(binary)}],
                'bufferViews': [{'buffer': 0, 'byteLength': len(binary)}],
                'accessors': [{'componentType': 5126, 'type': 'SCALAR', 'bufferView': 0,
                               'count': len(times), 'min': [min(times)], 'max': [max(times)]}],
                'animations': [{'samplers': [{'input': 0, 'output': 1, 'interpolation': interpolation}], 'channels': []}]}
        encoded = json.dumps(data).encode();encoded += b' '*((-len(encoded)) % 4)
        return struct.pack('<4sII', b'glTF', 2, 28+len(encoded)+len(binary))+struct.pack('<II', len(encoded), 0x4e4f534a)+encoded+struct.pack('<II', len(binary), 0x004e4942)+binary

    def test_fractional_fps_corrects_only_verified_derivative_times(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'preview.glb'
            for rate in [30/1.001, 30, 30*1.001]:
                target.write_bytes(self.glb([f/rate for f in range(9)]))
                result = viewer_timebase.normalize(target, 1, 9, 30, 1.001)
                self.assertFalse(result['original_scene_changed'])
                raw = target.read_bytes();length = struct.unpack_from('<I', raw, 12)[0]
                times = struct.unpack_from('<9f', raw, 28+length)
                for frame, time in enumerate(times):self.assertAlmostEqual(time, frame/(30/1.001), places=6)

    def test_unknown_partial_unordered_and_nonfinite_timing_refuses_without_write(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'preview.glb'
            for times in [[0, .1], [0, .2, .1], [0, float('nan')], [.2], [0, .12, 8/30.03]]:
                raw = self.glb(times);target.write_bytes(raw)
                with self.subTest(times=times), self.assertRaises(DirectorError):viewer_timebase.normalize(target, 1, 9, 30, 1.001)
                self.assertEqual(target.read_bytes(), raw)
            raw = self.glb([0, 8/30.03], 'CUBICSPLINE');target.write_bytes(raw)
            with self.assertRaises(DirectorError):viewer_timebase.normalize(target, 1, 9, 30, 1.001)
            self.assertEqual(target.read_bytes(), raw)


if __name__ == '__main__':unittest.main()
