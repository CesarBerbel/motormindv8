(function () {
  function getOptionLabel(vehicle) {
    return vehicle.label || [vehicle.placa, `${vehicle.marca || ''} ${vehicle.modelo || ''}`.trim(), vehicle.versao].filter(Boolean).join(' - ');
  }

  function setLoading(select, isLoading) {
    if (!select) return;
    select.disabled = isLoading;
    select.classList.toggle('opacity-60', isLoading);
  }

  function replaceVehicleOptions(vehicleSelect, vehicles, selectedId) {
    if (!vehicleSelect) return;

    const currentValue = selectedId || vehicleSelect.value;
    vehicleSelect.innerHTML = '';

    const emptyOption = document.createElement('option');
    emptyOption.value = '';
    emptyOption.textContent = '---------';
    vehicleSelect.appendChild(emptyOption);

    vehicles.forEach((vehicle) => {
      const option = document.createElement('option');
      option.value = String(vehicle.id);
      option.textContent = getOptionLabel(vehicle);
      vehicleSelect.appendChild(option);
    });

    const hasCurrentValue = vehicles.some((vehicle) => String(vehicle.id) === String(currentValue));
    if (hasCurrentValue) {
      vehicleSelect.value = String(currentValue);
    } else if (vehicles.length > 0) {
      vehicleSelect.value = String(vehicles[0].id);
    } else {
      vehicleSelect.value = '';
    }

    vehicleSelect.dispatchEvent(new Event('change', { bubbles: true }));
  }

  async function loadVehicles({ endpoint, customerId, vehicleSelect, selectedId }) {
    if (!endpoint || !customerId || !vehicleSelect) {
      replaceVehicleOptions(vehicleSelect, [], '');
      return;
    }

    const url = new URL(endpoint, window.location.origin);
    url.searchParams.set('cliente', customerId);

    setLoading(vehicleSelect, true);
    try {
      const response = await fetch(url.toString(), {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      if (!response.ok) throw new Error('Falha ao carregar veículos do cliente.');
      const data = await response.json();
      replaceVehicleOptions(vehicleSelect, data.results || [], selectedId || '');
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(vehicleSelect, false);
    }
  }

  function setupWorkOrderCustomerVehicle() {
    const form = document.querySelector('[data-work-order-form]');
    if (!form) return;

    const customerSelect = form.querySelector('[data-work-order-customer]');
    const vehicleSelect = form.querySelector('[data-work-order-vehicle]');
    const endpoint = form.dataset.workOrderVehiclesUrl;
    const initialVehicleId = form.dataset.currentVehicleId || (vehicleSelect ? vehicleSelect.value : '');

    if (!customerSelect || !vehicleSelect || !endpoint) return;
    if (customerSelect.disabled || vehicleSelect.disabled || form.dataset.workOrderLocked === 'true') return;

    customerSelect.addEventListener('change', () => {
      loadVehicles({
        endpoint,
        customerId: customerSelect.value,
        vehicleSelect,
        selectedId: ''
      });
    });

    if (customerSelect.value) {
      loadVehicles({
        endpoint,
        customerId: customerSelect.value,
        vehicleSelect,
        selectedId: initialVehicleId
      });
    }
  }

  document.addEventListener('DOMContentLoaded', setupWorkOrderCustomerVehicle);
})();
