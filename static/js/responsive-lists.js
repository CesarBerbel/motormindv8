(function () {
  'use strict';

  var TABLET_BREAKPOINT = 1024;
  var MOBILE_BREAKPOINT = 768;

  function normalizeText(value) {
    return (value || '').replace(/\s+/g, ' ').trim();
  }

  function cellText(cell) {
    return normalizeText(cell ? cell.textContent : '');
  }

  function isEmptyRow(row) {
    var cells = Array.prototype.slice.call(row.children || []);
    if (!cells.length) return true;
    if (cells.length === 1 && cells[0].hasAttribute('colspan')) return true;
    return cells.every(function (cell) { return !cellText(cell); });
  }

  function columnIndexByLabel(labels, patterns) {
    for (var i = 0; i < labels.length; i += 1) {
      var label = labels[i].toLowerCase();
      for (var j = 0; j < patterns.length; j += 1) {
        if (patterns[j].test(label)) return i;
      }
    }
    return -1;
  }

  function parseIndexList(value, max) {
    if (!value) return [];
    return value.split(',').map(function (item) {
      return parseInt(item.trim(), 10);
    }).filter(function (index) {
      return Number.isInteger(index) && index >= 0 && index < max;
    });
  }

  function cloneInteractiveElement(element) {
    if (!element) return null;
    var clone = element.cloneNode(true);
    clone.removeAttribute('id');
    if (clone.tagName === 'LABEL') {
      clone.setAttribute('role', 'button');
      clone.tabIndex = 0;
    }
    clone.classList.remove('btn-xs');
    clone.classList.add('btn-sm');
    return clone;
  }

  function collectActions(actionCell) {
    if (!actionCell) return [];
    var preferred = Array.prototype.slice.call(actionCell.querySelectorAll('a[href], label[for]'));
    var fallbackButtons = Array.prototype.slice.call(actionCell.querySelectorAll('button:not([type="hidden"])'));
    return preferred.concat(fallbackButtons).filter(function (element, index, list) {
      if (list.indexOf(element) !== index) return false;
      if (element.closest('.modal')) return false;
      return normalizeText(element.textContent) || element.getAttribute('aria-label') || element.getAttribute('title');
    });
  }

  function addTabletColumnClasses(table, labels, indexes) {
    var visible = new Set(indexes);
    Array.prototype.slice.call(table.querySelectorAll('tr')).forEach(function (row) {
      Array.prototype.slice.call(row.children).forEach(function (cell, index) {
        if (!visible.has(index)) {
          cell.classList.add('responsive-tablet-hidden');
        } else {
          cell.classList.add('responsive-tablet-visible');
        }
      });
    });
  }

  function inferConfig(table, labels) {
    var columnCount = labels.length;
    var actionIndex = columnIndexByLabel(labels, [/aç(õ|o)es?/, /acoes?/, /opções?/, /opcoes?/]);
    if (actionIndex < 0) actionIndex = columnCount - 1;

    var statusIndex = columnIndexByLabel(labels, [/status/, /situação/, /situacao/, /estoque/, /publicado/, /padrão/, /padrao/]);

    var titleIndex = parseInt(table.dataset.cardTitleIndex || '', 10);
    if (!Number.isInteger(titleIndex)) {
      titleIndex = 0;
      var firstBodyRow = table.tBodies[0] ? table.tBodies[0].querySelector('tr') : null;
      if (firstBodyRow) {
        var cells = Array.prototype.slice.call(firstBodyRow.children || []);
        var anchorIndex = cells.findIndex(function (cell, index) {
          return index !== actionIndex && cell.querySelector('a[href]');
        });
        if (anchorIndex >= 0) titleIndex = anchorIndex;
      }
    }

    var metaIndexes = parseIndexList(table.dataset.cardMetaIndexes, columnCount);
    if (!metaIndexes.length) {
      for (var i = 0; i < columnCount; i += 1) {
        if (i === titleIndex || i === statusIndex || i === actionIndex) continue;
        metaIndexes.push(i);
        if (metaIndexes.length >= 4) break;
      }
    }

    var tabletVisible = parseIndexList(table.dataset.tabletVisibleColumns, columnCount);
    if (!tabletVisible.length) {
      tabletVisible = [titleIndex];
      if (statusIndex >= 0) tabletVisible.push(statusIndex);
      metaIndexes.slice(0, 2).forEach(function (index) { tabletVisible.push(index); });
      if (actionIndex >= 0) tabletVisible.push(actionIndex);
      tabletVisible = Array.prototype.slice.call(new Set(tabletVisible));
    }

    return {
      titleIndex: Math.max(0, Math.min(titleIndex, columnCount - 1)),
      statusIndex: statusIndex,
      actionIndex: actionIndex,
      metaIndexes: metaIndexes,
      tabletVisible: tabletVisible
    };
  }

  function sortRows(table, columnIndex, direction) {
    var tbody = table.tBodies[0];
    if (!tbody) return;
    var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr')).filter(function (row) {
      return !isEmptyRow(row);
    });
    rows.sort(function (a, b) {
      var av = cellText(a.children[columnIndex]);
      var bv = cellText(b.children[columnIndex]);
      var an = parseFloat(av.replace(/[^\d,-]/g, '').replace('.', '').replace(',', '.'));
      var bn = parseFloat(bv.replace(/[^\d,-]/g, '').replace('.', '').replace(',', '.'));
      var cmp;
      if (!Number.isNaN(an) && !Number.isNaN(bn) && /\d/.test(av) && /\d/.test(bv)) {
        cmp = an - bn;
      } else {
        cmp = av.localeCompare(bv, 'pt-BR', { numeric: true, sensitivity: 'base' });
      }
      return direction === 'desc' ? -cmp : cmp;
    });
    rows.forEach(function (row) { tbody.appendChild(row); });
  }

  function enhanceSorting(table, rebuildCards) {
    var headers = table.tHead ? Array.prototype.slice.call(table.tHead.querySelectorAll('th')) : [];
    headers.forEach(function (header, index) {
      if (header.classList.contains('no-sort')) return;
      if (normalizeText(header.textContent).toLowerCase().match(/aç(õ|o)es?|acoes?/)) return;
      header.classList.add('responsive-sortable-header');
      header.tabIndex = 0;
      header.setAttribute('role', 'button');
      header.setAttribute('aria-sort', 'none');
      header.title = 'Ordenar por ' + normalizeText(header.textContent);

      function toggleSort() {
        var current = header.getAttribute('aria-sort');
        var next = current === 'ascending' ? 'descending' : 'ascending';
        headers.forEach(function (item) { item.setAttribute('aria-sort', 'none'); });
        header.setAttribute('aria-sort', next);
        sortRows(table, index, next === 'descending' ? 'desc' : 'asc');
        rebuildCards();
      }

      header.addEventListener('click', toggleSort);
      header.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          toggleSort();
        }
      });
    });
  }

  function buildCards(table, wrapper, labels, config) {
    var old = wrapper.parentElement ? wrapper.parentElement.querySelector('[data-responsive-card-list-for="' + table.dataset.responsiveTableId + '"]') : null;
    if (old) old.remove();

    var list = document.createElement('div');
    list.className = 'responsive-card-list md:hidden';
    list.dataset.responsiveCardListFor = table.dataset.responsiveTableId;

    var tbody = table.tBodies[0];
    if (!tbody) return list;

    var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
    rows.forEach(function (row) {
      var cells = Array.prototype.slice.call(row.children || []);
      if (!cells.length) return;

      if (isEmptyRow(row)) {
        var empty = document.createElement('div');
        empty.className = 'responsive-list-empty';
        empty.textContent = cellText(cells[0]) || 'Nenhum registro encontrado.';
        list.appendChild(empty);
        return;
      }

      var card = document.createElement('article');
      card.className = 'responsive-row-card';

      var header = document.createElement('div');
      header.className = 'responsive-row-card__header';

      var titleWrap = document.createElement('div');
      titleWrap.className = 'min-w-0';
      var title = document.createElement('div');
      title.className = 'responsive-row-card__title';
      var titleCell = cells[config.titleIndex];
      var titleLink = titleCell ? titleCell.querySelector('a[href]') : null;
      if (titleLink) {
        var clonedTitleLink = titleLink.cloneNode(true);
        clonedTitleLink.removeAttribute('id');
        clonedTitleLink.className = 'link link-primary font-semibold';
        title.appendChild(clonedTitleLink);
      } else {
        title.textContent = cellText(titleCell) || 'Registro';
      }
      titleWrap.appendChild(title);

      var subtitleIndex = config.metaIndexes[0];
      if (subtitleIndex !== undefined && cells[subtitleIndex]) {
        var subtitle = document.createElement('p');
        subtitle.className = 'responsive-row-card__subtitle';
        subtitle.textContent = cellText(cells[subtitleIndex]);
        titleWrap.appendChild(subtitle);
      }
      header.appendChild(titleWrap);

      if (config.statusIndex >= 0 && cells[config.statusIndex]) {
        var status = document.createElement('div');
        status.className = 'responsive-row-card__status';
        status.innerHTML = cells[config.statusIndex].innerHTML;
        header.appendChild(status);
      }
      card.appendChild(header);

      var meta = document.createElement('dl');
      meta.className = 'responsive-row-card__meta';
      config.metaIndexes.slice(0, 4).forEach(function (index) {
        if (index === subtitleIndex) return;
        var source = cells[index];
        if (!source || !cellText(source)) return;
        var item = document.createElement('div');
        item.className = 'responsive-row-card__meta-item';
        var dt = document.createElement('dt');
        dt.textContent = labels[index] || 'Info';
        var dd = document.createElement('dd');
        dd.innerHTML = source.innerHTML;
        item.appendChild(dt);
        item.appendChild(dd);
        meta.appendChild(item);
      });
      if (meta.children.length) card.appendChild(meta);

      var actions = collectActions(cells[config.actionIndex]);
      if (!actions.length && titleLink) actions = [titleLink];
      if (actions.length) {
        var actionBar = document.createElement('div');
        actionBar.className = 'responsive-row-card__actions';
        var primary = cloneInteractiveElement(actions[0]);
        if (primary) {
          primary.classList.add('btn', 'btn-primary', 'flex-1');
          primary.classList.remove('btn-ghost', 'btn-outline', 'btn-error');
          actionBar.appendChild(primary);
        }
        if (actions.length > 1) {
          var dropdown = document.createElement('div');
          dropdown.className = 'dropdown dropdown-end';
          var trigger = document.createElement('button');
          trigger.type = 'button';
          trigger.className = 'btn btn-outline btn-sm';
          trigger.textContent = 'Mais';
          var menu = document.createElement('ul');
          menu.className = 'menu dropdown-content z-30 mt-2 w-48 rounded-box bg-base-100 p-2 shadow';
          actions.slice(1).forEach(function (action) {
            var li = document.createElement('li');
            var cloned = action.cloneNode(true);
            cloned.removeAttribute('id');
            if (cloned.tagName === 'LABEL') {
              cloned.setAttribute('role', 'button');
              cloned.tabIndex = 0;
            }
            cloned.className = '';
            li.appendChild(cloned);
            menu.appendChild(li);
          });
          dropdown.appendChild(trigger);
          dropdown.appendChild(menu);
          actionBar.appendChild(dropdown);
        }
        card.appendChild(actionBar);
      }

      list.appendChild(card);
    });
    return list;
  }

  function enhanceTable(table, index) {
    if (table.dataset.responsiveEnhanced === 'true') return;
    if (table.closest('.modal, form, [data-no-responsive-list]')) return;
    if (!table.tHead || !table.tBodies.length) return;

    var wrapper = table.closest('[data-responsive-list]') || table.parentElement;
    if (!wrapper) return;

    table.dataset.responsiveEnhanced = 'true';
    table.dataset.responsiveTableId = table.dataset.responsiveTableId || ('responsive-table-' + index + '-' + Math.random().toString(36).slice(2));
    wrapper.classList.add('responsive-list-shell');
    wrapper.classList.add('responsive-list-shell--enhanced');
    wrapper.dataset.responsiveList = wrapper.dataset.responsiveList || 'true';

    var labels = Array.prototype.slice.call(table.tHead.querySelectorAll('th')).map(function (th) {
      return normalizeText(th.textContent);
    });
    if (!labels.length) return;

    var config = inferConfig(table, labels);
    addTabletColumnClasses(table, labels, config.tabletVisible);

    function rebuildCards() {
      if (!wrapper.parentElement) return;
      var list = buildCards(table, wrapper, labels, config);
      wrapper.insertAdjacentElement('afterend', list);
    }

    enhanceSorting(table, rebuildCards);
    rebuildCards();
  }

  function enhanceFilterPanel(panel) {
    if (panel.dataset.responsiveFilterEnhanced === 'true') return;
    var form = panel.querySelector('form');
    if (!form) return;
    panel.dataset.responsiveFilterEnhanced = 'true';
    panel.classList.add('responsive-filter-panel');

    var isActive = panel.dataset.activeFilters === 'true' || /Filtros ativos|Filtro ativo/i.test(panel.textContent);
    if (isActive || window.innerWidth >= TABLET_BREAKPOINT) {
      panel.classList.add('is-open');
    }

    var header = document.createElement('div');
    header.className = 'responsive-filter-panel__header';
    var title = document.createElement('div');
    title.className = 'min-w-0';
    title.innerHTML = '<p class="text-sm font-semibold">Filtros e busca</p><p class="text-xs text-base-content/60">Use filtros combinados sem ocupar espaço no tablet.</p>';
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-outline btn-sm responsive-filter-panel__toggle';
    button.setAttribute('aria-expanded', panel.classList.contains('is-open') ? 'true' : 'false');
    button.textContent = panel.classList.contains('is-open') ? 'Recolher' : 'Abrir filtros';
    button.addEventListener('click', function () {
      panel.classList.toggle('is-open');
      var open = panel.classList.contains('is-open');
      button.setAttribute('aria-expanded', open ? 'true' : 'false');
      button.textContent = open ? 'Recolher' : 'Abrir filtros';
    });
    header.appendChild(title);
    header.appendChild(button);
    panel.insertBefore(header, form);
  }

  function init() {
    var tables = Array.prototype.slice.call(document.querySelectorAll('main [data-responsive-list] table'));
    tables.forEach(enhanceTable);

    var panels = Array.prototype.slice.call(document.querySelectorAll('[data-responsive-filter-panel], main .responsive-filter-panel'));
    panels.forEach(enhanceFilterPanel);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
