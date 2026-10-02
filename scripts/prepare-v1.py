"""One-time integration edits, only used on the isolated v1 preparation branch.

Exact-match assertions fail instead of guessing when the base source differs.
The candidate workflow commits the resulting application files only after tests.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
VERSION='1.0.0-alpha.1'

def change(path,old,new):
    file=ROOT/path; text=file.read_text()
    if old not in text:
        if new in text:return
        raise RuntimeError(f'Integration base differs: {path}: {old[:90]!r}')
    if text.count(old)!=1:raise RuntimeError(f'Ambiguous integration anchor: {path}: {old[:90]!r}')
    file.write_text(text.replace(old,new))

if (ROOT/'app/__init__.py').read_text().find(VERSION)>=0:
    print('Integration already committed.');raise SystemExit(0)

# Location profile has eight direction limits, preserving existing stored records.
change('app/models.py','    alerts: bool = True\n','''    alerts: bool = True
    horizon_profile: list[float] = Field(default_factory=list, max_length=8)
    @field_validator("horizon_profile")
    @classmethod
    def horizon_values(cls, v):
        from .horizon import validate_profile
        return validate_profile(v)
''')
for cls in ('Credentials','PasswordChange'):
    change('app/models.py',f'class {cls}(StrictModel):\n',f'class {cls}(StrictModel):\n    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=False)\n')

file=ROOT/'app/store.py';text=file.read_text();a=text.index('    def hydrate(');b=text.index('    def launches(',a)
text=text[:a]+'''    def hydrate(self, launch):
        from .evidence import usable
        result = dict(launch)
        acquired = usable(self.meta('acquired:'+launch['id'], {}), launch)
        if acquired:
            result['acquisition'] = acquired
        return result
'''+text[b:];file.write_text(text)
change('app/geometry.py','from .models import Trajectory','from .models import Trajectory\nfrom .horizon import viewing_limit')
change('app/geometry.py','        above=a["elevation"]>=observer.get("min_elevation_deg",5)','        limit=viewing_limit(observer,a["azimuth"])\n        above=a["elevation"]>=limit')
change('app/geometry.py','"sunlit":sunlit,"above":above,','"sunlit":sunlit,"above":above,"horizon_limit_deg":limit,')

# Never send the historical transfer-orbit model to a station mission by default.
change('app/trajectory_sources.py',"    targets=['Falcon Heavy Demo 1'] if family=='falcon-heavy' else ['DM-1','Orbcomm OG2']",'''    text=' '.join(str(launch.get(k,'')) for k in ('orbit','mission','mission_name')).lower()
    if family=='falcon-heavy': targets=['Falcon Heavy Demo 1']
    elif 'transfer' in text or 'geostationary' in text: targets=['SES-9','Thaicom 8']
    elif 'international space station' in text or 'crew' in text or 'crs' in text: targets=['DM-1','SpaceX CRS-8']
    else: targets=['Orbcomm OG2','DM-1']''')

change('app/main.py','from .geometry import predict, utc, illustrative_track', 'from .geometry import utc, illustrative_track\nfrom .prediction_cache import predict\nfrom .evidence import quality, diagnostic_snapshot')
change('app/main.py','    return cached_prediction(json.dumps(launch,sort_keys=True),json.dumps(loc,sort_keys=True),json.dumps(track,sort_keys=True) if track else "")','    result = cached_prediction(json.dumps(launch,sort_keys=True),json.dumps(loc,sort_keys=True),json.dumps(track,sort_keys=True) if track else "")\n    return {**result, "quality": quality(launch, result, track)}')
change('app/main.py','                await providers.refresh()\n                await asyncio.to_thread(notifier.plan)','                await asyncio.to_thread(notifier.plan)')
change('app/main.py','    source_wakeup = asyncio.Event()', '''    async def feed_loop():
        while True:
            try:
                await providers.refresh()
                store.set_meta("feed_worker_heartbeat", time.time())
            except asyncio.CancelledError: raise
            except Exception as exc: log.error("Schedule worker failed: %s", type(exc).__name__)
            await asyncio.sleep(30)
    source_wakeup = asyncio.Event()''')
change('app/main.py','        task=asyncio.create_task(loop()) if settings.worker_enabled else None','        task=asyncio.create_task(loop()) if settings.worker_enabled else None\n        feed_task=asyncio.create_task(feed_loop()) if settings.worker_enabled else None')
change('app/main.py','        finally:\n            if source_task:', '''        finally:
            if feed_task:
                feed_task.cancel()
                try: await feed_task
                except asyncio.CancelledError: pass
            if source_task:''')
change('app/main.py','    @app.get("/api/admin/status")', '''    @app.get("/api/diagnostics")
    def diagnostics(user=Depends(auth)):
        return diagnostic_snapshot(store, settings, user, __version__)
    @app.get("/api/admin/status")''')
change('app/main.py','        if request.url.path.startswith("/api/"): response.headers["Cache-Control"]="no-store"', '        if request.url.path.startswith("/api/"): response.headers["Cache-Control"]="no-store"\n        elif request.url.path.startswith("/static/"): response.headers["Cache-Control"]="no-cache"')

change('app/notifications.py','from .geometry import utc, predict','from .geometry import utc\nfrom .prediction_cache import predict')
change('app/notifications.py','def eligible(launch,loc,pred,prefs):','def eligible(launch,loc,pred,prefs,now=None):\n    now=time.time() if now is None else now')
change('app/notifications.py','time.time()-launch["feed_seen"]>1800','now-launch["feed_seen"]>1800')
# Only cancelled/expired, unsent events can be rescheduled, never a sent or failed message.
change('app/notifications.py','INSERT OR IGNORE INTO deliveries(key,user_id,subscription_id,launch_id,location_id,net,kind,payload,next_try,expires) VALUES(?,?,?,?,?,?,?,?,?,?)',"INSERT INTO deliveries(key,user_id,subscription_id,launch_id,location_id,net,kind,payload,next_try,expires) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET status='pending',payload=excluded.payload,next_try=excluded.next_try,expires=excluded.expires,error=NULL WHERE deliveries.status IN ('cancelled','expired') AND deliveries.attempts<3")
f=ROOT/'app/notifications.py';s=f.read_text().replace('eligible(launch,loc,pred,prefs)','eligible(launch,loc,pred,prefs,now)');f.write_text(s)
change('app/notifications.py','            try:\n                sender(json.loads(sub["data"])', '''            current = self.store.one("SELECT status FROM deliveries WHERE key=?", (item["key"],))
            if not current or current["status"] != "pending": continue
            try:
                sender(json.loads(sub["data"])''')

# Draw exactly the same azimuth-dependent obstruction limits as the backend.
change('app/static/timeline.js','    p.above=p.elevation>=cutoff;', '''    p.horizon_limit_deg=Number.isFinite(a.horizon_limit_deg)&&Number.isFinite(b.horizon_limit_deg)
      ?a.horizon_limit_deg+f*(b.horizon_limit_deg-a.horizon_limit_deg):cutoff;
    p.above=p.elevation>=p.horizon_limit_deg;''')
change('app/static/timeline.js','    if(!p.above)return `Below your ${cutoff}° viewing limit`;', '    if(!p.above)return `Below your ${Number((p.horizon_limit_deg??cutoff).toFixed(1))}° viewing limit`;')
change('app/static/timeline.js','    const max=Math.max(cutoff,...inView.map(p=>p.elevation),0);','    const max=Math.max(cutoff,...inView.map(p=>p.elevation),...inView.map(p=>p.horizon_limit_deg??cutoff),0);')
change('app/static/timeline.js',"      ctx.strokeStyle='#c7b594';ctx.setLineDash([5,5]);ctx.lineWidth=1.2;ctx.beginPath();ctx.moveTo(L,y(cutoff));ctx.lineTo(width-R,y(cutoff));ctx.stroke();ctx.setLineDash([]);", "      ctx.strokeStyle='#c7b594';ctx.setLineDash([5,5]);ctx.lineWidth=1.2;ctx.beginPath();let previousLimit=null;for(const p of points){if(previousLimit===null||p.t_s-previousLimit>120)ctx.moveTo(x(p.t_s),y(p.horizon_limit_deg??cutoff));else ctx.lineTo(x(p.t_s),y(p.horizon_limit_deg??cutoff));previousLimit=p.t_s;}ctx.stroke();ctx.setLineDash([]);")
f=ROOT/'app/static/timeline.js';s=f.read_text().replace('Dashed: your ${cutoff}° limit','Dashed: your local viewing limit');f.write_text(s)
change('app/static/observer.js',"    if(p.elevation<cutoff)return 'below_limit';", "    if(p.elevation<(p.horizon_limit_deg??cutoff))return 'below_limit';")
change('app/static/observer.js',"      if(cutoff>0){const line=[];for(let a=0;a<=360;a+=1)line.push({azimuth:a,elevation:cutoff});lineFrom(line,'#ccb591',[5,5],1.3);}", "      if(cutoff>0||launch.location.horizon_profile?.length){const line=[];for(let a=0;a<=360;a+=1)line.push({azimuth:a,elevation:root.DownrangeV1.horizonLimit(launch.location.horizon_profile,cutoff,a)});lineFrom(line,'#ccb591',[5,5],1.3);}")
f=ROOT/'app/static/observer.js';s=f.read_text().replace('Dashed amber line: your ${cutoff}° viewing limit.','Dashed amber line: your configured viewing limits, including manually entered obstructions.').replace('No local terrain, trees, star map or camera overlay.','No downloaded terrain, star map or camera overlay.');f.write_text(s)

change('app/static/app.js',"headers:{'X-Downrange':'1'}};", "headers:{'X-Downrange':'1'},cache:'no-store'};")
change('app/static/app.js',"$('#locTz').value=l.timezone;$('#locAlerts').checked=l.alerts;", "$('#locTz').value=l.timezone;$('#locAlerts').checked=l.alerts;window.DownrangeV1?.fillHorizon(l.horizon_profile||[]);")
change('app/static/app.js',"function resetLocationForm(){ $('#locationForm').reset();", "function resetLocationForm(){ $('#locationForm').reset();window.DownrangeV1?.fillHorizon([]);")
change('app/static/app.js',"timezone:$('#locTz').value,alerts:$('#locAlerts').checked", "timezone:$('#locTz').value,alerts:$('#locAlerts').checked,horizon_profile:window.DownrangeV1?.horizon()||[]")
change('app/static/app.js','  list.sort((a,b)=>', "  if(window.DownrangeV1)list=list.filter(l=>DownrangeV1.selected(l,$('#launchSearch')?.value||'', $('#qualityFilter')?.value||'all'));\n  list.sort((a,b)=>")
change('app/static/app.js','    renderCards();renderSourceStatus();','    renderCards();renderSourceStatus();document.dispatchEvent(new Event("downrange:feed"));')
change('app/static/app.js',"state.page==='dashboard'&&!$('#detailDialog').open", "['dashboard','sources'].includes(state.page)&&!$('#detailDialog').open")
change('app/static/sources-ui.js','    Last acquisition: ${esc(fmt(p.source_checked))}', '    Last research attempt: ${esc(fmt(p.source_checked))}')

# Hooks load after app.js; initial async sign-in can complete only after all defer scripts.
change('app/static/index.html','<script src="/static/sources-ui.js" defer></script>', '<script src="/static/v1-ui.js" defer></script><script src="/static/sources-ui.js" defer></script>')
change('app/static/index.html','<link rel="stylesheet" href="/static/viewing.css">','<link rel="stylesheet" href="/static/viewing.css"><link rel="stylesheet" href="/static/v1.css">')

# Test actual edit/save/read/reopen paths in both browser sizes, not just painted screenshots.
change('scripts/browser-smoke.py',"                    assert page.locator('#sourcePanel').is_visible()", '''                    assert page.locator('#sourcePanel').is_visible()
                    page.locator('[data-page="locations"]').first.click()
                    page.locator('[data-edit-location]').first.click()
                    page.locator('#horizonEditor summary').click()
                    page.locator('#horizon-4').fill('25')
                    page.locator('#locationForm button[type="submit"]').click()
                    page.locator('[data-launch="demo-0"]').wait_for()
                    saved = page.evaluate("api('/locations')")
                    assert saved[0]['horizon_profile'][4] == 25
                    page.locator('[data-page="locations"]').first.click()
                    page.locator('[data-edit-location]').first.click()
                    page.locator('#horizon-4').fill('0')
                    page.locator('#locationForm button[type="submit"]').click()
                    page.locator('[data-launch="demo-0"]').wait_for()
                    page.locator('#launchSearch').fill('no-such-mission-fixture')
                    assert page.locator('#launchCards .launch-card').count() == 0
                    page.locator('#launchSearch').fill('')
                    page.locator('[data-launch="demo-0"]').wait_for()
                    page.locator('[data-page="sources"]').first.click()
                    assert page.locator('#sourceDesk').is_visible()
                    report = page.evaluate("api('/diagnostics')")
                    assert 'latitude' not in json.dumps(report) and 'password' not in report.get('configuration',{})
                    page.locator('[data-page="dashboard"]').first.click()''')

# Build numbers/assets are tied together. Historical release docs are retained.
for path in ['app/__init__.py','Dockerfile','templates/downrange-local.xml','scripts/install-unraid-local.sh',
             'app/static/index.html','app/static/sources-ui.js']:
    file=ROOT/path;s=file.read_text();s=re.sub(r'0\.3\.[012]-alpha\.[12]',VERSION,s);file.write_text(s)
f=ROOT/'app/static/index.html';s=f.read_text();s=re.sub(r'(/static/[^"?]+\.(?:js|css))(?=")',r'\1?v='+VERSION,s);f.write_text(s)
print('v1 integration applied with exact anchors. No user data or external services modified.')
