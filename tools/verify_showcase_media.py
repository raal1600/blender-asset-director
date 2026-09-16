"""Verify approved native showcase files; never repair, transcode or download them.

Checks exact byte counts and SHA256 before ffprobe and a strict full ffmpeg
decode. Tests of this tool are not acceptance of a particular recording.
"""
from pathlib import Path
from fractions import Fraction
import argparse
import hashlib
import json
import math
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'showcase' / 'approved-media.json'
MAX_BYTES = 8 * 1024 * 1024


class MediaError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def checked_bytes(directory, spec):
    """A readable header or approximate size is not proof of a complete file."""
    name = spec.get('filename')
    if name not in ('latest-demo.mp4', 'latest-demo-poster.jpg'):
        raise MediaError('INVALID_MANIFEST', 'Unexpected media filename')
    size = spec.get('bytes')
    if type(size) is not int or not 0 < size <= MAX_BYTES:
        raise MediaError('INVALID_MANIFEST', 'Invalid expected byte count')
    if not re.fullmatch(r'[0-9a-f]{64}', spec.get('sha256', '')):
        raise MediaError('INVALID_MANIFEST', 'Invalid expected SHA256')
    directory = Path(directory)
    path = directory / name
    if directory.is_symlink() or path.is_symlink():
        raise MediaError('UNSAFE_MEDIA', 'Media paths must not be symlinks')
    if not path.is_file():
        raise MediaError('MISSING_APPROVED_MEDIA',
                         f'{name} is missing. Upload the exact approved native file; '
                         'do not change the manifest to accept another recording.')
    with path.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) != size:
        raise MediaError('MEDIA_SIZE_MISMATCH',
                         f'{name}: expected {size} bytes, found {len(data)}')
    if hashlib.sha256(data).hexdigest() != spec['sha256']:
        raise MediaError('MEDIA_HASH_MISMATCH', f'{name}: SHA256 differs from approval')
    return data


def check_probe(probe, spec, is_video):
    streams = probe.get('streams', [])
    if len(streams) != 1 or streams[0].get('codec_type') != 'video':
        raise MediaError('MEDIA_STREAM_MISMATCH', 'Exactly one video/image stream is required')
    stream = streams[0]
    for key in ('codec_name', 'width', 'height'):
        if stream.get(key) != spec[key]:
            raise MediaError('MEDIA_FORMAT_MISMATCH', f'Unexpected {key}')
    if str(stream.get('nb_read_frames')) != str(spec['frames']):
        raise MediaError('MEDIA_FRAME_MISMATCH', 'Decoded frame count differs from approval')
    if is_video:
        if stream.get('pix_fmt') != spec['pix_fmt']:
            raise MediaError('MEDIA_FORMAT_MISMATCH', 'Unexpected pixel format')
        try:
            fps = Fraction(stream['avg_frame_rate'])
            seconds = float(probe['format']['duration'])
        except (KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
            raise MediaError('MEDIA_TIMEBASE_MISMATCH', 'Invalid timebase') from exc
        if (fps != spec['fps'] or not math.isfinite(seconds)
                or abs(seconds - spec['seconds']) > 0.001):
            raise MediaError('MEDIA_TIMEBASE_MISMATCH', 'Duration or FPS differs from approval')


def verify(directory, manifest):
    if manifest.get('schema') != 1:
        raise MediaError('INVALID_MANIFEST', 'Unknown approval schema')
    data = {kind: checked_bytes(directory, manifest[kind]) for kind in ('video', 'poster')}
    result = {}
    for kind in ('video', 'poster'):
        spec = manifest[kind]
        path = Path(directory) / spec['filename']
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-count_frames', '-show_entries',
             'stream=codec_type,codec_name,width,height,pix_fmt,avg_frame_rate,nb_read_frames:format=duration',
             '-of', 'json', str(path)],
            check=True, capture_output=True, text=True, timeout=30)
        if probe.stderr.strip():
            raise MediaError('MEDIA_DECODE_FAILED', f'{kind}: ffprobe reported errors')
        metadata = json.loads(probe.stdout)
        check_probe(metadata, spec, kind == 'video')
        decoded = subprocess.run(
            ['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-err_detect', 'explode',
             '-i', str(path), '-map', '0:v:0', '-f', 'null', '-'],
            check=True, capture_output=True, text=True, timeout=30)
        if decoded.stderr.strip():
            raise MediaError('MEDIA_DECODE_FAILED', f'{kind}: ffmpeg reported errors')
        if checked_bytes(directory, spec) != data[kind]:
            raise MediaError('MEDIA_CHANGED', f'{kind}: changed during verification')
        result[kind] = {'filename': spec['filename'], 'sha256': spec['sha256'],
                        'bytes': len(data[kind]), 'probe': metadata, 'full_decode': 'PASS'}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--media-dir', type=Path, default=ROOT / 'showcase' / 'media')
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--identity-only', action='store_true',
                        help='Fast byte/hash preflight only, not full media acceptance')
    args = parser.parse_args()
    report = {'status': 'FAIL', 'commit': os.environ.get('GITHUB_SHA', 'LOCAL'),
              'run_id': os.environ.get('GITHUB_RUN_ID', 'LOCAL'),
              'artistic_acceptance': 'NOT_ESTABLISHED'}
    try:
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        if args.identity_only:
            if manifest.get('schema') != 1:
                raise MediaError('INVALID_MANIFEST', 'Unknown approval schema')
            for kind in ('video', 'poster'):
                checked_bytes(args.media_dir, manifest[kind])
            report.update(status='IDENTITY_PASS', full_decode='NOT_RUN')
        else:
            report['media'] = verify(args.media_dir, manifest)
            report['status'] = 'PASS'
    except MediaError as exc:
        report.update(code=exc.code, message=str(exc))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        report.update(code=type(exc).__name__, message='Manifest, decoder or file verification failed')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report), flush=True)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as out:
            out.write(f"## Approved showcase media: {report['status']}\n\n")
            out.write(f"Commit: `{report['commit']}`; run: `{report['run_id']}`.\n\n")
            out.write(report.get('message', 'Exact file identity checked; full decode: ' + ('NOT_RUN' if args.identity_only else 'PASS')) + '\n')
    return 0 if report['status'] in ('PASS', 'IDENTITY_PASS') else 1


if __name__ == '__main__':
    raise SystemExit(main())
