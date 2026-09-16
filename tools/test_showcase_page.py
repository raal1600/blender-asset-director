"""Test the real landing-page recording in the same branded Chrome CI installs."""
from pathlib import Path
import hashlib
import json
import os
import sys
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main(url, output):
    out = Path(output); out.mkdir(parents=True, exist_ok=True)
    approved = json.loads((ROOT / 'showcase/approved-media.json').read_text(encoding='utf-8'))
    report = {'status': 'FAIL', 'commit': os.environ.get('GITHUB_SHA', 'LOCAL'),
              'run_id': os.environ.get('GITHUB_RUN_ID', 'LOCAL'), 'checks': [],
              'artistic_acceptance': 'NOT_ESTABLISHED'}
    # Persist a failure receipt even if Chrome cannot launch.
    (out/'browser-report.json').write_text(json.dumps(dict(report, phase='BROWSER_START'),indent=2)+'\n',encoding='utf-8')
    errors = []; http_errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        report['browser'] = browser.version
        page = browser.new_page(viewport={'width':1365, 'height':1000})
        page.on('pageerror', lambda e: errors.append(str(e)[:1000]))
        page.on('response', lambda r: http_errors.append(r.status) if r.status >= 400 else None)
        try:
            response = page.goto(url, wait_until='networkidle', timeout=60000)
            assert response.status == 200
            assert page.locator('video').count() == 1
            assert page.locator('a[href="technical-validation/"]').count() == 1
            for kind in ('video', 'poster'):
                path = 'media/' + approved[kind]['filename']
                response = page.request.get(url.rstrip('/') + '/' + path)
                assert response.status == 200, (kind, response.status)
                data = response.body()
                assert len(data) == approved[kind]['bytes'], kind
                assert hashlib.sha256(data).hexdigest() == approved[kind]['sha256'], kind
            report['checks'].append('served video and poster match exact approved hashes')
            for name, width, height in [('desktop',1365,1000),('mobile',390,844)]:
                page.set_viewport_size({'width':width,'height':height})
                page.locator('#speed').select_option('1')
                page.locator('#restart-demo').click()
                page.wait_for_function('''() => {
                    const v=document.querySelector('video');
                    if(v.error)throw new Error(v.error.message);
                    return !v.paused && v.readyState>=2 && v.currentTime>0.15;
                }''', timeout=20000)
                state = page.locator('video').evaluate('''v => ({
                    width:v.videoWidth,height:v.videoHeight,duration:v.duration,
                    time:v.currentTime,src:v.currentSrc,
                    decoded:v.getVideoPlaybackQuality().totalVideoFrames
                })''')
                assert state['width'] == approved['video']['width'], state
                assert state['height'] == approved['video']['height'], state
                assert abs(state['duration']-approved['video']['seconds']) < .001, state
                assert state['decoded'] > 0, state
                assert state['src'].endswith('/media/latest-demo.mp4'), state
                page.locator('video').evaluate('(v)=>v.pause()')
                page.locator('#speed').select_option('0.25')
                assert page.locator('video').evaluate('(v)=>v.playbackRate') == .25
                assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
                assert not page.locator('#play-status').inner_text()
                page.screenshot(path=str(out/(name+'.png')), full_page=True)
                report[name] = state
                report['checks'].append(name+': decoded playback after user gesture, speed and layout')
            assert not errors, errors
            assert not http_errors, http_errors
            report['checks'].append('no JavaScript or HTTP errors')
            report['status'] = 'PASS'
        except Exception as exc:
            report['failure'] = str(exc)[-2000:]
            try: page.screenshot(path=str(out/'failure.png'), full_page=True)
            except Exception: pass
            raise
        finally:
            report['javascript_errors'] = errors
            report['http_errors'] = http_errors
            (out/'browser-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(report),flush=True)
            browser.close()


if __name__ == '__main__':
    main(*sys.argv[1:])
