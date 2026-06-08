import json
import logging
import re
from dataclasses import dataclass
from urllib import request as urlrequest
from urllib import error as urlerror
from urllib.parse import urlparse

from django.core.cache import cache
from django.utils.html import strip_tags

from .models import AIAssistantAction, AIInteractionLog, AIProvider, AISettings

logger = logging.getLogger('ai_assistant')

# Limites de timeout para evitar chamadas que bloqueiam o worker indefinidamente.
MIN_TIMEOUT = 1
MAX_TIMEOUT = 60
DEFAULT_TIMEOUT = 20

# Rate limiting por utilizador (janela deslizante simples via cache).
AI_RATE_LIMIT = 20
AI_RATE_WINDOW_SECONDS = 60

# Hosts de loopback onde se aceita http simples (ex.: Ollama local).
LOOPBACK_HOSTS = {'localhost', '127.0.0.1', '::1', '0.0.0.0'}


class AIServiceError(Exception):
    pass


class AIRateLimitError(AIServiceError):
    pass


def clamp_timeout(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = DEFAULT_TIMEOUT
    return max(MIN_TIMEOUT, min(value or DEFAULT_TIMEOUT, MAX_TIMEOUT))


def mask_secret(value):
    if not value:
        return ''
    if len(value) <= 8:
        return '••••'
    return f'{value[:4]}••••{value[-4:]}'


def validate_provider_url(url):
    """Valida o endpoint antes de qualquer chamada externa (anti-SSRF).

    - Apenas http/https sao aceites (bloqueia file://, gopher:// etc.).
    - http simples so e permitido para hosts de loopback; endpoints externos
      tem de usar HTTPS.
    """
    if not url:
        raise AIServiceError('Endpoint da IA não configurado.')
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'}:
        raise AIServiceError('O endpoint da IA deve usar http ou https.')
    if not parsed.hostname:
        raise AIServiceError('Endpoint da IA inválido.')
    host = parsed.hostname.lower()
    if parsed.scheme == 'http' and host not in LOOPBACK_HOSTS:
        raise AIServiceError('Endpoints externos da IA devem usar HTTPS.')
    return url


def check_ai_rate_limit(user, limit=AI_RATE_LIMIT, window=AI_RATE_WINDOW_SECONDS):
    """Devolve True se o pedido for permitido dentro da janela atual."""
    user_id = getattr(user, 'pk', None) or 'anon'
    key = f'ai_assist_rate:{user_id}'
    if cache.add(key, 1, timeout=window):
        return True
    try:
        current = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window)
        return True
    return current <= limit


@dataclass
class AIResult:
    text: str
    provider: str
    model: str
    raw: dict | None = None


def clean_text(value):
    return (strip_tags(value or '').replace('\r\n', '\n').replace('\r', '\n')).strip()


def limit_text(value, limit):
    value = clean_text(value)
    if not limit or len(value) <= limit:
        return value
    return value[:limit].rstrip() + '…'


def get_action_instruction(settings, action):
    if action == AIAssistantAction.IMPROVE_PROBLEM:
        return settings.instrucao_problema_relatado or ''
    if action == AIAssistantAction.IMPROVE_DIAGNOSIS:
        return settings.instrucao_diagnostico or ''
    if action == AIAssistantAction.SUGGEST_OBSERVATION:
        return settings.instrucao_observacao or ''
    if action in {
        AIAssistantAction.IMPROVE_MESSAGE,
        AIAssistantAction.EMAIL_TEMPLATE,
        AIAssistantAction.WHATSAPP_TEMPLATE,
    }:
        return settings.instrucao_template_mensagem or ''
    return ''


def format_context_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def build_prompt(settings, action, text, context=None):
    context = context or {}
    action_label = dict(AIAssistantAction.choices).get(action, action)
    specific_instruction = get_action_instruction(settings, action)
    context_lines = []
    for key, value in context.items():
        if value in (None, ''):
            continue
        label = str(key).replace('_', ' ').capitalize()
        context_lines.append(f'{label}: {format_context_value(value)}')

    instructions = [
        settings.instrucoes_gerais or '',
        f'Tom desejado: {settings.tom_resposta or "profissional e objetivo"}.',
        f'Características da oficina: {settings.caracteristicas_oficina or "não informado"}.',
        f'Limite aproximado: {settings.limite_caracteres_resposta} caracteres.',
        'Retorne apenas o texto final, sem explicações sobre o que você fez.',
        'Não invente dados técnicos, medições, peças, códigos de falha, prazos, valores ou serviços não informados.',
        'Use o contexto informado quando ele for relevante para o campo solicitado.',
    ]
    if specific_instruction:
        instructions.append(f'Instrução específica deste campo: {specific_instruction}')

    if action == AIAssistantAction.IMPROVE_PROBLEM:
        task = (
            'Melhorar o problema relatado pelo cliente para uso na OS. '
            'Não transforme o relato em diagnóstico técnico; mantenha o foco no que o cliente percebeu.'
        )
    elif action == AIAssistantAction.IMPROVE_DIAGNOSIS:
        task = (
            'Melhorar e detalhar o diagnóstico técnico da oficina, explicando serviço recomendado, desmontagem, verificações, esforço realizado '
            'e próximos passos, somente com base nas informações disponíveis.'
        )
    elif action == AIAssistantAction.SUGGEST_OBSERVATION:
        task = (
            'Sugerir uma observação pertinente para a OS usando o contexto disponível: cliente, veículo, problema relatado, diagnóstico, itens, status '
            'e necessidades de autorização/peças/retorno.'
        )
    elif action == AIAssistantAction.EMAIL_TEMPLATE:
        task = (
            'Criar um template de email profissional considerando o contexto, o tipo de template e o momento da OS. '
            'Preserve e use variáveis Django quando fizer sentido, como {{ cliente.nome_razao_social }}, {{ ordem_servico.codigo }}, {{ veiculo }} e {{ link_aprovacao }}.'
        )
    elif action == AIAssistantAction.WHATSAPP_TEMPLATE:
        task = (
            'Criar um template curto para WhatsApp considerando o contexto, o tipo de template e o momento da OS. '
            'Preserve e use variáveis Django quando fizer sentido.'
        )
    elif action == AIAssistantAction.IMPROVE_MESSAGE:
        task = (
            'Melhorar o texto do template/mensagem considerando o contexto, sem remover variáveis do sistema, placeholders ou informações operacionais.'
        )
    else:
        task = action_label

    prompt = '\n'.join(part for part in [
        'Você é um assistente de texto para uma oficina mecânica usando um sistema de OS.',
        *instructions,
        f'Tarefa: {task}',
        'Contexto:\n' + ('\n'.join(context_lines) if context_lines else 'Sem contexto adicional.'),
        'Texto atual:\n' + (text or 'Sem texto atual. Gere uma sugestão adequada ao contexto.'),
    ] if part)
    return prompt


def local_generate(settings, action, text, context=None):
    text = clean_text(text)
    context = context or {}
    problem = clean_text(context.get('problema_relatado'))
    diagnosis = clean_text(context.get('diagnostico'))
    obs = clean_text(context.get('observacao'))
    vehicle = clean_text(context.get('veiculo'))
    customer = clean_text(context.get('cliente'))
    template_type = clean_text(context.get('tipo_template'))
    template_name = clean_text(context.get('nome_template')) or clean_text(context.get('template_selecionado'))
    subject = clean_text(context.get('assunto')) or 'Atualização da sua ordem de serviço'

    if action == AIAssistantAction.IMPROVE_PROBLEM:
        base = text or problem or 'Sintoma informado pelo cliente ainda não detalhado.'
        result = f'Cliente relata {base[0].lower() + base[1:] if len(base) > 1 else base}'.strip()
        if not result.endswith('.'):
            result += '.'
    elif action == AIAssistantAction.IMPROVE_DIAGNOSIS:
        base = text or diagnosis or 'Diagnóstico técnico pendente de detalhamento.'
        result = (
            f'Diagnóstico técnico: {base}\n\n'
            'Serviço recomendado: realizar conferência do conjunto relacionado ao sintoma, com desmontagem apenas dos componentes necessários para acesso e validação visual/técnica.\n\n'
            'Esforço realizado: registrar testes executados, condição encontrada, peças ou sistemas afetados e evidências observadas. Dados não medidos ou não confirmados devem permanecer como pendentes de validação antes da execução final.'
        )
    elif action == AIAssistantAction.SUGGEST_OBSERVATION:
        parts = []
        if customer:
            parts.append(f'cliente {customer}')
        if vehicle:
            parts.append(f'veículo {vehicle}')
        if problem:
            parts.append(f'problema relatado: {problem}')
        if diagnosis:
            parts.append(f'diagnóstico: {diagnosis}')
        if obs:
            parts.append(f'observação atual: {obs}')
        base = '; '.join(parts)
        result = (
            f'Considerando {base}, ' if base else ''
        ) + 'recomenda-se manter o cliente informado antes de serviços adicionais, confirmar autorização formal quando houver mudança de escopo e validar disponibilidade de peças antes da execução.'
    elif action == AIAssistantAction.EMAIL_TEMPLATE:
        context_note = f' sobre {template_type}' if template_type else ''
        result = (
            f'Assunto: {subject}\n\n'
            'Olá, {{ cliente.nome_razao_social }}.\n\n'
            f'Estamos entrando em contato{context_note} referente à OS {{ ordem_servico.codigo }} do veículo {{ veiculo }}.\n\n'
            'Segue a atualização: {{ mensagem }}\n\n'
            'Quando houver orçamento ou aprovação pendente, acesse: {{ link_aprovacao }}\n\n'
            'Ficamos à disposição para esclarecer qualquer dúvida.\n\nAtenciosamente,\nEquipe da oficina'
        )
    elif action == AIAssistantAction.WHATSAPP_TEMPLATE:
        prefix = f'{template_name}: ' if template_name else ''
        result = (
            f'{prefix}Olá, {{ cliente.nome_razao_social }}! Temos uma atualização sobre a OS {{ ordem_servico.codigo }} '
            'do veículo {{ veiculo }}. {{ mensagem }} '
            'Se houver aprovação pendente, acesse: {{ link_aprovacao }}. Ficamos à disposição.'
        )
    elif action == AIAssistantAction.IMPROVE_MESSAGE:
        base = text or 'Mensagem sem conteúdo informado.'
        context_note = []
        if template_type:
            context_note.append(f'tipo: {template_type}')
        if template_name:
            context_note.append(f'nome: {template_name}')
        suffix = f'\n\nContexto considerado: {", ".join(context_note)}.' if context_note else ''
        result = f'{base}\n\nTexto revisado para ficar mais claro, objetivo e cordial, preservando variáveis do sistema como {{{{ cliente.nome_razao_social }}}}, {{{{ ordem_servico.codigo }}}} e {{{{ link_aprovacao }}}}.{suffix}'
    else:
        if 'IA conectada com sucesso' in text:
            result = 'IA conectada com sucesso.'
        else:
            result = text or 'Sugestão gerada pelo assistente local.'

    return limit_text(result, settings.limite_caracteres_resposta)


def post_json(url, payload, headers=None, timeout=20):
    validate_provider_url(url)
    timeout = clamp_timeout(timeout)
    data = json.dumps(payload).encode('utf-8')
    req = urlrequest.Request(url, data=data, headers={
        'Content-Type': 'application/json',
        **(headers or {}),
    }, method='POST')
    try:
        with urlrequest.urlopen(req, timeout=timeout) as response:
            body = response.read().decode('utf-8')
            return json.loads(body) if body else {}
    except urlerror.HTTPError as exc:
        details = exc.read().decode('utf-8', errors='ignore')
        raise AIServiceError(f'Erro HTTP {exc.code}: {details[:500]}') from exc
    except urlerror.URLError as exc:
        raise AIServiceError(f'Falha de conexão: {exc.reason}') from exc
    except TimeoutError as exc:
        raise AIServiceError('Tempo limite excedido ao chamar o provedor de IA.') from exc
    except json.JSONDecodeError as exc:
        raise AIServiceError('O provedor respondeu, mas não retornou JSON válido.') from exc


def extract_text_from_provider(provider, data):
    if provider == AIProvider.OPENAI:
        if data.get('output_text'):
            return data['output_text']
        output = data.get('output') or []
        chunks = []
        for item in output:
            for content in item.get('content', []):
                if content.get('type') in {'output_text', 'text'} and content.get('text'):
                    chunks.append(content['text'])
        return '\n'.join(chunks).strip()
    if provider == AIProvider.ANTHROPIC:
        chunks = [part.get('text', '') for part in data.get('content', []) if part.get('type') == 'text']
        return '\n'.join(chunks).strip()
    if provider == AIProvider.GEMINI:
        candidates = data.get('candidates') or []
        chunks = []
        for candidate in candidates:
            for part in candidate.get('content', {}).get('parts', []):
                if part.get('text'):
                    chunks.append(part['text'])
        return '\n'.join(chunks).strip()
    if provider == AIProvider.OLLAMA:
        return (data.get('response') or '').strip()
    if provider == AIProvider.CUSTOM:
        for key in ('text', 'response', 'content', 'message'):
            if data.get(key):
                value = data[key]
                return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return ''


def generate_with_provider(settings, action, text, context=None):
    prompt = build_prompt(settings, action, text, context)
    provider = settings.provedor
    model = settings.modelo or ''
    timeout = clamp_timeout(settings.timeout_segundos)
    temperature = float(settings.temperatura or 0.3)

    if provider == AIProvider.LOCAL:
        return AIResult(text=local_generate(settings, action, text, context), provider=provider, model=model)

    if provider == AIProvider.OPENAI:
        base = (settings.endpoint_base or 'https://api.openai.com').rstrip('/')
        data = post_json(
            f'{base}/v1/responses',
            {
                'model': model or 'gpt-4o-mini',
                'input': prompt,
                'temperature': temperature,
            },
            headers={'Authorization': f'Bearer {settings.api_key}'},
            timeout=timeout,
        )
    elif provider == AIProvider.ANTHROPIC:
        base = (settings.endpoint_base or 'https://api.anthropic.com').rstrip('/')
        data = post_json(
            f'{base}/v1/messages',
            {
                'model': model or 'claude-3-5-sonnet-latest',
                'max_tokens': max(256, min(settings.limite_caracteres_resposta or 1200, 4000)),
                'temperature': temperature,
                'messages': [{'role': 'user', 'content': prompt}],
            },
            headers={'x-api-key': settings.api_key, 'anthropic-version': '2023-06-01'},
            timeout=timeout,
        )
    elif provider == AIProvider.GEMINI:
        base = (settings.endpoint_base or 'https://generativelanguage.googleapis.com').rstrip('/')
        gemini_model = model or 'gemini-1.5-flash'
        sep = '&' if '?' in base else '?'
        data = post_json(
            f'{base}/v1beta/models/{gemini_model}:generateContent{sep}key={settings.api_key}',
            {
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'temperature': temperature},
            },
            timeout=timeout,
        )
    elif provider == AIProvider.OLLAMA:
        base = settings.endpoint_base.rstrip('/')
        data = post_json(
            f'{base}/api/generate',
            {
                'model': model or 'llama3',
                'prompt': prompt,
                'stream': False,
                'options': {'temperature': temperature},
            },
            timeout=timeout,
        )
    elif provider == AIProvider.CUSTOM:
        data = post_json(
            settings.endpoint_base,
            {
                'action': action,
                'prompt': prompt,
                'text': text,
                'context': context or {},
                'model': model,
                'temperature': temperature,
            },
            headers={'Authorization': f'Bearer {settings.api_key}'} if settings.api_key else None,
            timeout=timeout,
        )
    else:
        raise AIServiceError('Provedor de IA inválido.')

    result_text = extract_text_from_provider(provider, data)
    if not result_text:
        raise AIServiceError('O provedor respondeu, mas não retornou texto utilizável.')
    return AIResult(text=limit_text(result_text, settings.limite_caracteres_resposta), provider=provider, model=model, raw=data)


OS_ACTIONS = {
    AIAssistantAction.IMPROVE_PROBLEM,
    AIAssistantAction.IMPROVE_DIAGNOSIS,
    AIAssistantAction.SUGGEST_OBSERVATION,
}
MESSAGE_ACTIONS = {
    AIAssistantAction.IMPROVE_MESSAGE,
    AIAssistantAction.EMAIL_TEMPLATE,
    AIAssistantAction.WHATSAPP_TEMPLATE,
}


def ensure_action_enabled(settings, action):
    """Aplica as regras de negocio de habilitacao da IA por tipo de acao."""
    if action in OS_ACTIONS and not settings.habilitar_os:
        raise AIServiceError('A IA para campos da OS está desabilitada nas configurações.')
    if action in MESSAGE_ACTIONS and not settings.habilitar_mensagens:
        raise AIServiceError('A IA para mensagens/templates está desabilitada nas configurações.')


def generate_ai_text(action, text='', context=None, user=None):
    settings = AISettings.get_solo()
    context = context or {}
    if not settings.ativo:
        raise AIServiceError('O módulo de IA está desativado nas configurações.')
    if action not in AIAssistantAction.values:
        raise AIServiceError('Ação de IA inválida.')
    ensure_action_enabled(settings, action)

    log = AIInteractionLog.objects.create(
        acao=action,
        provedor=settings.provedor,
        modelo=settings.modelo or '',
        entrada=text or '',
        contexto=context,
        usuario=user if getattr(user, 'is_authenticated', False) else None,
    )
    logger.info(
        'IA: ação=%s provedor=%s modelo=%s usuário=%s chave=%s',
        action,
        settings.provedor,
        settings.modelo or '-',
        getattr(user, 'pk', None) or 'anon',
        mask_secret(settings.api_key),
    )
    try:
        result = generate_with_provider(settings, action, text, context)
    except Exception as exc:
        log.erro = str(exc)
        log.sucesso = False
        log.save(update_fields=['erro', 'sucesso'])
        logger.warning('IA: falha ação=%s provedor=%s erro=%s', action, settings.provedor, exc)
        raise

    log.resposta = result.text
    log.sucesso = True
    log.save(update_fields=['resposta', 'sucesso'])
    return result


def test_ai_connection(user=None):
    return generate_ai_text(
        AIAssistantAction.GENERAL,
        'Responda apenas: IA conectada com sucesso.',
        context={'teste': 'conexao'},
        user=user,
    )


def sanitize_context(context):
    cleaned = {}
    for key, value in (context or {}).items():
        if isinstance(value, (dict, list)):
            cleaned[key] = value
        else:
            cleaned[key] = limit_text(str(value or ''), 1000)
    return cleaned
