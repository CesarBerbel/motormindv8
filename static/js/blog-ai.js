(function () {
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input && input.value) return input.value;
    return getCookie('csrftoken');
  }

  const button = document.querySelector('[data-blog-ai-generate]');
  if (!button) return;

  const notice = document.querySelector('[data-blog-ai-notice]');
  function setNotice(message, type) {
    if (!notice) return;
    notice.textContent = message || '';
    notice.className = 'mt-2 text-sm ' + (type === 'error' ? 'text-error' : 'text-base-content/70');
  }

  button.addEventListener('click', async function () {
    const endpoint = button.dataset.blogAiUrl;
    const subjectEl = document.querySelector('#blog-ai-subject');
    const subject = (subjectEl ? subjectEl.value : '').trim();
    if (!subject) {
      setNotice('Digite um assunto para gerar o artigo.', 'error');
      if (subjectEl) subjectEl.focus();
      return;
    }

    const titulo = document.querySelector('#id_titulo');
    const resumo = document.querySelector('#id_resumo');
    const conteudo = document.querySelector('#id_conteudo');

    if (conteudo && conteudo.value.trim() &&
        !window.confirm('Isto vai substituir o título, resumo e conteúdo atuais do artigo. Continuar?')) {
      return;
    }

    const originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = 'Gerando...';
    setNotice('Gerando artigo com IA. Isto pode levar alguns segundos...', 'info');

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ assunto: subject })
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Não foi possível gerar o artigo.');
      }
      if (titulo && data.titulo) titulo.value = data.titulo;
      if (resumo && typeof data.resumo === 'string') resumo.value = data.resumo;
      if (conteudo && data.conteudo) {
        conteudo.value = data.conteudo;
        conteudo.dispatchEvent(new Event('input', { bubbles: true }));
      }
      setNotice('Artigo gerado! Revise o conteúdo e ajuste antes de publicar.', 'info');
    } catch (error) {
      setNotice(error.message || 'Erro ao gerar o artigo.', 'error');
    } finally {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  });
})();
