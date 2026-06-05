from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.template import Context, Template
from django.urls import reverse
from django.utils.html import strip_tags

from core.models import Customer, PessoaTipo, Supplier
from core.money import format_money_br
from .models import (
    MessageLog,
    MessageSettings,
    MessageStatus,
    MessageTemplate,
    MessageTemplateType,
    MessageType,
    RecipientKind,
    WorkOrderStatusMessageRule,
    WORK_ORDER_STATUS_CHOICES,
    get_work_order_status_label,
)


@dataclass(frozen=True)
class Recipient:
    kind: str
    obj: object

    @property
    def email(self):
        return self.obj.email

    @property
    def name(self):
        return self.obj.nome_razao_social

    @property
    def tipo_pessoa(self):
        return self.obj.tipo_pessoa


DEFAULT_TEMPLATE_CONTENT = {
    MessageTemplateType.CUSTOMER_BIRTHDAY_PHYSICAL: {
        'subject': 'Feliz aniversário, {{ nome }}!',
        'body': '<p>Olá, {{ nome }}!</p><p>Hoje é o seu dia, e toda a equipe MotorMind deseja muita saúde, felicidade e sucesso.</p><p>Parabéns pelo seu aniversário!</p>',
    },
    MessageTemplateType.CUSTOMER_FOUNDATION_LEGAL: {
        'subject': 'Parabéns pelo aniversário da {{ nome }}!',
        'body': '<p>Olá, {{ nome }}!</p><p>Hoje celebramos a data de fundação da sua empresa.</p><p>A equipe MotorMind deseja muitos anos de crescimento, bons negócios e sucesso.</p>',
    },
    MessageTemplateType.WORK_ORDER_STATUS: {
        'subject': 'Atualização da OS {{ ordem_servico.codigo }}: {{ status_novo_label }}',
        'body': '<p>Olá, {{ nome }}!</p><p>A OS <strong>{{ ordem_servico.codigo }}</strong> do veículo <strong>{{ veiculo }}</strong> mudou para <strong>{{ status_novo_label }}</strong>.</p><p>{{ mensagem_status }}</p>',
    },
    MessageTemplateType.WORK_ORDER_APPROVAL: {
        'subject': 'Orçamento da OS {{ ordem_servico.codigo }} aguardando aprovação',
        'body': '<p>Olá, {{ nome }}!</p><p>O orçamento <strong>{{ orcamento.codigo }}</strong> da OS <strong>{{ ordem_servico.codigo }}</strong> está aguardando sua aprovação.</p><p>Total do orçamento: <strong>{{ valor_total }}</strong>.</p><p>Acesse: <a href="{{ link_aprovacao }}">{{ link_aprovacao }}</a></p>',
    },
}


def _recipient_kind_for_object(obj):
    if isinstance(obj, Customer):
        return RecipientKind.CUSTOMER
    if isinstance(obj, Supplier):
        return RecipientKind.SUPPLIER
    raise TypeError(f'Destinatário não suportado: {type(obj)!r}')


def build_recipient_context(recipient, target_date=None):
    target_date = target_date or date.today()
    obj = recipient.obj
    return {
        'destinatario': obj,
        'cliente': obj if recipient.kind == RecipientKind.CUSTOMER else None,
        'fornecedor': obj if recipient.kind == RecipientKind.SUPPLIER else None,
        'nome': recipient.name,
        'email': recipient.email,
        'tipo_pessoa': recipient.tipo_pessoa,
        'data_envio': target_date,
        'hoje': target_date,
    }


def render_template_string(template_string, context):
    return Template(template_string or '').render(Context(context)).strip()


def render_subject_string(template_string, context):
    return ' '.join(render_template_string(template_string, context).splitlines()).strip()


def get_default_message_template(template_type):
    return MessageTemplate.objects.filter(tipo=template_type, padrao=True).first()


def render_message_content(recipient, subject, body, template=None, target_date=None):
    context = build_recipient_context(recipient, target_date=target_date)

    if template and not subject and not body:
        rendered_subject = template.render_subject(context)
        rendered_body = template.render_body(context)
    else:
        rendered_subject = render_subject_string(subject, context)
        rendered_body = render_template_string(body, context)

    return rendered_subject, rendered_body


def _create_log(recipient, message_type, subject, body, user=None, reference_year=None, template=None, work_order=None, work_order_status=''):
    return MessageLog.objects.create(
        tipo=message_type,
        status=MessageStatus.PENDING,
        destinatario_tipo=recipient.kind,
        destinatario_id=recipient.obj.pk,
        destinatario_nome=recipient.name,
        destinatario_email=recipient.email,
        destinatario_tipo_pessoa=recipient.tipo_pessoa,
        template=template,
        assunto=subject,
        corpo=body,
        ano_referencia=reference_year,
        ordem_servico_id=getattr(work_order, 'pk', None),
        ordem_servico_codigo=getattr(work_order, 'codigo', '') or '',
        ordem_servico_status=work_order_status or '',
        enviado_por=user,
    )


def send_logged_email(recipient, message_type, subject, body, user=None, reference_year=None, fail_silently=False, template=None, work_order=None, work_order_status=''):
    with transaction.atomic():
        try:
            log = _create_log(
                recipient,
                message_type,
                subject,
                body,
                user=user,
                reference_year=reference_year,
                template=template,
                work_order=work_order,
                work_order_status=work_order_status,
            )
        except IntegrityError:
            return None

    try:
        plain_body = strip_tags(body)
        send_mail(
            subject=subject,
            message=plain_body,
            from_email=None,
            recipient_list=[recipient.email],
            fail_silently=fail_silently,
            html_message=body if body != plain_body else None,
        )
        log.mark_sent()
    except Exception as exc:
        log.mark_error(exc)

    return log


def send_manual_message(recipients, subject, body, user=None, template=None):
    logs = []
    for recipient in recipients:
        rendered_subject, rendered_body = render_message_content(
            recipient=recipient,
            subject=subject,
            body=body,
            template=template,
        )
        logs.append(send_logged_email(
            recipient=recipient,
            message_type=MessageType.MANUAL,
            subject=rendered_subject,
            body=rendered_body,
            user=user,
            template=template,
        ))
    return [log for log in logs if log is not None]


def customer_has_anniversary_today(customer, target_date):
    if not customer.data_nascimento_fundacao:
        return False
    return (
        customer.data_nascimento_fundacao.month == target_date.month
        and customer.data_nascimento_fundacao.day == target_date.day
    )


def get_anniversary_message_type(customer):
    if customer.tipo_pessoa == PessoaTipo.FISICA:
        return MessageType.BIRTHDAY
    return MessageType.FOUNDATION


def get_anniversary_template_type(customer):
    if customer.tipo_pessoa == PessoaTipo.FISICA:
        return MessageTemplateType.CUSTOMER_BIRTHDAY_PHYSICAL
    return MessageTemplateType.CUSTOMER_FOUNDATION_LEGAL


def build_anniversary_email(customer, target_date):
    recipient = Recipient(kind=RecipientKind.CUSTOMER, obj=customer)
    template_type = get_anniversary_template_type(customer)
    template = get_default_message_template(template_type)

    if template:
        subject, body = render_message_content(
            recipient=recipient,
            subject='',
            body='',
            template=template,
            target_date=target_date,
        )
        return subject, body, template

    fallback = DEFAULT_TEMPLATE_CONTENT[template_type]
    context = build_recipient_context(recipient, target_date=target_date)
    subject = render_subject_string(fallback['subject'], context)
    body = render_template_string(fallback['body'], context)
    return subject, body, None


def get_message_settings():
    return MessageSettings.get_solo()


def is_anniversary_enabled_for_customer(customer, settings=None):
    settings = settings or get_message_settings()
    if customer.tipo_pessoa == PessoaTipo.FISICA:
        return settings.enviar_aniversario_pessoa_fisica
    return settings.enviar_fundacao_pessoa_juridica


def get_disabled_anniversary_features(settings=None):
    settings = settings or get_message_settings()
    disabled = []
    if not settings.enviar_aniversario_pessoa_fisica:
        disabled.append({
            'key': 'physical_birthday',
            'label': 'aniversário de pessoa física',
            'message': 'ERRO: envio automático de aniversário para pessoa física está desabilitado nas configurações de mensagens.',
        })
    if not settings.enviar_fundacao_pessoa_juridica:
        disabled.append({
            'key': 'legal_foundation',
            'label': 'fundação de pessoa jurídica',
            'message': 'ERRO: envio automático de fundação para pessoa jurídica está desabilitado nas configurações de mensagens.',
        })
    return disabled


def get_anniversary_customers(target_date=None, settings=None, respect_settings=True):
    target_date = target_date or date.today()
    settings = settings or get_message_settings()
    customers = Customer.objects.filter(
        data_nascimento_fundacao__isnull=False,
        email__isnull=False,
    ).exclude(email='')

    selected = []
    for customer in customers:
        if not customer_has_anniversary_today(customer, target_date):
            continue
        if respect_settings and not is_anniversary_enabled_for_customer(customer, settings=settings):
            continue
        selected.append(customer)

    return selected


def already_sent_anniversary(customer, message_type, year):
    return MessageLog.objects.filter(
        tipo=message_type,
        status=MessageStatus.SENT,
        destinatario_tipo=RecipientKind.CUSTOMER,
        destinatario_id=customer.pk,
        ano_referencia=year,
    ).exists()


def send_anniversary_messages(target_date=None, limit=None, dry_run=False):
    target_date = target_date or date.today()
    settings = get_message_settings()
    selected_customers = []
    logs = []

    for customer in get_anniversary_customers(target_date, settings=settings, respect_settings=True):
        message_type = get_anniversary_message_type(customer)
        if already_sent_anniversary(customer, message_type, target_date.year):
            continue

        selected_customers.append(customer)
        if limit and len(selected_customers) >= limit:
            break

    if dry_run:
        return selected_customers, logs

    for customer in selected_customers:
        subject, body, template = build_anniversary_email(customer, target_date)
        logs.append(send_logged_email(
            recipient=Recipient(kind=RecipientKind.CUSTOMER, obj=customer),
            message_type=get_anniversary_message_type(customer),
            subject=subject,
            body=body,
            reference_year=target_date.year,
            template=template,
        ))

    return selected_customers, [log for log in logs if log is not None]


WORK_ORDER_STATUS_MESSAGES = {
    'aberta': 'A ordem de serviço foi aberta e registrada em nosso sistema.',
    'diagnostico': 'Seu veículo está em diagnóstico técnico para avaliarmos a melhor solução.',
    'orcamento': 'O orçamento da OS está sendo preparado com base na avaliação realizada.',
    'aguardando_aprovacao': 'O orçamento está aguardando sua aprovação para continuidade dos serviços.',
    'aprovada': 'A OS foi aprovada e seguirá para programação de execução.',
    'em_execucao': 'O serviço foi iniciado pela equipe técnica.',
    'aguardando_peca': 'A OS está aguardando peça ou insumo necessário para continuidade.',
    'em_teste': 'O serviço foi concluído e o veículo está em teste/verificação.',
    'pronta': 'A OS foi finalizada internamente.',
    'pronto_para_retirar': 'Seu veículo está pronto para retirada.',
    'entregue': 'A OS foi entregue ao cliente. Agradecemos pela preferência.',
    'cancelada': 'A OS foi cancelada.',
    'arquivada': 'A OS foi arquivada administrativamente.',
}


def ensure_work_order_status_message_rules():
    created = []
    for index, (status, _label) in enumerate(WORK_ORDER_STATUS_CHOICES, start=1):
        rule, was_created = WorkOrderStatusMessageRule.objects.get_or_create(
            status=status,
            defaults={'ordem': index, 'enviar_email': False},
        )
        if not was_created and rule.ordem != index:
            rule.ordem = index
            rule.save(update_fields=['ordem', 'atualizado_em'])
        if was_created:
            created.append(rule)
    return created


def build_work_order_status_context(order, transition, target_date=None):
    target_date = target_date or date.today()
    previous_status = getattr(transition, 'status_anterior', '') or ''
    new_status = getattr(transition, 'status_novo', getattr(order, 'status', '')) or ''
    vehicle = getattr(order, 'veiculo', None)
    vehicle_label = '-'
    if vehicle:
        vehicle_label = f'{vehicle.placa or "Sem placa"} - {vehicle.marca} {vehicle.modelo}'.strip()
    return {
        'destinatario': order.cliente,
        'cliente': order.cliente,
        'fornecedor': None,
        'nome': order.cliente.nome_razao_social,
        'email': order.cliente.email,
        'tipo_pessoa': order.cliente.tipo_pessoa,
        'data_envio': target_date,
        'hoje': target_date,
        'ordem_servico': order,
        'os': order,
        'codigo_os': order.codigo,
        'status_anterior': previous_status,
        'status_anterior_label': get_work_order_status_label(previous_status),
        'status_novo': new_status,
        'status_novo_label': get_work_order_status_label(new_status),
        'mensagem_status': WORK_ORDER_STATUS_MESSAGES.get(new_status, ''),
        'veiculo': vehicle_label,
        'placa': getattr(vehicle, 'placa', '') if vehicle else '',
    }


def build_work_order_status_email(order, transition, rule=None):
    recipient = Recipient(kind=RecipientKind.CUSTOMER, obj=order.cliente)
    template = getattr(rule, 'template', None) or get_default_message_template(MessageTemplateType.WORK_ORDER_STATUS)
    context = build_work_order_status_context(order, transition)

    if template:
        subject = template.render_subject(context)
        body = template.render_body(context)
        return recipient, subject, body, template

    fallback = DEFAULT_TEMPLATE_CONTENT[MessageTemplateType.WORK_ORDER_STATUS]
    subject = render_subject_string(fallback['subject'], context)
    body = render_template_string(fallback['body'], context)
    return recipient, subject, body, None


def send_work_order_status_change_message(order, transition, user=None):
    settings = get_message_settings()
    if not settings.enviar_status_os:
        return None
    if not getattr(order.cliente, 'email', ''):
        return None

    ensure_work_order_status_message_rules()
    rule = WorkOrderStatusMessageRule.objects.select_related('template').filter(
        status=transition.status_novo,
    ).first()
    if not rule or not rule.enviar_email:
        return None

    recipient, subject, body, template = build_work_order_status_email(order, transition, rule=rule)
    return send_logged_email(
        recipient=recipient,
        message_type=MessageType.WORK_ORDER_STATUS,
        subject=subject,
        body=body,
        user=user,
        template=template,
        work_order=order,
        work_order_status=transition.status_novo,
    )



def build_work_order_approval_url(budget, request=None):
    path = reverse('work_order_public_approval', kwargs={'token': budget.token})
    if request is not None:
        return request.build_absolute_uri(path)
    base_url = getattr(settings, 'PUBLIC_BASE_URL', '') or getattr(settings, 'SITE_URL', '')
    if base_url:
        return f'{base_url.rstrip("/")}{path}'
    return path


def build_work_order_approval_context(budget, request=None, target_date=None):
    target_date = target_date or date.today()
    order = budget.ordem_servico
    vehicle = getattr(order, 'veiculo', None)
    vehicle_label = '-'
    if vehicle:
        vehicle_label = f'{vehicle.placa or "Sem placa"} - {vehicle.marca} {vehicle.modelo}'.strip()
    return {
        'destinatario': order.cliente,
        'cliente': order.cliente,
        'fornecedor': None,
        'nome': order.cliente.nome_razao_social,
        'email': order.cliente.email,
        'tipo_pessoa': order.cliente.tipo_pessoa,
        'data_envio': target_date,
        'hoje': target_date,
        'ordem_servico': order,
        'os': order,
        'codigo_os': order.codigo,
        'orcamento': budget,
        'versao_orcamento': budget.versao,
        'subtotal': format_money_br(budget.subtotal_snapshot),
        'valor_desconto': format_money_br(budget.valor_desconto_snapshot),
        'valor_total': format_money_br(budget.valor_total_snapshot),
        'link_aprovacao': build_work_order_approval_url(budget, request=request),
        'veiculo': vehicle_label,
        'placa': getattr(vehicle, 'placa', '') if vehicle else '',
    }


def get_work_order_approval_template():
    settings_obj = get_message_settings()
    configured_template = getattr(settings_obj, 'template_orcamento_os', None)
    if (
        configured_template
        and configured_template.tipo == MessageTemplateType.WORK_ORDER_APPROVAL
        and configured_template.ativo
        and configured_template.excluido_em is None
    ):
        return configured_template
    return get_default_message_template(MessageTemplateType.WORK_ORDER_APPROVAL)


def build_work_order_approval_email(budget, request=None):
    recipient = Recipient(kind=RecipientKind.CUSTOMER, obj=budget.ordem_servico.cliente)
    template = get_work_order_approval_template()
    context = build_work_order_approval_context(budget, request=request)
    if template:
        subject = template.render_subject(context)
        body = template.render_body(context)
        return recipient, subject, body, template
    fallback = DEFAULT_TEMPLATE_CONTENT[MessageTemplateType.WORK_ORDER_APPROVAL]
    subject = render_subject_string(fallback['subject'], context)
    body = render_template_string(fallback['body'], context)
    return recipient, subject, body, None


def send_work_order_approval_message(budget, user=None, request=None):
    if not getattr(budget.ordem_servico.cliente, 'email', ''):
        return None
    recipient, subject, body, template = build_work_order_approval_email(budget, request=request)
    return send_logged_email(
        recipient=recipient,
        message_type=MessageType.WORK_ORDER_APPROVAL,
        subject=subject,
        body=body,
        user=user,
        template=template,
        work_order=budget.ordem_servico,
        work_order_status=budget.ordem_servico.status,
    )
