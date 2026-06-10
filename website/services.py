"""Serviços auxiliares do site público."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.urls import NoReverseMatch, reverse

from .models import SiteSettings

logger = logging.getLogger('website')


def get_workshop_lead_recipient(site=None):
    """Retorna o e-mail interno da oficina para avisos de pedidos do site."""
    site = site or SiteSettings.get_solo()
    return (site.email_oficina or site.email_contato or settings.DEFAULT_FROM_EMAIL or '').strip()


def get_lead_internal_url(lead=None):
    """URL interna usada nas notificações de novos pedidos do site."""
    try:
        if lead is not None:
            return reverse('site_lead_detail', args=[lead.pk])
        return reverse('site_lead_list')
    except NoReverseMatch:
        return '/painel/orcamentos/'


def get_lead_admin_url(lead):
    """URL interna usada no corpo do e-mail recebido pela oficina."""
    return get_lead_internal_url(lead)


def build_new_lead_email_message(lead, admin_url=''):
    linhas = [
        'Novo pedido de orçamento recebido pelo site:',
        '',
        f'Nome: {lead.nome}',
        f'Telefone/WhatsApp: {lead.telefone}',
    ]
    if lead.email:
        linhas.append(f'E-mail: {lead.email}')
    if lead.veiculo:
        linhas.append(f'Veículo: {lead.veiculo}')
    if lead.placa:
        linhas.append(f'Placa: {lead.placa}')
    if lead.servico:
        linhas.append(f'Serviço de interesse: {lead.servico.titulo}')
    if lead.mensagem:
        linhas.append('')
        linhas.append('Mensagem:')
        linhas.append(lead.mensagem)
    if admin_url:
        linhas.append('')
        linhas.append(f'Ver no painel: {admin_url}')
    return '\n'.join(linhas)


def create_new_lead_notifications(lead):
    """Cria notificações internas para ADM/superusuário quando chega um pedido do site."""
    try:
        from accounts.models import EmployeeRole, User
        from core.models import AppNotification, AppNotificationLevel
    except Exception:  # pragma: no cover - defensivo para migrações/imports iniciais
        logger.exception('Falha ao importar modelos para notificação de lead %s', getattr(lead, 'pk', None))
        return 0

    recipients = User.objects.filter(is_active=True).filter(
        Q(is_superuser=True)
        | Q(role=EmployeeRole.ADM)
        | Q(user_permissions__codename='view_lead')
        | Q(groups__permissions__codename='view_lead')
    ).distinct()

    if not recipients.exists():
        return 0

    vehicle_label = lead.veiculo or 'veículo não informado'
    if lead.placa:
        vehicle_label = f'{vehicle_label} · {lead.placa}'
    message = f'{lead.nome} solicitou orçamento para {vehicle_label}. Telefone: {lead.telefone}.'
    if lead.servico:
        message += f' Serviço: {lead.servico.titulo}.'

    notifications = [
        AppNotification(
            usuario=user,
            titulo='Novo pedido de orçamento pelo site',
            mensagem=message,
            url=get_lead_internal_url(lead),
            nivel=AppNotificationLevel.INFO,
            categoria='lead_site',
        )
        for user in recipients
    ]
    AppNotification.objects.bulk_create(notifications)
    return len(notifications)


def notify_new_lead(lead):
    """Notifica a oficina sobre um novo pedido de orçamento.

    A notificação interna é criada para ADM/superusuário. O e-mail é enviado
    para o e-mail da oficina cadastrado em Configurações > Oficina.
    Falhas de e-mail não quebram a experiência do visitante.
    """
    create_new_lead_notifications(lead)

    site = SiteSettings.get_solo()
    destinatario = get_workshop_lead_recipient(site)
    if not destinatario:
        return False

    admin_url = get_lead_admin_url(lead)
    try:
        send_mail(
            subject=f'[{site.nome_fantasia}] Novo pedido de orçamento de {lead.nome}',
            message=build_new_lead_email_message(lead, admin_url=admin_url),
            from_email=None,
            recipient_list=[destinatario],
            fail_silently=True,
        )
        return True
    except Exception:  # pragma: no cover - defensivo
        logger.exception('Falha ao notificar novo lead %s', lead.pk)
        return False
