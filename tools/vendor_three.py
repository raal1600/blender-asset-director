"""Explicit developer-only, checksum-pinned vendoring. Never run by the app/installer."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request

VERSION = '0.186.0'
URL = f'https://registry.npmjs.org/three/-/three-{VERSION}.tgz'
INTEGRITY = 'cr/fIM2ddMSVbYVgkfD4jLJv7Fh/8ZTjvo+7gQeSVGUZHxpx9FDwoL5iC7hUz/LiRA8wMbqfnb90xKfm1/HHkQ=='
FILES = ('LICENSE', 'build/three.module.js', 'build/three.core.js',
         'examples/jsm/loaders/GLTFLoader.js', 'examples/jsm/controls/OrbitControls.js',
         'examples/jsm/utils/BufferGeometryUtils.js', 'examples/jsm/utils/SkeletonUtils.js')


def vendor(archive):
    payload = archive.read_bytes()
    if base64.b64encode(hashlib.sha512(payload).digest()).decode() != INTEGRITY:
        raise ValueError('Three.js archive checksum mismatch; nothing extracted')
    destination = Path(__file__).resolve().parents[1] / 'launcher/public/vendor/three'
    destination.mkdir(parents=True, exist_ok=True)
    hashes = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as package:
        for name in FILES:
            entry = package.getmember('package/' + name)
            if not entry.isfile() or entry.size > 5 * 1024**2:
                raise ValueError('Unexpected vendor member')
            original = package.extractfile(entry).read()
            # Local module resolution, without inline import maps or a runtime CDN.
            adapted = original.replace(b"from 'three';", b"from '../../../build/three.module.js';") if name.startswith('examples/') else original
            output = destination / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(adapted)
            hashes[name] = {'upstream_sha256': hashlib.sha256(original).hexdigest(),
                            'sha256': hashlib.sha256(adapted).hexdigest()}
    manifest = {'package': 'three', 'version': VERSION, 'license': 'MIT', 'url': URL,
                'archive_sha512': INTEGRITY, 'archive_sha256': hashlib.sha256(payload).hexdigest(),
                'adaptation': "examples' bare three import resolves to the local build module; no other changes",
                'files': hashes}
    (destination / 'VENDOR.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--download', action='store_true', help='Explicit permission required; archive must not exist')
    args = parser.parse_args()
    if args.download:
        args.archive.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(URL, timeout=30) as response, args.archive.open('xb') as output:
            payload = response.read(8 * 1024**2 + 1)
            if len(payload) > 8 * 1024**2:
                raise ValueError('Vendor archive exceeds download limit')
            output.write(payload)
    vendor(args.archive)
