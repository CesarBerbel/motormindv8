(function () {
  function formatBytes(bytes) {
    if (!bytes) return '0 KB';
    var units = ['B', 'KB', 'MB', 'GB'];
    var size = bytes;
    var unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size = size / 1024;
      unitIndex += 1;
    }
    return (unitIndex === 0 ? size : size.toFixed(1)).replace('.', ',') + ' ' + units[unitIndex];
  }

  function createInput(originalInput, index) {
    var input = originalInput.cloneNode(false);
    input.value = '';
    input.id = originalInput.id + '_extra_' + index;
    input.name = originalInput.name;
    input.required = false;
    input.className = originalInput.className;
    input.setAttribute('accept', 'image/*');
    input.setAttribute('capture', 'environment');
    input.setAttribute('multiple', 'multiple');
    return input;
  }

  function refreshSummary(container, list) {
    var inputs = container.querySelectorAll('input[type="file"][name="fotos"]');
    var files = [];
    inputs.forEach(function (input) {
      Array.prototype.forEach.call(input.files || [], function (file) {
        files.push(file);
      });
    });

    list.innerHTML = '';
    if (!files.length) {
      var empty = document.createElement('p');
      empty.className = 'text-sm text-base-content/60';
      empty.textContent = 'Nenhuma nova foto selecionada.';
      list.appendChild(empty);
      return;
    }

    files.forEach(function (file, index) {
      var row = document.createElement('div');
      row.className = 'flex items-center justify-between gap-3 rounded-lg bg-base-200 px-3 py-2 text-sm';

      var name = document.createElement('span');
      name.className = 'min-w-0 truncate';
      name.textContent = (index + 1) + '. ' + file.name;

      var size = document.createElement('span');
      size.className = 'shrink-0 text-base-content/60';
      size.textContent = formatBytes(file.size);

      row.appendChild(name);
      row.appendChild(size);
      list.appendChild(row);
    });
  }

  function enhanceCheckinPhotos() {
    var originalInput = document.querySelector('input[type="file"][name="fotos"]');
    if (!originalInput || originalInput.dataset.multiPhotoEnhanced === 'true') return;
    originalInput.dataset.multiPhotoEnhanced = 'true';
    originalInput.setAttribute('multiple', 'multiple');
    originalInput.setAttribute('accept', 'image/*');
    originalInput.setAttribute('capture', 'environment');

    var container = document.createElement('div');
    container.className = 'mt-2 space-y-3 rounded-box border border-dashed border-base-300 bg-base-200/40 p-3';

    var helper = document.createElement('p');
    helper.className = 'text-sm text-base-content/70';
    helper.textContent = 'Selecione várias fotos de uma vez ou use o botão abaixo para abrir a câmera novamente e adicionar novas fotos.';

    var fields = document.createElement('div');
    fields.className = 'space-y-3';

    var addButton = document.createElement('button');
    addButton.type = 'button';
    addButton.className = 'btn btn-outline btn-sm whitespace-nowrap';
    addButton.textContent = 'Adicionar outra foto';

    var listTitle = document.createElement('p');
    listTitle.className = 'text-sm font-medium';
    listTitle.textContent = 'Novas fotos selecionadas';

    var list = document.createElement('div');
    list.className = 'space-y-2';

    originalInput.parentNode.insertBefore(container, originalInput.nextSibling);
    fields.appendChild(originalInput);
    container.appendChild(helper);
    container.appendChild(fields);
    container.appendChild(addButton);
    container.appendChild(listTitle);
    container.appendChild(list);

    var count = 0;
    addButton.addEventListener('click', function () {
      count += 1;
      var input = createInput(originalInput, count);
      fields.appendChild(input);
      input.addEventListener('change', function () {
        refreshSummary(container, list);
      });
      input.click();
    });

    fields.addEventListener('change', function () {
      refreshSummary(container, list);
    });

    refreshSummary(container, list);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhanceCheckinPhotos);
  } else {
    enhanceCheckinPhotos();
  }
})();
