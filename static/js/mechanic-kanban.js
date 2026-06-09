(function () {
  var activeItemTarget = null;
  var itemPickers = {};

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function readJsonScript(scriptId) {
    var script = document.getElementById(scriptId);
    if (!script) {
      return [];
    }
    try {
      return JSON.parse(script.textContent || '[]');
    } catch (error) {
      console.error('Erro ao carregar dados do Kanban:', error);
      return [];
    }
  }

  function createToast(message, type) {
    var container = document.querySelector('[data-toast-container]');
    if (!container) {
      container = document.createElement('div');
      container.className = 'app-toast-container';
      container.setAttribute('data-toast-container', '');
      container.setAttribute('aria-live', 'polite');
      container.setAttribute('aria-atomic', 'true');
      document.body.appendChild(container);
    }

    var toast = document.createElement('div');
    var alertClass = 'alert-info';
    if (type === 'success') {
      alertClass = 'alert-success';
    } else if (type === 'error') {
      alertClass = 'alert-error';
    } else if (type === 'warning') {
      alertClass = 'alert-warning';
    }

    toast.className = 'alert app-toast shadow-xl ' + alertClass;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('data-toast', '');
    toast.setAttribute('data-toast-duration', type === 'error' ? '12000' : '4500');

    var text = document.createElement('span');
    text.className = 'min-w-0 flex-1';
    text.textContent = message;

    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'btn btn-ghost btn-xs btn-circle shrink-0';
    close.setAttribute('data-toast-close', '');
    close.setAttribute('aria-label', 'Fechar mensagem');
    close.textContent = '✕';

    toast.appendChild(text);
    toast.appendChild(close);
    container.appendChild(toast);

    var timeoutId = window.setTimeout(function () {
      toast.classList.add('is-hiding');
      window.setTimeout(function () {
        toast.remove();
      }, 220);
    }, Number.parseInt(toast.getAttribute('data-toast-duration'), 10));

    close.addEventListener('click', function () {
      window.clearTimeout(timeoutId);
      toast.classList.add('is-hiding');
      window.setTimeout(function () {
        toast.remove();
      }, 220);
    });
  }

  function getColumn(status) {
    return document.querySelector('[data-kanban-column][data-status="' + status + '"]');
  }

  function updateColumnEmptyState(column) {
    if (!column) {
      return;
    }
    var cards = column.querySelectorAll('[data-kanban-card]');
    var count = column.querySelector('[data-kanban-column-count]');
    var empty = column.querySelector('[data-kanban-empty]');

    if (count) {
      count.textContent = String(cards.length);
    }
    if (empty) {
      empty.classList.toggle('hidden', cards.length > 0);
    }
  }

  function updateAllColumnStates() {
    document.querySelectorAll('[data-kanban-column]').forEach(updateColumnEmptyState);
  }

  function replaceCard(oldCard, html) {
    var template = document.createElement('template');
    template.innerHTML = html.trim();
    var newCard = template.content.firstElementChild;
    if (!newCard) {
      return oldCard;
    }
    oldCard.replaceWith(newCard);
    setupCard(newCard);
    return newCard;
  }

  function moveCardElement(card, status) {
    var targetColumn = getColumn(status);
    if (!targetColumn) {
      return false;
    }
    var list = targetColumn.querySelector('[data-kanban-card-list]');
    var empty = targetColumn.querySelector('[data-kanban-empty]');
    if (!list) {
      return false;
    }
    if (empty) {
      list.insertBefore(card, empty);
    } else {
      list.appendChild(card);
    }
    card.dataset.currentStatus = status;
    updateAllColumnStates();
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
    return true;
  }

  function setCardBusy(card, isBusy) {
    if (!card) {
      return;
    }
    card.classList.toggle('opacity-60', isBusy);
    card.classList.toggle('pointer-events-none', isBusy);
    card.querySelectorAll('button').forEach(function (button) {
      button.disabled = isBusy;
    });
  }

  function handleJsonResponse(response) {
    return response.json().then(function (payload) {
      return { ok: response.ok, payload: payload };
    });
  }

  function submitMove(card, status) {
    if (!card || !status || card.dataset.moving === 'true') {
      return;
    }

    var previousStatus = card.dataset.currentStatus;
    var previousColumn = getColumn(previousStatus);
    var moveUrl = card.dataset.moveUrl;

    if (!moveUrl) {
      createToast('Não foi possível localizar a rota de movimentação da OS.', 'error');
      return;
    }

    setCardBusy(card, true);
    card.dataset.moving = 'true';

    var body = new URLSearchParams();
    body.set('status', status);

    fetch(moveUrl, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCsrfToken(),
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: body.toString(),
      credentials: 'same-origin'
    })
      .then(handleJsonResponse)
      .then(function (result) {
        var payload = result.payload || {};
        if (!result.ok || payload.ok === false) {
          if (payload.card_html) {
            card = replaceCard(card, payload.card_html);
          }
          moveCardElement(card, payload.final_status || previousStatus);
          updateColumnEmptyState(previousColumn);
          var message = payload.message || 'Não foi possível mover a OS.';
          if (payload.checkin_url) {
            message += ' Faça o check-in antes de iniciar execução.';
          }
          createToast(message, 'error');
          return;
        }

        if (payload.card_html) {
          card = replaceCard(card, payload.card_html);
        }
        moveCardElement(card, payload.final_status || status);
        createToast(payload.message || 'OS movida com sucesso.', 'success');
      })
      .catch(function () {
        moveCardElement(card, previousStatus);
        createToast('Erro de comunicação ao mover a OS. Tente novamente.', 'error');
      })
      .finally(function () {
        card.dataset.moving = 'false';
        setCardBusy(card, false);
        updateAllColumnStates();
      });
  }

  function submitAddItem(target, selectedItem, quantity) {
    if (!target || !target.card || !target.url || !target.type || !selectedItem) {
      createToast('Não foi possível identificar a OS para adicionar o item.', 'error');
      return;
    }

    var card = target.card;
    var previousStatus = card.dataset.currentStatus;
    var previousColumn = getColumn(previousStatus);
    var body = new URLSearchParams();
    body.set('item_type', target.type);
    body.set('item_id', selectedItem.id);
    body.set('quantidade', quantity || '1');

    setCardBusy(card, true);

    fetch(target.url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCsrfToken(),
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: body.toString(),
      credentials: 'same-origin'
    })
      .then(handleJsonResponse)
      .then(function (result) {
        var payload = result.payload || {};
        if (payload.card_html) {
          card = replaceCard(card, payload.card_html);
        }
        moveCardElement(card, payload.final_status || previousStatus);
        updateColumnEmptyState(previousColumn);

        if (!result.ok || payload.ok === false) {
          createToast(payload.message || 'Não foi possível adicionar o item à OS.', 'error');
          return;
        }

        createToast(payload.message || 'Item adicionado à OS.', 'success');
      })
      .catch(function () {
        createToast('Erro de comunicação ao adicionar o item. Tente novamente.', 'error');
      })
      .finally(function () {
        setCardBusy(card, false);
        updateAllColumnStates();
      });
  }

  function submitReopenItems(card, url) {
    if (!card || !url || card.dataset.reopeningItems === 'true') {
      return;
    }

    var previousStatus = card.dataset.currentStatus;
    var previousColumn = getColumn(previousStatus);
    setCardBusy(card, true);
    card.dataset.reopeningItems = 'true';

    fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCsrfToken(),
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: '',
      credentials: 'same-origin'
    })
      .then(handleJsonResponse)
      .then(function (result) {
        var payload = result.payload || {};
        if (payload.card_html) {
          card = replaceCard(card, payload.card_html);
        }
        moveCardElement(card, payload.final_status || previousStatus);
        updateColumnEmptyState(previousColumn);

        if (!result.ok || payload.ok === false) {
          createToast(payload.message || 'Não foi possível reabrir o orçamento técnico.', 'error');
          return;
        }

        createToast(payload.message || 'Orçamento técnico reaberto.', 'success');
      })
      .catch(function () {
        createToast('Erro de comunicação ao reabrir orçamento técnico. Tente novamente.', 'error');
      })
      .finally(function () {
        card.dataset.reopeningItems = 'false';
        setCardBusy(card, false);
        updateAllColumnStates();
      });
  }

  function openItemPicker(button, card) {
    var type = button.dataset.itemType;
    var picker = itemPickers[type];
    var addUrl = button.dataset.addUrl;

    if (!picker) {
      createToast('Modal de item não encontrado. Recarregue a página e tente novamente.', 'error');
      return;
    }
    if (!addUrl) {
      createToast('Não foi possível localizar a rota para adicionar item à OS.', 'error');
      return;
    }

    activeItemTarget = {
      card: card,
      type: type,
      url: addUrl
    };
    picker.open();
  }

  function setupCard(card) {
    card.querySelectorAll('[data-kanban-move-status]').forEach(function (button) {
      button.addEventListener('click', function () {
        submitMove(card, button.dataset.kanbanMoveStatus);
      });
    });

    card.querySelectorAll('[data-kanban-add-item]').forEach(function (button) {
      button.addEventListener('click', function () {
        openItemPicker(button, card);
      });
    });

    card.querySelectorAll('[data-kanban-reopen-items]').forEach(function (button) {
      button.addEventListener('click', function () {
        submitReopenItems(card, button.dataset.reopenUrl);
      });
    });
  }

  function setupItemPicker(config) {
    var dialog = document.getElementById(config.dialogId);
    if (!dialog || !window.ReusableSelectModal) {
      return;
    }

    itemPickers[config.type] = new window.ReusableSelectModal({
      dialog: dialog,
      items: readJsonScript(config.scriptId),
      getExcludedIds: function () {
        return [];
      },
      onSave: function (selection) {
        submitAddItem(activeItemTarget, selection.item, selection.quantity);
      }
    });
  }

  function setupItemPickers() {
    setupItemPicker({
      type: 'servico',
      dialogId: 'mechanic_kanban_service_picker_modal',
      scriptId: 'mechanic-kanban-services-data'
    });
    setupItemPicker({
      type: 'combo',
      dialogId: 'mechanic_kanban_combo_picker_modal',
      scriptId: 'mechanic-kanban-combos-data'
    });
    setupItemPicker({
      type: 'peca',
      dialogId: 'mechanic_kanban_part_picker_modal',
      scriptId: 'mechanic-kanban-parts-data'
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var board = document.querySelector('[data-mechanic-kanban-board]');
    if (!board) {
      return;
    }
    setupItemPickers();
    document.querySelectorAll('[data-kanban-card]').forEach(setupCard);
    updateAllColumnStates();
  });
})();
