"""Real H.264 playback and responsive-page checks, in disposable Actions only.

Start playback through a user gesture: preload=metadata does not promise a decoded
frame. Branded Chrome provides the proprietary video codecs under test. Failure
receipts retain media state and screenshots instead of losing the useful evidence.
"""
from pathlib import Path
import json
import os
import sys
from playwright.sync_api import sync_playwright


def media_state(page):
    return page.locator('video').evaluate('''v => ({
        currentSrc:v.currentSrc, readyState:v.readyState, networkState:v.networkState,
        width:v.videoWidth, height:v.videoHeight, duration:v.duration,
        currentTime:v.currentTime, paused:v.paused, ended:v.ended, seeking:v.seeking,
        playbackRate:v.playbackRate, decodedFrames:v.getVideoPlaybackQuality?.().totalVideoFrames,
        mp4Support:v.canPlayType('video/mp4; codecs="avc1.64001f"'),
        error:v.error ? {code:v.error.code,message:v.error.message} : null
    })''')


def main(url,out):
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    report={'status':'FAIL','artistic_acceptance':'NOT_ESTABLISHED','checks':[]}
    errors=[];responses=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome')
        page=browser.new_page(viewport={'width':1365,'height':1000},device_scale_factor=1)
        report['browser']=browser.version
        page.on('pageerror',lambda e:errors.append(str(e)[:1000]))
        page.on('response',lambda r:responses.append({'url':r.url,'status':r.status}) if r.url.endswith(('.mp4','.json')) else None)
        try:
            page.goto(url,wait_until='networkidle',timeout=60000)
            page.wait_for_function("document.querySelector('#gap').textContent !== '—'")
            report['checks'].append('measured metrics loaded at project-relative URL')
            initial=media_state(page);report['initial_media']=initial
            assert initial['mp4Support'] in ('maybe','probably'),initial
            # A deliberate user gesture is required before asking for decoded
            # frames. A metadata-only preload is valid production behaviour.
            page.locator('#restart').click()
            page.wait_for_function("""() => {
                const v=document.querySelector('video');
                if(v.error)throw new Error(v.error.message);
                return v.readyState>=2 && !v.paused && v.currentTime>0.12;
            }""",timeout=20000)
            assert page.locator('video').evaluate('(v)=>v.videoWidth')==960
            assert page.locator('video').evaluate('(v)=>Math.abs(v.duration-4)<0.05')
            report['checks'].append('H.264 decoded and playback time advanced after user gesture')
            page.locator('video').evaluate('(v)=>v.pause()')
            page.locator('[data-rate="0.25"]').click()
            assert page.locator('video').evaluate('(v)=>v.playbackRate')==.25
            assert page.locator('[data-rate="0.25"]').get_attribute('aria-pressed')=='true'
            page.locator('[data-rate="1"]').click()
            page.locator('#join').click()
            page.wait_for_function("!document.querySelector('video').paused && document.querySelector('video').currentTime>0.55")
            report['checks'].append('slow motion and inspect-join controls work')
            page.locator('video').evaluate('(v)=>{v.pause();v.currentTime=1.22;}')
            page.wait_for_function("Math.abs(document.querySelector('video').currentTime-1.22)<.01 && !document.querySelector('video').seeking && document.querySelector('video').readyState>=2")
            page.wait_for_timeout(150)
            assert page.locator('.timeline-row').count()==4
            assert page.locator('.method-cards article').count()==4
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
            page.screenshot(path=str(out/'desktop.png'),full_page=True)
            page.locator('video').screenshot(path=str(out/'video-frame.png'))
            report['checks'].append('four methods, seeked video frame and desktop layout')
            page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(150)
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
            page.screenshot(path=str(out/'mobile.png'),full_page=True)
            report['checks'].append('mobile layout has no horizontal overflow')
            assert not errors,errors
            report['checks'].append('no JavaScript exceptions')
            report.update(status='PASS',video='H.264 960x720, 30fps, 4s; decoded, played and seeked')
        except Exception as exc:
            report['failure']=str(exc)[-3000:]
            try:page.screenshot(path=str(out/'failure.png'),full_page=True)
            except Exception:pass
            raise
        finally:
            try:report['final_media']=media_state(page)
            except Exception:report['final_media']='unavailable'
            report['javascript_errors']=errors
            report['media_responses']=responses[-20:]
            (out/'browser-report.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report),flush=True)
            browser.close()


if __name__=='__main__':main(*sys.argv[1:])
