(function () {
  const root = document.documentElement;
  const config = window.MotorMindPWA || {};
  const pwaEnabled = config.enabled === true || root.dataset.pwaEnabled === 'true';
  const pwaDebug = config.debug === true || root.dataset.pwaDebug === 'true';
  const serviceWorkerUrl = config.serviceWorkerUrl || '/sw.js';
  const serviceWorkerScope = config.scope || '/';
  const installButton = document.querySelector('[data-pwa-install]');
  const installButtonLabel = installButton?.querySelector('[data-pwa-install-label]');
  const installButtonIcon = installButton?.querySelector('[data-pwa-install-icon]');
  const installDialog = document.querySelector('[data-pwa-install-dialog]');
  const installDialogTitle = installDialog?.querySelector('[data-pwa-install-title]');
  const installDialogStatus = installDialog?.querySelector('[data-pwa-install-status]');
  const installDialogDetails = installDialog?.querySelector('[data-pwa-install-details]');
  let deferredInstallPrompt = null;
  let serviceWorkerRegistration = null;
  let serviceWorkerReady = false;
  let serviceWorkerError = '';

  function debugLog() {
    if (!pwaDebug) return;
    console.info.apply(console, ['MotorMind PWA:'].concat(Array.prototype.slice.call(arguments)));
  }

  function isStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  }

  function isLocalhost() {
    return ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
  }

  function isSecurePwaContext() {
    return window.isSecureContext || isLocalhost();
  }

  function isIOS() {
    return /iphone|ipad|ipod/i.test(window.navigator.userAgent) ||
      (window.navigator.platform === 'MacIntel' && window.navigator.maxTouchPoints > 1);
  }

  function isAndroid() {
    return /android/i.test(window.navigator.userAgent);
  }

  function setInstallButtonState() {
    if (!installButton) return;

    if (!pwaEnabled || isStandalone()) {
      installButton.hidden = true;
      return;
    }

    installButton.hidden = false;
    installButton.disabled = false;
    installButton.classList.toggle('btn-primary', Boolean(deferredInstallPrompt));
    installButton.classList.toggle('btn-outline', !deferredInstallPrompt);

    if (installButtonLabel) {
      installButtonLabel.textContent = deferredInstallPrompt ? 'Instalar app' : 'Como instalar';
    }
    if (installButtonIcon) {
      installButtonIcon.textContent = deferredInstallPrompt ? '⬇️' : '📲';
    }

    if (!isSecurePwaContext()) {
      installButton.title = 'Para instalar o app, acesse por HTTPS ou localhost.';
    } else if (!deferredInstallPrompt) {
      installButton.title = 'Abrir instruções de instalação do app.';
    } else {
      installButton.title = 'Instalar o MotorMind neste dispositivo.';
    }
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
    setInstallButtonState();
    try {
      await unregisterMotorMindServiceWorkers();
      await clearMotorMindCaches();
    } catch (error) {
      console.warn('Falha ao limpar PWA local:', error);
    }
  }

  function getInstallHelpItems() {
    const items = [];

    if (isStandalone()) {
      items.push('O MotorMind já está aberto no modo aplicativo neste dispositivo.');
      return items;
    }

    if (!pwaEnabled) {
      items.push('O PWA está desativado neste ambiente. Em desenvolvimento local, defina PWA_ENABLED=True no arquivo .env para testar a instalação.');
      return items;
    }

    if (!isSecurePwaContext()) {
      items.push('A instalação de PWA exige HTTPS ou localhost. Em tablet/celular usando IP da rede, como http://192.168.x.x:8000, o navegador não libera a instalação.');
      items.push('Para testar localmente no próprio computador, use http://localhost:8000. Para testar em tablet/celular, use HTTPS.');
      return items;
    }

    if (!('serviceWorker' in navigator)) {
      items.push('Este navegador não oferece suporte completo a service worker, então não libera instalação automática do app.');
    }

    if (serviceWorkerError) {
      items.push(serviceWorkerError);
    } else if (!serviceWorkerReady && 'serviceWorker' in navigator) {
      items.push('O service worker ainda está inicializando. Aguarde alguns segundos e atualize a página.');
    }

    if (isIOS()) {
      items.push('No iPhone/iPad, toque no botão Compartilhar do Safari e escolha “Adicionar à Tela de Início”. O iOS não exibe o instalador automático do navegador.');
    } else if (isAndroid()) {
      items.push('No Android, use o Chrome/Edge e toque no menu ⋮ do navegador. Depois escolha “Instalar app” ou “Adicionar à tela inicial”.');
    } else {
      items.push('No Chrome ou Edge para desktop, use o ícone de instalação na barra de endereço ou o menu do navegador e escolha “Instalar MotorMind”.');
    }

    if (!deferredInstallPrompt) {
      items.push('Se o botão automático ainda não aparecer, confira se o app não já está instalado e se o navegador não bloqueou a instalação após uma tentativa recusada.');
    }

    return items;
  }

  function openInstallHelp() {
    const title = deferredInstallPrompt ? 'Instalar MotorMind' : 'Como instalar o MotorMind';
    const status = deferredInstallPrompt
      ? 'O navegador liberou a instalação automática. Clique novamente em “Instalar app” para abrir o instalador.'
      : 'A instalação automática ainda não está disponível neste navegador/ambiente. Use as instruções abaixo.';
    const items = getInstallHelpItems();

    if (installDialogTitle) installDialogTitle.textContent = title;
    if (installDialogStatus) installDialogStatus.textContent = status;
    if (installDialogDetails) {
      installDialogDetails.innerHTML = '';
      items.forEach(function (text) {
        const item = document.createElement('li');
        item.textContent = text;
        installDialogDetails.appendChild(item);
      });
    }

    if (installDialog && typeof installDialog.showModal === 'function') {
      installDialog.showModal();
      return;
    }

    window.alert([status].concat(items).join('\n\n'));
  }

  window.addEventListener('beforeinstallprompt', function (event) {
    event.preventDefault();
    deferredInstallPrompt = event;
    debugLog('beforeinstallprompt recebido');
    setInstallButtonState();
  });

  window.addEventListener('appinstalled', function () {
    deferredInstallPrompt = null;
    debugLog('app instalado');
    setInstallButtonState();
  });

  if (installButton) {
    installButton.addEventListener('click', async function () {
      if (!pwaEnabled || isStandalone()) {
        setInstallButtonState();
        return;
      }

      if (!deferredInstallPrompt) {
        openInstallHelp();
        return;
      }

      installButton.disabled = true;
      if (installButtonLabel) installButtonLabel.textContent = 'Abrindo...';

      try {
        deferredInstallPrompt.prompt();
        const choice = await deferredInstallPrompt.userChoice;
        debugLog('resultado da instalação', choice && choice.outcome);
      } catch (error) {
        console.warn('Falha ao abrir instalador do PWA:', error);
        openInstallHelp();
      } finally {
        deferredInstallPrompt = null;
        installButton.disabled = false;
        setInstallButtonState();
      }
    });
  }

  async function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) {
      serviceWorkerError = 'O navegador atual não suporta service worker.';
      setInstallButtonState();
      return;
    }

    if (!isSecurePwaContext()) {
      serviceWorkerError = 'O service worker só pode ser registrado em HTTPS ou localhost.';
      setInstallButtonState();
      console.info('MotorMind PWA indisponível: acesse por HTTPS ou localhost para instalar o app.');
      return;
    }

    try {
      serviceWorkerRegistration = await navigator.serviceWorker.register(serviceWorkerUrl, { scope: serviceWorkerScope });
      debugLog('service worker registrado', serviceWorkerRegistration.scope);

      if (serviceWorkerRegistration.waiting) {
        serviceWorkerRegistration.waiting.postMessage({ type: 'SKIP_WAITING' });
      }

      serviceWorkerRegistration.addEventListener('updatefound', function () {
        const installingWorker = serviceWorkerRegistration.installing;
        if (!installingWorker) return;
        installingWorker.addEventListener('statechange', function () {
          debugLog('service worker state', installingWorker.state);
        });
      });

      await navigator.serviceWorker.ready;
      serviceWorkerReady = true;
      serviceWorkerError = '';
      setInstallButtonState();
    } catch (error) {
      serviceWorkerError = 'Falha ao registrar o service worker. Atualize a página e tente novamente.';
      console.warn('Falha ao registrar o service worker:', error);
      setInstallButtonState();
    }
  }

  if (!pwaEnabled) {
    window.addEventListener('load', disableLocalPwa);
    setInstallButtonState();
    return;
  }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', function (event) {
      if (event.data && event.data.type === 'notification-click' && event.data.url) {
        window.location.href = event.data.url;
      }
      if (event.data && event.data.type === 'service-worker-ready') {
        debugLog('service worker pronto');
      }
    });
  }

  window.addEventListener('load', registerServiceWorker);
  setInstallButtonState();
})();
