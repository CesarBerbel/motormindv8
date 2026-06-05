function setupVehicleMasks() {
  document.querySelectorAll('[data-mask="placa"]').forEach((input) => {
    input.addEventListener('input', () => {
      const raw = input.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 7);
      if (/^[A-Z]{3}[0-9]{4}$/.test(raw)) {
        input.value = `${raw.slice(0, 3)}-${raw.slice(3)}`;
        return;
      }
      input.value = raw;
    });
  });

  document.querySelectorAll('[data-mask="chassi"]').forEach((input) => {
    input.addEventListener('input', () => {
      input.value = input.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 17);
    });
  });
}

function normalizeFuel(value) {
  const text = String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();

  if (text.includes('flex')) return 'flex';
  if (text.includes('alcool') || text.includes('etanol')) return 'etanol';
  if (text.includes('gasolina')) return 'gasolina';
  if (text.includes('diesel')) return 'diesel';
  if (text.includes('gnv')) return 'gnv';
  if (text.includes('eletric')) return 'eletrico';
  if (text.includes('hibrid')) return 'hibrido';
  return text ? 'outro' : '';
}

function setupFipeLookup() {
  const widget = document.querySelector('[data-fipe-widget]');
  if (!widget) return;

  const form = document.querySelector('[data-vehicle-form]');
  const typeSelect = form?.querySelector('[data-fipe-type]');
  const brandSelect = widget.querySelector('[data-fipe-brand-select]');
  const modelSelect = widget.querySelector('[data-fipe-model-select]');
  const yearSelect = widget.querySelector('[data-fipe-year-select]');
  const statusBadge = document.querySelector('[data-fipe-status]');
  const resultBox = document.querySelector('[data-fipe-result]');

  const brandCodeInput = form?.querySelector('[name="fipe_marca_codigo"]');
  const modelCodeInput = form?.querySelector('[name="fipe_modelo_codigo"]');
  const yearCodeInput = form?.querySelector('[name="fipe_ano_codigo"]');
  const codeFipeInput = form?.querySelector('[name="codigo_fipe"]');
  const referenceInput = form?.querySelector('[name="mes_referencia_fipe"]');
  const brandNameInput = form?.querySelector('[name="marca"]');
  const modelNameInput = form?.querySelector('[name="modelo"]');
  const versionInput = form?.querySelector('[name="versao"]');
  const fuelInput = form?.querySelector('[name="combustivel"]');

  function setStatus(message, state = 'info') {
    if (!statusBadge) return;
    statusBadge.textContent = message;
    statusBadge.className = 'badge badge-outline whitespace-nowrap';
    if (state === 'loading') statusBadge.classList.add('badge-warning');
    if (state === 'success') statusBadge.classList.add('badge-success');
    if (state === 'error') statusBadge.classList.add('badge-error');
  }

  function showResult(message, type = 'info') {
    if (!resultBox) return;
    resultBox.textContent = message;
    resultBox.classList.remove('hidden', 'alert-info', 'alert-success', 'alert-error');
    resultBox.classList.add(type === 'error' ? 'alert-error' : type === 'success' ? 'alert-success' : 'alert-info');
  }

  function clearResult() {
    if (!resultBox) return;
    resultBox.textContent = '';
    resultBox.classList.add('hidden');
  }

  function resetSelect(select, placeholder = 'Selecione') {
    if (!select) return;
    select.innerHTML = `<option value="">${placeholder}</option>`;
    select.disabled = true;
  }

  function fillSelect(select, items, placeholder = 'Selecione') {
    resetSelect(select, placeholder);
    const fragment = document.createDocumentFragment();
    items.forEach((item) => {
      const option = document.createElement('option');
      option.value = item.code;
      option.textContent = item.name;
      option.dataset.name = item.name;
      fragment.appendChild(option);
    });
    select.appendChild(fragment);
    select.disabled = false;
  }

  async function fetchResults(url, params) {
    const query = new URLSearchParams(params);
    const response = await fetch(`${url}?${query.toString()}`, {
      headers: { 'Accept': 'application/json' }
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Erro ao consultar a FIPE.');
    }
    return data;
  }

  async function loadBrands({ preserve = false } = {}) {
    if (!typeSelect || !brandSelect) return;
    setStatus('Carregando marcas...', 'loading');
    clearResult();
    resetSelect(brandSelect);
    resetSelect(modelSelect);
    resetSelect(yearSelect);

    try {
      const data = await fetchResults(widget.dataset.brandsUrl, { tipo: typeSelect.value });
      fillSelect(brandSelect, data.results || [], 'Selecione a marca');
      const current = preserve ? (brandSelect.dataset.current || brandCodeInput?.value || '') : '';
      if (current) {
        brandSelect.value = current;
        if (brandSelect.value) await loadModels({ preserve: true });
      }
      setStatus('FIPE pronta', 'success');
    } catch (error) {
      setStatus('Erro FIPE', 'error');
      showResult(error.message, 'error');
    }
  }

  async function loadModels({ preserve = false } = {}) {
    if (!brandSelect?.value) return;
    setStatus('Carregando modelos...', 'loading');
    clearResult();
    resetSelect(modelSelect);
    resetSelect(yearSelect);
    brandCodeInput.value = brandSelect.value;
    brandNameInput.value = brandSelect.selectedOptions[0]?.dataset.name || brandSelect.selectedOptions[0]?.textContent || brandNameInput.value;

    try {
      const data = await fetchResults(widget.dataset.modelsUrl, { tipo: typeSelect.value, marca: brandSelect.value });
      fillSelect(modelSelect, data.results || [], 'Selecione o modelo');
      const current = preserve ? (modelSelect.dataset.current || modelCodeInput?.value || '') : '';
      if (current) {
        modelSelect.value = current;
        if (modelSelect.value) await loadYears({ preserve: true });
      }
      setStatus('FIPE pronta', 'success');
    } catch (error) {
      setStatus('Erro FIPE', 'error');
      showResult(error.message, 'error');
    }
  }

  async function loadYears({ preserve = false } = {}) {
    if (!brandSelect?.value || !modelSelect?.value) return;
    setStatus('Carregando anos/versões...', 'loading');
    clearResult();
    resetSelect(yearSelect);
    modelCodeInput.value = modelSelect.value;
    modelNameInput.value = modelSelect.selectedOptions[0]?.dataset.name || modelSelect.selectedOptions[0]?.textContent || modelNameInput.value;

    try {
      const data = await fetchResults(widget.dataset.yearsUrl, { tipo: typeSelect.value, marca: brandSelect.value, modelo: modelSelect.value });
      fillSelect(yearSelect, data.results || [], 'Selecione o ano/versão');
      const current = preserve ? (yearSelect.dataset.current || yearCodeInput?.value || '') : '';
      if (current) {
        yearSelect.value = current;
        if (yearSelect.value) await loadValue();
      }
      setStatus('FIPE pronta', 'success');
    } catch (error) {
      setStatus('Erro FIPE', 'error');
      showResult(error.message, 'error');
    }
  }

  async function loadValue() {
    if (!brandSelect?.value || !modelSelect?.value || !yearSelect?.value) return;
    setStatus('Consultando detalhe...', 'loading');
    clearResult();
    yearCodeInput.value = yearSelect.value;

    try {
      const data = await fetchResults(widget.dataset.valueUrl, {
        tipo: typeSelect.value,
        marca: brandSelect.value,
        modelo: modelSelect.value,
        ano: yearSelect.value
      });

      brandNameInput.value = data.brand || brandSelect.selectedOptions[0]?.textContent || brandNameInput.value;
      modelNameInput.value = data.model || modelSelect.selectedOptions[0]?.textContent || modelNameInput.value;
      const versionParts = [data.modelYear, data.fuel].filter(Boolean);
      versionInput.value = versionParts.length ? versionParts.join(' - ') : (yearSelect.selectedOptions[0]?.textContent || versionInput.value);
      codeFipeInput.value = data.codeFipe || '';
      referenceInput.value = data.referenceMonth || '';

      const normalizedFuel = normalizeFuel(data.fuel);
      if (fuelInput && normalizedFuel) {
        fuelInput.value = normalizedFuel;
      }

      const messageParts = [];
      if (data.codeFipe) messageParts.push(`Código FIPE: ${data.codeFipe}`);
      if (data.referenceMonth) messageParts.push(`Referência: ${data.referenceMonth}`);
      if (data.price) messageParts.push(`Valor FIPE: ${data.price}`);
      showResult(messageParts.join(' | ') || 'Dados FIPE preenchidos com sucesso.', 'success');
      setStatus('FIPE preenchida', 'success');
    } catch (error) {
      setStatus('Erro FIPE', 'error');
      showResult(error.message, 'error');
    }
  }

  typeSelect?.addEventListener('change', () => {
    brandCodeInput.value = '';
    modelCodeInput.value = '';
    yearCodeInput.value = '';
    codeFipeInput.value = '';
    referenceInput.value = '';
    brandSelect.dataset.current = '';
    modelSelect.dataset.current = '';
    yearSelect.dataset.current = '';
    loadBrands();
  });
  brandSelect?.addEventListener('change', () => loadModels());
  modelSelect?.addEventListener('change', () => loadYears());
  yearSelect?.addEventListener('change', () => loadValue());

  loadBrands({ preserve: true });
}

document.addEventListener('DOMContentLoaded', () => {
  setupVehicleMasks();
  setupFipeLookup();
});
