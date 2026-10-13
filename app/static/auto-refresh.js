/* Refresh only the selected launch; don't turn scheduled time into live telemetry. */
(function(){
'use strict';
const dialog=document.querySelector('#detailDialog'),content=document.querySelector('#detailContent');
let active=false,nextCheck=0,latestError='',notice='',pending=null;
function capture(){
return {time:Number(document.querySelector('#timeSlider')?.value||0),
 zoom:document.querySelector('#focusTimeline')?.getAttribute('aria-pressed')==='true',
 observer:document.querySelector('#observerView')?.downrangeCapture?.(),
 scroll:dialog.scrollTop,
 expanded:[...content.querySelectorAll('details[open]')].map(e=>e.id||e.className)};
}
function restore(saved){
if(saved.zoom)document.querySelector('#focusTimeline:not([disabled])')?.click();
const slider=document.querySelector('#timeSlider');
if(slider){slider.value=Math.min(Number(slider.max),Math.max(Number(slider.min),saved.time));slider.dispatchEvent(new Event('input',{bubbles:true}));}
for(const d of content.querySelectorAll('details'))if(saved.expanded.includes(d.id||d.className))d.open=true;
const obs=document.querySelector('#observerView');
if(obs?.downrangeRestore)obs.downrangeRestore(saved.observer);
else pending={launch:state.detail?.id,observer:saved.observer};
requestAnimationFrame(()=>{dialog.scrollTop=saved.scroll});
}
document.addEventListener('downrange:observer-mounted',()=>{
if(pending?.launch===state.detail?.id)document.querySelector('#observerView')?.downrangeRestore?.(pending.observer);
pending=null;
});
function status(){
if(!dialog.open||!state.detail)return;
let node=document.querySelector('#refreshStatus');
if(!node){node=document.createElement('section');node.id='refreshStatus';node.className='refresh-status';content.prepend(node);}
const f=state.detail.freshness||{},age=f.schedule_fetched_at?Date.now()/1000-f.schedule_fetched_at:Infinity;
const concern=Boolean(latestError||f.verification_pending||!f.schedule_fresh||!['go','tbc'].includes(String(state.detail.status).toLowerCase()));
node.classList.toggle('warning',concern);
const fmtStamp=v=>v?esc(fmt(v)):'Not available';
node.innerHTML='<strong>'+esc(latestError|| (f.verification_pending?'Launch missing from latest schedule: verification pending':concern?'Schedule stale or launch not Go/TBC; forecast unverified':'Automatic refresh active · forecast based on scheduled liftoff'))+'</strong>'+
(notice?'<p>'+esc(notice)+'</p>':'')+
'<p class="small">Schedule fetched: '+fmtStamp(f.schedule_fetched_at)+' · next attempt: '+fmtStamp(f.schedule_next_check)+'</p>'+
'<p class="small">Trajectory evidence fetched: '+fmtStamp(f.source_fetched_at)+' · last research: '+fmtStamp(f.source_last_attempt)+'</p>'+
'<p class="small">Prediction calculated: '+fmtStamp(f.prediction_calculated_at)+'</p>'+
'<button id="recheckOpen" type="button" class="text-button">Check server snapshot ↻</button>';
node.querySelector('#recheckOpen').onclick=()=>poll(true);
}
async function poll(force=false){
if(active||document.hidden||!dialog.open||!state.detail||(!force&&Date.now()<nextCheck))return;
const target={id:state.detail.id,location:state.location?.id,generation:state.detailGeneration};
if(content.querySelector('.detail-admin[open]'))return; // Never discard unsaved trajectory edits.
active=true;nextCheck=Date.now()+30000;
try{
 const next=await api('/launches/'+encodeURIComponent(target.id)+'?location_id='+encodeURIComponent(target.location));
 if(!dialog.open||target.generation!==state.detailGeneration||state.detail?.id!==target.id||state.location?.id!==target.location)return;
 latestError='';
 if(next.freshness?.revision!==state.detail.freshness?.revision){
   const saved=capture();
   if(document.querySelector('#observerPlay')?.getAttribute('aria-pressed')==='true')document.querySelector('#observerPlay').click();
   notice=next.net!==state.detail.net?'Scheduled liftoff moved. Updated geometry; playback paused.':next.status!==state.detail.status?'Launch status changed; playback paused.':'Trajectory or viewing conditions changed; updated predicted path.';
   await openDetail(target.id,{snapshot:next,refresh:true});
   if(dialog.open&&state.detail?.id===target.id)restore(saved);
 }else{state.detail.freshness=next.freshness;state.detail.prediction.quality=next.prediction.quality;}
 status();
}catch(e){if(dialog.open&&target.generation===state.detailGeneration){latestError='Refresh failed; previous prediction retained. Retrying.';status();}}
finally{active=false;}
}
document.addEventListener('downrange:detail-ready',e=>{if(!e.detail?.refresh){notice='';latestError='';pending=null;}nextCheck=Date.now()+30000;status();});
dialog.addEventListener('close',()=>{pending=null;notice='';latestError='';nextCheck=0;});
document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll(true)});
window.addEventListener('online',()=>poll(true));
setInterval(()=>poll(false),1000);
})();