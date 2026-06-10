{% if not pwa_enabled %}
/* PWA desabilitado neste ambiente. Em desenvolvimento este service worker
   remove registros/cache antigos para evitar CSS/JS obsoletos no runserver. */
self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.indexOf('motormind-') === 0)
          .map((key) => caches.delete(key))
      ))
      .then(() => self.registration.unregister())
      .then(() => self.clients.matchAll({ type: 'window', includeUncontrolled: true }))
      .then((clients) => clients.forEach((client) => client.navigate(client.url)))
  );
});
{% else %}
/* Service worker do MotorMind (PWA).
   Mantem assets estaticos em cache e evita cachear paginas autenticadas.
   Quando o usuario estiver sem conexao em uma navegacao, mostra uma resposta
   simples em vez de expor dados antigos de OS, clientes ou financeiro. */
const STATIC_CACHE = '{{ pwa_cache_prefix|default:"motormind" }}-static-v3';
const RUNTIME_CACHE = '{{ pwa_cache_prefix|default:"motormind" }}-runtime-v3';
const PRECACHE_URLS = [
  '/static/manifest.webmanifest',
  '/static/css/styles.css',
  '/static/js/pwa.js',
  '/static/js/menu.js',
  '/static/js/toasts.js',
  '/static/js/theme-toggle.js',
  '/static/img/pwa/icon-192.png',
  '/static/img/pwa/icon-512.png',
  '/static/img/pwa/icon-maskable-512.png',
  '/static/img/pwa/apple-touch-icon.png'
];

function offlineResponse() {
  return new Response(`<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#1f2937">
  <title>MotorMind offline</title>
  <style>
    :root{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#172033;background:#eef2f7;}
    body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;}
    main{max-width:460px;border:1px solid rgba(15,23,42,.12);border-radius:24px;background:#fff;padding:28px;box-shadow:0 18px 60px rgba(15,23,42,.12);}
    h1{margin:0;font-size:1.5rem;} p{line-height:1.55;color:#526071;} button{margin-top:12px;border:0;border-radius:999px;background:#1f2937;color:white;padding:12px 18px;font-weight:700;}
  </style>
</head>
<body>
  <main>
    <h1>Sem conexao com o MotorMind</h1>
    <p>Esta area precisa de internet para carregar dados atualizados da oficina. Confira sua conexao e tente novamente.</p>
    <button onclick="location.reload()">Tentar novamente</button>
  </main>
</body>
</html>`, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store'
    }
  });
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .catch(() => null)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.indexOf('{{ pwa_cache_prefix|default:"motormind" }}-') === 0 && ![STATIC_CACHE, RUNTIME_CACHE].includes(key))
          .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (req.mode === 'navigate') {
    event.respondWith(fetch(req).catch(() => offlineResponse()));
    return;
  }

  if (!url.pathname.startsWith('/static/')) return;

  event.respondWith(
    caches.open(RUNTIME_CACHE).then(async (cache) => {
      const cached = await cache.match(req);
      const networkFetch = fetch(req).then((res) => {
        if (res && res.ok) cache.put(req, res.clone());
        return res;
      }).catch(() => cached);
      return cached || networkFetch;
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = event.notification.data && event.notification.data.url ? event.notification.data.url : '/dashboard/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) {
          client.postMessage({ type: 'notification-click', url: targetUrl });
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
      return null;
    })
  );
});

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (error) {
    payload = { title: 'MotorMind', message: event.data ? event.data.text() : '' };
  }

  const title = payload.title || 'MotorMind';
  const options = {
    body: payload.message || payload.body || '',
    icon: '/static/img/pwa/icon-192.png',
    badge: '/static/img/pwa/icon-192.png',
    data: { url: payload.url || '/dashboard/' },
    tag: payload.tag || 'motormind-push'
  };

  event.waitUntil(self.registration.showNotification(title, options));
});
{% endif %}
