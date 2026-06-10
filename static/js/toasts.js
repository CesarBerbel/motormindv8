(function () {
  function updateToastOffset() {
    var navbar = document.querySelector('[data-main-navbar], header.navbar');
    if (!navbar) {
      document.documentElement.style.removeProperty('--app-navbar-height');
      return;
    }

    var height = Math.ceil(navbar.getBoundingClientRect().height || 0);
    if (height > 0) {
      document.documentElement.style.setProperty('--app-navbar-height', height + 'px');
    }
  }

  function closeToast(toast) {
    if (!toast || toast.dataset.closing === 'true') {
      return;
    }

    toast.dataset.closing = 'true';
    toast.classList.add('is-hiding');

    window.setTimeout(function () {
      toast.remove();
    }, 220);
  }

  function setupToast(toast) {
    if (!toast || toast.dataset.toastReady === 'true') {
      return;
    }

    toast.dataset.toastReady = 'true';

    var duration = Number.parseInt(toast.dataset.toastDuration || '5000', 10);
    if (!Number.isFinite(duration) || duration <= 0) {
      duration = 5000;
    }

    var timeoutId = window.setTimeout(function () {
      closeToast(toast);
    }, duration);

    toast.querySelectorAll('[data-toast-close]').forEach(function (button) {
      button.addEventListener('click', function () {
        window.clearTimeout(timeoutId);
        closeToast(toast);
      });
    });
  }

  function initToasts() {
    updateToastOffset();
    document.querySelectorAll('[data-toast]').forEach(setupToast);
  }

  document.addEventListener('DOMContentLoaded', initToasts);
  window.addEventListener('resize', updateToastOffset);
  window.addEventListener('orientationchange', updateToastOffset);
})();
