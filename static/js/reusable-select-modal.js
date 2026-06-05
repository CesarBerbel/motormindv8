class ReusableSelectModal {
  constructor({ dialog, items, onSave, getExcludedIds }) {
    this.dialog = dialog;
    this.items = Array.isArray(items) ? items : [];
    this.onSave = typeof onSave === 'function' ? onSave : () => {};
    this.getExcludedIds = typeof getExcludedIds === 'function' ? getExcludedIds : () => [];

    this.searchInput = dialog.querySelector('[data-picker-search]');
    this.dropdown = dialog.querySelector('[data-picker-dropdown]');
    this.cards = dialog.querySelector('[data-picker-cards]');
    this.selectedCard = dialog.querySelector('[data-picker-selected-card]');
    this.quantityInput = dialog.querySelector('[data-picker-quantity]');
    this.errorBox = dialog.querySelector('[data-picker-error]');
    this.saveButton = dialog.querySelector('[data-picker-save]');
    this.cancelButton = dialog.querySelector('[data-picker-cancel]');
    this.emptyMessage = dialog.dataset.modalEmptyMessage || 'Nenhum resultado encontrado.';
    this.requireQuantity = dialog.dataset.pickerRequireQuantity !== 'false';
    this.selectedItem = null;

    this.bindEvents();
  }

  bindEvents() {
    this.searchInput?.addEventListener('input', () => this.renderResults());
    this.searchInput?.addEventListener('focus', () => this.renderDropdown());
    this.searchInput?.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        this.hideDropdown();
      }
    });

    this.saveButton?.addEventListener('click', () => this.save());
    this.cancelButton?.addEventListener('click', () => this.close());

    document.addEventListener('click', (event) => {
      if (!this.dialog.open) {
        return;
      }
      if (!this.dropdown?.contains(event.target) && event.target !== this.searchInput) {
        this.hideDropdown();
      }
    });
  }

  open() {
    this.selectedItem = null;
    this.searchInput.value = '';
    if (this.quantityInput) {
      this.quantityInput.value = '1';
    }
    this.clearError();
    this.renderSelected();
    this.renderResults();
    this.dialog.showModal();
    window.setTimeout(() => this.searchInput?.focus(), 50);
  }

  close() {
    this.hideDropdown();
    this.dialog.close();
  }

  getExcludedSet() {
    return new Set((this.getExcludedIds() || []).map((id) => String(id)));
  }

  getAvailableItems() {
    const excluded = this.getExcludedSet();
    return this.items.filter((item) => !excluded.has(String(item.id)));
  }

  getFilteredItems() {
    const term = (this.searchInput?.value || '').trim().toLowerCase();
    const availableItems = this.getAvailableItems();

    if (!term) {
      return availableItems.slice(0, 8);
    }

    return availableItems
      .filter((item) => (item.search || '').includes(term))
      .slice(0, 12);
  }

  selectItem(item) {
    this.selectedItem = item;
    this.searchInput.value = item.label || item.nome || '';
    this.hideDropdown();
    this.renderSelected();
    this.clearError();
    if (this.requireQuantity) {
      this.quantityInput?.focus();
    }
  }

  renderResults() {
    this.renderCards();
    this.renderDropdown();
  }

  renderDropdown() {
    if (!this.dropdown) {
      return;
    }

    const term = (this.searchInput?.value || '').trim();
    if (term.length < 2) {
      this.hideDropdown();
      return;
    }

    const results = this.getFilteredItems();
    this.dropdown.innerHTML = '';

    if (!results.length) {
      const empty = document.createElement('div');
      empty.className = 'px-4 py-3 text-sm text-base-content/60';
      empty.textContent = this.emptyMessage;
      this.dropdown.appendChild(empty);
    } else {
      results.forEach((item) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'block w-full px-4 py-3 text-left hover:bg-base-200 focus:bg-base-200 focus:outline-none';
        button.innerHTML = `
          <span class="block font-medium">${this.escapeHtml(item.label || item.nome)}</span>
          <span class="block truncate text-xs text-base-content/60">${this.escapeHtml(this.buildSubtitle(item))}</span>
        `;
        button.addEventListener('click', () => this.selectItem(item));
        this.dropdown.appendChild(button);
      });
    }

    this.dropdown.classList.remove('hidden');
    this.searchInput?.setAttribute('aria-expanded', 'true');
  }

  hideDropdown() {
    this.dropdown?.classList.add('hidden');
    this.searchInput?.setAttribute('aria-expanded', 'false');
  }

  renderCards() {
    if (!this.cards) {
      return;
    }

    const results = this.getFilteredItems();
    this.cards.innerHTML = '';

    if (!results.length) {
      const empty = document.createElement('div');
      empty.className = 'rounded-box border border-dashed border-base-300 p-4 text-sm text-base-content/60 sm:col-span-2';
      empty.textContent = this.emptyMessage;
      this.cards.appendChild(empty);
      return;
    }

    results.forEach((item) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'rounded-box border border-base-300 bg-base-100 p-3 text-left shadow-sm transition hover:border-primary hover:bg-primary/5 focus:border-primary focus:outline-none';
      button.innerHTML = this.renderItemCardHtml(item, false);
      button.addEventListener('click', () => this.selectItem(item));
      this.cards.appendChild(button);
    });
  }

  renderSelected() {
    if (!this.selectedCard) {
      return;
    }

    if (!this.selectedItem) {
      this.selectedCard.innerHTML = '<p class="text-sm text-base-content/60">Nenhum item selecionado.</p>';
      return;
    }

    this.selectedCard.innerHTML = this.renderItemCardHtml(this.selectedItem, true);
  }

  getCardFields(item) {
    if (Array.isArray(item.card_fields) && item.card_fields.length) {
      return item.card_fields.slice(0, 6);
    }

    return [
      { label: 'Categoria', value: item.categoria || '-' },
      { label: 'Marca', value: item.marca || '-' },
      { label: 'Estoque', value: `${item.estoque_atual || '0'} ${item.unidade || ''}`.trim() },
      { label: 'Custo', value: item.preco_custo || 'R$ 0,00' }
    ];
  }

  renderItemCardHtml(item, selected) {
    const fields = this.getCardFields(item);
    const fieldsHtml = fields.map((field) => `
      <div><span class="block text-base-content/50">${this.escapeHtml(field.label)}</span><strong>${this.escapeHtml(field.value || '-')}</strong></div>
    `).join('');

    return `
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0">
          <p class="truncate font-semibold">${this.escapeHtml(item.nome)}</p>
          <p class="font-mono text-xs text-base-content/60">${this.escapeHtml(item.sku || item.codigo || 'Sem código')}</p>
        </div>
        <span class="badge ${selected ? 'badge-primary' : 'badge-outline'} shrink-0">${this.escapeHtml(item.tipo || 'Item')}</span>
      </div>
      <div class="mt-3 grid grid-cols-2 gap-2 text-xs text-base-content/70">
        ${fieldsHtml}
      </div>
    `;
  }

  buildSubtitle(item) {
    if (Array.isArray(item.card_fields) && item.card_fields.length) {
      return item.card_fields.map((field) => field.value).filter(Boolean).join(' | ');
    }
    const parts = [item.categoria, item.marca, `${item.estoque_atual || '0'} ${item.unidade || ''}`, item.preco_custo];
    return parts.filter(Boolean).join(' | ');
  }

  normalizeQuantity(value) {
    const raw = String(value || '').trim();

    if (!/^\d+$/.test(raw)) {
      return null;
    }

    const number = Number(raw);
    if (!Number.isSafeInteger(number) || number <= 0) {
      return null;
    }

    return String(number);
  }

  save() {
    if (!this.selectedItem) {
      this.showError('Selecione um item.');
      return;
    }

    let quantity = null;
    if (this.requireQuantity) {
      quantity = this.normalizeQuantity(this.quantityInput?.value);
      if (!quantity) {
        this.showError('Informe uma quantidade inteira maior que zero.');
        return;
      }
    }

    this.onSave({ item: this.selectedItem, quantity });
    this.close();
  }

  showError(message) {
    if (!this.errorBox) {
      return;
    }
    this.errorBox.textContent = message;
    this.errorBox.classList.remove('hidden');
  }

  clearError() {
    if (!this.errorBox) {
      return;
    }
    this.errorBox.textContent = '';
    this.errorBox.classList.add('hidden');
  }

  escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }
}

window.ReusableSelectModal = ReusableSelectModal;
