"""Pinned Mesa LLVMpipe ONLY for a disposable hosted Windows desktop test.

Per-application deployment in RUNNER_TEMP, never system32 or a user's Blender.
25.3.3 MSVC asset digest: pal1000/mesa-dist-win release asset 336461281.
No rendering/compatibility claim is made until the actual Blender GUI is tested.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

URL = 'https://github.com/pal1000/mesa-dist-win/releases/download/25.3.3/mesa3d-25.3.3-release-msvc.7z'
SHA256 = '66b79057ba273c08daa03551a231995d48b8623bb1efa9f3a7c3e09792d8f1ba'
MAX_BYTES = 80 * 1024 * 1024
FILES = ('opengl32.dll', 'libgallium_wgl.dll')


def validate_destination(blender, runner):
    executable = Path(blender).resolve()
    trusted = (Path(runner).resolve() / 'verified-blender')
    if not executable.is_file() or not executable.is_relative_to(trusted):
        raise ValueError('Mesa is restricted to this runner\'s disposable verified Blender')
    if any((executable.parent / n).exists() for n in FILES):
        raise ValueError('Refusing to overwrite an existing OpenGL driver')
    return executable.parent


def install(blender):
    if sys.platform != 'win32' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('CI-only graphics setup; not a production installer')
    runner = Path(os.environ['RUNNER_TEMP']).resolve()
    destination = validate_destination(blender, runner)
    sevenzip = shutil.which('7z') or r'C:\Program Files\7-Zip\7z.exe'
    work = Path(tempfile.mkdtemp(prefix='verified-mesa-', dir=runner))
    archive = work / 'mesa.7z'
    with urllib.request.urlopen(URL, timeout=120) as response, archive.open('xb') as out:
        if not response.url.startswith('https://'):
            raise ValueError('Insecure graphics package redirect')
        count = 0
        while block := response.read(1024 * 1024):
            count += len(block)
            if count > MAX_BYTES:
                raise ValueError('Graphics package exceeds download bound')
            out.write(block)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError('Graphics package checksum mismatch')
    # Only fixed members of the hash-pinned archive. No vendor install script runs.
    subprocess.run([sevenzip, 'e', '-y', '-o' + str(work), str(archive),
                    *('x64/' + n for n in FILES)], check=True, timeout=90)
    hashes = {}
    for name in FILES:
        source = work / name
        if not source.is_file() or not 0 < source.stat().st_size <= 512 * 1024 * 1024:
            raise ValueError('Missing or unbounded graphics library: ' + name)
        hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    for name in FILES:
        with (work / name).open('rb') as source, (destination / name).open('xb') as out:
            shutil.copyfileobj(source, out)
    receipt = work / 'graphics.json'
    receipt.write_text(json.dumps(dict(source=URL, archive_sha256=SHA256, driver='llvmpipe',
        scope='CI_ONLY_PER_APPLICATION', files=hashes, production_install=False), indent=2), encoding='utf-8')
    with Path(os.environ['GITHUB_ENV']).open('a', encoding='utf-8') as out:
        out.write('GALLIUM_DRIVER=llvmpipe\nNATIVE_MESA_RECEIPT=' + str(receipt) + '\n')
    print('Verified CI-only Mesa. Actual native acceptance still required.')


if __name__ == '__main__':
    install(sys.argv[1])
