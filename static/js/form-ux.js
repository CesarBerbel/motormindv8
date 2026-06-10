(function () {
  function storageKey(form, field) {
    var id = form.getAttribute('data-form-autosave-id') || window.location.pathname;
    return 'motormind:form-draft:' + id + ':' + (field.name || field.id || 'field');
  }

  function isAutosavable(field) {
    if (!field.name || field.disabled || field.readOnly) return false;
    if (field.type === 'hidden' || field.type === 'password' || field.type === 'file') return false;
    return field.matches('textarea, input[type="text"], input[type="search"], input[type="email"], input[type="tel"], input[type="number"], input[type="url"]');
  }

  function showDraftBadge(form) {
    var badge = form.querySelector('[data-form-draft-badge]');
    if (badge) badge.classList.remove('hidden');
  }

  function hideDraftBadge(form) {
    var badge = form.querySelector('[data-form-draft-badge]');
    if (badge) badge.classList.add('hidden');
  }

  function escapeCss(value) {
    if (window.CSS && typeof window.CSS.escape === 'function') return window.CSS.escape(value);
    return String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  }

  function setupAutosave(form) {
    if (!form.hasAttribute('data-form-autosave')) return;
    var fields = Array.prototype.slice.call(form.elements).filter(isAutosavable);
    var restored = false;

    fields.forEach(function (field) {
      var key = storageKey(form, field);
      try {
        var saved = localStorage.getItem(key);
        if (saved && !field.value) {
          field.value = saved;
          restored = true;
        }
      } catch (e) {}

      field.addEventListener('input', function () {
        try {
          if (field.value) localStorage.setItem(key, field.value);
          else localStorage.removeItem(key);
        } catch (e) {}
        showDraftBadge(form);
      });
    });

    if (restored) showDraftBadge(form);

    form.addEventListener('submit', function () {
      fields.forEach(function (field) {
        try { localStorage.removeItem(storageKey(form, field)); } catch (e) {}
      });
      hideDraftBadge(form);
    });

    var clearButton = form.querySelector('[data-form-clear-draft]');
    if (clearButton) {
      clearButton.addEventListener('click', function () {
        fields.forEach(function (field) {
          try { localStorage.removeItem(storageKey(form, field)); } catch (e) {}
        });
        hideDraftBadge(form);
      });
    }
  }

  function setupDirtyGuard(form) {
    if (!form.hasAttribute('data-form-dirty-guard')) return;
    var dirty = false;
    var submitted = false;

    form.addEventListener('input', function () { dirty = true; });
    form.addEventListener('change', function () { dirty = true; });
    form.addEventListener('submit', function () { submitted = true; dirty = false; });

    window.addEventListener('beforeunload', function (event) {
      if (!dirty || submitted) return;
      event.preventDefault();
      event.returnValue = '';
    });
  }

  function setupMobileProgress(form) {
    var required = Array.prototype.slice.call(form.querySelectorAll('[required]'));
    if (!required.length) return;
    var meter = form.querySelector('[data-form-progress]');
    var label = form.querySelector('[data-form-progress-label]');
    if (!meter && !label) return;

    function update() {
      var filled = required.filter(function (field) {
        if (field.type === 'checkbox' || field.type === 'radio') {
          return form.querySelector('[name="' + escapeCss(field.name) + '"]:checked');
        }
        return (field.value || '').trim() !== '';
      }).length;
      var percent = Math.round((filled / required.length) * 100);
      if (meter) meter.value = percent;
      if (label) label.textContent = filled + '/' + required.length + ' obrigatórios';
    }
    form.addEventListener('input', update);
    form.addEventListener('change', update);
    update();
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('form[data-ux-form]').forEach(function (form) {
      setupAutosave(form);
      setupDirtyGuard(form);
      setupMobileProgress(form);
    });
  });
})();
