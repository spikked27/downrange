'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = {config:null,user:null,locations:[],launches:[],location:null,page:'dashboard',register:false,detail:null};
let toastTimer;
function toast(message,error=false){$('#toast').textContent=message;$('#toast').classList.toggle('error-toast',error);$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,7000);}
async function api(path,method='GET',body){
  const opts={method,credentials:'same-origin',headers:{'X-Downrange':'1'},cache:'no-store'};
  if(body!==undefined){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body);}
  const r=await fetch('/api'+path,opts);let data;try{data=await r.json();}catch{throw new Error('Server returned an unreadable response');}
  if(!r.ok){let m=data.detail;if(Array.isArray(m))m=m.map(x=>`${x.loc.slice(1).join('.')}: ${x.msg}`).join('; ');throw new Error(m||`Request failed (${r.status})`);}
  return data;
}
function run(fn){return async e=>{try{await fn(e);}catch(err){toast(err.message,true);}};}
function tz(){return state.location?.timezone||Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC';}
function fmt(iso,kind='full'){
  if(!iso)return 'Not available';
  const d=new Date(typeof iso==='number'?iso*1000:iso);
  if(!Number.isFinite(d.getTime()))return 'Unknown time';
  const options=kind==='time'?{hour:'numeric',minute:'2-digit',timeZoneName:'short'}:{month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'};
  return new Intl.DateTimeFormat(undefined,{...options,timeZone:tz()}).format(d);
}
function launchTime(l){return l.time_precise?fmt(l.net):`${esc(l.precision)} precision · ${new Intl.DateTimeFormat(undefined,{month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(l.net))} (time unconfirmed)`;}
function setPage(page){
  state.page=page;$$('.page').forEach(p=>p.hidden=p.id!=='page-'+page);$$('.nav-item').forEach(b=>{b.classList.toggle('active',b.dataset.page===page);b.setAttribute('aria-current',b.dataset.page===page?'page':'false');});
  if(page==='alerts')loadAlerts().catch(e=>toast(e.message,true));
  if(page==='account')loadAccount().catch(e=>toast(e.message,true));
  window.scrollTo({top:0,behavior:'instant'});
}
async function signIn(){
  state.user=await api('/me');$('#authView').hidden=true;$('#shell').hidden=false;
  $('#modeBadge').textContent=state.config.demo_mode?'SYNTHETIC DEMO':'ALPHA';
  $('#fetchProvider').hidden=!state.user.admin;
  await loadLocations();
  if(!state.locations.length)setPage('locations');else{setPage('dashboard');await loadFeed();const launchId=new URLSearchParams(location.search).get('launch');if(launchId)await openDetail(launchId);}
  if(window.isSecureContext&&'serviceWorker'in navigator){try{await navigator.serviceWorker.register('/sw.js');}catch(e){console.warn('Service worker registration unavailable:',e.message);}}
}
async function loadLocations(){
  state.locations=await api('/locations');
  let id=state.location?.id||new URLSearchParams(location.search).get('location')||sessionStorage.getItem('downrange-location');
  state.location=state.locations.find(l=>l.id===id)||state.locations[0]||null;
  $('#locationSelect').innerHTML=state.locations.length?state.locations.map(l=>`<option value="${esc(l.id)}">${esc(l.name)}</option>`).join(''):'<option value="">Add a viewing location</option>';
  if(state.location){$('#locationSelect').value=state.location.id;sessionStorage.setItem('downrange-location',state.location.id);}
  $('#savedLocations').innerHTML=state.locations.map(l=>`<article class="location-card"><h3>${esc(l.name)}</h3><p>${l.latitude.toFixed(4)}°, ${l.longitude.toFixed(4)}° · horizon ≥ ${l.min_elevation_deg}°</p><p>${esc(l.timezone)} · Alerts ${l.alerts?'included':'off'}</p><div class="inline"><button class="text-button" data-edit-location="${esc(l.id)}">Edit</button><button class="text-button" data-delete-location="${esc(l.id)}">Delete</button></div></article>`).join('')||'<p class="muted">Your saved spots will appear here.</p>';
  $$('[data-edit-location]').forEach(b=>b.onclick=()=>editLocation(b.dataset.editLocation));
  $$('[data-delete-location]').forEach(b=>b.onclick=run(async()=>{if(!confirm('Delete this saved location and cancel its pending reminders?'))return;await api('/locations/'+b.dataset.deleteLocation,'DELETE');await loadLocations();await loadFeed();toast('Location deleted');}));
}
function editLocation(id){
  const l=state.locations.find(x=>x.id===id);if(!l)return;
  $('#locationId').value=l.id;$('#locName').value=l.name;$('#locLat').value=l.latitude;$('#locLon').value=l.longitude;$('#locAlt').value=l.elevation_m;$('#locMin').value=l.min_elevation_deg;$('#locTz').value=l.timezone;$('#locAlerts').checked=l.alerts;window.DownrangeV1?.fillHorizon(l.horizon_profile||[]);
  $('#locationFormTitle').textContent='Edit viewing location';$('#cancelEdit').hidden=false;setPage('locations');$('#locName').focus();
}
function resetLocationForm(){ $('#locationForm').reset();window.DownrangeV1?.fillHorizon([]);$('#locationId').value='';$('#locationFormTitle').textContent='Add a location';$('#cancelEdit').hidden=true;$('#locTz').value=Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC';}
function fillPlace(p){$('#locName').value=p.name;$('#locLat').value=p.latitude;$('#locLon').value=p.longitude;$('#locAlt').value=p.elevation_m??0;$('#locTz').value=p.timezone||tz();$('#searchResults').innerHTML='';}
async function searchPlaces(){const q=$('#placeSearch').value.trim();if(q.length<2)throw new Error('Enter at least two characters');$('#searchButton').disabled=true;try{const places=await api('/geocode?q='+encodeURIComponent(q));$('#searchResults').innerHTML=places.map((p,i)=>`<button type="button" class="search-result" data-place="${i}">${esc(p.name)}<small>${esc(p.region)}</small></button>`).join('')||'<p class="small muted">No places found. Try a different name or use coordinates.</p>';$$('[data-place]').forEach(b=>b.onclick=()=>fillPlace(places[Number(b.dataset.place)]));}finally{$('#searchButton').disabled=false;}}
async function loadFeed(){
  if(!state.location){state.launches=[];renderCards();return;}
  const request=state.feedRequest=(state.feedRequest||0)+1;
  $('#refreshButton').disabled=true;
  try{
    const data=await api(`/launches?location_id=${encodeURIComponent(state.location.id)}&days=${$('#daysSelect').value}`);
    if(request!==state.feedRequest)return;
    state.launches=data.launches;state.sources=data.sources;const f=data.feed;
    const fetched=f.last_success?fmt(f.last_success):'not yet fetched';
    if(state.config.demo_mode){$('#feedBanner').textContent='SYNTHETIC DEMO — These launches and flight paths are fictional. Live data and real notifications are disabled.';$('#feedBanner').className='notice';}
    else{$('#feedBanner').textContent=(data.stale?'Feed is stale or unavailable. Viewing reminders are suppressed. ':'')+`Launch data last fetched: ${fetched}. `+(f.error||'')+(f.truncated?` Cache covers the first ${f.returned} of ${f.available} upcoming records.`:'')+(f.skipped?` ${f.skipped} invalid records were skipped.`:'');$('#feedBanner').className=data.stale?'notice':'notice subtle';}
    $('#statLaunches').textContent=state.launches.length;
    $('#statModeled').textContent=state.launches.filter(l=>Boolean(l.prediction.viewing_plan?.first)).length;
    $('#statJelly').textContent=state.launches.filter(l=>l.prediction.jellyfish_windows.length).length;
    $('#statHorizon').textContent=state.location.min_elevation_deg+'°';
    renderCards();renderSourceStatus();document.dispatchEvent(new Event("downrange:feed"));
  }finally{if(request===state.feedRequest)$('#refreshButton').disabled=false;}
}
function renderCards(){
  const filter=$('#feedFilter').value;
  let list=state.launches.filter(l=>filter==='all'||(filter==='candidates'&&l.prediction.candidate)||(filter==='modeled'&&Boolean(l.prediction.viewing_plan?.first))||(filter==='jellyfish'&&l.prediction.jellyfish_windows.length));
  if(window.DownrangeV1)list=list.filter(l=>DownrangeV1.selected(l,$('#launchSearch')?.value||'', $('#qualityFilter')?.value||'all'));
  list.sort((a,b)=>Number(Boolean(a.prediction.low_information))-Number(Boolean(b.prediction.low_information))||new Date(a.net)-new Date(b.net));
  if(!list.length){$('#launchCards').innerHTML=`<div class="empty"><h3>${state.location?'No matching opportunities in this cached feed.':'Give your sky a starting point.'}</h3><p>${state.location?'This is not an all-clear on the sky. Try “All cached launches,” extend the date range, or check whether the feed and mission trajectories are available.':'Save a town or coordinates anywhere in the world to begin.'}</p>${!state.location?'<button class="primary" id="emptyAddLocation">Add a viewing location</button>':''}</div>`;if($('#emptyAddLocation'))$('#emptyAddLocation').onclick=()=>setPage('locations');return;}
  $('#launchCards').innerHTML=list.map((l,i)=>{
    const p=l.prediction;const modeled=p.mode==='trajectory';
    const badge=l.demo?'DEMO':p.automatic?'AUTO ESTIMATE':modeled?(p.confidence==='estimated'?'EXPERIMENTAL':'SOURCED TRACK'):(p.candidate?'UNMODELED CANDIDATE':'OUTSIDE SCREEN');
    const badgeClass=l.demo?'demo':modeled&&p.confidence==='mission-specific'?'good':'warn';
    return `<article class="launch-card"><div class="card-top"><span class="card-index">${String(i+1).padStart(2,'0')} / LAUNCH</span><span class="tag ${badgeClass}">${badge}</span></div><div class="card-body"><h3>${esc(l.name)}</h3><p class="card-meta">${esc(l.pad.site||l.pad.name)}<br>${esc(l.provider)}</p><div class="launch-time">${launchTime(l)}<small>${l.time_precise?'Nominal liftoff · '+esc(l.status_name):'Not an exact liftoff time'}</small></div>${DownrangeTimeline.card(l,tz())}<div class="assessment"><div><span>Launch visibility</span><span>${esc(p.ordinary)}</span></div><div><span>Jellyfish</span><span>${esc(p.jellyfish)}</span></div><div><span>${modeled?'Geometric peak':'Flight path'}</span><span>${modeled?(p.max_elevation_deg==null?'Below selected horizon':`${p.automatic?'up to ':''}${p.max_elevation_deg}° · ${esc(p.direction)}`):'Not available'}</span></div></div><div class="card-weather" data-weather="${esc(l.id)}">Open viewing brief for weather.</div></div><div class="card-footer"><span>${p.automatic?'Assumed scenarios, not a forecast':modeled?'Geometry, not a guarantee':'Visibility unknown'}</span><button class="text-button" data-launch="${esc(l.id)}">Viewing brief ↗</button></div></article>`;
  }).join('');
  $$('[data-launch]').forEach(b=>b.onclick=run(()=>openDetail(b.dataset.launch)));
  loadCardWeather();
}
async function openDetail(id){
  const l=await api(`/launches/${encodeURIComponent(id)}?location_id=${encodeURIComponent(state.location.id)}`);state.detail=l;
  const p=l.prediction;const win=(name,rows)=>rows.length?`<h3>${name}</h3>${rows.map(w=>`<p>${esc(fmt(w.start))} — ${esc(fmt(w.end,'time'))}</p>`).join('')}`:'';
  $('#detailContent').innerHTML=`<h2 class="dialog-heading">${esc(l.name)}</h2><p class="muted">${esc(l.pad.name)} · ${esc(l.provider)}<br>${launchTime(l)} · ${esc(l.status_name)}</p>${l.demo?'<div class="detail-warning">SYNTHETIC DEMO. Not an upcoming real launch.</div>':''}${p.warnings.map(w=>`<div class="detail-warning">${esc(w)}</div>`).join('')}<div class="detail-grid"><div><small>Ordinary launch</small><strong>${esc(p.ordinary)}</strong></div><div><small>Sunlit plume</small><strong>${esc(p.jellyfish)}</strong></div><div><small>Best geometric elevation</small><strong>${p.max_elevation_deg==null?'Unknown / outside track':p.max_elevation_deg+'° · '+esc(p.direction)}</strong></div></div>${p.points.length?`<div class="plot-box"><h3>${p.automatic?'One assumed path across your sky':'Path across your sky'}</h3><canvas id="skyPlot" width="1000" height="380" aria-label="Predicted azimuth and elevation path"></canvas><p class="small muted">True north = 0°/360° · cyan: powered flight · amber: sunlit plume in twilight · gray: other track segments. ${p.automatic?'Only one favorable scenario is shown; the actual trajectory is unknown.':'This is the supplied path, not a measured flight.'}</p></div>`:'<div class="notice subtle">No path is drawn because there is no mission trajectory. Launchpad direction is not a substitute for where the rocket will appear.</div>'}<div class="windows">${win('Possible powered-flight window',p.ordinary_windows)}${win('Favorable jellyfish geometry',p.jellyfish_windows)}</div>${p.scenario_counts?`<div class="notice subtle small">${p.scenario_counts.total} assumed scenarios checked: ${p.scenario_counts.ordinary} with powered-night geometry; ${p.scenario_counts.jellyfish} with sunlit-plume geometry. These counts are not probabilities. Elevation range among above-horizon scenarios: ${p.elevation_range_deg?p.elevation_range_deg.join('–')+'°':'none'}.</div>`:''}<h3>Trajectory provenance</h3><p class="small muted">${esc(p.source)}${p.source_url?`<br><a href="${esc(p.source_url)}" target="_blank" rel="noopener noreferrer">Trajectory source ↗</a>`:''}<br>${esc(p.notes||'')}</p><h3>Viewing conditions</h3><div id="detailWeather" class="notice subtle small">Checking the observer’s forecast grid cell…</div><details><summary>Mission information</summary><p class="small muted top-gap">${esc(l.mission||'No description supplied.')}</p><p class="small muted">Provider record last updated: ${esc(fmt(l.provider_updated))}<br>Launch ID: ${esc(l.id)}</p></details>${state.user.admin?`<details class="detail-admin"><summary>Administrator · Flight path tools</summary><p class="small muted">A source label is not a validation certificate. Only mark a path mission-specific when it is actually sourced for this launch. Imported points use seconds after liftoff, degrees, and kilometers above the WGS84 ellipsoid.</p><form id="trackForm"><label>Import trajectory JSON<input id="trackFile" type="file" accept=".json,application/json"></label><label>Trajectory document<textarea id="trackJSON" spellcheck="false" placeholder='{"source":"Source and mission", "kind":"estimated", "points":[...]}'></textarea></label><div class="inline"><button class="primary" type="submit">Save trajectory</button><button class="secondary" id="deleteTrack" type="button">Remove trajectory</button></div></form><hr><h3>Explore a hypothetical heading</h3><p class="small muted">This uses a hand-chosen generic ascent, not actual vehicle telemetry. Do not assume a heading from a mission name. Saving it replaces the current trajectory for this launch.</p><form id="scenarioForm"><label>Initial heading, degrees clockwise from true north<input id="scenarioHeading" type="number" min="0" max="359.999" step="any" placeholder="Enter a direction to explore" required></label><label class="check"><input type="checkbox" required>I understand this is a what-if scenario, not a mission forecast.</label><button class="secondary" type="submit">Save experimental scenario</button></form></details>`:''}`;
  if(!$('#detailDialog').open)$('#detailDialog').showModal();
  if(p.points.length)drawSky(p.points,state.location.min_elevation_deg);
  state.timelineCleanup?.();
  state.timelineCleanup=DownrangeTimeline.mount($('#detailContent'),l);
  if(state.user.admin){
    const track=await api('/admin/trajectories/'+encodeURIComponent(id));if(state.detail?.id!==id||!$('#trackJSON'))return;$('#trackJSON').value=track?JSON.stringify(track,null,2):'';
    $('#trackFile').onchange=run(async e=>{const f=e.target.files[0];if(!f)return;if(f.size>1024*1024)throw new Error('Trajectory file must be under 1 MiB');$('#trackJSON').value=await f.text();});
    $('#trackForm').onsubmit=run(async e=>{e.preventDefault();let data;try{data=JSON.parse($('#trackJSON').value);}catch{throw new Error('Invalid trajectory JSON');}await api('/admin/trajectories/'+encodeURIComponent(id),'PUT',data);toast('Trajectory saved');await loadFeed();await openDetail(id);});
    $('#deleteTrack').onclick=run(async()=>{if(!confirm('Remove this launch’s supplied path?'))return;await api('/admin/trajectories/'+encodeURIComponent(id),'DELETE');await loadFeed();await openDetail(id);toast('Trajectory removed');});
    $('#scenarioForm').onsubmit=run(async e=>{e.preventDefault();await api('/admin/trajectories/'+encodeURIComponent(id)+'/scenario','POST',{heading_deg:Number($('#scenarioHeading').value)});await loadFeed();await openDetail(id);toast('Experimental scenario saved and labeled');});
  }
  try{
    const w=await api(`/weather?launch_id=${encodeURIComponent(id)}&location_id=${encodeURIComponent(state.location.id)}`);
    if(state.detail?.id!==id||!$('#detailWeather'))return;
    $('#detailWeather').textContent=w.available?`${w.stale?'STALE FORECAST · ':''}Cloud cover: ${w.cloud_cover??'unknown'}% (low ${w.cloud_cover_low??'?'}%, middle ${w.cloud_cover_mid??'?'}%, high ${w.cloud_cover_high??'?'}%). Surface visibility: ${w.visibility==null?'unknown':(w.visibility/1000).toFixed(1)+' km'}. Forecast hour: ${fmt(w.forecast_time)}. Requested for ${w.target_basis||'liftoff'} at ${fmt(w.target_time||l.net)}. ${w.scope}. Weather does not gate alerts in this alpha.`:w.reason;
  }catch(e){if(state.detail?.id===id&&$('#detailWeather'))$('#detailWeather').textContent=e.message;}
}
function drawSky(points,minElevation){
  const canvas=$('#skyPlot'),ctx=canvas.getContext('2d');const W=canvas.width,H=canvas.height,L=65,T=20,B=60,R=25;
  const x=a=>L+a/360*(W-L-R),y=e=>H-B-e/90*(H-B-T);
  ctx.clearRect(0,0,W,H);ctx.font='15px system-ui';ctx.lineWidth=1;
  for(let el=0;el<=90;el+=15){ctx.strokeStyle='#263a50';ctx.beginPath();ctx.moveTo(L,y(el));ctx.lineTo(W-R,y(el));ctx.stroke();ctx.fillStyle='#91a6bb';ctx.fillText(el+'°',15,y(el)+5);}
  [0,90,180,270,360].forEach((a,i)=>{ctx.fillStyle='#9db1c5';ctx.fillText(['N 0°','E 90°','S 180°','W 270°','N 360°'][i],x(a)-(i===4?55:10),H-22);});
  ctx.setLineDash([6,5]);ctx.strokeStyle='#d4b793';ctx.beginPath();ctx.moveTo(L,y(minElevation));ctx.lineTo(W-R,y(minElevation));ctx.stroke();ctx.setLineDash([]);
  ctx.save();ctx.beginPath();ctx.rect(L,T,W-L-R,H-T-B);ctx.clip();ctx.lineWidth=3;
  for(let i=1;i<points.length;i++){
    const a=points[i-1],b=points[i];if(Math.abs(a.azimuth-b.azimuth)>180)continue;
    ctx.strokeStyle=a.jellyfish?'#efbd90':a.powered?'#86e5cc':'#6d839a';ctx.beginPath();ctx.moveTo(x(a.azimuth),y(a.elevation));ctx.lineTo(x(b.azimuth),y(b.elevation));ctx.stroke();
  }
  ctx.restore();
}
function base64Bytes(s){const raw=atob(s.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((-s.length%4+4)%4));return Uint8Array.from(raw,c=>c.charCodeAt(0));}
async function browserSubscription(){if(!window.isSecureContext||!('serviceWorker'in navigator))return null;const reg=await navigator.serviceWorker.getRegistration('/');return reg?await reg.pushManager.getSubscription():null;}
async function loadAlerts(){
  const p=await api('/preferences');$('#alertsEnabled').checked=p.enabled;$('#leadMinutes').value=p.lead_minutes.join(', ');$('#includeCandidates').checked=p.include_candidates;$('#includeEstimates').checked=p.include_estimates;$('#jellyOnly').checked=p.jellyfish_only;$('#scheduleChanges').checked=p.schedule_changes;$('#quietStart').value=p.quiet_start??'';$('#quietEnd').value=p.quiet_end??'';
  const supported=window.isSecureContext&&'Notification'in window&&'serviceWorker'in navigator&&'PushManager'in window;
  const sub=await browserSubscription();
  $('#pushBanner').textContent=state.config.demo_mode?'Synthetic demo: real notifications are disabled.':!window.isSecureContext?'You are using an HTTP address. The website works, but phone push notifications and GPS need HTTPS. Configure your reverse proxy and PUBLIC_URL, then reopen that address.':!state.config.push_configured?'Set PUBLIC_URL in the container template so the push service can identify this server.':!supported?'This browser does not support push here. On iPhone, install to the home screen and open the installed app.':'This server can schedule alerts independently of an open browser tab. Allow notifications on each device and enable the master alert switch.';
  $('#deviceStatus').textContent=!supported?'Push is unavailable in this browser context.':`Browser permission: ${Notification.permission}. ${sub?'This browser has a push subscription.':'This browser is not subscribed.'}`;
  $('#enablePush').disabled=!supported||state.config.demo_mode;$('#testPush').disabled=!supported||!sub||!state.config.push_configured||state.config.demo_mode;
  await refreshPushStatus();
}
async function refreshPushStatus(){
  const d=await api('/push/status');$('#deviceCount').textContent=`${d.devices} notification device${d.devices===1?'':'s'} registered for this account. Worker heartbeat: ${d.worker_heartbeat?fmt(d.worker_heartbeat):'not yet recorded'}.`;
  $('#deliveryList').innerHTML=d.deliveries.map(r=>{let p={};try{p=JSON.parse(r.payload);}catch{}return `<div class="delivery"><strong>${esc(p.title||r.kind)}</strong> · ${esc(r.status)}<br>${esc(fmt(r.next_try))}${r.error?'<br>'+esc(r.error):''}</div>`;}).join('')||'No delivery attempts yet. A successful test still needs to be confirmed on your phone.';
}
async function enablePush(){
  if(!window.isSecureContext)throw new Error('Open Downrange over HTTPS first');
  const permission=await Notification.requestPermission();if(permission!=='granted')throw new Error('Notification permission was not granted');
  await navigator.serviceWorker.register('/sw.js');const reg=await navigator.serviceWorker.ready;
  let sub=await reg.pushManager.getSubscription();if(!sub)sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:base64Bytes(state.config.vapid_public_key)});
  await api('/push/subscribe','POST',sub.toJSON());toast('Device registered. Save your alert rules and send a test.');await loadAlerts();
}
async function loadAccount(){
  $('#accountName').textContent=`Signed in as ${state.user.username}${state.user.admin?' · administrator':''}.`;
  const data=state.user.admin?await api('/admin/status'):{version:state.config.version,push_configured:state.config.push_configured};
  $('#systemStatus').textContent=JSON.stringify(data,null,2);
}
// Bind events once; server-provided strings are escaped before entering markup.
document.addEventListener('click',e=>{const b=e.target.closest('[data-page]');if(b)setPage(b.dataset.page);});
$('#authForm').onsubmit=async e=>{e.preventDefault();$('#authError').textContent='';$('#authSubmit').disabled=true;try{const body={username:$('#username').value,password:$('#password').value};if(state.register){body.invite_code=$('#inviteCode').value;await api('/register','POST',body);}await api('/login','POST',body);$('#password').value='';$('#inviteCode').value='';await signIn();}catch(err){$('#authError').textContent=err.message;}finally{$('#authSubmit').disabled=false;}};
$('#toggleRegister').onclick=()=>{state.register=!state.register;$('#inviteField').hidden=!state.register;$('#authSubmit').textContent=state.register?'Create account':'Sign in ↗';$('#toggleRegister').textContent=state.register?'Already have an account? Sign in':'Create an invited account';$('#password').autocomplete=state.register?'new-password':'current-password';$('#authHint').textContent=state.register?'Use the invitation code from your server administrator.':'Sign in to your server to set up your sky.';};
$('#logoutButton').onclick=run(async()=>{await api('/logout','POST');state.user=null;state.locations=[];state.launches=[];state.location=null;$('#shell').hidden=true;$('#authView').hidden=false;toast('Signed out. Scheduled notifications remain controlled by your saved alert settings.');});
$('#locationSelect').onchange=run(async e=>{state.location=state.locations.find(l=>l.id===e.target.value)||null;if(state.location)sessionStorage.setItem('downrange-location',state.location.id);await loadFeed();});
$('#refreshButton').onclick=run(loadFeed);$('#feedFilter').onchange=renderCards;$('#daysSelect').onchange=run(loadFeed);
$('#searchButton').onclick=run(searchPlaces);$('#placeSearch').onkeydown=run(async e=>{if(e.key==='Enter'){e.preventDefault();await searchPlaces();}});
$('#gpsButton').onclick=run(async()=>{if(!window.isSecureContext)throw new Error('Device location needs HTTPS. You can enter coordinates manually.');if(!navigator.geolocation)throw new Error('Geolocation is unavailable');const pos=await new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,reject,{timeout:15000,maximumAge:60000,enableHighAccuracy:false}));$('#locLat').value=pos.coords.latitude.toFixed(6);$('#locLon').value=pos.coords.longitude.toFixed(6);$('#locName').value=$('#locName').value||'Current location';$('#locTz').value=Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC';toast('Coordinates filled. Check the location timezone and save.');});
$('#locationForm').onsubmit=run(async e=>{e.preventDefault();const id=$('#locationId').value;const body={name:$('#locName').value,latitude:Number($('#locLat').value),longitude:Number($('#locLon').value),elevation_m:Number($('#locAlt').value),min_elevation_deg:Number($('#locMin').value),timezone:$('#locTz').value,alerts:$('#locAlerts').checked,horizon_profile:window.DownrangeV1?.horizon()||[]};const l=await api('/locations'+(id?'/'+id:''),id?'PUT':'POST',body);state.location=l;await loadLocations();resetLocationForm();await loadFeed();toast('Viewing location saved');setPage('dashboard');});
$('#cancelEdit').onclick=resetLocationForm;
$('#preferencesForm').onsubmit=run(async e=>{e.preventDefault();const leads=$('#leadMinutes').value.split(',').map(v=>Number(v.trim()));if(leads.some(v=>!Number.isInteger(v)))throw new Error('Reminder times must be whole numbers');await api('/preferences','PUT',{enabled:$('#alertsEnabled').checked,lead_minutes:leads,include_candidates:$('#includeCandidates').checked,include_estimates:$('#includeEstimates').checked,jellyfish_only:$('#jellyOnly').checked,schedule_changes:$('#scheduleChanges').checked,quiet_start:$('#quietStart').value===''?null:Number($('#quietStart').value),quiet_end:$('#quietEnd').value===''?null:Number($('#quietEnd').value)});toast('Alert preferences saved');});
$('#enablePush').onclick=run(enablePush);$('#testPush').onclick=run(async()=>{const d=await api('/push/test','POST');toast(d.message);await refreshPushStatus();});$('#refreshPush').onclick=run(refreshPushStatus);
$('#disablePush').onclick=run(async()=>{const sub=await browserSubscription();if(!sub){toast('This browser is not subscribed');return;}const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(sub.endpoint));const id=[...new Uint8Array(hash)].map(v=>v.toString(16).padStart(2,'0')).join('');await api('/push/subscriptions/'+id,'DELETE');await sub.unsubscribe();toast('This notification device was removed');await loadAlerts();});
$('#passwordForm').onsubmit=run(async e=>{e.preventDefault();const d=await api('/account/password','POST',{current_password:$('#currentPassword').value,new_password:$('#newPassword').value});$('#passwordForm').reset();state.user=null;$('#shell').hidden=true;$('#authView').hidden=false;toast(d.message);});
$('#fetchProvider').onclick=run(async()=>{await api('/admin/refresh','POST');await loadAccount();await loadFeed();toast('Provider status checked; the quota guard remains in effect');});
$('#closeDetail').onclick=()=>$('#detailDialog').close();$('#detailDialog').addEventListener('click',e=>{if(e.target===$('#detailDialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
(async()=>{try{state.config=await api('/config');$$('.version').forEach(e=>e.textContent=state.config.version);$('#toggleRegister').hidden=!state.config.registration_open;$('#locTz').value=Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC';try{await signIn();}catch(e){if(!/sign in|session/i.test(e.message))toast(e.message,true);}}catch(e){$('#authError').textContent='Cannot reach the Downrange server. '+e.message;}})();


// Refresh visible feed data automatically; never auto-change preferences or device permissions.
setInterval(()=>{
  if(!document.hidden&&state.user&&['dashboard','sources'].includes(state.page)&&!$('#detailDialog').open&&!$('#refreshButton').disabled)
    loadFeed().catch(e=>toast(e.message,true));
},60000);
$('#detailDialog').addEventListener('close',()=>{state.timelineCleanup?.();state.timelineCleanup=null;state.detail=null;});
function renderSourceStatus(){
  let panel=$('#sourcePanel');
  if(!panel){panel=document.createElement('div');panel.id='sourcePanel';panel.className='source-panel';$('.feed-toolbar').before(panel);}
  const s=state.sources||{};
  const supported=state.launches.filter(l=>l.prediction.source_evidence?.length||l.prediction.confidence==='mission-specific').length;
  const broad=state.launches.filter(l=>l.prediction.low_information).length;
  const running=s.running&&Date.now()/1000-(s.checked||0)<900;
  const status=state.config.demo_mode?'Synthetic demo — no real launch or weather claims.':s.enabled===false?'Automatic trajectory-source acquisition is disabled.':running?'Checking trajectory sources…':s.checked?'Last source check: '+fmt(s.completed||s.checked):'Waiting for the first trajectory-source check…';
  const sources=Object.entries(s.sources||{}).map(([name,result])=>name+': '+result.status).join(' · ');
  panel.innerHTML=`<div class="source-controls"><strong class="small">${esc(status)}</strong>${state.user.admin&&!state.config.demo_mode?'<button id="recheckSources" class="text-button">Recheck sources ↻</button>':''}</div>
    <p>${supported} launches with matched source evidence · ${broad} broad estimates. Sorted by direction confidence, then launch time.</p>
    <p class="source-facts">${esc(sources||'Generic estimates may appear before source research completes.')}</p>`;
  if($('#recheckSources'))$('#recheckSources').onclick=run(async()=>{const r=await api('/admin/sources/refresh','POST');toast(r.message);});
}
const cardWeatherCache=new Map();
function loadCardWeather(){
  const location=state.location;if(!location)return;
  // Limit background weather to six cards; detail pages can fetch the others.
  const targets=$$('[data-weather]').slice(0,6);
  const queue=targets.map(node=>({node,launch:state.launches.find(l=>l.id===node.dataset.weather)})).filter(x=>x.launch&&!x.launch.demo);
  async function worker(){
    while(queue.length){
      const {node,launch}=queue.shift();const key=`${location.id}|${launch.id}|${launch.net}`;
      let entry=cardWeatherCache.get(key);
      if(!entry||Date.now()-entry.when>300000){
        entry={when:Date.now(),promise:api(`/weather?launch_id=${encodeURIComponent(launch.id)}&location_id=${encodeURIComponent(location.id)}`)};
        cardWeatherCache.set(key,entry);
        if(cardWeatherCache.size>150)cardWeatherCache.delete(cardWeatherCache.keys().next().value);
      }
      try{
        const w=await entry.promise;
        if(!node.isConnected||state.location?.id!==location.id)continue;
        node.textContent=w.available?`${w.stale?'Stale weather · ':''}Observer cloud forecast: ${w.cloud_cover==null?'unknown':w.cloud_cover+'%'} · ${fmt(w.forecast_time,'time')}`:w.reason;
      }catch{if(node.isConnected)node.textContent='Weather unavailable; geometric estimate retained.';}
    }
  }
  worker();worker();
}
