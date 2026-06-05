function getServicePartItems() {
  const script = document.getElementById('service-part-items-data');
  if (!script) {
    return [];
  }

  try {
    return JSON.parse(script.textContent || '[]');
  } catch (error) {
    console.error('Erro ao carregar dados das peças:', error);
    return [];
  }
}

function setupServicePartsModal() {
  const form = document.querySelector('[data-service-parts-form]');
  const dialog = document.getElementById('service_part_picker_modal');
  const openButton = document.querySelector('[data-service-part-open-modal]');
  const list = document.querySelector('[data-service-parts-list]');
  const emptyState = document.querySelector('[data-service-parts-empty]');
  const hiddenForms = document.querySelector('[data-service-parts-hidden-forms]');
  const emptyTemplate = document.querySelector('[data-service-part-empty-form-template]');
  const totalFormsInput = document.querySelector('input[name="parts-TOTAL_FORMS"]');

  if (!form || !dialog || !openButton || !list || !hiddenForms || !emptyTemplate || !totalFormsInput || !window.ReusableSelectModal) {
    return;
  }

  const items = getServicePartItems();
  const itemsById = new Map(items.map((item) => [String(item.id), item]));

  function getField(row, suffix) {
    return row.querySelector(`[name$="-${suffix}"]`);
  }

  function getRows() {
    return Array.from(hiddenForms.querySelectorAll('[data-service-part-form]'));
  }

  function isDeleted(row) {
    const deleteInput = getField(row, 'DELETE');
    return Boolean(deleteInput?.checked);
  }

  function getActiveRows() {
    return getRows().filter((row) => {
      const itemInput = getField(row, 'item');
      return itemInput?.value && !isDeleted(row);
    });
  }

  function getActiveItemIds() {
    return getActiveRows().map((row) => getField(row, 'item')?.value).filter(Boolean);
  }

  function formatQuantity(value) {
    const number = Number(String(value || '0'));
    if (!Number.isSafeInteger(number)) {
      return value || '0';
    }
    return number.toLocaleString('pt-BR');
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function getRowErrors(row) {
    const errors = row.querySelector('[data-service-part-errors]');
    return errors ? errors.innerHTML : '';
  }

  function renderList() {
    const activeRows = getActiveRows();
    list.innerHTML = '';
    emptyState?.classList.toggle('hidden', activeRows.length > 0);

    activeRows.forEach((row) => {
      const itemId = getField(row, 'item')?.value;
      const quantity = getField(row, 'quantidade')?.value;
      const item = itemsById.get(String(itemId));
      const errorsHtml = getRowErrors(row);

      if (!item) {
        return;
      }

      const card = document.createElement('div');
      card.className = 'rounded-box border border-base-300 bg-base-100 p-4 shadow-sm';
      card.dataset.servicePartDisplayRow = itemId;
      card.innerHTML = `
        <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="badge badge-outline font-mono">${escapeHtml(item.sku || 'Sem SKU')}</span>
              <span class="font-semibold">${escapeHtml(item.nome)}</span>
              <span class="badge badge-ghost">${escapeHtml(item.tipo || 'Item')}</span>
            </div>
            <div class="mt-2 grid gap-2 text-sm text-base-content/70 md:grid-cols-4">
              <div><span class="block text-xs text-base-content/50">Categoria</span>${escapeHtml(item.categoria || '-')}</div>
              <div><span class="block text-xs text-base-content/50">Marca</span>${escapeHtml(item.marca || '-')}</div>
              <div><span class="block text-xs text-base-content/50">Quantidade padrão</span><strong>${escapeHtml(formatQuantity(quantity))} ${escapeHtml(item.unidade || '')}</strong></div>
              <div><span class="block text-xs text-base-content/50">Custo unitário</span>${escapeHtml(item.preco_custo || 'R$ 0,00')}</div>
            </div>
            ${errorsHtml ? `<div class="alert alert-error mt-3 text-sm">${errorsHtml}</div>` : ''}
          </div>
          <div class="flex shrink-0 justify-end">
            <button type="button" class="btn btn-error btn-outline btn-sm whitespace-nowrap" data-service-part-remove>Excluir</button>
          </div>
        </div>
      `;

      card.querySelector('[data-service-part-remove]')?.addEventListener('click', () => {
        const deleteInput = getField(row, 'DELETE');
        if (deleteInput) {
          deleteInput.checked = true;
        }
        renderList();
      });

      list.appendChild(card);
    });
  }

  function createFormRow() {
    const index = Number(totalFormsInput.value || '0');
    const html = emptyTemplate.innerHTML.replaceAll('__prefix__', String(index));
    const wrapper = document.createElement('div');
    wrapper.innerHTML = html.trim();
    const row = wrapper.firstElementChild;
    row.dataset.formIndex = String(index);
    hiddenForms.appendChild(row);
    totalFormsInput.value = String(index + 1);
    return row;
  }

  function addPart({ item, quantity }) {
    const activeIds = getActiveItemIds();
    if (activeIds.includes(String(item.id))) {
      return;
    }

    const row = createFormRow();
    const itemInput = getField(row, 'item');
    const quantityInput = getField(row, 'quantidade');
    const observationInput = getField(row, 'observacao');
    const deleteInput = getField(row, 'DELETE');

    if (itemInput) {
      itemInput.value = String(item.id);
    }
    if (quantityInput) {
      quantityInput.value = quantity;
    }
    if (observationInput) {
      observationInput.value = '';
    }
    if (deleteInput) {
      deleteInput.checked = false;
    }

    renderList();
  }

  const picker = new window.ReusableSelectModal({
    dialog,
    items,
    getExcludedIds: getActiveItemIds,
    onSave: addPart
  });

  openButton.addEventListener('click', () => picker.open());
  renderList();
}

document.addEventListener('DOMContentLoaded', setupServicePartsModal);
