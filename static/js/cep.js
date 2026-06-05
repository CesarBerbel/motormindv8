function onlyDigits(value) {
  return (value || '').replace(/\D/g, '');
}

function maskCepValue(value) {
  const digits = onlyDigits(value).slice(0, 8);

  if (digits.length <= 5) {
    return digits;
  }

  return `${digits.slice(0, 5)}-${digits.slice(5)}`;
}

async function buscarCep(cep) {
  const cleanedCep = onlyDigits(cep);

  if (cleanedCep.length !== 8) {
    return;
  }

  const cepInput = document.getElementById('id_cep');

  try {
    const response = await fetch(`https://viacep.com.br/ws/${cleanedCep}/json/`);
    const data = await response.json();

    if (data.erro) {
      alert('CEP não encontrado. Preencha o endereço manualmente.');
      return;
    }

    const mapping = {
      id_logradouro: data.logradouro,
      id_bairro: data.bairro,
      id_cidade: data.localidade,
      id_uf: data.uf
    };

    for (const [fieldId, value] of Object.entries(mapping)) {
      const field = document.getElementById(fieldId);
      if (field && !field.value) {
        field.value = value || '';
      }
    }
  } catch (error) {
    console.error('Erro ao buscar CEP:', error);
    alert('Não foi possível buscar o CEP agora. Preencha o endereço manualmente.');
  } finally {
    if (cepInput) {
      cepInput.value = maskCepValue(cepInput.value);
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const cepInput = document.getElementById('id_cep');

  if (!cepInput) {
    return;
  }

  cepInput.addEventListener('input', () => {
    cepInput.value = maskCepValue(cepInput.value);
  });

  cepInput.addEventListener('blur', () => buscarCep(cepInput.value));
});
