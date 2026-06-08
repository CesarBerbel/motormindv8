// Regista o service worker do MotorMind (PWA).
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function (err) {
      console.warn('Falha ao registar o service worker:', err);
    });
  });
}
