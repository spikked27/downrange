/* Observer-local perspective. All coordinates come from the selected modeled path.
 * Symbolic position/guide only: no plume-size, brightness, stars, terrain or camera feed.
 */
(function(root){
  'use strict';
  const RAD=Math.PI/180;
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
  const wrap=a=>((a%360)+360)%360;
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const dot=(a,b)=>a.reduce((sum,x,i)=>sum+x*b[i],0);
  const directions=['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
  const compass=a=>directions[Math.floor((wrap(a)+11.25)/22.5)%16];
  function vector(azimuth,elevation){
    const a=azimuth*RAD,e=elevation*RAD;
    return [Math.cos(e)*Math.sin(a),Math.cos(e)*Math.cos(a),Math.sin(e)];
  }
  function basis(camera){
    const a=camera.azimuth*RAD,e=camera.elevation*RAD;
    return {forward:vector(camera.azimuth,camera.elevation),right:[Math.cos(a),-Math.sin(a),0],
      up:[-Math.sin(e)*Math.sin(a),-Math.sin(e)*Math.cos(a),Math.cos(e)]};
  }
  function project(azimuth,elevation,camera,width,height){
    if(![azimuth,elevation,camera.azimuth,camera.elevation,camera.fov,width,height].every(Number.isFinite)||width<=0||height<=0||camera.fov<=0||camera.fov>=180)return null;
    const v=vector(azimuth,elevation),b=basis(camera),z=dot(v,b.forward);
    if(z<=0.0001)return null;
    const f=width/(2*Math.tan(camera.fov*RAD/2));
    const x=width/2+f*dot(v,b.right)/z,y=height/2-f*dot(v,b.up)/z;
    return {x,y,inFrame:x>=0&&x<=width&&y>=0&&y<=height};
  }
  function unproject(x,y,camera,width,height){
    const b=basis(camera),f=width/(2*Math.tan(camera.fov*RAD/2));
    const u=(x-width/2)/f,v=(height/2-y)/f;
    const ray=b.forward.map((c,i)=>c+b.right[i]*u+b.up[i]*v),norm=Math.hypot(...ray);
    return {azimuth:wrap(Math.atan2(ray[0],ray[1])/RAD),elevation:Math.asin(clamp(ray[2]/norm,-1,1))/RAD};
  }
  function circularFrame(angles){
    if(!angles.length)return {center:0,span:0};
    const sorted=angles.map(wrap).sort((a,b)=>a-b);let gap=-1,start=sorted[0];
    for(let i=0;i<sorted.length;i++){
      const next=i+1<sorted.length?sorted[i+1]:sorted[0]+360,d=next-sorted[i];
      if(d>gap){gap=d;start=next;}
    }
    const span=360-gap;return {center:wrap(start+span/2),span};
  }
  function framePath(points,width=800,height=420){
    let candidates=points.filter(p=>p.ordinary||p.jellyfish);
    if(!candidates.length)candidates=points.filter(p=>p.elevation>=0);
    if(!candidates.length)candidates=points.slice(0,1);
    if(!candidates.length)return {azimuth:0,elevation:12,fov:90};
    const span=circularFrame(candidates.map(p=>p.azimuth));
    const low=Math.max(0,Math.min(...candidates.map(p=>p.elevation))),high=Math.max(...candidates.map(p=>p.elevation));
    const camera={azimuth:span.center,elevation:clamp((low+high)/2,5,85),fov:90};
    const b=basis(camera);let slope=Math.tan(37.5*RAD);
    for(const p of candidates){
      const v=vector(p.azimuth,p.elevation),z=dot(v,b.forward);
      if(z<=0.01){slope=Math.tan(60*RAD);break;}
      slope=Math.max(slope,Math.abs(dot(v,b.right)/z)/0.8,Math.abs(dot(v,b.up)/z)*width/height/0.8);
    }
    camera.fov=clamp(2*Math.atan(slope)/RAD,75,120);return camera;
  }
  function markerState(p,cutoff){
    if(!p)return 'no_data';
    if(p.elevation<0)return 'below_horizon';
    if(p.elevation<(p.horizon_limit_deg??cutoff))return 'below_limit';
    if(p.jellyfish)return 'plume';
    if(p.ordinary)return 'powered';
    return 'unassessed';
  }
  function mount(parent,launch,slider){
    const points=launch.prediction.points||[],plan=launch.prediction.viewing_plan;
    const api=root.DownrangeTimeline;
    if(!points.length||!plan||!slider||!api)return ()=>{};
    const cutoff=plan.min_elevation_deg,first=plan.first?.t_s??points[0].t_s,end=points.at(-1).t_s;
    const section=document.createElement('section');section.id='observerView';section.className='observer-panel';
    section.innerHTML=`<div class="observer-heading"><div><span class="eyebrow">FROM ${esc(launch.location.name||'YOUR SAVED LOCATION')}</span><h3>Your view of the sky</h3></div><span class="tag">MODELED PERSPECTIVE</span></div>
      <p class="small muted observer-intro">A view looking outward from your location—not down from space. Drag to look around. The marker and path are guides, not a prediction of apparent size or brightness.</p>
      <div class="observer-toolbar"><button type="button" id="observerFit" class="secondary compact">Frame flight</button><button type="button" id="observerHorizon" class="secondary compact">Face horizon</button><label class="check"><input type="checkbox" id="observerFollow">Follow marker</label><label class="check"><input type="checkbox" id="observerGuide" checked>Path guide</label></div>
      <div class="observer-scene"><canvas id="observerCanvas" tabindex="0" aria-label="Observer sky perspective. Arrow keys look around; plus and minus zoom. Position is also described below." role="img"></canvas><div class="observer-orientation" id="observerOrientation"></div><div class="observer-clock" id="observerClock"></div><div class="observer-camera-help">DRAG TO LOOK · + / − TO ZOOM</div></div>
      <div class="observer-controls"><div class="observer-play-controls"><button type="button" id="observerPlay" class="primary compact" aria-pressed="false">Play flight</button><button type="button" id="observerStart" class="secondary compact">First window</button><label>Speed<select id="observerSpeed" aria-label="Flight playback speed"><option value="1">1×</option><option value="10" selected>10×</option><option value="30">30×</option></select></label></div><div class="observer-zoom"><button type="button" id="observerZoomIn" class="secondary compact" aria-label="Zoom in">+</button><span id="observerFov"></span><button type="button" id="observerZoomOut" class="secondary compact" aria-label="Zoom out">−</button></div></div>
      <label class="observer-scrub-label">Flight time · linked to the graph below<input type="range" id="observerTime" min="0" max="${end}" step="1" value="${slider.value}" aria-label="Sky view time since launch"></label>
      <p id="observerStatus" class="observer-status" role="status" aria-live="polite"></p>
      <p class="small muted observer-footnote">Generic flat horizon at 0°. Dashed amber line: your configured viewing limits, including manually entered obstructions. Solid cyan: powered-night guide; amber: sunlit-plume guide; gray/dashed: other or future path. Below-horizon positions are hidden. ${launch.prediction.automatic?'This shows ONE scenario, not every possible flight path.':'This uses the supplied path.'} No downloaded terrain, star map or camera overlay.</p>`;
    const timeline=parent.querySelector('#viewingTimeline');timeline?timeline.before(section):parent.prepend(section);
    const el=id=>section.querySelector('#'+id),canvas=el('observerCanvas'),ctx=canvas.getContext('2d'),scrub=el('observerTime');
    let selected=Number(slider.value),camera=framePath(points),width=800,height=400,disposed=false,playing=false,frame=0,lastFrame=0,playTime=selected,lastRendered=-1,updating=false;
    let autoFrame=true,drag=null,drawPending=0;
    const query=root.matchMedia?.('(prefers-reduced-motion: reduce)');
    if(query?.matches)el('observerSpeed').value='1';
    function queueDraw(){if(!disposed&&!drawPending)drawPending=requestAnimationFrame(()=>{drawPending=0;draw();});}
    function lineFrom(points2,color,dash=[],lineWidth=1){
      ctx.strokeStyle=color;ctx.lineWidth=lineWidth;ctx.setLineDash(dash);ctx.beginPath();let last=null;
      for(const item of points2){
        const q=project(item.azimuth,item.elevation,camera,width,height);
        if(!q){last=null;continue;}
        if(last&&Math.abs(q.x-last.x)<width*1.5&&Math.abs(q.y-last.y)<height*1.5)ctx.lineTo(q.x,q.y);else ctx.moveTo(q.x,q.y);
        last=q;
      }
      ctx.stroke();ctx.setLineDash([]);
    }
    function text(content,x,y,color='#c3d5df',align='center'){
      ctx.textAlign=align;ctx.textBaseline='middle';ctx.font='11px system-ui';
      ctx.lineWidth=3;ctx.strokeStyle='rgba(6,15,26,.85)';ctx.strokeText(content,x,y);ctx.fillStyle=color;ctx.fillText(content,x,y);
    }
    function draw(){
      if(disposed)return;
      const current=api.sampleAt(points,selected,cutoff),state=markerState(current,cutoff);
      if(el('observerFollow').checked&&current&&current.elevation>=0){camera.azimuth=current.azimuth;camera.elevation=clamp(current.elevation,0,89);}
      const sun=current?.sun_altitude??-18;
      const sky=ctx.createLinearGradient(0,0,0,height);
      sky.addColorStop(0,sun>=0?'#284c66':sun>-12?'#13233e':'#071221');
      sky.addColorStop(1,sun>=0?'#829b9e':sun>-12?'#665454':'#203847');
      ctx.fillStyle=sky;ctx.fillRect(0,0,width,height);
      const focal=width/(2*Math.tan(camera.fov*RAD/2));
      const horizon=height/2+focal*Math.tan(camera.elevation*RAD);
      ctx.fillStyle='#142326';ctx.fillRect(0,clamp(horizon,0,height),width,height);
      ctx.save();ctx.beginPath();ctx.rect(0,0,width,clamp(horizon,0,height));ctx.clip();
      for(let a=0;a<360;a+=30){const line=[];for(let e=0;e<=90;e+=2)line.push({azimuth:a,elevation:e});lineFrom(line,'rgba(151,187,208,.14)');}
      for(const e of [0,10,20,30,45,60,75]){
        const line=[];for(let a=0;a<=360;a+=2)line.push({azimuth:a,elevation:e});lineFrom(line,'rgba(151,187,208,.18)');
        const q=project(camera.azimuth,e,camera,width,height);if(q&&q.y>54&&q.y<height-22)text(e+'°',width/2,q.y,'#849eae');
      }
      if(cutoff>0||launch.location.horizon_profile?.length){const line=[];for(let a=0;a<=360;a+=1)line.push({azimuth:a,elevation:root.DownrangeV1.horizonLimit(launch.location.horizon_profile,cutoff,a)});lineFrom(line,'#ccb591',[5,5],1.3);}
      if(el('observerGuide').checked){
        for(let i=1;i<points.length;i++){
          const a=points[i-1],b=points[i];if(b.t_s-a.t_s>120)continue;
          const guideColor=a.jellyfish?'#efbd90':a.ordinary?'#86e5cc':'#83929c';
          lineFrom([a,b],guideColor,b.t_s>selected?[3,5]:[],a.ordinary||a.jellyfish?2.2:1.1);
        }
        for(const [title,p] of [['First',plan.first],['Peak',plan.peak],['Last',plan.last]]){
          if(!p)continue;const q=project(p.azimuth,p.elevation,camera,width,height);
          if(q?.inFrame&&q.y>50){ctx.fillStyle='#d4e6e8';ctx.beginPath();ctx.arc(q.x,q.y,2,0,Math.PI*2);ctx.fill();text(title+' '+api.tplus(p.t_s),q.x,q.y+(title==='Peak'?-15:15),'#d0dfdf');}
        }
      }
      let marker=null;
      if(current&&state!=='below_horizon'){
        marker=project(current.azimuth,current.elevation,camera,width,height);
        if(marker?.inFrame){
          const lit=state==='powered'||state==='plume',color=state==='plume'?'#ffd2a6':lit?'#c0ffe8':'#b7c7d3';
          ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();ctx.arc(marker.x,marker.y,7,0,2*Math.PI);ctx.stroke();
          if(lit){ctx.fillStyle=color;ctx.beginPath();ctx.arc(marker.x,marker.y,3,0,2*Math.PI);ctx.fill();}
          for(const [dx,dy] of [[-1,0],[1,0],[0,1],[0,-1]]){ctx.beginPath();ctx.moveTo(marker.x+dx*10,marker.y+dy*10);ctx.lineTo(marker.x+dx*15,marker.y+dy*15);ctx.stroke();}
        }
      }
      ctx.restore();
      if(horizon>=0&&horizon<=height){
        ctx.strokeStyle='#708c8e';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(0,horizon);ctx.lineTo(width,horizon);ctx.stroke();
        text('0° · generic horizon',width-12,clamp(horizon+15,16,height-16),'#b0c4bd','right');
      }
      const bearingBandY=45;
      for(let a=0;a<360;a+=15){
        const q=project(a,camera.elevation,camera,width,height);
        if(q&&q.x>23&&q.x<width-23){
          const important=a%45===0;
          text((important?compass(a)+' ':'')+a+'°',q.x,bearingBandY,important?'#d9e6ef':'#91abbf');
        }
      }
      const outOfView=current&&state!=='below_horizon'&&!marker?.inFrame;
      const explanation=api.phase(current,cutoff)+(outOfView?' · outside this view—pan or use Follow marker':'');
      canvas.dataset.marker=state==='below_horizon'?'hidden-below-horizon':!current?'no-data':marker?.inFrame?'in-view':'offscreen';
      canvas.dataset.time=String(selected);
      el('observerOrientation').textContent=`Facing ${compass(camera.azimuth)} ${Math.round(wrap(camera.azimuth))}° true · tilt ${camera.elevation.toFixed(0)}°`;
      el('observerClock').textContent=api.tplus(selected)+(playing?' · replay':' · model');
      el('observerFov').textContent=Math.round(camera.fov)+'° view';
      const time=launch.time_precise?new Intl.DateTimeFormat(undefined,{hour:'numeric',minute:'2-digit',second:'2-digit',timeZoneName:'short',timeZone:launch.location.timezone}).format(new Date(new Date(launch.net).getTime()+selected*1000)):'Clock time unconfirmed';
      el('observerStatus').textContent=`${api.tplus(selected)} · ${time}${current?' · '+compass(current.azimuth)+' '+current.azimuth.toFixed(0)+'° true · '+current.elevation.toFixed(1)+'° elevation':''}. ${explanation}.`;
      scrub.setAttribute('aria-valuetext',el('observerStatus').textContent);
    }
    function resize(){
      const rect=canvas.getBoundingClientRect();width=Math.max(240,rect.width);height=width<480?310:390;
      canvas.style.height=height+'px';const ratio=Math.min(root.devicePixelRatio||1,3);
      canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);ctx.setTransform(ratio,0,0,ratio,0,0);
      if(autoFrame)camera=framePath(points,width,height);queueDraw();
    }
    function pause(){playing=false;el('observerStatus').setAttribute('aria-live','polite');cancelAnimationFrame(frame);frame=0;lastFrame=0;el('observerPlay').textContent='Play flight';el('observerPlay').setAttribute('aria-pressed','false');queueDraw();}
    function seek(t,external=false){
      if(!Number.isFinite(t))return;
      selected=clamp(Math.round(t),0,end);scrub.value=selected;
      if(!external){updating=true;slider.value=selected;slider.dispatchEvent(new Event('input',{bubbles:true}));updating=false;}
      queueDraw();
    }
    function advance(now){
      if(!playing||disposed)return;
      if(document.hidden){pause();return;}
      if(!lastFrame)lastFrame=now;
      playTime+=Math.min((now-lastFrame)/1000,0.25)*Number(el('observerSpeed').value);lastFrame=now;
      if(Math.floor(playTime)!==lastRendered){lastRendered=Math.floor(playTime);seek(playTime);}
      if(playTime>=end){seek(end);pause();return;}
      frame=requestAnimationFrame(advance);
    }
    el('observerPlay').onclick=()=>{
      if(playing){pause();return;}
      if(selected>=end)seek(0);
      playing=true;el('observerStatus').setAttribute('aria-live','off');playTime=selected;lastFrame=0;lastRendered=-1;el('observerPlay').textContent='Pause';el('observerPlay').setAttribute('aria-pressed','true');frame=requestAnimationFrame(advance);
    };
    scrub.oninput=()=>{pause();seek(Number(scrub.value));};
    el('observerStart').textContent=plan.first?'First window':'Start of track';
    el('observerStart').onclick=()=>{pause();seek(first);};
    el('observerFit').onclick=()=>{autoFrame=true;el('observerFollow').checked=false;camera=framePath(points,width,height);queueDraw();};
    el('observerHorizon').onclick=()=>{autoFrame=false;el('observerFollow').checked=false;camera.elevation=0;queueDraw();};
    const zoom=d=>{autoFrame=false;camera.fov=clamp(camera.fov+d,30,120);queueDraw();};
    el('observerZoomIn').onclick=()=>zoom(-10);el('observerZoomOut').onclick=()=>zoom(10);
    el('observerFollow').onchange=()=>{autoFrame=false;queueDraw();};el('observerGuide').onchange=queueDraw;
    canvas.addEventListener('pointerdown',event=>{if(!event.isPrimary)return;drag={id:event.pointerId,x:event.clientX,y:event.clientY,a:camera.azimuth,e:camera.elevation};autoFrame=false;el('observerFollow').checked=false;canvas.setPointerCapture(event.pointerId);});
    canvas.addEventListener('pointermove',event=>{if(!drag||drag.id!==event.pointerId)return;camera.azimuth=wrap(drag.a-(event.clientX-drag.x)*camera.fov/width);camera.elevation=clamp(drag.e+(event.clientY-drag.y)*camera.fov/width,-15,89);queueDraw();});
    const stopDrag=()=>{drag=null;};canvas.addEventListener('pointerup',stopDrag);canvas.addEventListener('pointercancel',stopDrag);
    canvas.addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-'].includes(event.key))return;
      event.preventDefault();autoFrame=false;el('observerFollow').checked=false;
      if(event.key==='ArrowLeft')camera.azimuth=wrap(camera.azimuth-5);
      if(event.key==='ArrowRight')camera.azimuth=wrap(camera.azimuth+5);
      if(event.key==='ArrowUp')camera.elevation=clamp(camera.elevation+5,-15,89);
      if(event.key==='ArrowDown')camera.elevation=clamp(camera.elevation-5,-15,89);
      if(['+','='].includes(event.key))zoom(-10);if(event.key==='-')zoom(10);queueDraw();
    });
    const sliderObserver=new MutationObserver(()=>{const t=Number(slider.value);if(Math.abs(t-selected)>0.01){pause();seek(t,true);}});
    sliderObserver.observe(slider,{attributes:true,attributeFilter:['aria-valuetext']});
    const onExternalInput=()=>{if(!updating){pause();seek(Number(slider.value),true);}};
    slider.addEventListener('input',onExternalInput);
    const onVisibility=()=>{if(document.hidden)pause();};document.addEventListener('visibilitychange',onVisibility);
    const observer=new ResizeObserver(resize);observer.observe(canvas);resize();
    return ()=>{if(disposed)return;disposed=true;cancelAnimationFrame(frame);cancelAnimationFrame(drawPending);observer.disconnect();sliderObserver.disconnect();slider.removeEventListener('input',onExternalInput);document.removeEventListener('visibilitychange',onVisibility);section.remove();};
  }
  const exports={vector,basis,project,unproject,circularFrame,framePath,markerState,mount};
  if(typeof module!=='undefined'&&module.exports)module.exports=exports;else root.DownrangeObserver=exports;
})(typeof window!=='undefined'?window:globalThis);
