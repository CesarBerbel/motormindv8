// Alternador de tema claro/escuro. A preferência ('mm-theme' = 'light' | 'dark')
// é guardada no localStorage e partilhada entre a área restrita e o site público.
// Cada página define os nomes de tema reais em data-theme-light/data-theme-dark
// no elemento <html>. A aplicação inicial é feita por um script inline no <head>
// (ver as bases) para evitar o flash de tema errado.
(function () {
  var root = document.documentElement;

  function names() {
    return {
      light: root.getAttribute('data-theme-light') || 'light',
      dark: root.getAttribute('data-theme-dark') || 'dark',
    };
  }

  function pref() {
    try {
      return localStorage.getItem('mm-theme') === 'dark' ? 'dark' : 'light';
    } catch (e) {
      return 'light';
    }
  }

  function updateButtons(p) {
    document.querySelectorAll('[data-theme-icon]').forEach(function (el) {
      el.textContent = p === 'dark' ? '☀️' : '🌙';
    });
    document.querySelectorAll('[data-theme-toggle]').forEach(function (el) {
      el.setAttribute('aria-pressed', p === 'dark' ? 'true' : 'false');
      el.setAttribute('title', p === 'dark' ? 'Mudar para tema claro' : 'Mudar para tema escuro');
    });
  }

  function apply(p) {
    var n = names();
    root.setAttribute('data-theme', p === 'dark' ? n.dark : n.light);
    try {
      localStorage.setItem('mm-theme', p);
    } catch (e) {}
    updateButtons(p);
  }

  document.addEventListener('DOMContentLoaded', function () {
    updateButtons(pref());
  });

  document.addEventListener('click', function (event) {
    var btn = event.target.closest('[data-theme-toggle]');
    if (!btn) return;
    event.preventDefault();
    apply(pref() === 'dark' ? 'light' : 'dark');
  });
})();
