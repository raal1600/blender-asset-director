"""Browser checks for the actual encoded video/site, run only in GitHub Actions."""
from pathlib import Path
import json
import os
import sys
from playwright.sync_api import sync_playwright


def main(url,out):
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':1365,'height':1000},device_scale_factor=1)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url,wait_until='networkidle',timeout=60000)
        page.wait_for_function("document.querySelector('#gap').textContent !== '—'")
        page.wait_for_function("document.querySelector('video').readyState >= 2")
        assert page.locator('video').evaluate('(v)=>v.videoWidth')==960
        assert page.locator('video').evaluate('(v)=>Math.abs(v.duration-4)<0.05')
        page.locator('[data-rate="0.25"]').click()
        assert page.locator('video').evaluate('(v)=>v.playbackRate')==.25
        page.locator('[data-rate="1"]').click()
        page.locator('#join').click()
        page.wait_for_timeout(150)
        assert page.locator('video').evaluate('(v)=>!v.paused')
        page.locator('video').evaluate('(v)=>{v.pause();v.currentTime=1.22;}')
        page.wait_for_function("Math.abs(document.querySelector('video').currentTime-1.22)<.01 && !document.querySelector('video').seeking")
        page.screenshot(path=str(out/'desktop.png'),full_page=True)
        assert page.locator('.timeline-row').count()==4
        assert page.locator('.method-cards article').count()==4
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(150)
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        page.screenshot(path=str(out/'mobile.png'),full_page=True)
        assert not errors,errors
        browser.close()
    report={'status':'PASS','video':'H.264 960x720, 30fps, 4s; loaded, seeked, and played',
            'checks':['relative project URL','measured metrics loaded','four comparison methods','slow motion','join playback','desktop layout','mobile overflow','no JavaScript exceptions'],
            'artistic_acceptance':'NOT_ESTABLISHED'}
    (out/'browser-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))


if __name__=='__main__':main(*sys.argv[1:])
