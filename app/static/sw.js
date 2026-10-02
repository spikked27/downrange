'use strict';
const VERSION='1.0.0-alpha.1';
const CACHE='downrange-shell-'+VERSION;
const PATHS=['/','/static/styles.css','/static/viewing.css','/static/v1.css','/static/observer.css',
  '/static/app.js','/static/timeline.js','/static/v1-ui.js','/static/observer.js','/static/sources-ui.js',
  '/static/icon.svg','/static/icon-192.png','/static/icon-512.png','/manifest.webmanifest'];
const cacheKey=path=>path==='/'?'/':path+'?v='+VERSION;
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(PATHS.map(cacheKey))).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('downrange-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
  const u=new URL(event.request.url);
  // Private API data is never cached. Navigation parameters do not create more cached shells.
  if(event.request.method!=='GET'||u.origin!==self.location.origin||!PATHS.includes(u.pathname))return;
  const key=cacheKey(u.pathname);
  event.respondWith(fetch(event.request,{cache:'no-cache'}).then(response=>{
    if(response.ok){const copy=response.clone();event.waitUntil(caches.open(CACHE).then(c=>c.put(key,copy)));}
    return response;
  }).catch(()=>caches.open(CACHE).then(c=>c.match(key)).then(r=>r||Response.error())));
});
self.addEventListener('push',event=>{
  let data={title:'Downrange',body:'Open Downrange for an update.',url:'/'};
  try{if(event.data)data={...data,...event.data.json()};}catch{}
  event.waitUntil(self.registration.showNotification(String(data.title).slice(0,150),{
    body:String(data.body).slice(0,1000),icon:'/static/icon-192.png',badge:'/static/icon-192.png',
    tag:String(data.tag||'downrange'),data:{url:typeof data.url==='string'&&data.url.startsWith('/?')?data.url:'/'},renotify:false}));
});
self.addEventListener('notificationclick',event=>{
  event.notification.close();const requested=new URL(event.notification.data?.url||'/',self.location.origin);
  const target=requested.origin===self.location.origin&&requested.pathname==='/'?requested.href:new URL('/',self.location.origin).href;
  event.waitUntil(self.clients.matchAll({type:'window',includeUncontrolled:true}).then(windows=>{
    const found=windows.find(w=>new URL(w.url).origin===self.location.origin);
    if(found)return found.navigate(target).then(()=>found.focus());return self.clients.openWindow(target);
  }));
});
