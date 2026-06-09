"""Middleware de auditoria de requisições.

- Disponibiliza a request atual aos signals (via thread-local).
- Regista cada navegação (GET) e cada ação (POST/PUT/PATCH/DELETE), ignorando
  ruído (estáticos, healthcheck, autocomplete, etc.). Login/logout são tratados
  pelos signals de autenticação, por isso são ignorados aqui.
"""

import logging

from django.conf import settings

from .context import clear_current_request, set_current_request
from .models import AuditAction, AuditCategory, AuditLog

logger = logging.getLogger('audit')

DEFAULT_SKIP_PREFIXES = (
    '/static/', '/media/', '/sw.js', '/healthz', '/favicon',
    '/login', '/logout', '/admin/jsi18n',
)
# Trechos no caminho que indicam ruído (XHR de apoio).
SKIP_SUBSTRINGS = ('autocomplete', '/fipe/', '/ia/assistir-texto')
AUDITED_METHODS = {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'}


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        configured = getattr(settings, 'AUDIT_SKIP_PREFIXES', None)
        self.skip_prefixes = tuple(configured) if configured else DEFAULT_SKIP_PREFIXES

    def __call__(self, request):
        set_current_request(request)
        try:
            response = self.get_response(request)
            try:
                self._log_request(request, response)
            except Exception:  # pragma: no cover - auditoria nunca quebra a resposta
                logger.exception('Falha ao auditar a requisição %s', getattr(request, 'path', '?'))
            return response
        finally:
            clear_current_request()

    def _should_skip(self, request):
        method = request.method
        if method not in AUDITED_METHODS:
            return True
        path = request.path or ''
        if any(path.startswith(prefix) for prefix in self.skip_prefixes):
            return True
        if any(token in path for token in SKIP_SUBSTRINGS):
            return True
        # Ignora XHR de apoio (autocomplete, validações), mantendo navegação real.
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' and method == 'GET':
            return True
        return False

    def _log_request(self, request, response):
        if self._should_skip(request):
            return

        status = getattr(response, 'status_code', None)
        if request.method == 'GET':
            # Audita apenas páginas (HTML) que carregaram com sucesso.
            content_type = response.get('Content-Type', '') if hasattr(response, 'get') else ''
            if status and status >= 400:
                return
            if 'text/html' not in content_type:
                return
            acao = AuditAction.ACESSO
            categoria = AuditCategory.NAVEGACAO
            descricao = f'Acessou {request.path}'
        else:
            acao = AuditAction.ACAO
            categoria = AuditCategory.ACAO
            descricao = f'{request.method} {request.path}'

        AuditLog.registrar(
            acao=acao,
            categoria=categoria,
            request=request,
            descricao=descricao,
            status_code=status,
        )
