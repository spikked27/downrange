"""Actual localhost service-worker install and offline-shell test, synthetic data.

No real credentials, provider data, device push, camera or GPS are used.
"""
from pathlib import Path
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

def main():
    with tempfile.TemporaryDirectory(prefix='downrange-pwa-') as directory:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        origin=f'http://127.0.0.1:{port}'
        env={**os.environ,'DATA_DIR':directory,'ADMIN_PASSWORD':secrets.token_urlsafe(24),
             'PUBLIC_URL':'','DEMO_MODE':'true','WORKER_ENABLED':'false','SOURCES_ENABLED':'false',
             'REGISTRATION_CODE':'','LL2_API_KEY':'','FLIGHTCLUB_API_KEY':''}
        with tempfile.TemporaryFile() as logs:
            server=subprocess.Popen([sys.executable,'-m','uvicorn','app.server:app','--host','127.0.0.1',
                                      '--port',str(port),'--no-access-log'],cwd=ROOT,env=env,stdout=logs,stderr=logs)
            try:
                for _ in range(100):
                    try:
                        with urlopen(origin+'/healthz',timeout=1) as response:
                            if response.status==200:break
                    except Exception:time.sleep(.1)
                else:raise RuntimeError('PWA fixture server did not start')
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
                    context=browser.new_context(service_workers='allow')
                    page=context.new_page();page.set_default_timeout(15000)
                    page.goto(origin,wait_until='networkidle')
                    page.locator('#password').fill(env['ADMIN_PASSWORD'])
                    page.locator('#authSubmit').click()
                    page.locator('[data-launch="demo-0"]').wait_for()
                    page.wait_for_function('Boolean(navigator.serviceWorker.controller)')
                    version=page.evaluate("api('/config').then(c=>c.version)")
                    keys=page.evaluate("async()=>{const c=await caches.open('downrange-shell-'+"+repr(version)+");return (await c.keys()).map(r=>new URL(r.url).pathname)}")
                    assert '/static/v1-ui.js' in keys and '/static/observer.js' in keys
                    assert not any(k.startswith('/api/') for k in keys), 'Private API data must not be cached'
                    awaitable=page.evaluate("async()=>{const r=await navigator.serviceWorker.getRegistration();return r.active.scriptURL;}")
                    assert awaitable.endswith('/sw.js')
                    context.set_offline(True)
                    page.goto(origin+'/?launch=synthetic-fixture',wait_until='load')
                    page.locator('#authSubmit').wait_for()
                    assert page.locator('h2').first.inner_text()=='Welcome to Downrange'
                    assert page.evaluate('typeof DownrangeTimeline')=='object'
                    assert page.evaluate('typeof DownrangeV1')=='object'
                    assert page.evaluate("fetch('/api/me').then(()=>false).catch(()=>true)"), 'Offline API data was substituted'
                    context.set_offline(False)
                    page.reload(wait_until='networkidle')
                    page.locator('[data-launch="demo-0"]').wait_for()
                    assert page.locator('#nextOpportunity').is_visible()
                    print('PASS: real service-worker install, versioned shell/observer cache, private API exclusion, query-string offline shell, and online session recovery.')
                    context.close();browser.close()
            finally:
                server.terminate()
                try:server.wait(timeout=10)
                except subprocess.TimeoutExpired:server.kill();server.wait()
                if server.returncode not in (0,-15):
                    logs.seek(0);print(logs.read(5000).decode(errors='replace'))
    print('PWA test used localhost Chromium. It does not verify production TLS, cross-version worker migration or real phone push.')

if __name__=='__main__':main()
