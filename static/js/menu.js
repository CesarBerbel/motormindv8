document.addEventListener('DOMContentLoaded', () => {
  const navbar = document.querySelector('[data-main-navbar]');

  if (!navbar) {
    return;
  }

  const getRootMenus = () => Array.from(navbar.querySelectorAll('details[data-menu-root]'));
  const getNestedMenus = () => Array.from(navbar.querySelectorAll('details[data-menu-nested]'));
  const getAllMenus = () => Array.from(navbar.querySelectorAll('details[data-menu-root], details[data-menu-nested]'));

  const closeMenus = (menus, except = null) => {
    menus.forEach((menu) => {
      if (menu !== except) {
        menu.open = false;
      }
    });
  };

  getRootMenus().forEach((menu) => {
    menu.addEventListener('toggle', () => {
      if (menu.open) {
        closeMenus(getRootMenus(), menu);
      }
    });
  });

  getNestedMenus().forEach((menu) => {
    menu.addEventListener('toggle', () => {
      if (!menu.open) {
        return;
      }

      const parentList = menu.closest('ul');
      const siblingMenus = getNestedMenus().filter((otherMenu) => otherMenu.closest('ul') === parentList);
      closeMenus(siblingMenus, menu);
    });
  });

  document.addEventListener('click', (event) => {
    if (!navbar.contains(event.target)) {
      closeMenus(getAllMenus());
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeMenus(getAllMenus());
    }
  });

  navbar.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      closeMenus(getAllMenus());
    });
  });
});
