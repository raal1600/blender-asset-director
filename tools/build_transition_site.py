"""Encode the bounded public comparison and copy only allowlisted website files."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
STATIC=('index.html','style.css','app.js')
METHODS=('cut','nla','aligned','director')
TITLES=('01   HARD CUT','02   UNALIGNED NLA','03   ALIGNED NLA','04   DIRECTOR BRIDGE')


def checked_metrics(data):
    if data.get('schema')!='asset-director.transition-showcase/1' or data.get('synthetic') is not True or data.get('private_assets_used') is not False:
        raise ValueError('Only generated public benchmark evidence is allowed')
    if data['fixture_status']!='PASS' or data['original_result_unchanged'] is not True:
        raise ValueError('Do not publish a failed benchmark')
    if data['frames_per_method']!=120 or data['fps']!=30 or data['render']['total_frames']!=480:
        raise ValueError('Unexpected render work budget')
    if set(data['methods'])!=set(METHODS):raise ValueError('All four honest controls are required')
    if any(len(data['methods'][m]['anchor_positions'])!=120 for m in METHODS):raise ValueError('Missing measured timeline')
    if data['source_seconds'][1]<37:raise ValueError('The full-length incoming regression is required')
    if len(data['commit'])!=40 or any(c not in '0123456789abcdef' for c in data['commit']):raise ValueError('Need exact source SHA')
    return data


def build(render,site):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise RuntimeError('Build/render tests belong in Actions')
    render,site=Path(render).resolve(),Path(site).resolve();tmp=Path(os.environ['RUNNER_TEMP']).resolve()
    if not render.is_relative_to(tmp) or not site.is_relative_to(tmp):raise ValueError('Use isolated temporary directories')
    data=checked_metrics(json.loads((render/'metrics.json').read_text()))
    site.mkdir(parents=True,exist_ok=False);media=site/'media';media.mkdir()
    for name in STATIC:shutil.copyfile(ROOT/'showcase'/name,site/name)
    (site/'.nojekyll').write_text('')
    for method in METHODS:
        files=list((render/method).glob('*.png'))
        if len(files)!=120 or not all((render/method/f'{i:04d}.png').is_file() for i in range(120)):
            raise ValueError('Missing frames for '+method)
    cmd=['ffmpeg','-hide_banner','-loglevel','warning','-y']
    for m in METHODS:cmd+=['-framerate','30','-start_number','0','-i',str(render/m/'%04d.png')]
    filters=[]
    for i,title in enumerate(TITLES):
        filters.append(f"[{i}:v]drawbox=x=0:y=0:w=iw:h=33:color=0x10161c@0.94:t=fill,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{title}':fontcolor=white:fontsize=14:x=13:y=9[v{i}]")
    filters.append('[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[out]')
    video=media/'comparison.mp4'
    cmd+=['-filter_complex',';'.join(filters),'-map','[out]','-frames:v','120','-an','-c:v','libx264','-crf','20','-preset','veryfast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(video)]
    subprocess.run(cmd,check=True,timeout=180)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)],timeout=20))
    stream=next(s for s in probe['streams'] if s['codec_type']=='video')
    assert stream['codec_name']=='h264' and stream['width']==960 and stream['height']==720
    assert int(stream['nb_frames'])==120 and stream['r_frame_rate']=='30/1'
    assert abs(float(probe['format']['duration'])-4)<.05 and video.stat().st_size<20*1024**2
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','warning','-y','-ss','1.22','-i',str(video),'-frames:v','1','-q:v','2',str(media/'poster.jpg')],check=True,timeout=30)
    data['media']={'url':'media/comparison.mp4','sha256':hashlib.sha256(video.read_bytes()).hexdigest(),
                   'bytes':video.stat().st_size,'seconds':float(probe['format']['duration']),'width':960,'height':720,'fps':30,'frames':120}
    (site/'metrics.json').write_text(json.dumps(data,indent=2)+'\n')
    permitted={*STATIC,'.nojekyll','metrics.json','media/comparison.mp4','media/poster.jpg'}
    actual={p.relative_to(site).as_posix() for p in site.rglob('*') if p.is_file()}
    assert actual==permitted and not any(p.is_symlink() for p in site.rglob('*'))
    print(json.dumps({'status':'PASS','published_files':sorted(actual),'media':data['media']}))


if __name__=='__main__':build(*sys.argv[1:])
