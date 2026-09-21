"""CI-only portable FFmpeg 8.0.1; checksum pinned to the Microsoft WinGet manifest.

Source: microsoft/winget-pkgs, manifests/g/Gyan/FFmpeg/8.0.1/Gyan.FFmpeg.installer.yaml
Vendor release: github.com/GyanD/codexffmpeg/releases/tag/8.0.1
This never installs or changes a user's studio. Only a fresh runner directory.
"""
from pathlib import Path
import hashlib
import shutil
import sys
import urllib.request
import zipfile

URL = 'https://github.com/GyanD/codexffmpeg/releases/download/8.0.1/ffmpeg-8.0.1-full_build.zip'
SHA256 = '467cde100a47ed4b03a897988aeb4a296890c1e2b2d2864204657d002bc5fb90'
PREFIX = 'ffmpeg-8.0.1-full_build/bin/'
MAX_BYTES = 400 * 1024 * 1024
# Static full-build executables together exceed the compressed ZIP size. This
# separate bound applies only after the fixed vendor SHA256 is verified.
MAX_EXTRACTED_BYTES = 1024 * 1024 * 1024


def extract(archive, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Encoder destination must be new')
    if Path(archive).stat().st_size > MAX_BYTES:
        raise ValueError('Encoder archive exceeds download bound')
    if hashlib.sha256(Path(archive).read_bytes()).hexdigest() != SHA256:
        raise ValueError('FFmpeg archive checksum mismatch')
    with zipfile.ZipFile(archive) as z:
        names = [PREFIX + name for name in ('ffmpeg.exe', 'ffprobe.exe')]
        if any(z.namelist().count(name) != 1 for name in names):
            raise ValueError('Missing or ambiguous encoder executable')
        if any(z.getinfo(name).is_dir() or z.getinfo(name).file_size <= 0 for name in names):
            raise ValueError('Empty or non-file encoder entry')
        expanded = sum(z.getinfo(name).file_size for name in names)
        if expanded > MAX_EXTRACTED_BYTES:
            raise ValueError('Encoder payload exceeds extraction bound: ' + str(expanded))
        destination.mkdir(parents=True)
        for name in names:
            with z.open(name) as source, (destination / Path(name).name).open('xb') as out:
                shutil.copyfileobj(source, out, 1024 * 1024)
    return destination


def main(destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Encoder destination must be new')
    archive = destination.with_suffix('.zip')
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        raise ValueError('Encoder archive destination already exists')
    created = False
    try:
        with archive.open('xb') as out, urllib.request.urlopen(URL, timeout=120) as response:
            created = True
            if not response.url.startswith('https://'):
                raise ValueError('Insecure encoder redirect')
            count = 0
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > MAX_BYTES:
                    raise ValueError('Encoder download exceeds bound')
                out.write(block)
        print(extract(archive, destination))
    finally:
        if created:
            archive.unlink(missing_ok=True)


if __name__ == '__main__':
    main(sys.argv[1])
