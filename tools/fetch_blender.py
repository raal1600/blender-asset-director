"""CI-only official Blender download, verified against its release checksum list."""
from pathlib import Path
import hashlib
import re
import shutil
import sys
import tarfile
import urllib.request

version=sys.argv[1];require=re.fullmatch(r'\d+\.\d+\.\d+',version)
if not require:raise SystemExit('Invalid fixed version')
base='https://download.blender.org/release/Blender'+'.'.join(version.split('.')[:2])+'/'
filename=f'blender-{version}-linux-x64.tar.xz';dest=Path(sys.argv[2]).resolve();dest.mkdir(parents=True,exist_ok=True)
manifest=urllib.request.urlopen(base+f'blender-{version}.sha256',timeout=60).read().decode()
lines=[line for line in manifest.splitlines() if line.split()[-1].lstrip('*')==filename]
if len(lines)!=1:raise SystemExit('Official checksum entry missing or ambiguous')
expected=lines[0].split()[0];archive=dest/filename
with urllib.request.urlopen(base+filename,timeout=120) as response,archive.open('wb') as out:shutil.copyfileobj(response,out,1024*1024)
with archive.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
if actual!=expected:raise SystemExit('Official Blender checksum mismatch')
with tarfile.open(archive) as tar:tar.extractall(dest,filter='data')
archive.unlink()
print(dest/f'blender-{version}-linux-x64'/'blender')
