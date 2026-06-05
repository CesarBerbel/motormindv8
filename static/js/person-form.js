function digitsOnly(value) {
  return (value || '').replace(/\D/g, '');
}

function maskCpf(value) {
  const digits = digitsOnly(value).slice(0, 11);

  if (digits.length <= 3) {
    return digits;
  }

  if (digits.length <= 6) {
    return `${digits.slice(0, 3)}.${digits.slice(3)}`;
  }

  if (digits.length <= 9) {
    return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6)}`;
  }

  return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9)}`;
}

function maskCnpj(value) {
  const digits = digitsOnly(value).slice(0, 14);

  if (digits.length <= 2) {
    return digits;
  }

  if (digits.length <= 5) {
    return `${digits.slice(0, 2)}.${digits.slice(2)}`;
  }

  if (digits.length <= 8) {
    return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5)}`;
  }

  if (digits.length <= 12) {
    return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8)}`;
  }

  return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8, 12)}-${digits.slice(12)}`;
}

function maskPhone(value) {
  const digits = digitsOnly(value).slice(0, 11);

  if (digits.length <= 2) {
    return digits;
  }

  if (digits.length <= 6) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
  }

  if (digits.length <= 10) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
  }

  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

function maskCep(value) {
  const digits = digitsOnly(value).slice(0, 8);

  if (digits.length <= 5) {
    return digits;
  }

  return `${digits.slice(0, 5)}-${digits.slice(5)}`;
}

function updatePersonLabels() {
  const tipoPessoaField = document.getElementById('id_tipo_pessoa');

  if (!tipoPessoaField) {
    return;
  }

  const isFisica = tipoPessoaField.value === 'fisica';

  const labels = {
    id_nome_razao_social: isFisica ? 'Nome' : 'Razão social',
    id_documento: isFisica ? 'CPF' : 'CNPJ',
    id_data_nascimento_fundacao: isFisica ? 'Data de nascimento' : 'Data de fundação'
  };

  for (const [fieldId, labelText] of Object.entries(labels)) {
    const label = document.querySelector(`label[for="${fieldId}"] .label-text`)
      || document.querySelector(`label[for="${fieldId}"]`);

    if (label) {
      const requiredMark = label.querySelector('.text-error');
      label.textContent = labelText;

      if (requiredMark) {
        label.appendChild(document.createTextNode(' '));
        label.appendChild(requiredMark);
      }
    }
  }
}

function updateDocumentMask() {
  const tipoPessoaField = document.getElementById('id_tipo_pessoa');
  const documentoField = document.getElementById('id_documento');

  if (!tipoPessoaField || !documentoField) {
    return;
  }

  const isFisica = tipoPessoaField.value === 'fisica';
  documentoField.placeholder = isFisica ? '000.000.000-00' : '00.000.000/0000-00';
  documentoField.maxLength = isFisica ? 14 : 18;
  documentoField.value = isFisica ? maskCpf(documentoField.value) : maskCnpj(documentoField.value);
}

function bindMasks() {
  const documentoField = document.getElementById('id_documento');
  const whatsappField = document.getElementById('id_whatsapp');
  const cepField = document.getElementById('id_cep');

  if (documentoField) {
    documentoField.addEventListener('input', updateDocumentMask);
    updateDocumentMask();
  }

  if (whatsappField) {
    whatsappField.addEventListener('input', () => {
      whatsappField.value = maskPhone(whatsappField.value);
    });
    whatsappField.value = maskPhone(whatsappField.value);
  }

  if (cepField) {
    cepField.addEventListener('input', () => {
      cepField.value = maskCep(cepField.value);
    });
    cepField.value = maskCep(cepField.value);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const tipoPessoaField = document.getElementById('id_tipo_pessoa');

  if (!tipoPessoaField) {
    return;
  }

  updatePersonLabels();
  bindMasks();

  tipoPessoaField.addEventListener('change', () => {
    updatePersonLabels();
    updateDocumentMask();
  });
});
