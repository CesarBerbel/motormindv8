import logging

from django.conf import settings
from django.db import models

logger = logging.getLogger('audit')


class AuditAction(models.TextChoices):
    LOGIN = 'login', 'Login'
    LOGIN_FALHA = 'login_falha', 'Falha de login'
    LOGOUT = 'logout', 'Logout'
    CRIAR = 'criar', 'Criação'
    EDITAR = 'editar', 'Alteração'
    EXCLUIR = 'excluir', 'Exclusão lógica'
    RESTAURAR = 'restaurar', 'Restauração'
    EXCLUIR_FISICO = 'excluir_fisico', 'Exclusão física'
    ACESSO = 'acesso', 'Acesso'
    ACAO = 'acao', 'Ação'


class AuditCategory(models.TextChoices):
    AUTENTICACAO = 'autenticacao', 'Autenticação'
    DADOS = 'dados', 'Dados'
    NAVEGACAO = 'navegacao', 'Navegação'
    ACAO = 'acao', 'Ação'


class AuditLog(models.Model):
    """Registro imutável de auditoria. Não deve ser editado ou apagado a não ser
    pela rotina de retenção."""

    criado_em = models.DateTimeField('Data', auto_now_add=True, db_index=True)
    categoria = models.CharField('Categoria', max_length=20, choices=AuditCategory.choices, db_index=True)
    acao = models.CharField('Ação', max_length=20, choices=AuditAction.choices, db_index=True)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Usuário',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='auditorias',
    )
    usuario_email = models.CharField('Email do usuário', max_length=254, blank=True, db_index=True)

    objeto_app = models.CharField('App', max_length=100, blank=True)
    objeto_modelo = models.CharField('Modelo', max_length=100, blank=True, db_index=True)
    objeto_id = models.CharField('ID do objeto', max_length=64, blank=True, db_index=True)
    objeto_descricao = models.CharField('Objeto', max_length=255, blank=True)

    descricao = models.CharField('Descrição', max_length=300, blank=True)
    alteracoes = models.JSONField('Alterações', default=dict, blank=True)

    caminho = models.CharField('Caminho', max_length=255, blank=True)
    metodo = models.CharField('Método', max_length=10, blank=True)
    status_code = models.PositiveSmallIntegerField('Status HTTP', blank=True, null=True)
    ip = models.GenericIPAddressField('IP', blank=True, null=True)
    user_agent = models.CharField('User agent', max_length=300, blank=True)
    metadados = models.JSONField('Metadados', default=dict, blank=True)

    class Meta:
        verbose_name = 'Registro de auditoria'
        verbose_name_plural = 'Registros de auditoria'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['categoria', 'acao']),
            models.Index(fields=['objeto_modelo', 'objeto_id']),
            models.Index(fields=['usuario', '-criado_em']),
        ]

    def __str__(self):
        quem = self.usuario_email or 'anônimo'
        return f'{self.get_acao_display()} por {quem} em {self.criado_em:%d/%m/%Y %H:%M}'

    @classmethod
    def registrar(cls, *, acao, categoria, usuario=None, request=None, descricao='',
                  objeto=None, alteracoes=None, status_code=None, metadados=None):
        """Cria um registro de auditoria de forma resiliente (nunca levanta)."""
        try:
            dados = {
                'acao': acao,
                'categoria': categoria,
                'descricao': (descricao or '')[:300],
                'alteracoes': alteracoes or {},
                'metadados': metadados or {},
                'status_code': status_code,
            }

            user = usuario
            if user is None and request is not None:
                req_user = getattr(request, 'user', None)
                if req_user is not None and getattr(req_user, 'is_authenticated', False):
                    user = req_user
            if user is not None:
                dados['usuario'] = user
                dados['usuario_email'] = (getattr(user, 'email', '') or '')[:254]

            if request is not None:
                from .utils import get_client_ip
                dados['caminho'] = (request.path or '')[:255]
                dados['metodo'] = (request.method or '')[:10]
                dados['ip'] = get_client_ip(request)
                dados['user_agent'] = (request.META.get('HTTP_USER_AGENT', '') or '')[:300]

            if objeto is not None:
                meta = objeto._meta
                dados['objeto_app'] = meta.app_label
                dados['objeto_modelo'] = meta.object_name
                dados['objeto_id'] = str(getattr(objeto, 'pk', '') or '')
                dados['objeto_descricao'] = str(objeto)[:255]

            return cls.objects.create(**dados)
        except Exception:  # pragma: no cover - auditoria nunca deve quebrar o fluxo
            logger.exception('Falha ao registrar auditoria (acao=%s)', acao)
            return None
