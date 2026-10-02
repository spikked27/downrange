/* Alpha-1 product controls. Never changes an account's alert opt-ins. */
(function(root){
  'use strict';
  const labels=['N','NE','E','SE','S','SW','W','NW'];
  function horizonLimit(profile,floor,azimuth){
    if(!profile||profile.length!==8)return floor;
    const p=((azimuth%360)+360)%360/45,i=Math.floor(p),f=p-i;
    return Math.max(floor,profile[i]*(1-f)+profile[(i+1)%8]*f);
  }
  function selected(launch,search,quality){
    const text=[launch.name,launch.vehicle,launch.provider,launch.pad?.site].join(' ').toLowerCase();
    if(search&&!text.includes(search.toLowerCase().trim()))return false;
    if(quality==='constrained'&&launch.prediction.low_information)return false;
    if(quality==='mission'&&launch.prediction.confidence!=='mission-specific')return false;
    return true;
  }
  if(typeof module!=='undefined'&&module.exports){module.exports={horizonLimit,selected};return;}
  function fillHorizon(profile){labels.forEach((_,i)=>{const e=document.querySelector('#horizon-'+i);if(e)e.value=profile?.[i]??0;});}
  function horizon(){const p=labels.map((_,i)=>Number(document.querySelector('#horizon-'+i)?.value||0));return p.some(v=>v!==0)?p:[];}
  root.DownrangeV1={horizonLimit,selected,fillHorizon,horizon};
  const form=document.querySelector('#locationForm');
  const editor=document.createElement('details');editor.id='horizonEditor';editor.className='horizon-editor';
  editor.innerHTML=`<summary>Local obstructions by direction</summary><p class="small muted">Enter the angle to the top of your trees or buildings, measured above a level horizon. Zero adds no obstruction. Values blend between the eight directions; the global minimum elevation remains a floor. These are your estimates, not downloaded terrain.</p><div class="horizon-grid">${labels.map((name,i)=>`<label>${name} · ${i*45}° true<input id="horizon-${i}" type="number" min="0" max="85" step="0.5" value="0" aria-label="${name} obstruction angle"></label>`).join('')}</div>`;
  document.querySelector('#locTz').closest('label').before(editor);
  const toolbar=document.querySelector('.feed-toolbar');
  const controls=document.createElement('div');controls.className='discovery-controls';
  controls.innerHTML='<label>Search launches<input id="launchSearch" type="search" placeholder="Mission, vehicle, provider or site" autocomplete="off"></label><label>Trajectory evidence<select id="qualityFilter"><option value="all">All evidence levels</option><option value="constrained">Exclude broad direction guesses</option><option value="mission">Mission-specific paths only</option></select></label>';
  toolbar.after(controls);
  controls.querySelector('#launchSearch').addEventListener('input',()=>renderCards());
  controls.querySelector('#qualityFilter').addEventListener('change',()=>renderCards());
  const dayOption=document.createElement('option');dayOption.value='1';dayOption.textContent='Next 24 hours';document.querySelector('#daysSelect').prepend(dayOption);

  const sourceNav=document.createElement('button');sourceNav.className='nav-item';sourceNav.dataset.page='sources';sourceNav.innerHTML='<span>◈</span> Sources & health';
  document.querySelector('.sidebar nav [data-page="method"]').before(sourceNav);
  const sourcePage=document.createElement('section');sourcePage.className='page';sourcePage.id='page-sources';sourcePage.hidden=true;
  sourcePage.innerHTML='<div class="section-heading"><span class="eyebrow">WHAT SUPPORTS YOUR FORECAST</span><h1>Sources & health</h1><p class="muted">A source being online is not the same as having a trajectory for a particular launch. Evidence age and schedule age are separate.</p></div><div id="sourceDesk"></div><div class="panel top-gap"><h2>Support diagnostics</h2><p class="small muted">Export a redacted status report for troubleshooting. It excludes your coordinates, location names, username, hostname, passwords, API keys, cookies, notification endpoints and private keys. Nothing is automatically uploaded.</p><button id="diagnosticExport" class="secondary">Download redacted diagnostics</button></div>';
  document.querySelector('main').appendChild(sourcePage);
  sourceNav.addEventListener('click',()=>loadFeed().catch(e=>toast(e.message,true)));
  sourcePage.querySelector('#diagnosticExport').onclick=run(async()=>{
    const data=await api('/diagnostics');
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='downrange-diagnostics.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  function render(){
    const sources=state.sources||{};
    let spotlight=document.querySelector('#nextOpportunity');
    if(!spotlight){spotlight=document.createElement('section');spotlight.id='nextOpportunity';spotlight.className='next-opportunity';document.querySelector('#feedBanner').after(spotlight);}
    const choices=state.launches.filter(l=>l.prediction.viewing_plan?.first&&
      new Date(l.prediction.viewing_plan.first.time).getTime()>Date.now()&&['go','tbc'].includes(String(l.status).toLowerCase()))
      .sort((a,b)=>new Date(a.prediction.viewing_plan.first.time)-new Date(b.prediction.viewing_plan.first.time));
    const l=choices.find(l=>!l.prediction.low_information)||choices[0];
    if(l){
      const first=l.prediction.viewing_plan.first,q=l.prediction.quality;
      spotlight.innerHTML=`<div><span class="eyebrow">${l.demo?'SYNTHETIC DEMO':l.prediction.low_information?'NEXT BROAD ESTIMATE':'NEXT MODELED VIEWING WINDOW'}</span><h2>${esc(l.name)}</h2><p><strong>${l.time_precise?esc(fmt(first.time)):'Liftoff time not precise'}</strong> · ${DownrangeTimeline.tplus(first.t_s)} · look ${esc(first.direction)} at ${first.elevation.toFixed(1)}°</p><small>${esc(q?.label||l.prediction.source)}. Weather and actual brightness may prevent a sighting.</small></div><button id="openNext" class="primary">Open observer view ↗</button>`;
      document.querySelector('#openNext').onclick=run(()=>openDetail(l.id));
    }else{
      spotlight.innerHTML='<span class="eyebrow">YOUR NEXT WINDOW</span><h2>No modeled viewing window in this feed yet.</h2><p>Broaden the date range or review the source coverage below. This does not prove there is nothing to see.</p>';
    }
    const counts={};for(const launch of state.launches){const label=launch.prediction.quality?.label||'Not classified';counts[label]=(counts[label]||0)+1;}
    document.querySelector('#sourceDesk').innerHTML=`<div class="source-desk-grid"><article class="panel"><h2>Evidence across this feed</h2>${Object.entries(counts).map(([name,n])=>`<p class="source-row"><span>${esc(name)}</span><strong>${n}</strong></p>`).join('')||'<p>Add a viewing location and load the feed.</p>'}<p class="small muted">Counts describe model inputs, not probability of seeing a launch.</p></article><article class="panel"><h2>Acquisition services</h2>${Object.entries(sources.sources||{}).map(([name,row])=>`<p class="source-row"><span>${esc(name)}</span><strong>${esc(row.status)}</strong></p>`).join('')||'<p>Waiting for source status.</p>'}<p class="small muted">Last research cycle: ${esc(fmt(sources.completed||sources.checked))}. ${sources.running?'Currently checking sources.':''}</p><p class="small muted">Flight Club is optional; “not configured” does not block public-source estimates.</p></article></div>`;
  }
  document.addEventListener('downrange:feed',render);
  function detail(){
    const launch=state.detail,parent=document.querySelector('#detailContent');
    if(!launch||!parent.children.length||parent.querySelector('#evidenceSummary'))return;
    const q=launch.prediction.quality;if(!q)return;
    const section=document.createElement('details');section.id='evidenceSummary';section.className='evidence-summary';
    section.innerHTML=`<summary>Evidence quality: ${esc(q.label)}</summary><p class="small muted">Last research attempt: ${esc(fmt(q.last_attempt))}. Oldest matched direction fetched: ${esc(fmt(q.oldest_evidence_at))}. ${q.schedule_age_s==null?'Schedule freshness unavailable.':'Launch record fetched '+Math.round(q.schedule_age_s/60)+' minutes ago.'}</p>${(q.source_checks||[]).map(r=>`<p class="small source-row"><span>${esc(r.source)}</span><strong>${esc(r.status.replaceAll('_',' '))}</strong></p>`).join('')}<p class="small muted">A historical profile is an analogue, a generic profile is an assumption, and a simulation is not measured flight telemetry.</p>`;
    parent.appendChild(section);
  }
  new MutationObserver(detail).observe(document.querySelector('#detailContent'),{childList:true});
})(typeof window!=='undefined'?window:globalThis);
