const CACHE_NAME = 'courier-tracker-v2';
const ASSETS_TO_CACHE = [
  '/',
  '/static/css/main.css',
  '/static/logo.png',
  '/static/delivery_truck.png'
];

// Install Event
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('Opened cache');
      return cache.addAll(ASSETS_TO_CACHE);
    }).catch(err => console.warn('Cache opening failed:', err))
  );
  self.skipWaiting();
});

// Activate Event
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cache => {
          if (cache !== CACHE_NAME) {
            console.log('Clearing old cache:', cache);
            return caches.delete(cache);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch Event (Network-first fallback to Cache)
self.addEventListener('fetch', event => {
  // Only cache GET requests
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  if (url.pathname.includes('/socket.io/')) return;
  // Bypass cache for dynamic pages
  if (url.pathname.startsWith('/dispatch') || url.pathname.startsWith('/scan') || url.pathname.startsWith('/dashboard') || url.pathname.startsWith('/admin') || url.pathname.startsWith('/api')) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then(response => {
        // If valid response, clone and update cache
        if (response && response.status === 200 && response.type === 'basic') {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseToCache);
          });
        }
        return response;
      })
      .catch(async () => {
        // If offline / server down, return from cache if available
        try {
          const cached = await caches.match(event.request);
          if (cached) return cached;
        } catch (e) {}

        if (event.request.mode === 'navigate') {
          return new Response(
            '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Connection Error</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{background:#0a0f1e;color:#e8eaf6;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center}.box{background:rgba(255,255,255,0.05);padding:32px;border-radius:16px;border:1px solid rgba(255,255,255,0.1);max-width:400px}button{background:#4f8ef7;border:none;color:#fff;padding:10px 20px;border-radius:8px;cursor:pointer;margin-top:16px;font-weight:600}</style></head><body><div class="box"><h2>Connection Notice</h2><p style="color:#94a3b8">The server took too long to respond or network was interrupted.</p><button onclick="location.reload()">Retry Connection</button></div></body></html>',
            { headers: { 'Content-Type': 'text/html; charset=utf-8' }, status: 503 }
          );
        }
        return new Response('', { status: 503, statusText: 'Service Unavailable' });
      })
  );
});
