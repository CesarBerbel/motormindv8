function debounce(callback, delay = 250) {
  let timeoutId;

  return (...args) => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => callback(...args), delay);
  };
}

function clearAutocomplete(resultsBox, input) {
  resultsBox.innerHTML = '';
  resultsBox.classList.add('hidden');
  input.setAttribute('aria-expanded', 'false');
}

function renderAutocompleteResults(resultsBox, input, results) {
  resultsBox.innerHTML = '';

  if (!results.length) {
    const emptyItem = document.createElement('div');
    emptyItem.className = 'px-3 py-2 text-sm text-base-content/60';
    emptyItem.textContent = 'Nenhum resultado encontrado.';
    resultsBox.appendChild(emptyItem);
    resultsBox.classList.remove('hidden');
    input.setAttribute('aria-expanded', 'true');
    return;
  }

  results.forEach((item) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'block w-full px-3 py-2 text-left hover:bg-base-200 focus:bg-base-200 focus:outline-none';

    const label = document.createElement('span');
    label.className = 'block truncate text-sm font-medium';
    label.textContent = item.label;

    const subtitle = document.createElement('span');
    subtitle.className = 'block truncate text-xs text-base-content/60';
    subtitle.textContent = item.subtitle || '';

    button.appendChild(label);
    button.appendChild(subtitle);

    button.addEventListener('click', () => {
      input.value = item.value || item.label;
      clearAutocomplete(resultsBox, input);
      input.form?.submit();
    });

    resultsBox.appendChild(button);
  });

  resultsBox.classList.remove('hidden');
  input.setAttribute('aria-expanded', 'true');
}

async function fetchAutocomplete(input, resultsBox) {
  const term = input.value.trim();

  if (term.length < 2) {
    clearAutocomplete(resultsBox, input);
    return;
  }

  const url = new URL(input.dataset.autocompleteUrl, window.location.origin);
  url.searchParams.set('q', term);

  try {
    const response = await fetch(url, {
      headers: {
        Accept: 'application/json'
      }
    });

    if (!response.ok) {
      clearAutocomplete(resultsBox, input);
      return;
    }

    const data = await response.json();
    renderAutocompleteResults(resultsBox, input, data.results || []);
  } catch (error) {
    console.error('Erro ao buscar sugestões:', error);
    clearAutocomplete(resultsBox, input);
  }
}

function setupAdvancedSearchAutocomplete() {
  const inputs = document.querySelectorAll('[data-autocomplete-url]');

  inputs.forEach((input) => {
    const wrapper = input.closest('[data-autocomplete-wrapper]');
    const resultsBox = wrapper?.querySelector('[data-autocomplete-results]');

    if (!wrapper || !resultsBox) {
      return;
    }

    const debouncedFetch = debounce(() => fetchAutocomplete(input, resultsBox));

    input.addEventListener('input', debouncedFetch);
    input.addEventListener('focus', () => {
      if (input.value.trim().length >= 2) {
        fetchAutocomplete(input, resultsBox);
      }
    });

    input.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        clearAutocomplete(resultsBox, input);
      }
    });

    document.addEventListener('click', (event) => {
      if (!wrapper.contains(event.target)) {
        clearAutocomplete(resultsBox, input);
      }
    });
  });
}

function setupUfUppercase() {
  document.querySelectorAll('input[name="uf"]').forEach((input) => {
    input.addEventListener('input', () => {
      input.value = input.value.toUpperCase().slice(0, 2);
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  setupAdvancedSearchAutocomplete();
  setupUfUppercase();
});
