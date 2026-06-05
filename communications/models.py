from django.conf import settings
from django.db import models
from django.db.models import Q
from django.template import Context, Template
from django.utils import timezone


class RecipientKind(models.TextChoices):
    CUSTOMER = 'customer', 'Cliente'
    SUPPLIER = 'supplier', 'Fornecedor'


WORK_ORDER_STATUS_CHOICES = [
    ('aberta', 'Aberta'),
    ('diagnostico', 'Diagnóstico'),
    ('orcamento', 'Orçamento'),
    ('aguardando_aprovacao', 'Aguardando aprovação'),
    ('aprovada', 'Aprovada'),
    ('em_execucao', 'Em execução'),
    ('aguardando_peca', 'Aguardando peça'),
    ('em_teste', 'Em teste'),
    ('pronta', 'Pronta'),
    ('pronto_para_retirar', 'Pronto para retirar'),
    ('entregue', 'Entregue'),
    ('cancelada', 'Cancelada'),
    ('arquivada', 'Arquivada'),
]

WORK_ORDER_STATUS_ORDER = {status: index for index, (status, _label) in enumerate(WORK_ORDER_STATUS_CHOICES, start=1)}


def get_work_order_status_label(status):
    return dict(WORK_ORDER_STATUS_CHOICES).get(status, status)


class MessageType(models.TextChoices):
    MANUAL = 'manual', 'Manual'
    BIRTHDAY = 'birthday', 'Aniversário'
    FOUNDATION = 'foundation', 'Fundação'
    WORK_ORDER_STATUS = 'work_order_status', 'Status da OS'
    WORK_ORDER_APPROVAL = 'work_order_approval', 'Orçamento / aprovação da OS'


class MessageStatus(models.TextChoices):
    PENDING = 'pending', 'Pendente'
    SENT = 'sent', 'Enviado'
    ERROR = 'error', 'Erro'


class MessageTemplateType(models.TextChoices):
    CUSTOMER_BIRTHDAY_PHYSICAL = 'customer_birthday_physical', 'Aniversário - Cliente pessoa física'
    CUSTOMER_FOUNDATION_LEGAL = 'customer_foundation_legal', 'Fundação - Cliente pessoa jurídica'
    WORK_ORDER_STATUS = 'work_order_status', 'Mudança de status da OS'
    WORK_ORDER_APPROVAL = 'work_order_approval', 'Orçamento / aprovação da OS'
    MANUAL = 'manual', 'Manual / Outro'


class ActiveMessageTemplateManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(ativo=True, excluido_em__isnull=True)


class MessageTemplate(models.Model):
    nome = models.CharField('Nome', max_length=120)
    tipo = models.CharField('Tipo', max_length=40, choices=MessageTemplateType.choices, db_index=True)
    assunto = models.CharField('Assunto', max_length=180)
    corpo = models.TextField('Corpo')
    ativo = models.BooleanField('Ativo?', default=True, db_index=True)
    padrao = models.BooleanField('Template padrão?', default=False, db_index=True)
    excluido_em = models.DateTimeField('Excluído em', blank=True, null=True, db_index=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    objects = ActiveMessageTemplateManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'Template de mensagem'
        verbose_name_plural = 'Templates de mensagens'
        ordering = ['tipo', 'nome']
        constraints = [
            models.UniqueConstraint(
                fields=['tipo'],
                condition=Q(padrao=True, ativo=True, excluido_em__isnull=True),
                name='unique_active_default_message_template_by_type',
            ),
        ]

    def render_subject(self, context):
        rendered = Template(self.assunto).render(Context(context))
        return ' '.join(rendered.splitlines()).strip()

    def render_body(self, context):
        return Template(self.corpo).render(Context(context)).strip()

    def soft_delete(self):
        self.ativo = False
        self.padrao = False
        self.excluido_em = timezone.now()
        self.save(update_fields=['ativo', 'padrao', 'excluido_em', 'atualizado_em'])

    def restore(self):
        self.ativo = True
        self.excluido_em = None
        self.save(update_fields=['ativo', 'excluido_em', 'atualizado_em'])

    def __str__(self):
        return self.nome


class MessageSettings(models.Model):
    enviar_aniversario_pessoa_fisica = models.BooleanField(
        'Enviar aniversário para pessoa física?',
        default=True,
        help_text='Quando desabilitado, o comando automático não envia emails de aniversário para clientes pessoa física.',
    )
    enviar_fundacao_pessoa_juridica = models.BooleanField(
        'Enviar fundação para pessoa jurídica?',
        default=True,
        help_text='Quando desabilitado, o comando automático não envia emails de fundação para clientes pessoa jurídica.',
    )
    enviar_status_os = models.BooleanField(
        'Enviar email quando a OS mudar de status?',
        default=False,
        help_text='Quando habilitado, o sistema verifica as regras por status abaixo a cada mudança de status da OS.',
    )
    template_orcamento_os = models.ForeignKey(
        MessageTemplate,
        verbose_name='Template de orçamento / aprovação da OS',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
        limit_choices_to={'tipo': MessageTemplateType.WORK_ORDER_APPROVAL},
        help_text='Template usado no email enviado quando a OS gera um orçamento para aprovação. Se ficar vazio, será usado o template padrão deste tipo.',
    )
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Configuração de mensagens'
        verbose_name_plural = 'Configurações de mensagens'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.enviar_aniversario_pessoa_fisica = False
        self.enviar_fundacao_pessoa_juridica = False
        self.enviar_status_os = False
        self.template_orcamento_os = None
        self.save(update_fields=[
            'enviar_aniversario_pessoa_fisica',
            'enviar_fundacao_pessoa_juridica',
            'enviar_status_os',
            'template_orcamento_os',
            'atualizado_em',
        ])

    def __str__(self):
        return 'Configurações de mensagens'


class WorkOrderStatusMessageRule(models.Model):
    status = models.CharField('Status da OS', max_length=30, choices=WORK_ORDER_STATUS_CHOICES, unique=True, db_index=True)
    ordem = models.PositiveSmallIntegerField('Ordem', default=999, db_index=True)
    enviar_email = models.BooleanField('Enviar email?', default=False, db_index=True)
    template = models.ForeignKey(
        MessageTemplate,
        verbose_name='Template',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='regras_status_os',
        limit_choices_to={'tipo': MessageTemplateType.WORK_ORDER_STATUS},
        help_text='Template usado quando a OS entrar neste status. Se ficar vazio, será usado o template padrão de mudança de status da OS.',
    )
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Regra de mensagem por status da OS'
        verbose_name_plural = 'Regras de mensagem por status da OS'
        ordering = ['ordem', 'status']

    def save(self, *args, **kwargs):
        self.ordem = WORK_ORDER_STATUS_ORDER.get(self.status, 999)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_status_display()} - {"Enviar" if self.enviar_email else "Não enviar"}'


class MessageLog(models.Model):
    tipo = models.CharField('Tipo da mensagem', max_length=20, choices=MessageType.choices)
    status = models.CharField('Status', max_length=20, choices=MessageStatus.choices, default=MessageStatus.PENDING, db_index=True)

    destinatario_tipo = models.CharField('Tipo de destinatário', max_length=20, choices=RecipientKind.choices)
    destinatario_id = models.PositiveBigIntegerField('ID do destinatário')
    destinatario_nome = models.CharField('Nome do destinatário', max_length=180)
    destinatario_email = models.EmailField('Email do destinatário')
    destinatario_tipo_pessoa = models.CharField('Tipo de pessoa', max_length=20, blank=True)

    template = models.ForeignKey(
        MessageTemplate,
        verbose_name='Template usado',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='historicos',
    )
    assunto = models.CharField('Assunto', max_length=180)
    corpo = models.TextField('Corpo')
    erro = models.TextField('Erro', blank=True)

    ano_referencia = models.PositiveIntegerField('Ano de referência', blank=True, null=True, db_index=True)
    ordem_servico_id = models.PositiveBigIntegerField('ID da OS', blank=True, null=True, db_index=True)
    ordem_servico_codigo = models.CharField('Código da OS', max_length=20, blank=True)
    ordem_servico_status = models.CharField('Status da OS', max_length=30, blank=True, choices=WORK_ORDER_STATUS_CHOICES)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Enviado por',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='mensagens_enviadas',
    )
    enviado_em = models.DateTimeField('Enviado em', blank=True, null=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Histórico de mensagem'
        verbose_name_plural = 'Histórico de mensagens'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['tipo', 'status', 'ano_referencia']),
            models.Index(fields=['destinatario_tipo', 'destinatario_id']),
            models.Index(fields=['ordem_servico_id', 'ordem_servico_status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tipo', 'destinatario_tipo', 'destinatario_id', 'ano_referencia'],
                condition=Q(status='sent') & Q(tipo__in=['birthday', 'foundation']) & Q(ano_referencia__isnull=False),
                name='unique_sent_anniversary_message_per_year',
            ),
        ]

    def mark_sent(self):
        self.status = MessageStatus.SENT
        self.erro = ''
        self.enviado_em = timezone.now()
        self.save(update_fields=['status', 'erro', 'enviado_em', 'atualizado_em'])

    def mark_error(self, error):
        self.status = MessageStatus.ERROR
        self.erro = str(error)
        self.save(update_fields=['status', 'erro', 'atualizado_em'])

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.destinatario_email} - {self.get_status_display()}'
