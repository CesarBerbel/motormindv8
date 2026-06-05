(function () {
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

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-toast]').forEach(setupToast);
  });
})();
