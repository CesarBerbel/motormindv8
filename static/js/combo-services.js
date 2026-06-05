function getComboServices() {
  const script = document.getElementById('combo-services-data');
  if (!script) {
    return [];
  }

  try {
    return JSON.parse(script.textContent || '[]');
  } catch (error) {
    console.error('Erro ao carregar dados dos serviços:', error);
    return [];
  }
}

function setupComboServicesModal() {
  const form = document.querySelector('[data-combo-services-form]');
  const dialog = document.getElementById('combo_service_picker_modal');
  const openButton = document.querySelector('[data-combo-service-open-modal]');
  const list = document.querySelector('[data-combo-services-list]');
  const emptyState = document.querySelector('[data-combo-services-empty]');
  const hiddenForms = document.querySelector('[data-combo-services-hidden-forms]');
  const emptyTemplate = document.querySelector('[data-combo-service-empty-form-template]');
  const totalFormsInput = document.querySelector('input[name="services-TOTAL_FORMS"]');

  if (!form || !dialog || !openButton || !list || !hiddenForms || !emptyTemplate || !totalFormsInput || !window.ReusableSelectModal) {
    return;
  }

  const services = getComboServices();
  const servicesById = new Map(services.map((service) => [String(service.id), service]));

  function getField(row, suffix) {
    return row.querySelector(`[name$="-${suffix}"]`);
  }

  function getRows() {
    return Array.from(hiddenForms.querySelectorAll('[data-combo-service-form]'));
  }

  function isDeleted(row) {
    const deleteInput = getField(row, 'DELETE');
    return Boolean(deleteInput?.checked);
  }

  function getActiveRows() {
    return getRows().filter((row) => {
      const serviceInput = getField(row, 'service');
      return serviceInput?.value && !isDeleted(row);
    });
  }

  function getActiveServiceIds() {
    return getActiveRows().map((row) => getField(row, 'service')?.value).filter(Boolean);
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
    const errors = row.querySelector('[data-combo-service-errors]');
    return errors ? errors.innerHTML : '';
  }

  function renderList() {
    const activeRows = getActiveRows();
    list.innerHTML = '';
    emptyState?.classList.toggle('hidden', activeRows.length > 0);

    activeRows.forEach((row) => {
      const serviceId = getField(row, 'service')?.value;
      const service = servicesById.get(String(serviceId));
      const errorsHtml = getRowErrors(row);

      if (!service) {
        return;
      }

      const card = document.createElement('div');
      card.className = 'rounded-box border border-base-300 bg-base-100 p-4 shadow-sm';
      card.dataset.comboServiceDisplayRow = serviceId;
      card.innerHTML = `
        <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="badge badge-outline font-mono">${escapeHtml(service.codigo || 'Sem código')}</span>
              <span class="font-semibold">${escapeHtml(service.nome)}</span>
              <span class="badge badge-ghost">Serviço</span>
            </div>
            <div class="mt-2 grid gap-2 text-sm text-base-content/70 md:grid-cols-3">
              <div><span class="block text-xs text-base-content/50">Duração</span>${escapeHtml(service.duracao || '-')}</div>
              <div><span class="block text-xs text-base-content/50">Valor</span>${escapeHtml(service.valor || 'R$ 0,00')}</div>
              <div><span class="block text-xs text-base-content/50">Peças padrão</span>${escapeHtml(service.pecas || '-')}</div>
            </div>
            ${errorsHtml ? `<div class="alert alert-error mt-3 text-sm">${errorsHtml}</div>` : ''}
          </div>
          <div class="flex shrink-0 justify-end">
            <button type="button" class="btn btn-error btn-outline btn-sm whitespace-nowrap" data-combo-service-remove>Excluir</button>
          </div>
        </div>
      `;

      card.querySelector('[data-combo-service-remove]')?.addEventListener('click', () => {
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

  function addService({ item }) {
    const activeIds = getActiveServiceIds();
    if (activeIds.includes(String(item.id))) {
      return;
    }

    const row = createFormRow();
    const serviceInput = getField(row, 'service');
    const deleteInput = getField(row, 'DELETE');

    if (serviceInput) {
      serviceInput.value = String(item.id);
    }
    if (deleteInput) {
      deleteInput.checked = false;
    }

    renderList();
  }

  const picker = new window.ReusableSelectModal({
    dialog,
    items: services,
    getExcludedIds: getActiveServiceIds,
    onSave: addService
  });

  openButton.addEventListener('click', () => picker.open());
  renderList();
}

document.addEventListener('DOMContentLoaded', setupComboServicesModal);
