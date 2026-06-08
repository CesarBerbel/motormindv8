"""Signals de auditoria: autenticação e alterações de modelos de negócio."""

import logging

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .context import get_current_request
from .models import AuditAction, AuditCategory, AuditLog
from .utils import is_sensitive_field, serialize_value

logger = logging.getLogger('audit')

# Apps cujos modelos são auditados nas alterações de dados.
AUDITED_APPS = {
    'accounts', 'core', 'operations', 'stock',
    'communications', 'ai_assistant', 'website',
}
# Modelos de alta rotatividade ou já cobertos por outro mecanismo.
EXCLUDED_MODELS = {('accounts', 'loginattempt')}
# Campos automáticos/ruidosos que não geram alteração relevante.
SKIP_FIELDS = {'criado_em', 'atualizado_em', 'last_login', 'date_joined'}


def _should_audit_model(sender):
    meta = getattr(sender, '_meta', None)
    if meta is None or meta.app_label not in AUDITED_APPS:
        return False
    return (meta.app_label, meta.model_name) not in EXCLUDED_MODELS


def _tracked_fields(instance):
    for field in instance._meta.concrete_fields:
        if field.name in SKIP_FIELDS:
            continue
        if getattr(field, 'auto_now', False) or getattr(field, 'auto_now_add', False):
            continue
        yield field


def _snapshot(instance):
    data = {}
    for field in _tracked_fields(instance):
        try:
            data[field.name] = field.value_from_object(instance)
        except Exception:
            data[field.name] = None
    return data


# --------------------------------------------------------------------------- #
# Autenticação
# --------------------------------------------------------------------------- #
@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    AuditLog.registrar(
        acao=AuditAction.LOGIN,
        categoria=AuditCategory.AUTENTICACAO,
        usuario=user,
        request=request,
        descricao=f'Login de {getattr(user, "email", "") or user}',
    )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    AuditLog.registrar(
        acao=AuditAction.LOGOUT,
        categoria=AuditCategory.AUTENTICACAO,
        usuario=user,
        request=request,
        descricao=f'Logout de {getattr(user, "email", "") or "sessão"}',
    )


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request=None, **kwargs):
    email = ''
    if credentials:
        email = credentials.get('username') or credentials.get('email') or ''
    AuditLog.registrar(
        acao=AuditAction.LOGIN_FALHA,
        categoria=AuditCategory.AUTENTICACAO,
        usuario=None,
        request=request,
        descricao=f'Falha de login: {email}',
        metadados={'email': email},
    )


# --------------------------------------------------------------------------- #
# Alterações de modelos
# --------------------------------------------------------------------------- #
@receiver(pre_save)
def capture_pre_save(sender, instance, **kwargs):
    if not _should_audit_model(sender):
        return
    old = None
    if instance.pk is not None:
        try:
            old = sender._base_manager.filter(pk=instance.pk).first()
        except Exception:
            old = None
    instance._audit_old = _snapshot(old) if old is not None else None


@receiver(post_save)
def log_post_save(sender, instance, created, **kwargs):
    if not _should_audit_model(sender):
        return
    try:
        request = get_current_request()
        verbose = sender._meta.verbose_name

        if created or getattr(instance, '_audit_old', None) is None:
            AuditLog.registrar(
                acao=AuditAction.CRIAR,
                categoria=AuditCategory.DADOS,
                request=request,
                objeto=instance,
                descricao=f'Criou {verbose}: {instance}',
            )
            return

        old = instance._audit_old
        new = _snapshot(instance)
        changes = {}
        for name, new_val in new.items():
            old_val = old.get(name)
            if old_val == new_val:
                continue
            if is_sensitive_field(name):
                changes[name] = {'de': '***', 'para': '***'}
            else:
                changes[name] = {'de': serialize_value(old_val), 'para': serialize_value(new_val)}

        if not changes:
            return

        acao = AuditAction.EDITAR
        verbo = 'Alterou'
        if 'excluido_em' in changes:
            old_excl = old.get('excluido_em')
            new_excl = new.get('excluido_em')
            if old_excl is None and new_excl is not None:
                acao, verbo = AuditAction.EXCLUIR, 'Excluiu (lógico)'
            elif old_excl is not None and new_excl is None:
                acao, verbo = AuditAction.RESTAURAR, 'Restaurou'

        AuditLog.registrar(
            acao=acao,
            categoria=AuditCategory.DADOS,
            request=request,
            objeto=instance,
            descricao=f'{verbo} {verbose}: {instance}',
            alteracoes=changes,
        )
    except Exception:  # pragma: no cover - auditoria nunca quebra o save
        logger.exception('Falha no post_save de auditoria (%s)', sender)


@receiver(post_delete)
def log_post_delete(sender, instance, **kwargs):
    if not _should_audit_model(sender):
        return
    AuditLog.registrar(
        acao=AuditAction.EXCLUIR_FISICO,
        categoria=AuditCategory.DADOS,
        request=get_current_request(),
        objeto=instance,
        descricao=f'Excluiu (físico) {sender._meta.verbose_name}: {instance}',
    )
