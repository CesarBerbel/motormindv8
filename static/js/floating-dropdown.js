(function () {
  const ROOT_SELECTOR = '[data-floating-dropdown]';
  const GAP = 6;
  let activeRoot = null;

  function getTrigger(root) {
    return root.querySelector('button, summary, [data-dropdown-trigger], [tabindex]');
  }

  function getMenu(root) {
    return root.querySelector('.dropdown-content');
  }

  function resetMenu(menu) {
    menu.style.position = '';
    menu.style.left = '';
    menu.style.top = '';
    menu.style.right = '';
    menu.style.bottom = '';
    menu.style.marginTop = '';
    menu.style.marginBottom = '';
    menu.style.zIndex = '';
  }

  function closeDropdown() {
    if (!activeRoot) return;
    const menu = getMenu(activeRoot);
    activeRoot.classList.remove('dropdown-open');
    activeRoot.removeAttribute('data-floating-dropdown-open');
    if (menu) resetMenu(menu);
    activeRoot = null;
  }

  function positionDropdown(root) {
    const trigger = getTrigger(root);
    const menu = getMenu(root);
    if (!trigger || !menu) return;

    menu.style.position = 'fixed';
    menu.style.right = 'auto';
    menu.style.bottom = 'auto';
    menu.style.marginTop = '0';
    menu.style.marginBottom = '0';
    menu.style.zIndex = '1000';

    const triggerRect = trigger.getBoundingClientRect();
    const menuRect = menu.getBoundingClientRect();
    const viewportPadding = 8;
    const width = menuRect.width || menu.offsetWidth || 192;
    const height = menuRect.height || menu.offsetHeight || 180;

    let left = triggerRect.right - width;
    left = Math.max(viewportPadding, Math.min(left, window.innerWidth - width - viewportPadding));

    let top = triggerRect.bottom + GAP;
    if (top + height > window.innerHeight - viewportPadding) {
      top = triggerRect.top - height - GAP;
    }
    top = Math.max(viewportPadding, Math.min(top, window.innerHeight - height - viewportPadding));

    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
  }

  function openDropdown(root) {
    if (activeRoot && activeRoot !== root) closeDropdown();
    activeRoot = root;
    root.classList.add('dropdown-open');
    root.setAttribute('data-floating-dropdown-open', 'true');
    positionDropdown(root);
  }

  document.addEventListener('click', function (event) {
    const root = event.target.closest(ROOT_SELECTOR);
    if (root) {
      const trigger = event.target.closest('button, summary, [data-dropdown-trigger], [tabindex]');
      if (trigger && root.contains(trigger) && !event.target.closest('.dropdown-content')) {
        event.preventDefault();
        if (activeRoot === root) {
          closeDropdown();
        } else {
          openDropdown(root);
        }
        return;
      }
      return;
    }
    closeDropdown();
  }, true);

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closeDropdown();
  });

  document.addEventListener('scroll', function () {
    if (activeRoot) positionDropdown(activeRoot);
  }, true);

  window.addEventListener('resize', function () {
    if (activeRoot) positionDropdown(activeRoot);
  });
})();
