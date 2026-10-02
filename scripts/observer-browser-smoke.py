"""Real HTTP observer-view integration, synthetic launch data, no external services."""
import json,os,secrets,socket,subprocess,sys,tempfile,time
from pathlib import Path
from datetime import datetime,timezone,timedelta
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.store import Store
from app.geometry import illustrative_track
from playwright.sync_api import sync_playwright


def main():
    output=ROOT/'browser-artifacts';output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='downrange-perspective-') as directory:
        password=secrets.token_urlsafe(24)
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        origin=f'http://127.0.0.1:{port}'
        env={**os.environ,'DATA_DIR':directory,'ADMIN_PASSWORD':password,'PUBLIC_URL':'',
             'DEMO_MODE':'true','WORKER_ENABLED':'false','SOURCES_ENABLED':'false',
             'REGISTRATION_CODE':'','LL2_API_KEY':'','FLIGHTCLUB_API_KEY':''}
        log=open(Path(directory)/'server.log','w+')
        process=subprocess.Popen([sys.executable,'-m','uvicorn','app.server:app','--host','127.0.0.1',
                                  '--port',str(port),'--no-access-log'],cwd=ROOT,env=env,stdout=log,stderr=log)
        try:
            for _ in range(80):
                try:
                    with urlopen(origin+'/healthz',timeout=1) as r:
                        if r.status==200:break
                except Exception:time.sleep(.1)
            else:raise RuntimeError('Test server did not start')
            store=Store(Path(directory)/'downrange.sqlite3')
            launch=next(l for l in store.launches(hydrate=False) if l['id']=='demo-0')
            launch['name']='DEMO · Observer-view regression'
            launch['net']=(datetime.now(timezone.utc).replace(hour=3,minute=54,second=0,microsecond=0)+timedelta(days=1)).isoformat()
            track=illustrative_track(launch,45,'SYNTHETIC observer-view regression only, not an upcoming real flight')
            for p in track['points']:
                if p['t_s']==240:p['powered']=p['plume']=False
            store.execute('UPDATE launches SET data=? WHERE id=?',(json.dumps(launch),launch['id']))
            store.execute('UPDATE tracks SET data=? WHERE launch_id=?',(json.dumps(track),launch['id']))
            with sync_playwright() as pw:
                options={'headless':True,'args':['--no-sandbox']}
                if os.environ.get('CHROMIUM_EXECUTABLE'):options['executable_path']=os.environ['CHROMIUM_EXECUTABLE']
                browser=pw.chromium.launch(**options)
                for label,width,height in [('desktop',1440,1100),('mobile',390,844)]:
                    context=browser.new_context(viewport={'width':width,'height':height},is_mobile=label=='mobile',
                                               has_touch=label=='mobile',service_workers='block')
                    external=[]
                    def route_request(route):
                        if route.request.url.startswith(origin+'/'):route.continue_()
                        else:external.append(route.request.url);route.abort()
                    context.route('**/*',route_request)
                    page=context.new_page();page.set_default_timeout(15000);errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(origin,wait_until='networkidle')
                    page.locator('#password').fill(password);page.locator('#authSubmit').click()
                    page.locator('[data-launch="demo-0"]').click()
                    sky=page.locator('#observerCanvas');sky.wait_for(state='visible')
                    assert page.locator('#observerView').count()==1
                    page.locator('#timeSlider').evaluate('(e)=>{e.value=0;e.dispatchEvent(new Event("input",{bubbles:true}));}')
                    page.wait_for_function('document.querySelector("#observerCanvas").dataset.marker==="hidden-below-horizon"')
                    assert page.locator('#observerTime').input_value()=='0'
                    page.locator('#observerTime').evaluate('(e)=>{e.value=240;e.dispatchEvent(new Event("input",{bubbles:true}));}')
                    assert page.locator('#timeSlider').input_value()=='240'
                    page.wait_for_function('document.querySelector("#observerCanvas").dataset.time==="240"')
                    assert 'T+04:00' in page.locator('#timeReadout').inner_text()
                    assert 'no modeled luminous segment' in page.locator('#observerStatus').inner_text()
                    page.locator('.viewing-event').nth(1).click()
                    peak=page.locator('.viewing-event').nth(1).get_attribute('data-seek')
                    page.wait_for_function('(t)=>Number(document.querySelector("#observerTime").value)===Math.round(Number(t))',arg=peak)
                    page.locator('#observerFollow').check()
                    page.wait_for_function('document.querySelector("#observerCanvas").dataset.marker==="in-view"')
                    before=page.locator('#observerOrientation').inner_text();sky.focus();sky.press('ArrowRight')
                    page.wait_for_function('(s)=>document.querySelector("#observerOrientation").textContent!==s',arg=before)
                    assert not page.locator('#observerFollow').is_checked()
                    fov=page.locator('#observerFov').inner_text();page.locator('#observerZoomIn').click()
                    page.wait_for_function('(s)=>document.querySelector("#observerFov").textContent!==s',arg=fov)
                    page.locator('#observerGuide').uncheck();assert not page.locator('#observerGuide').is_checked()
                    page.locator('#observerGuide').check();page.locator('#observerFit').click()
                    page.locator('#observerStart').click();first=float(page.locator('#observerTime').input_value())
                    page.locator('#observerPlay').click()
                    page.wait_for_function('(t)=>Number(document.querySelector("#observerTime").value)>t',arg=first)
                    page.locator('#observerPlay').click();assert page.locator('#observerPlay').get_attribute('aria-pressed')=='false'
                    page.locator('#observerTime').evaluate('(e)=>{e.value=300;e.dispatchEvent(new Event("input",{bubbles:true}));}')
                    page.locator('#observerFit').click();page.wait_for_timeout(100)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    assert page.locator('#detailDialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth')
                    if label=='desktop':page.locator('#detailDialog').evaluate('(e)=>e.scrollTop=0')
                    else:page.locator('#observerView').scroll_into_view_if_needed()
                    page.screenshot(path=str(output/f'observer-{label}.png'))
                    page.locator('#observerPlay').click();page.locator('#closeDetail').click()
                    page.locator('[data-launch="demo-0"]').click();sky.wait_for(state='visible')
                    assert page.locator('#observerView').count()==1
                    assert page.locator('#observerPlay').get_attribute('aria-pressed')=='false'
                    assert not errors,errors
                    assert not external,external
                    print('PASS',label,'actual HTTP perspective: both-way time sync, horizon hide, event button, follow/pan, zoom, guide, replay and cleanup; no page errors or horizontal overflow.')
                    context.close()
                browser.close()
        finally:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            log.seek(0)
            print(log.read()[-2000:])
            log.close()
    print('Observer browser test uses synthetic data. No forecast-accuracy or real push claim.')

if __name__=='__main__':main()
