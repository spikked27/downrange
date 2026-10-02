"""Real HTTP + browser regression, isolated synthetic data; no real push or feeds."""
from __future__ import annotations
import json, os, secrets, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.store import Store
from app.geometry import illustrative_track
from playwright.sync_api import sync_playwright


def main():
    output=Path(os.environ.get('BROWSER_ARTIFACTS',str(ROOT/'browser-artifacts')))
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='downrange-browser-') as directory:
        password=secrets.token_urlsafe(24)
        with socket.socket() as port_socket:
            port_socket.bind(('127.0.0.1',0));port=port_socket.getsockname()[1]
        origin=f'http://127.0.0.1:{port}'
        env={**os.environ,'DATA_DIR':directory,'ADMIN_PASSWORD':password,'PUBLIC_URL':'',
             'DEMO_MODE':'true','WORKER_ENABLED':'false','SOURCES_ENABLED':'false',
             'REGISTRATION_CODE':'','LL2_API_KEY':'','FLIGHTCLUB_API_KEY':''}
        server=subprocess.Popen([sys.executable,'-m','uvicorn','app.server:app','--host','127.0.0.1',
                                 '--port',str(port),'--no-access-log'],cwd=ROOT,env=env,
                                stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            for _ in range(80):
                try:
                    with urlopen(origin+'/healthz',timeout=1) as response:
                        if response.status==200:break
                except Exception:time.sleep(.1)
            else:raise RuntimeError('Test server failed to start: '+server.stderr.read(4000).decode())
            memory_client=None
            if os.environ.get('BROWSER_IN_MEMORY')=='true':
                # No socket navigation in restricted authoring environments.
                # Serve a synthetic HTTPS origin entirely from FastAPI's ASGI test client.
                from fastapi.testclient import TestClient
                from app.main import create_app
                from app.config import Settings
                origin='https://downrange.test'
                memory_client=TestClient(create_app(Settings(data_dir=Path(directory),admin_password=password,
                    worker_enabled=False,sources_enabled=False,demo_mode=True)),base_url=origin)
                print('IN-MEMORY browser transport: not an HTTP/TLS deployment test.')
            store=Store(Path(directory)/'downrange.sqlite3')
            launch=next(l for l in store.launches(hydrate=False) if l['id']=='demo-0')
            launch['name']='DEMO · Night ascent time-axis test'
            launch['net']=(datetime.now(timezone.utc).replace(hour=3,minute=54,second=0,microsecond=0)+timedelta(days=1)).isoformat()
            track=illustrative_track(launch,45,'SYNTHETIC UI regression only — not a real mission')
            # Deliberate interval gap exercises a cutoff/restart in the UI.
            for p in track['points']:
                if p['t_s']==240:p['powered']=p['plume']=False
            store.execute('UPDATE launches SET data=? WHERE id=?',(json.dumps(launch),launch['id']))
            store.execute('UPDATE tracks SET data=? WHERE launch_id=?',(json.dumps(track),launch['id']))
            with sync_playwright() as pw:
                binary=os.environ.get('CHROMIUM_EXECUTABLE')
                options={'headless':True,'args':['--no-sandbox']}
                if binary:options['executable_path']=binary
                browser=pw.chromium.launch(**options)
                for label,width,height in [('desktop',1440,1100),('mobile',390,844)]:
                    context=browser.new_context(viewport={'width':width,'height':height},
                        device_scale_factor=1 if label=='desktop' else 2,is_mobile=label=='mobile',
                        has_touch=label=='mobile',service_workers='block')
                    # The browser must never send fixture information to external websites.
                    def handle(route):
                        if not route.request.url.startswith(origin+'/'):
                            route.abort();return
                        if memory_client is None:
                            route.continue_();return
                        from urllib.parse import urlsplit
                        url=urlsplit(route.request.url)
                        response=memory_client.request(route.request.method,url.path+('?' + url.query if url.query else ''),
                            content=route.request.post_data_buffer,headers=route.request.headers)
                        headers={k:v for k,v in response.headers.items() if k.lower() not in {'content-length','content-encoding','transfer-encoding'}}
                        route.fulfill(status=response.status_code,headers=headers,body=response.content)
                    context.route('**/*',handle)
                    if memory_client is not None:memory_client.cookies.clear()
                    page=context.new_page();page.set_default_timeout(12000);errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    if memory_client is None:
                        page.goto(origin,wait_until='networkidle')
                    else:
                        # Pure component harness: about:blank, local markup/scripts,
                        # and an in-memory ASGI mock. No browser navigation/network.
                        import re,base64
                        def call_api(_source,path,options):
                            response=memory_client.request(options.get('method','GET'),path,
                                content=options.get('body'),headers=options.get('headers',{}))
                            return {'status':response.status_code,'data':response.json()}
                        page.expose_binding('__testApi',call_api)
                        html=(ROOT/'app/static/index.html').read_text()
                        html=re.sub(r'<script[^>]*>.*?</script>','',html,flags=re.S)
                        html=re.sub(r'<link[^>]*>','',html)
                        icon=base64.b64encode((ROOT/'app/static/icon.svg').read_bytes()).decode()
                        html=html.replace('/static/icon.svg','data:image/svg+xml;base64,'+icon)
                        page.set_content(html)
                        page.add_style_tag(content=(ROOT/'app/static/styles.css').read_text())
                        page.add_style_tag(content=(ROOT/'app/static/viewing.css').read_text())
                        page.add_script_tag(content="window.fetch=async(path,options={})=>{const r=await window.__testApi(path,options);return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>r.data};};")
                        # about:blank disallows sessionStorage; replace only storage
                        # access in this component harness, not application code.
                        page.add_script_tag(content="window.testSessionStorage={getItem:()=>null,setItem:()=>{}};")
                        for filename in ('timeline.js','app.js','sources-ui.js'):
                            source=(ROOT/'app/static'/filename).read_text().replace('sessionStorage.','testSessionStorage.')
                            page.add_script_tag(content=source)
                    print('UI ready',label,flush=True)
                    page.locator('#password').fill(password);page.locator('#authSubmit').click()
                    page.locator('[data-launch="demo-0"]').wait_for()
                    print('Feed ready',label,flush=True)
                    assert page.locator('#sourcePanel').is_visible()
                    assert 'START LOOKING' in page.locator('[data-launch="demo-0"]').locator('xpath=ancestor::article').inner_text()
                    page.locator('[data-launch="demo-0"]').click()
                    page.locator('#timePlot').wait_for(state='visible')
                    page.locator('#timeSlider').evaluate('(e)=>{e.value=240;e.dispatchEvent(new Event("input",{bubbles:true}));}')
                    assert 'T+04:00' in page.locator('#timeReadout').inner_text()
                    assert 'no modeled luminous segment' in page.locator('#timeReadout').inner_text()
                    page.locator('#focusTimeline').click()
                    assert page.locator('#focusTimeline').get_attribute('aria-pressed')=='true'
                    page.locator('#fullTimeline').click()
                    events=page.locator('.viewing-event');assert events.count()==3
                    events.nth(1).click()
                    assert page.locator('#timeSlider').input_value()==events.nth(1).get_attribute('data-seek')
                    # Keyboard access and dynamic cursor feedback, not just a painted image.
                    slider=page.locator('#timeSlider');slider.focus();before=float(slider.input_value());slider.press('ArrowLeft')
                    assert float(slider.input_value())==before-1
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Horizontal page overflow'
                    assert page.locator('#detailDialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth'), 'Horizontal dialog overflow'
                    page.locator('.model-limits summary').click()
                    page.locator('.model-limits summary').click()
                    if label=='desktop':
                        page.locator('#detailDialog').evaluate('(e)=>e.scrollTop=0')
                    else:
                        page.locator('#timePlot').scroll_into_view_if_needed()
                    page.screenshot(path=str(output/f'timeline-{label}.png'))
                    page.locator('#closeDetail').click()
                    page.locator('[data-launch="demo-0"]').click()
                    page.locator('#timePlot').wait_for()
                    assert page.locator('#viewingTimeline').count()==1
                    assert not errors, errors
                    print(f'PASS {label}: login, cards, time plot, cutoff gap, first/peak/last, zoom, keyboard slider, reopen; no JS errors or horizontal overflow.')
                    context.close()
                browser.close()
        finally:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
    print('Browser smoke complete. Synthetic fixtures only; no live sighting or phone-push validation.')


if __name__=='__main__':main()
