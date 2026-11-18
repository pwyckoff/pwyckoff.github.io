// Coast path log: keeps the page and its libraries available offline.
// Only these files are cached. Map tiles and path data are not: the path is
// already stored in the browser, and tiles use the browser's normal cache.
const CACHE = 'coast-path-v2';
// The page is the folder's index.html, reached as /coastal-path/ or /coastal-path/index.html
const BASE = new URL('./', self.location).href;
const PAGE = BASE + 'index.html';
const PAGE_URLS = [BASE, PAGE];
const ASSETS = [
  'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js',
  'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css',
  'https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js',
  new URL('coast-path-icon-192.png', self.location).href
];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.add(new Request(PAGE, { cache: 'reload' }));
    await Promise.all(ASSETS.map(u => cache.add(new Request(u, { mode: 'cors', credentials: 'omit' })).catch(() => {})));
    self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) if (key !== CACHE) await caches.delete(key);
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const url = event.request.url.split('#')[0].split('?')[0];
  if (event.request.method !== 'GET') return;
  // The page: try the network first so updates arrive, fall back to the copy
  if (PAGE_URLS.includes(url)) {
    event.respondWith((async () => {
      try {
        const fresh = await fetch(event.request);
        if (fresh.ok) (await caches.open(CACHE)).put(PAGE, fresh.clone());
        return fresh;
      } catch (e) {
        return (await caches.match(PAGE)) || Response.error();
      }
    })());
    return;
  }
  // Pinned libraries never change, so the cached copy is always right
  if (ASSETS.includes(url)) {
    event.respondWith((async () => (await caches.match(url)) || fetch(event.request))());
  }
});
