const CACHE = 'portfolio-v2';
const FILES = ['/trade/dashboard.html', '/trade/app.html', '/trade/manifest.json', '/trade/'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  // HTML 导航: network-first — 保证看到当天最新净值, 断网才回退缓存
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req).then(resp => {
        const clone = resp.clone();
        caches.open(CACHE).then(c => c.put(req, clone));
        return resp;
      }).catch(() => caches.match(req).then(r => r || caches.match('/trade/')))
    );
    return;
  }
  // 其余: stale-while-revalidate
  e.respondWith(
    caches.match(req).then(cached => {
      const network = fetch(req).then(resp => {
        if (resp && resp.ok) {
          const clone = resp.clone();
          caches.open(CACHE).then(c => c.put(req, clone));
        }
        return resp;
      }).catch(() => cached);
      return cached || network;
    })
  );
});
