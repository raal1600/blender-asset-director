"""Portable verifier regression tests, not approval or playback of a recording."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('showcase_verifier', ROOT/'tools/verify_showcase_media.py')
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)


class ShowcaseMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.data = b'unit fixture, not a real MP4'
        self.spec = {'filename':'latest-demo.mp4','bytes':len(self.data),
                     'sha256':hashlib.sha256(self.data).hexdigest()}
        self.file = self.directory/self.spec['filename']; self.file.write_bytes(self.data)
        self.manifest = json.loads(v.MANIFEST.read_text(encoding='utf-8'))
        self.video = self.manifest['video']
        self.probe = {'streams':[{'codec_type':'video','codec_name':'h264','width':960,'height':800,
                                 'pix_fmt':'yuv420p','avg_frame_rate':'30/1','nb_read_frames':'120'}],
                      'format':{'duration':'4.000000'}}

    def test_exact_bytes_pass_identity_not_decode(self):
        self.assertEqual(v.checked_bytes(self.directory,self.spec),self.data)

    def test_missing_media_has_actionable_code(self):
        self.file.unlink()
        with self.assertRaises(v.MediaError) as e:v.checked_bytes(self.directory,self.spec)
        self.assertEqual(e.exception.code,'MISSING_APPROVED_MEDIA')

    def test_truncated_file_is_rejected(self):
        self.file.write_bytes(self.data[:-1])
        with self.assertRaises(v.MediaError) as e:v.checked_bytes(self.directory,self.spec)
        self.assertEqual(e.exception.code,'MEDIA_SIZE_MISMATCH')

    def test_same_size_corruption_is_rejected(self):
        self.file.write_bytes(b'X'+self.data[1:])
        with self.assertRaises(v.MediaError) as e:v.checked_bytes(self.directory,self.spec)
        self.assertEqual(e.exception.code,'MEDIA_HASH_MISMATCH')

    def test_appended_data_is_rejected(self):
        self.file.write_bytes(self.data+b'X')
        with self.assertRaises(v.MediaError):v.checked_bytes(self.directory,self.spec)

    def test_path_escape_is_rejected(self):
        for name in ('../latest-demo.mp4','/tmp/latest-demo.mp4','other.mp4'):
            with self.subTest(name=name),self.assertRaises(v.MediaError):
                v.checked_bytes(self.directory,dict(self.spec,filename=name))

    def test_invalid_manifest_identity_is_rejected(self):
        for changes in ({'sha256':'not a hash'},{'bytes':True},{'bytes':0},{'bytes':v.MAX_BYTES+1}):
            with self.subTest(changes=changes),self.assertRaises(v.MediaError):
                v.checked_bytes(self.directory,dict(self.spec,**changes))

    def test_link_refused_without_requiring_windows_symlink_privileges(self):
        with patch.object(Path,'is_symlink',return_value=True),self.assertRaises(v.MediaError):
            v.checked_bytes(self.directory,self.spec)

    def test_probe_valid(self):
        v.check_probe(self.probe,self.video,True)

    def test_wrong_or_missing_frame_count(self):
        for value in ('119','0',None,'N/A'):
            probe=copy.deepcopy(self.probe);probe['streams'][0]['nb_read_frames']=value
            with self.subTest(value=value),self.assertRaises(v.MediaError):
                v.check_probe(probe,self.video,True)

    def test_wrong_codec_dimensions_pixel_format(self):
        for key,value in [('codec_name','vp9'),('width',480),('height',720),('pix_fmt','yuv444p')]:
            probe=copy.deepcopy(self.probe);probe['streams'][0][key]=value
            with self.subTest(key=key),self.assertRaises(v.MediaError):v.check_probe(probe,self.video,True)

    def test_bad_duration_and_fps(self):
        for value in ('3.9','NaN','Infinity','invalid'):
            probe=copy.deepcopy(self.probe);probe['format']['duration']=value
            with self.subTest(value=value),self.assertRaises(v.MediaError):v.check_probe(probe,self.video,True)
        for value in ('25/1','0/0','invalid'):
            probe=copy.deepcopy(self.probe);probe['streams'][0]['avg_frame_rate']=value
            with self.subTest(value=value),self.assertRaises(v.MediaError):v.check_probe(probe,self.video,True)

    def test_extra_audio_or_missing_stream(self):
        for streams in ([],self.probe['streams']+[{'codec_type':'audio'}]):
            with self.assertRaises(v.MediaError):v.check_probe({'streams':streams},self.video,True)

    def test_no_decoder_or_network_before_both_identities_pass(self):
        with patch.object(v.subprocess,'run') as run,self.assertRaises(v.MediaError):
            v.verify(self.directory,self.manifest)
        run.assert_not_called()

    def test_unknown_approval_schema(self):
        with self.assertRaises(v.MediaError):v.verify(self.directory,dict(self.manifest,schema=2))

    def test_repository_pin_is_original_not_broken_web_derivative(self):
        self.assertEqual(self.video['sha256'],'6c8f43ed25b712f36dadfd0c2ccb0c2fc8a494c53b60d1baead56b7c64268fe7')
        self.assertEqual((self.video['bytes'],self.video['frames']),(1701127,120))


if __name__=='__main__':unittest.main()
