(function () {
  const root = document.querySelector('[data-app-notifications]');
  if (!root) return;

  const feedUrl = root.dataset.notificationFeedUrl;
  const readUrlTemplate = root.dataset.notificationReadUrl || '';
  const permissionButton = document.querySelector('[data-notification-permission]');
  const badge = document.querySelector('[data-notification-badge]');
  const notificationBell = document.querySelector('[data-notification-bell]');
  const toastContainerSelector = '[data-toast-container]';
  const pollInterval = Number.parseInt(root.dataset.notificationPollInterval || '45000', 10);
  const pwaConfig = window.MotorMindPWA || {};
  const pwaEnabled = Boolean(pwaConfig.enabled) || document.documentElement.dataset.pwaEnabled === 'true';

  function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function getToastContainer() {
    let container = document.querySelector(toastContainerSelector);
    if (container) return container;
    container = document.createElement('div');
    container.className = 'app-toast-container';
    container.dataset.toastContainer = 'true';
    container.setAttribute('aria-live', 'polite');
    container.setAttribute('aria-atomic', 'true');
    document.body.appendChild(container);
    return container;
  }

  function levelToAlertClass(level) {
    if (level === 'success') return 'alert-success';
    if (level === 'warning') return 'alert-warning';
    if (level === 'error') return 'alert-error';
    return 'alert-info';
  }

  function closeToast(toast) {
    if (!toast || toast.dataset.closing === 'true') return;
    toast.dataset.closing = 'true';
    toast.classList.add('is-hiding');
    window.setTimeout(() => toast.remove(), 220);
  }

  function markRead(id) {
    if (!id || !readUrlTemplate) return Promise.resolve();
    const url = readUrlTemplate.replace('/0/', `/${id}/`);
    return fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCsrfToken(),
        'X-Requested-With': 'XMLHttpRequest'
      }
    }).then((response) => response.ok ? response.json() : null).then((data) => {
      if (data && Number.isFinite(Number(data.unread_count))) {
        updateBadge(Number(data.unread_count));
      }
    }).catch(() => {});
  }

  function showInAppToast(notification) {
    const container = getToastContainer();
    const toast = document.createElement('div');
    toast.className = `alert app-toast shadow-xl ${levelToAlertClass(notification.level)}`;
    toast.dataset.toast = 'true';
    toast.dataset.toastDuration = '12000';
    toast.setAttribute('role', 'alert');

    const url = notification.open_url || notification.url || '#';
    toast.innerHTML = `
      <div class="min-w-0 flex-1">
        <p class="font-semibold">${escapeHtml(notification.title || 'Nova notificação')}</p>
        <p class="mt-0.5 text-sm opacity-85">${escapeHtml(notification.message || '')}</p>
      </div>
      <div class="flex shrink-0 items-center gap-1">
        ${url && url !== '#' ? `<a class="btn btn-ghost btn-xs" href="${escapeHtml(url)}" data-notification-open>Ver</a>` : ''}
        <button type="button" class="btn btn-ghost btn-xs btn-circle" data-toast-close aria-label="Fechar notificação">✕</button>
      </div>
    `;

    const timeoutId = window.setTimeout(() => closeToast(toast), 12000);
    toast.querySelector('[data-toast-close]')?.addEventListener('click', () => {
      window.clearTimeout(timeoutId);
      markRead(notification.id);
      closeToast(toast);
    });
    toast.querySelector('[data-notification-open]')?.addEventListener('click', () => {
      markRead(notification.id);
    });
    container.appendChild(toast);
  }

  function canUseBrowserNotifications() {
    return 'Notification' in window && Notification.permission === 'granted';
  }

  async function showBrowserNotification(notification) {
    if (!canUseBrowserNotifications()) return;

    const options = {
      body: notification.message || '',
      tag: `motormind-notification-${notification.id}`,
      icon: '/static/img/pwa/icon-192.png',
      badge: '/static/img/pwa/icon-192.png',
      data: { url: notification.open_url || notification.url || '/', id: notification.id },
      renotify: false
    };

    try {
      if (pwaEnabled && 'serviceWorker' in navigator) {
        const registration = await Promise.race([
          navigator.serviceWorker.ready,
          new Promise((resolve) => window.setTimeout(() => resolve(null), 1200))
        ]);
        if (registration?.showNotification) {
          await registration.showNotification(notification.title || 'MotorMind', options);
          return;
        }
      }
      const browserNotification = new Notification(notification.title || 'MotorMind', options);
      browserNotification.onclick = function () {
        window.focus();
        if (notification.open_url || notification.url) window.location.href = notification.open_url || notification.url;
        else markRead(notification.id);
      };
    } catch (error) {
      console.warn('Falha ao exibir notificação do navegador:', error);
    }
  }

  function updateBadge(count) {
    if (!badge) return;
    if (count > 0) {
      badge.textContent = count > 99 ? '99+' : String(count);
      badge.classList.remove('hidden');
      if (notificationBell) {
        notificationBell.title = `${count} notificação(ões) não lida(s)`;
        notificationBell.setAttribute('aria-label', `${count} notificação(ões) não lida(s). Abrir central de notificações`);
      }
    } else {
      badge.classList.add('hidden');
      if (notificationBell) {
        notificationBell.title = 'Central de notificações';
        notificationBell.setAttribute('aria-label', 'Abrir central de notificações');
      }
    }
  }

  async function pollNotifications() {
    if (!feedUrl) return;
    try {
      const response = await fetch(feedUrl, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        cache: 'no-store'
      });
      if (!response.ok) return;
      const data = await response.json();
      updateBadge(Number(data.unread_count || 0));
      (data.notifications || []).forEach((notification) => {
        showInAppToast(notification);
        showBrowserNotification(notification);
      });
    } catch (error) {
      console.warn('Falha ao buscar notificações internas:', error);
    }
  }

  function updatePermissionButton() {
    if (!permissionButton) return;
    if (!('Notification' in window)) {
      permissionButton.classList.add('hidden');
      return;
    }
    if (Notification.permission === 'granted') {
      permissionButton.title = 'Notificações do navegador ativadas';
      permissionButton.setAttribute('aria-label', 'Notificações do navegador ativadas');
      permissionButton.querySelector('[data-notification-icon]').textContent = '🔔';
      return;
    }
    if (Notification.permission === 'denied') {
      permissionButton.title = 'Notificações bloqueadas no navegador';
      permissionButton.setAttribute('aria-label', 'Notificações bloqueadas no navegador');
      permissionButton.querySelector('[data-notification-icon]').textContent = '🔕';
      return;
    }
    permissionButton.title = 'Ativar notificações do navegador';
    permissionButton.setAttribute('aria-label', 'Ativar notificações do navegador');
    permissionButton.querySelector('[data-notification-icon]').textContent = '🔔';
  }

  permissionButton?.addEventListener('click', async () => {
    if (!('Notification' in window)) return;
    if (Notification.permission === 'default') {
      await Notification.requestPermission();
    }
    updatePermissionButton();
    pollNotifications();
  });

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', (event) => {
      if (event.data?.type === 'notification-click' && event.data.url) {
        window.location.href = event.data.url;
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    updatePermissionButton();
    pollNotifications();
    window.setInterval(pollNotifications, Number.isFinite(pollInterval) && pollInterval >= 15000 ? pollInterval : 45000);
  });
})();
