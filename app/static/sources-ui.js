'use strict';
// Acquisition evidence and observer perspective extend the basic app without
// changing its prediction, credentials, locations, or notification settings.
const sourceDetail = document.querySelector('#detailContent');
function renderSourceEvidence() {
  const p = state.detail?.prediction;
  if (!p?.automatic || !sourceDetail.children.length || sourceDetail.querySelector('#sourceEvidence')) return;
  const section = document.createElement('section');
  section.id = 'sourceEvidence';
  section.className = 'panel top-gap';
  const safeLink = (url, text) => {
    try {
      const parsed = new URL(url);
      if (parsed.protocol === 'https:' && !parsed.username && !parsed.password) {
        return `<a href="${esc(parsed.href)}" target="_blank" rel="noopener noreferrer">${esc(text)}</a>`;
      }
    } catch {}
    return esc(text);
  };
  section.innerHTML = `<h3>Automatic source evidence</h3>
    <p class="small"><strong>${esc(p.evidence_level || 'estimated')}</strong><br>
    Last research attempt: ${esc(fmt(p.source_checked))}</p>
    ${(p.source_evidence || []).map(e => `<p class="small">${safeLink(e.url, e.source)} · ${Number(e.heading_deg).toFixed(1)}° departure heading<br>${esc(e.note)}</p>`).join('')}
    ${(p.historical_analogues || []).map(h => `<p class="small">Historical ascent: ${safeLink(h.url, h.name)}. This is a different flight, used as an analogue.</p>`).join('')}
    ${!p.source_evidence?.length ? '<p class="small">No matched published departure direction yet. Orbital/site assumptions or a broad envelope are in use.</p>' : ''}
    <p class="small">Departure headings are not the direction to look from your location. Weather and actual brightness are separate from this geometric estimate.</p>`;
  sourceDetail.appendChild(section);
}
new MutationObserver(renderSourceEvidence).observe(sourceDetail, { childList: true });

if ('serviceWorker' in navigator) {
  let hadController = Boolean(navigator.serviceWorker.controller);
  let reloading = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (hadController && !reloading) { reloading = true; window.location.reload(); }
    hadController = true;
  });
}
const launchCards = document.querySelector('#launchCards');
new MutationObserver(() => {
  launchCards.querySelectorAll('[data-launch]').forEach(button => {
    const launch = state.launches.find(item => item.id === button.dataset.launch);
    const prediction = launch?.prediction;
    if (!prediction?.automatic || launch.demo) return;
    const card = button.closest('.launch-card');
    const badge = card.querySelector('.tag');
    badge.textContent = prediction.confidence === 'mission-specific' ? 'SOURCED SIMULATION'
      : prediction.low_information ? 'BROAD ESTIMATE' : 'AUTO ESTIMATE';
    card.querySelector('.card-footer > span').textContent = prediction.low_information
      ? 'Low-information estimate' : 'Source details in brief';
  });
}).observe(launchCards, { childList: true });

const OBSERVER_ASSET_VERSION='1.0.0-alpha.1';
let observerAssets,observerCleanup,observerSlider,pendingObserverSlider,observerGeneration=0;
function loadObserverAssets(){
  if(observerAssets)return observerAssets;
  observerAssets=Promise.all([
    new Promise((resolve,reject)=>{
      const link=document.createElement('link');link.rel='stylesheet';link.href='/static/observer.css?v='+OBSERVER_ASSET_VERSION;
      link.onload=resolve;link.onerror=()=>reject(new Error('Sky-view stylesheet could not load. Refresh the page.'));document.head.appendChild(link);
    }),
    new Promise((resolve,reject)=>{
      const script=document.createElement('script');script.src='/static/observer.js?v='+OBSERVER_ASSET_VERSION;
      script.onload=resolve;script.onerror=()=>reject(new Error('Sky-view renderer could not load. Refresh the page.'));document.head.appendChild(script);
    })
  ]);
  return observerAssets;
}
function disposeObserver(){
  observerGeneration++;observerCleanup?.();observerCleanup=null;observerSlider=null;pendingObserverSlider=null;
}
function renderObserver(){
  const slider=sourceDetail.querySelector('#timeSlider');
  if(slider&&(slider===observerSlider||slider===pendingObserverSlider))return;
  disposeObserver();
  const launch=state.detail;
  if(!slider||!launch?.prediction?.points?.length||!document.querySelector('#detailDialog').open)return;
  const ticket=observerGeneration;pendingObserverSlider=slider;
  loadObserverAssets().then(()=>{
    if(ticket!==observerGeneration||!slider.isConnected||state.detail!==launch)return;
    pendingObserverSlider=null;observerSlider=slider;
    observerCleanup=window.DownrangeObserver.mount(sourceDetail,launch,slider);
  }).catch(error=>{
    if(ticket!==observerGeneration||!slider.isConnected)return;
    pendingObserverSlider=null;observerSlider=slider;
    const notice=document.createElement('p');notice.className='notice observer-load-error';notice.textContent=error.message;
    sourceDetail.prepend(notice);
  });
}
new MutationObserver(renderObserver).observe(sourceDetail,{childList:true});
document.querySelector('#detailDialog').addEventListener('close',disposeObserver);
