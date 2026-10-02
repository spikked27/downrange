'use strict';
// Keep acquisition/provenance presentation separate from the basic app shell.
// state, esc and fmt are supplied by app.js; only escaped source text is inserted.
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
    Last acquisition: ${esc(fmt(p.source_checked))}</p>
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
