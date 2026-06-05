function readWorkOrderJson(scriptId) {
  const script = document.getElementById(scriptId);
  if (!script) return [];
  try {
    return JSON.parse(script.textContent || '[]');
  } catch (error) {
    console.error(`Erro ao carregar ${scriptId}:`, error);
    return [];
  }
}

function setupWorkOrderPicker(config) {
  const form = document.querySelector('[data-work-order-form]');
  const dialog = document.getElementById(config.dialogId);
  const openButton = document.querySelector(config.openSelector);
  const list = document.querySelector(config.listSelector);
  const emptyState = document.querySelector(config.emptySelector);
  const hiddenForms = document.querySelector(config.hiddenSelector);
  const emptyTemplate = document.querySelector(config.templateSelector);
  const totalFormsInput = document.querySelector(`input[name="${config.prefix}-TOTAL_FORMS"]`);

  if (!form || !dialog || !openButton || !list || !hiddenForms || !emptyTemplate || !totalFormsInput || !window.ReusableSelectModal) {
    return;
  }

  const items = readWorkOrderJson(config.scriptId);
  const itemsById = new Map(items.map((item) => [String(item.id), item]));

  function getField(row, suffix) {
    return row.querySelector(`[name$="-${suffix}"]`);
  }

  function getRows() {
    return Array.from(hiddenForms.querySelectorAll(config.rowSelector));
  }

  function isDeleted(row) {
    const deleteInput = getField(row, 'DELETE');
    return Boolean(deleteInput?.checked);
  }

  function getActiveRows() {
    return getRows().filter((row) => {
      const itemInput = getField(row, config.fieldName);
      return itemInput?.value && !isDeleted(row);
    });
  }

  function getActiveIds() {
    return getActiveRows().map((row) => getField(row, config.fieldName)?.value).filter(Boolean);
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function formatQuantity(value) {
    const number = Number(value || '0');
    if (!Number.isSafeInteger(number)) return value || '0';
    return number.toLocaleString('pt-BR');
  }

  function getRowErrors(row) {
    const errors = row.querySelector(config.errorsSelector);
    return errors ? errors.innerHTML : '';
  }

  function renderList() {
    const activeRows = getActiveRows();
    list.innerHTML = '';
    emptyState?.classList.toggle('hidden', activeRows.length > 0);

    activeRows.forEach((row) => {
      const itemId = getField(row, config.fieldName)?.value;
      const quantity = getField(row, 'quantidade')?.value || '1';
      const item = itemsById.get(String(itemId));
      const errorsHtml = getRowErrors(row);

      if (!item) return;

      const fields = Array.isArray(config.listFields) ? config.listFields : [];
      const fieldsHtml = fields.map((field) => {
        const value = typeof field.value === 'function' ? field.value(item, quantity) : item[field.key];
        return `<div><span class="block text-xs text-base-content/50">${escapeHtml(field.label)}</span>${escapeHtml(value || '-')}</div>`;
      }).join('');

      const card = document.createElement('div');
      card.className = 'rounded-box border border-base-300 bg-base-100 p-4 shadow-sm';
      card.innerHTML = `
        <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="badge badge-outline font-mono">${escapeHtml(item.sku || item.codigo || 'Sem código')}</span>
              <span class="font-semibold">${escapeHtml(item.nome)}</span>
              <span class="badge badge-ghost">${escapeHtml(item.tipo || config.typeLabel)}</span>
            </div>
            <div class="mt-2 grid gap-2 text-sm text-base-content/70 md:grid-cols-4">
              <div><span class="block text-xs text-base-content/50">Quantidade</span><strong>${escapeHtml(formatQuantity(quantity))}</strong></div>
              ${fieldsHtml}
            </div>
            ${errorsHtml ? `<div class="alert alert-error mt-3 text-sm">${errorsHtml}</div>` : ''}
          </div>
          <div class="flex shrink-0 justify-end">
            <button type="button" class="btn btn-error btn-outline btn-sm whitespace-nowrap" data-work-order-remove>Excluir</button>
          </div>
        </div>
      `;

      card.querySelector('[data-work-order-remove]')?.addEventListener('click', () => {
        const deleteInput = getField(row, 'DELETE');
        if (deleteInput) deleteInput.checked = true;
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
    hiddenForms.appendChild(row);
    totalFormsInput.value = String(index + 1);
    return row;
  }

  function addItem({ item, quantity }) {
    const activeIds = getActiveIds();
    if (activeIds.includes(String(item.id))) return;

    const row = createFormRow();
    const itemInput = getField(row, config.fieldName);
    const quantityInput = getField(row, 'quantidade');
    const deleteInput = getField(row, 'DELETE');

    if (itemInput) itemInput.value = String(item.id);
    if (quantityInput) quantityInput.value = quantity || '1';
    if (deleteInput) deleteInput.checked = false;

    renderList();
  }

  const picker = new window.ReusableSelectModal({
    dialog,
    items,
    getExcludedIds: getActiveIds,
    onSave: addItem
  });

  openButton.addEventListener('click', () => picker.open());
  renderList();
}

function setupWorkOrderItems() {
  setupWorkOrderPicker({
    prefix: 'services',
    scriptId: 'work-order-services-data',
    dialogId: 'work_order_service_picker_modal',
    openSelector: '[data-work-order-service-open-modal]',
    listSelector: '[data-work-order-services-list]',
    emptySelector: '[data-work-order-services-empty]',
    hiddenSelector: '[data-work-order-services-hidden-forms]',
    templateSelector: '[data-work-order-service-empty-form-template]',
    rowSelector: '[data-work-order-service-form]',
    errorsSelector: '[data-work-order-service-errors]',
    fieldName: 'service',
    typeLabel: 'Serviço',
    listFields: [
      { label: 'Duração', key: 'duracao' },
      { label: 'Valor unitário', key: 'valor' },
      { label: 'Peças padrão', key: 'pecas' }
    ]
  });

  setupWorkOrderPicker({
    prefix: 'combos',
    scriptId: 'work-order-combos-data',
    dialogId: 'work_order_combo_picker_modal',
    openSelector: '[data-work-order-combo-open-modal]',
    listSelector: '[data-work-order-combos-list]',
    emptySelector: '[data-work-order-combos-empty]',
    hiddenSelector: '[data-work-order-combos-hidden-forms]',
    templateSelector: '[data-work-order-combo-empty-form-template]',
    rowSelector: '[data-work-order-combo-form]',
    errorsSelector: '[data-work-order-combo-errors]',
    fieldName: 'combo',
    typeLabel: 'Combo',
    listFields: [
      { label: 'Duração', key: 'duracao' },
      { label: 'Valor unitário', key: 'valor' },
      { label: 'Serviços', key: 'servicos' },
      { label: 'Peças padrão', key: 'pecas' }
    ]
  });

  setupWorkOrderPicker({
    prefix: 'parts',
    scriptId: 'work-order-parts-data',
    dialogId: 'work_order_part_picker_modal',
    openSelector: '[data-work-order-part-open-modal]',
    listSelector: '[data-work-order-parts-list]',
    emptySelector: '[data-work-order-parts-empty]',
    hiddenSelector: '[data-work-order-parts-hidden-forms]',
    templateSelector: '[data-work-order-part-empty-form-template]',
    rowSelector: '[data-work-order-part-form]',
    errorsSelector: '[data-work-order-part-errors]',
    fieldName: 'item',
    typeLabel: 'Peça/Insumo',
    listFields: [
      { label: 'Estoque', value: (item) => `${item.estoque_atual || '0'} ${item.unidade || ''}`.trim() },
      { label: 'Custo unitário', key: 'preco_custo' },
      { label: 'Categoria', key: 'categoria' }
    ]
  });
}

document.addEventListener('DOMContentLoaded', setupWorkOrderItems);
