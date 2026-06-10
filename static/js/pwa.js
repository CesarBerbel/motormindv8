(function () {
  const root = document.documentElement;
  const config = window.MotorMindPWA || {};
  const pwaEnabled = Boolean(config.enabled) || root.dataset.pwaEnabled === 'true';
  const serviceWorkerUrl = config.serviceWorkerUrl || '/sw.js';
  const serviceWorkerScope = config.scope || '/';
  const installButton = document.querySelector('[data-pwa-install]');
  let deferredInstallPrompt = null;

  function isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  }

  function isSecurePwaContext() {
    return window.isSecureContext || ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
  }

  function updateInstallButton() {
    if (!installButton) return;
    installButton.hidden = !pwaEnabled || !deferredInstallPrompt || isStandalone();
  }

  async function clearMotorMindCaches() {
    if (!('caches' in window)) return;
    const keys = await caches.keys();
    await Promise.all(
      keys
        .filter(function (key) { return key.indexOf('motormind-') === 0; })
        .map(function (key) { return caches.delete(key); })
    );
  }

  async function unregisterMotorMindServiceWorkers() {
    if (!('serviceWorker' in navigator)) return;
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(
      registrations
        .filter(function (registration) {
          const activeScript = registration.active && registration.active.scriptURL;
          const installingScript = registration.installing && registration.installing.scriptURL;
          const waitingScript = registration.waiting && registration.waiting.scriptURL;
          return [activeScript, installingScript, waitingScript].some(function (scriptUrl) {
            return scriptUrl && scriptUrl.indexOf('/sw.js') !== -1;
          });
        })
        .map(function (registration) { return registration.unregister(); })
    );
  }

  async function disableLocalPwa() {
    updateInstallButton();
    try {
      await unregisterMotorMindServiceWorkers();
      await clearMotorMindCaches();
    } catch (error) {
      console.warn('Falha ao limpar PWA local:', error);
    }
  }

  if (!pwaEnabled) {
    window.addEventListener('load', disableLocalPwa);
    updateInstallButton();
    return;
  }

  if ('serviceWorker' in navigator && isSecurePwaContext()) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register(serviceWorkerUrl, { scope: serviceWorkerScope }).catch(function (err) {
        console.warn('Falha ao registrar o service worker:', err);
      });
    });

    navigator.serviceWorker.addEventListener('message', function (event) {
      if (event.data && event.data.type === 'notification-click' && event.data.url) {
        window.location.href = event.data.url;
      }
      if (event.data && event.data.type === 'service-worker-ready') {
        console.info('MotorMind PWA pronto para uso.');
      }
    });
  } else if (!isSecurePwaContext()) {
    console.info('MotorMind PWA indisponível: acesse por HTTPS ou localhost para instalar o app.');
  }

  window.addEventListener('beforeinstallprompt', function (event) {
    event.preventDefault();
    deferredInstallPrompt = event;
    updateInstallButton();
  });

  installButton?.addEventListener('click', async function () {
    if (!deferredInstallPrompt) return;
    installButton.disabled = true;
    try {
      deferredInstallPrompt.prompt();
      await deferredInstallPrompt.userChoice;
    } finally {
      deferredInstallPrompt = null;
      installButton.disabled = false;
      updateInstallButton();
    }
  });

  window.addEventListener('appinstalled', function () {
    deferredInstallPrompt = null;
    updateInstallButton();
  });

  updateInstallButton();
})();
