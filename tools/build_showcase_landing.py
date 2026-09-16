"""Add only verified, approved native media to the completed synthetic site."""
from pathlib import Path
import argparse
import json
import os

from verify_showcase_media import MANIFEST, ROOT, MediaError, checked_bytes, verify

TECHNICAL_FILES = frozenset({'.nojekyll', 'index.html', 'app.js', 'style.css',
                             'metrics.json', 'media/comparison.mp4', 'media/poster.jpg'})


def build(root, media_dir):
    root = Path(root)
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    # Verify before moving anything, even when called without the CI preflight.
    verify(media_dir, manifest)
    media = {kind: checked_bytes(media_dir, manifest[kind]) for kind in ('video', 'poster')}
    template = (ROOT / 'showcase/latest/index.html').read_text(encoding='utf-8')
    entries = list(root.rglob('*'))
    if any(p.is_symlink() for p in entries):
        raise MediaError('UNSAFE_SITE', 'Synthetic site contains a symlink')
    files = {p.relative_to(root).as_posix() for p in entries if p.is_file()}
    if files != TECHNICAL_FILES:
        raise MediaError('UNEXPECTED_SITE', 'Synthetic site differs from the exact publication allowlist')
    technical = root / 'technical-validation'
    technical.mkdir()
    for path in list(root.iterdir()):
        if path != technical:
            path.rename(technical / path.name)
    (root / 'media').mkdir()
    for kind, data in media.items():
        (root / 'media' / manifest[kind]['filename']).write_bytes(data)
    (root / 'index.html').write_text(template, encoding='utf-8')
    (root / '.nojekyll').write_text('', encoding='utf-8')
    manifest['site_commit'] = os.environ.get('GITHUB_SHA', 'LOCAL')
    manifest['site_run'] = os.environ.get('GITHUB_RUN_ID', 'LOCAL')
    (root / 'showcase.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    expected = {'technical-validation/' + name for name in TECHNICAL_FILES}
    expected.update({'.nojekyll', 'index.html', 'showcase.json',
                     'media/latest-demo.mp4', 'media/latest-demo-poster.jpg'})
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != expected:
        raise MediaError('UNEXPECTED_SITE', 'Final site differs from the publication allowlist')
    print(json.dumps({'status': 'PASS', 'published_files': sorted(actual),
                      'video_sha256': manifest['video']['sha256']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site_root', type=Path)
    parser.add_argument('--media-dir', type=Path, default=ROOT / 'showcase/media')
    args = parser.parse_args()
    build(args.site_root, args.media_dir)
