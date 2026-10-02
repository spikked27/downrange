/* Time-based observer chart. No chart library, remote map tiles or tracking. */
(function (root) {
  'use strict';
  const escape = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clamp = (v,a,b) => Math.max(a,Math.min(b,v));
  function tplus(value) {
    const s=Math.round(Math.abs(value));
    return `T${value<0?'−':'+'}${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;
  }
  function clock(iso,timezone,seconds=false) {
    return new Intl.DateTimeFormat(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit',
      ...(seconds?{second:'2-digit'}:{}),timeZoneName:'short',timeZone:timezone||'UTC'}).format(new Date(iso));
  }
  function compass(az) {
    return ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'][Math.floor((az+11.25)/22.5)%16];
  }
  function sampleAt(points,t,cutoff=5) {
    if(!points.length || t<points[0].t_s || t>points.at(-1).t_s)return null;
    let lo=0,hi=points.length-1;
    while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(points[mid].t_s<=t)lo=mid;else hi=mid-1;}
    const a=points[lo],b=points[lo+1];
    if(a.t_s===t||!b)return {...a};
    if(b.t_s-a.t_s>120)return null;
    const f=(t-a.t_s)/(b.t_s-a.t_s),p={...a,t_s:t};
    for(const key of ['elevation','range_km','sun_altitude','altitude_km'])p[key]=a[key]+f*(b[key]-a[key]);
    p.azimuth=(a.azimuth+f*((b.azimuth-a.azimuth+540)%360-180)+360)%360;
    p.above=p.elevation>=cutoff;
    p.ordinary=p.above&&p.powered&&p.sun_altitude<0;
    p.jellyfish=p.above&&p.plume&&p.sunlit&&p.sun_altitude<=-4;
    return p;
  }
  function bounds(points,windows,focus,cutoff) {
    const end=Math.max(1,points.at(-1)?.t_s||1);
    let x0=0,x1=end;
    if(focus&&windows.length){x0=Math.max(0,windows[0].start_s-30);x1=Math.min(end,windows.at(-1).end_s+30);}
    if(x1<=x0)x1=x0+1;
    const inView=points.filter(p=>p.t_s>=x0&&p.t_s<=x1);
    const max=Math.max(cutoff,...inView.map(p=>p.elevation),0);
    const min=Math.min(0,...inView.map(p=>p.elevation));
    return {x0,x1,y0:Math.max(-90,Math.max(-15,Math.floor((min-2)/5)*5)),y1:Math.min(90,Math.max(10,Math.ceil((max+3)/5)*5))};
  }
  function phase(p,cutoff) {
    if(!p)return 'No trajectory samples at this time';
    if(p.elevation<0)return 'Below the geometric horizon';
    if(!p.above)return `Below your ${cutoff}° viewing limit`;
    if(p.jellyfish)return 'Sunlit-plume opportunity';
    if(p.ordinary)return 'Powered-night opportunity';
    if(p.sun_altitude>=0)return 'Above horizon · daylight visibility unassessed';
    return 'Above horizon · no modeled luminous segment';
  }
  function card(launch,timezone) {
    const p=launch.prediction,plan=p.viewing_plan;
    if(!plan)return '';
    const first=plan.first,peak=plan.peak;
    if(!first){
      const reason={no_path:'No flight path yet',daylight_unassessed:'Daylight visibility is not assessed',
        below_horizon:'Below your horizon in modeled paths',no_modeled_signal:'No modeled burn/plume viewing window'}[plan.status];
      return `<div class="viewing-card muted">${escape(reason||'Viewing window unavailable')}<small>Open the brief for evidence and model limits.</small></div>`;
    }
    return `<div class="viewing-card"><span class="eyebrow">START LOOKING · ${p.automatic?'PLOTTED SCENARIO':'SUPPLIED PATH'}</span>
      <strong>${tplus(first.t_s)} <span>after liftoff</span></strong>
      ${timezone&&launch.time_precise?'<small>'+escape(clock(first.time,timezone))+'</small>':''}<small>${escape(first.direction)} · ${first.elevation.toFixed(1)}° above the horizon</small>
      <small>Highest viewing elevation: ${peak.elevation.toFixed(1)}° ${escape(peak.direction)} at ${tplus(peak.t_s)}</small>
      <small>${plan.windows.length>1?plan.windows.length+' separate windows':'Ends '+tplus(plan.last.t_s)}${launch.time_precise?'':' · provisional liftoff time'}</small></div>`;
  }
  function mount(parent,launch) {
    const prediction=launch.prediction,plan=prediction.viewing_plan,points=prediction.points||[];
    if(!plan)return ()=>{};
    const timezone=launch.location.timezone,cutoff=plan.min_elevation_deg;
    const section=document.createElement('section');section.className='viewing-panel';section.id='viewingTimeline';
    const summary=(label,e)=>e?`<button class="viewing-event" data-seek="${e.t_s}" type="button"><small>${label}</small><strong>${tplus(e.t_s)}</strong><span>${escape(e.direction)} · ${e.elevation.toFixed(1)}°</span><small>${launch.time_precise?escape(clock(e.time,timezone)):'Clock time unconfirmed'}</small></button>`:'';
    section.innerHTML=`<div class="viewing-heading"><div><span class="eyebrow">WHEN & WHERE TO LOOK</span><h3>Visibility after liftoff</h3></div><span class="tag ${prediction.low_information?'warn':''}">${prediction.automatic?'ONE MODELED SCENARIO':'SUPPLIED PATH'}</span></div>
      <p class="small muted">T+ is elapsed time after the reported liftoff. ${launch.time_precise?'Clock times use '+escape(timezone)+'.':'Liftoff time is unconfirmed; clock predictions are provisional.'} This is a model, not live tracking.</p>
      ${plan.first?`<div class="viewing-events">${summary('First opportunity',plan.first)}${summary('Highest viewing elevation',plan.peak)}${summary('Last opportunity',plan.last)}</div>`:card(launch)}
      ${points.length?`<div class="viewing-controls"><button id="fullTimeline" class="secondary compact" aria-pressed="true">From liftoff</button><button id="focusTimeline" class="secondary compact" aria-pressed="false" ${plan.first?'':'disabled'}>Zoom to viewing</button><span id="viewingCountdown" class="small muted"></span></div>
      <canvas id="timePlot" aria-label="Elevation above the horizon against elapsed time since launch. Use the time slider for values." role="img"></canvas>
      <div class="timeline-legend small"><span class="legend-night">Powered-night window</span><span class="legend-plume">Sunlit-plume window</span><span>Dashed: your ${cutoff}° limit</span></div>
      <label class="time-slider-label" for="timeSlider">Explore flight time<input id="timeSlider" type="range" min="0" max="${points.at(-1).t_s}" step="1" value="${plan.first?.t_s||0}"></label>
      <div id="timeReadout" class="time-readout" aria-live="polite"></div>
      <p class="small muted">The vertical scale fits this path; below −15° may be clipped. Shaded intervals belong to the plotted path only. Click an event above, drag the slider, or tap the chart. Gaps and unpowered segments are not viewing windows.</p>`:''}
      <div id="viewingWindowList">${plan.windows.map((w,i)=>`<p class="small"><strong>Window ${i+1}:</strong> ${tplus(w.start_s)}–${tplus(w.end_s)} · ${escape(w.first.direction)} to ${escape(w.last.direction)}${launch.time_precise?'<br>'+escape(clock(w.start,timezone,true))+' – '+escape(clock(w.end,timezone,true)):''}</p>`).join('')}</div>
      ${prediction.automatic&&plan.scenario_windows.length?`<details class="scenario-alternatives"><summary>Timing across all alternatives (not the single plotted path)</summary><p class="small muted">${plan.scenario_windows.map(w=>tplus(w.start_s)+'–'+tplus(w.end_s)).join(' · ')}. These are merged possibilities from alternative paths, not a continuous guaranteed sighting. Notifications may use the earlier alternative.</p></details>`:''}
      ${points.length?'<details id="sampleTable"><summary>Flight-time values as a table</summary><div class="sample-table-scroll"></div></details>':''}`;
    // Replace duplicated summaries, but preserve the existing azimuth chart as an optional view.
    parent.querySelector('.detail-grid')?.remove();parent.querySelector('.windows')?.remove();
    const oldPlot=parent.querySelector('.plot-box');
    if(oldPlot){const fold=document.createElement('details');fold.className='sky-chart-fold';fold.innerHTML='<summary>Sky direction chart (azimuth versus elevation)</summary>';oldPlot.before(fold);fold.appendChild(oldPlot);}
    const warnings=[...parent.querySelectorAll('.detail-warning')];
    if(warnings.length){const fold=document.createElement('details');fold.className='model-limits';fold.innerHTML='<summary>Model assumptions and limits</summary>';warnings[0].before(fold);warnings.forEach(w=>fold.appendChild(w));}
    const heading=parent.querySelector('p.muted');heading?heading.after(section):parent.prepend(section);
    if(!points.length)return ()=>section.remove();
    const canvas=section.querySelector('#timePlot'),slider=section.querySelector('#timeSlider');
    let selected=Number(slider.value),focus=false,dimensions=null,destroyed=false;
    function draw() {
      if(destroyed)return;
      const width=Math.max(240,canvas.getBoundingClientRect().width),height=width<480?255:300;
      const ratio=Math.min(window.devicePixelRatio||1,3);
      canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);canvas.style.height=height+'px';
      const ctx=canvas.getContext('2d');ctx.setTransform(ratio,0,0,ratio,0,0);
      const d=bounds(points,plan.windows,focus,cutoff),L=44,R=14,T=22,B=47;
      dimensions={...d,L,R,T,B,width,height};
      const x=t=>L+(t-d.x0)/(d.x1-d.x0)*(width-L-R);
      const y=e=>height-B-(e-d.y0)/(d.y1-d.y0)*(height-T-B);
      ctx.clearRect(0,0,width,height);ctx.font='11px system-ui';
      ctx.fillStyle='#142239';ctx.fillRect(L,T,width-L-R,height-T-B);
      ctx.save();ctx.beginPath();ctx.rect(L,T,width-L-R,height-T-B);ctx.clip();
      ctx.fillStyle='rgba(8,15,28,.65)';ctx.fillRect(L,y(0),width-L-R,height-B-y(0));
      for(const [key,color] of [['ordinary_windows','rgba(134,229,204,.16)'],['jellyfish_windows','rgba(239,189,144,.24)']]){
        ctx.fillStyle=color;
        for(const w of plan[key])ctx.fillRect(x(w.start_s),T,Math.max(1,x(w.end_s)-x(w.start_s)),height-T-B);
      }
      ctx.restore();
      const yStep=(d.y1-d.y0)>60?15:(d.y1-d.y0)>25?10:5;
      ctx.textAlign='right';ctx.textBaseline='middle';
      for(let e=Math.ceil(d.y0/yStep)*yStep;e<=d.y1;e+=yStep){
        ctx.strokeStyle='#304258';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(L,y(e));ctx.lineTo(width-R,y(e));ctx.stroke();
        ctx.fillStyle='#b5c6d6';ctx.fillText(e+'°',L-8,y(e));
      }
      const step=[15,30,60,90,120,180,300,600,900,1800].find(s=>(d.x1-d.x0)/s<=Math.max(2,Math.floor((width-L-R)/75)))||1800;
      ctx.textAlign='center';ctx.textBaseline='top';
      for(let t=Math.ceil(d.x0/step)*step;t<=d.x1;t+=step){
        ctx.fillStyle='#b5c6d6';ctx.fillText(tplus(t).replace('T+',''),x(t),height-B+10);
      }
      ctx.fillText('Time since launch (minutes:seconds)',L+(width-L-R)/2,height-15);
      ctx.textAlign='left';ctx.fillStyle='#c7d9e8';ctx.fillText('Elevation above horizon',L,4);
      ctx.save();ctx.beginPath();ctx.rect(L,T,width-L-R,height-T-B);ctx.clip();
      ctx.strokeStyle='#c7b594';ctx.setLineDash([5,5]);ctx.lineWidth=1.2;ctx.beginPath();ctx.moveTo(L,y(cutoff));ctx.lineTo(width-R,y(cutoff));ctx.stroke();ctx.setLineDash([]);
      ctx.lineWidth=2.5;
      for(let i=1;i<points.length;i++){
        const a=points[i-1],b=points[i];if(b.t_s-a.t_s>120)continue;
        ctx.strokeStyle=a.jellyfish?'#efbd90':a.ordinary?'#86e5cc':'#8092aa';
        ctx.beginPath();ctx.moveTo(x(a.t_s),y(a.elevation));ctx.lineTo(x(b.t_s),y(b.elevation));ctx.stroke();
      }
      const current=sampleAt(points,selected,cutoff);
      ctx.strokeStyle='#f5f8fc';ctx.lineWidth=1;ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(x(selected),T);ctx.lineTo(x(selected),height-B);ctx.stroke();ctx.setLineDash([]);
      if(current){ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(x(selected),y(current.elevation),4,0,2*Math.PI);ctx.fill();}
      ctx.restore();
    }
    function select(t) {
      selected=clamp(Number(t),0,points.at(-1).t_s);slider.value=selected;
      const p=sampleAt(points,selected,cutoff),when=new Date(new Date(launch.net).getTime()+selected*1000);
      section.querySelector('#timeReadout').innerHTML=`<div><strong>${tplus(selected)}</strong><small>${launch.time_precise?escape(clock(when,timezone,true)):'Liftoff time unconfirmed'}</small></div>
        <div><strong>${p?p.elevation.toFixed(1)+'°':'—'}</strong><small>above horizon</small></div>
        <div><strong>${p?compass(p.azimuth)+' '+p.azimuth.toFixed(0)+'°':'—'}</strong><small>true azimuth</small></div>
        <div><strong>${p?Math.round(p.range_km).toLocaleString()+' km':'—'}</strong><small>slant distance</small></div><p>${escape(phase(p,cutoff))}</p>`;
      slider.setAttribute('aria-valuetext',tplus(selected)+(p?`, ${p.elevation.toFixed(1)} degrees elevation, ${compass(p.azimuth)}`:''));draw();
    }
    slider.addEventListener('input',()=>select(slider.value));
    section.querySelectorAll('[data-seek]').forEach(button=>button.onclick=()=>select(button.dataset.seek));
    for(const [id,value] of [['fullTimeline',false],['focusTimeline',true]])section.querySelector('#'+id).onclick=()=>{
      focus=value;section.querySelector('#fullTimeline').setAttribute('aria-pressed',String(!focus));section.querySelector('#focusTimeline').setAttribute('aria-pressed',String(focus));
      const d=bounds(points,plan.windows,focus,cutoff);select(clamp(selected,d.x0,d.x1));
    };
    const pick=event=>{
      if(!dimensions)return;
      const pos=event.clientX-canvas.getBoundingClientRect().left,d=dimensions;
      select(Math.round(d.x0+clamp((pos-d.L)/(d.width-d.L-d.R),0,1)*(d.x1-d.x0)));
    };
    canvas.addEventListener('pointerdown',pick);
    canvas.addEventListener('pointermove',event=>{if(event.buttons===1)pick(event);});
    const ro=new ResizeObserver(draw);ro.observe(canvas);
    let lastCountdown='';
    function countdown(){
      if(destroyed||document.hidden)return;
      let text='Clock time unconfirmed';
      if(launch.time_precise){
        const seconds=(Date.now()-new Date(launch.net).getTime())/1000;
        if(seconds<0){const left=Math.ceil(-seconds);text='Scheduled liftoff in '+(left>=3600?Math.floor(left/3600)+'h '+Math.floor(left%3600/60)+'m':Math.floor(left/60)+'m '+left%60+'s');}
        else if(seconds<=points.at(-1).t_s)text='Nominal launch clock: '+tplus(seconds)+' (not confirmed live)';
        else text='Modeled flight window is past';
      }
      if(text!==lastCountdown){section.querySelector('#viewingCountdown').textContent=text;lastCountdown=text;}
    }
    const timer=setInterval(countdown,1000);countdown();
    const chosen=points.filter((p,i)=>i===0||i===points.length-1||Math.floor(p.t_s/60)!==Math.floor(points[i-1].t_s/60)||p.ordinary!==points[i-1].ordinary||p.jellyfish!==points[i-1].jellyfish);
    section.querySelector('.sample-table-scroll').innerHTML=`<table><thead><tr><th>Time</th><th>Elevation</th><th>Direction</th><th>Model state</th></tr></thead><tbody>${chosen.map(p=>`<tr><td>${tplus(p.t_s)}</td><td>${p.elevation.toFixed(1)}°</td><td>${compass(p.azimuth)} ${p.azimuth.toFixed(0)}°</td><td>${escape(phase(p,cutoff))}</td></tr>`).join('')}</tbody></table>`;
    select(selected);
    return ()=>{destroyed=true;ro.disconnect();clearInterval(timer);};
  }
  const exported={tplus,sampleAt,bounds,phase,card,mount};
  if(typeof module!=='undefined'&&module.exports)module.exports=exported;
  else root.DownrangeTimeline=exported;
})(typeof window!=='undefined'?window:globalThis);
