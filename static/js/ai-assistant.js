(function () {
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }

  // Com CSRF_COOKIE_HTTPONLY=True o cookie csrftoken nao e legivel por JS.
  // Lemos o token da meta tag renderizada pelo servidor (ou de um campo
  // csrfmiddlewaretoken no formulario) e usamos o cookie apenas como fallback.
  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input && input.value) return input.value;
    return getCookie('csrftoken');
  }

  function findTarget(button) {
    const selector = button.dataset.aiTarget;
    if (selector) {
      const direct = document.querySelector(selector);
      if (direct) return direct;
    }
    const targetId = button.dataset.aiTargetId;
    if (targetId) return document.getElementById(targetId);
    return null;
  }

  function readValue(selector) {
    const el = document.querySelector(selector);
    return el ? (el.value || el.textContent || '').trim() : '';
  }

  function buildContext(button) {
    const context = {};
    const form = button.closest('form') || document;
    const selectors = {
      cliente: '#id_cliente option:checked',
      veiculo: '#id_veiculo option:checked',
      problema_relatado: '#id_problema_relatado',
      diagnostico: '#id_diagnostico',
      observacao: '#id_observacao',
      assunto: '#id_assunto',
      template_selecionado: '#id_template option:checked',
      tipo_template: '#id_tipo option:checked',
      nome_template: '#id_nome',
      mensagem: '#id_corpo'
    };

    Object.keys(selectors).forEach(function (key) {
      const el = form.querySelector(selectors[key]) || document.querySelector(selectors[key]);
      if (!el) return;
      const value = (el.value || el.textContent || '').trim();
      if (value) context[key] = value;
    });

    if (button.dataset.aiContext) {
      try {
        Object.assign(context, JSON.parse(button.dataset.aiContext));
      } catch (error) {
        console.warn('Contexto de IA inválido:', error);
      }
    }
    return context;
  }

  function setNotice(button, message, type) {
    let container = button.closest('[data-ai-field-wrapper]') || button.parentElement;
    if (!container) container = button;
    let notice = container.querySelector('[data-ai-inline-notice]');
    if (!notice) {
      notice = document.createElement('div');
      notice.dataset.aiInlineNotice = 'true';
      notice.className = 'mt-2 text-xs';
      container.appendChild(notice);
    }
    notice.textContent = message || '';
    notice.className = 'mt-2 text-xs ' + (type === 'error' ? 'text-error' : 'text-base-content/60');
  }

  async function requestAI(button) {
    const target = findTarget(button);
    const action = button.dataset.aiAction || 'general';
    const endpoint = button.dataset.aiUrl || window.MotorMindAIEndpoint || '/ia/assistir-texto/';
    if (!target) {
      setNotice(button, 'Campo de destino da IA não encontrado.', 'error');
      return;
    }

    const originalLabel = button.dataset.aiOriginalLabel || button.textContent;
    button.dataset.aiOriginalLabel = originalLabel;
    button.disabled = true;
    button.textContent = 'IA...';
    setNotice(button, 'Gerando sugestão...', 'info');

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
          action: action,
          text: target.value || '',
          context: buildContext(button)
        })
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Não foi possível gerar a sugestão.');
      }
      target.value = data.text || '';
      target.dispatchEvent(new Event('input', { bubbles: true }));
      target.dispatchEvent(new Event('change', { bubbles: true }));
      setNotice(button, 'Texto substituído pela sugestão da IA.', 'info');
    } catch (error) {
      setNotice(button, error.message || 'Erro ao chamar a IA.', 'error');
    } finally {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }

  async function testConnection(button) {
    const endpoint = button.dataset.aiTestUrl;
    const resultBox = document.querySelector('[data-ai-test-result]');
    const originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = 'Testando...';
    if (resultBox) {
      resultBox.className = 'alert alert-info';
      resultBox.textContent = 'Testando conexão com a IA...';
    }
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({})
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'Falha no teste da IA.');
      if (resultBox) {
        resultBox.className = 'alert alert-success';
        resultBox.textContent = `${data.text} Provedor: ${data.provider || '-'} Modelo: ${data.model || '-'}`;
      }
    } catch (error) {
      if (resultBox) {
        resultBox.className = 'alert alert-error';
        resultBox.textContent = error.message || 'Erro ao testar a IA.';
      }
    } finally {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }

  document.addEventListener('click', function (event) {
    const assistButton = event.target.closest('[data-ai-assist-button]');
    if (assistButton) {
      event.preventDefault();
      requestAI(assistButton);
      return;
    }
    const testButton = event.target.closest('[data-ai-test-button]');
    if (testButton) {
      event.preventDefault();
      testConnection(testButton);
    }
  });
})();
