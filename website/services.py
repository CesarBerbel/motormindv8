"""Serviços auxiliares do site público."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import NoReverseMatch, reverse

from .models import SiteSettings

logger = logging.getLogger('website')


def notify_new_lead(lead):
    """Notifica a oficina por e-mail sobre um novo pedido de orçamento.

    Falha de forma silenciosa: um problema no envio não deve quebrar a
    experiência do visitante. Devolve True se um e-mail foi enviado.
    """
    site = SiteSettings.get_solo()
    destinatario = (site.email_contato or settings.DEFAULT_FROM_EMAIL or '').strip()
    if not destinatario:
        return False

    try:
        admin_url = reverse('admin:website_lead_change', args=[lead.pk])
    except NoReverseMatch:
        admin_url = ''

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

    try:
        send_mail(
            subject=f'[{site.nome_fantasia}] Novo pedido de orçamento de {lead.nome}',
            message='\n'.join(linhas),
            from_email=None,
            recipient_list=[destinatario],
            fail_silently=True,
        )
        return True
    except Exception:  # pragma: no cover - defensivo
        logger.exception('Falha ao notificar novo lead %s', lead.pk)
        return False
