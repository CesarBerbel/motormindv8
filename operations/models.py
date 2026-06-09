from datetime import timedelta
from decimal import Decimal
import secrets
import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from core.money import MoneyField
from stock.models import InventoryItem, InventoryItemType, MIN_QUANTITY


class ActiveOperationsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(ativo=True, excluido_em__isnull=True)


class SoftDeleteModel(models.Model):
    ativo = models.BooleanField('Ativo?', default=True, db_index=True)
    excluido_em = models.DateTimeField('Excluído em', blank=True, null=True, db_index=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    objects = ActiveOperationsManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        self.ativo = False
        self.excluido_em = timezone.now()
        self.save(update_fields=['ativo', 'excluido_em', 'atualizado_em'])

    def restore(self):
        self.ativo = True
        self.excluido_em = None
        self.save(update_fields=['ativo', 'excluido_em', 'atualizado_em'])


class ServiceCategory(SoftDeleteModel):
    nome = models.CharField('Nome', max_length=120)
    descricao = models.TextField('Descrição', blank=True)

    class Meta:
        verbose_name = 'Categoria de serviço'
        verbose_name_plural = 'Categorias de serviços'
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(
                fields=['nome'],
                condition=Q(ativo=True) & Q(excluido_em__isnull=True),
                name='unique_active_service_category_name',
            )
        ]

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse('service_category_list')


class Service(SoftDeleteModel):
    codigo = models.CharField('Código', max_length=20, unique=True, blank=True, null=True, editable=False, db_index=True)
    nome = models.CharField('Nome', max_length=180)
    categoria = models.ForeignKey(
        ServiceCategory,
        verbose_name='Categoria',
        on_delete=models.PROTECT,
        related_name='servicos',
        blank=True,
        null=True,
    )
    descricao = models.TextField('Descrição', blank=True)
    duracao_minutos = models.PositiveIntegerField('Duração em minutos', default=60, validators=[MinValueValidator(1)])
    valor = MoneyField('Valor', default=Decimal('0.00'))
    pecas_padrao = models.ManyToManyField(
        InventoryItem,
        verbose_name='Peças padrão',
        through='ServiceDefaultPart',
        related_name='servicos_padrao',
        blank=True,
    )

    class Meta:
        verbose_name = 'Serviço'
        verbose_name_plural = 'Serviços'
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(
                fields=['nome'],
                condition=Q(ativo=True) & Q(excluido_em__isnull=True),
                name='unique_active_service_name',
            )
        ]

    def __str__(self):
        return f'{self.codigo or "Sem código"} - {self.nome}'

    def get_absolute_url(self):
        return reverse('service_detail', kwargs={'pk': self.pk})

    def generate_codigo(self):
        return f'SRV-{self.pk:05d}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.codigo:
            self.codigo = self.generate_codigo()
            type(self).all_objects.filter(pk=self.pk).update(codigo=self.codigo)

    @property
    def duracao_formatada(self):
        horas, minutos = divmod(self.duracao_minutos or 0, 60)
        if horas and minutos:
            return f'{horas}h {minutos}min'
        if horas:
            return f'{horas}h'
        return f'{minutos}min'

    @property
    def custo_pecas_padrao(self):
        total = Decimal('0.00')
        for part in self.pecas_associadas.select_related('item'):
            total += (part.item.preco_custo or Decimal('0.00')) * part.quantidade
        return total.quantize(Decimal('0.01'))

    @property
    def valor_pecas_padrao(self):
        from operations.services.work_order_pricing import inventory_sale_price

        total = Decimal('0.00')
        for part in self.pecas_associadas.select_related('item'):
            if part.item.tipo == InventoryItemType.PECA:
                total += inventory_sale_price(part.item) * part.quantidade
        return total.quantize(Decimal('0.01'))

    @property
    def valor_estimado_total(self):
        return ((self.valor or Decimal('0.00')) + self.valor_pecas_padrao).quantize(Decimal('0.01'))


class ServiceDefaultPart(models.Model):
    service = models.ForeignKey(
        Service,
        verbose_name='Serviço',
        on_delete=models.CASCADE,
        related_name='pecas_associadas',
    )
    item = models.ForeignKey(
        InventoryItem,
        verbose_name='Peça/Insumo',
        on_delete=models.PROTECT,
        related_name='servicos_associados',
    )
    quantidade = models.PositiveIntegerField(
        'Quantidade padrão',
        default=MIN_QUANTITY,
        validators=[MinValueValidator(MIN_QUANTITY)],
    )
    obrigatoria = models.BooleanField(
        'Obrigatória?',
        default=True,
        help_text='Peças obrigatórias acompanham o serviço. Se forem recusadas no orçamento, o serviço inteiro é recusado.',
    )
    observacao = models.CharField('Observação', max_length=180, blank=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Peça padrão do serviço'
        verbose_name_plural = 'Peças padrão do serviço'
        ordering = ['item__nome']
        constraints = [
            models.UniqueConstraint(fields=['service', 'item'], name='unique_service_default_part_item')
        ]

    def __str__(self):
        return f'{self.service.codigo or self.service_id} - {self.item.nome}'

    @property
    def custo_total(self):
        return ((self.item.preco_custo or Decimal('0.00')) * self.quantidade).quantize(Decimal('0.01'))

    @property
    def valor_total(self):
        from operations.services.work_order_pricing import inventory_sale_price

        return (inventory_sale_price(self.item) * self.quantidade).quantize(Decimal('0.01'))


class ServiceCombo(SoftDeleteModel):
    codigo = models.CharField('Código', max_length=20, unique=True, blank=True, null=True, editable=False, db_index=True)
    nome = models.CharField('Nome', max_length=180)
    descricao = models.TextField('Descrição', blank=True)
    desconto_percentual = models.DecimalField(
        'Desconto percentual',
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text='Informe de 0 a 100. Campo opcional.',
    )
    servicos = models.ManyToManyField(
        Service,
        verbose_name='Serviços associados',
        through='ServiceComboItem',
        related_name='combos_associados',
        blank=True,
    )

    class Meta:
        verbose_name = 'Combo de serviços'
        verbose_name_plural = 'Combos de serviços'
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(
                fields=['nome'],
                condition=Q(ativo=True) & Q(excluido_em__isnull=True),
                name='unique_active_service_combo_name',
            )
        ]

    def __str__(self):
        return f'{self.codigo or "Sem código"} - {self.nome}'

    def get_absolute_url(self):
        return reverse('service_combo_detail', kwargs={'pk': self.pk})

    def generate_codigo(self):
        return f'CMB-{self.pk:05d}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.codigo:
            self.codigo = self.generate_codigo()
            type(self).all_objects.filter(pk=self.pk).update(codigo=self.codigo)

    @property
    def desconto_percentual_normalizado(self):
        return self.desconto_percentual or Decimal('0.00')

    @property
    def subtotal_servicos(self):
        total = Decimal('0.00')
        for item in self.servicos_associados.select_related('service'):
            total += item.service.valor or Decimal('0.00')
        return total.quantize(Decimal('0.01'))

    @property
    def valor_desconto(self):
        subtotal = self.subtotal_servicos
        percentual = self.desconto_percentual_normalizado
        return (subtotal * percentual / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def valor_total(self):
        return (self.subtotal_servicos - self.valor_desconto).quantize(Decimal('0.01'))

    @property
    def duracao_total_minutos(self):
        return sum(item.service.duracao_minutos or 0 for item in self.servicos_associados.select_related('service'))

    @property
    def duracao_formatada(self):
        horas, minutos = divmod(self.duracao_total_minutos or 0, 60)
        if horas and minutos:
            return f'{horas}h {minutos}min'
        if horas:
            return f'{horas}h'
        return f'{minutos}min'


class ServiceComboItem(models.Model):
    combo = models.ForeignKey(
        ServiceCombo,
        verbose_name='Combo',
        on_delete=models.CASCADE,
        related_name='servicos_associados',
    )
    service = models.ForeignKey(
        Service,
        verbose_name='Serviço',
        on_delete=models.PROTECT,
        related_name='combo_associations',
    )
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Serviço do combo'
        verbose_name_plural = 'Serviços do combo'
        ordering = ['service__nome']
        constraints = [
            models.UniqueConstraint(fields=['combo', 'service'], name='unique_service_combo_service')
        ]

    def __str__(self):
        return f'{self.combo.codigo or self.combo_id} - {self.service.nome}'


class PdfTemplateType(models.TextChoices):
    CHECKIN = 'checkin', 'Check-in do veículo'
    ORCAMENTO = 'orcamento', 'Orçamento / aprovação da OS'


class PdfSettings(models.Model):
    logo = models.ImageField('Logo global', upload_to='pdf/logos/', blank=True, null=True)
    cabecalho_global = models.TextField('Cabeçalho global', blank=True)
    rodape_global = models.TextField('Rodapé global', blank=True)
    mostrar_assinatura_cliente_padrao = models.BooleanField('Mostrar assinatura do cliente por padrão?', default=True)
    mostrar_assinatura_oficina_padrao = models.BooleanField('Mostrar assinatura da oficina por padrão?', default=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Configuração de PDF'
        verbose_name_plural = 'Configurações de PDF'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.logo = None
        self.cabecalho_global = ''
        self.rodape_global = ''
        self.mostrar_assinatura_cliente_padrao = True
        self.mostrar_assinatura_oficina_padrao = True
        self.save(update_fields=[
            'logo', 'cabecalho_global', 'rodape_global',
            'mostrar_assinatura_cliente_padrao', 'mostrar_assinatura_oficina_padrao', 'atualizado_em',
        ])

    def __str__(self):
        return 'Configurações de PDF'


class PdfTemplateSettings(models.Model):
    tipo = models.CharField('Template', max_length=30, choices=PdfTemplateType.choices, unique=True, db_index=True)
    titulo = models.CharField('Título do PDF', max_length=180, blank=True)
    cabecalho = models.TextField('Cabeçalho específico', blank=True)
    notas_rodape = models.TextField('Notas de rodapé', blank=True)
    mostrar_assinatura_cliente = models.BooleanField('Mostrar assinatura do cliente?', default=True)
    mostrar_assinatura_oficina = models.BooleanField('Mostrar assinatura da oficina?', default=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Template de PDF'
        verbose_name_plural = 'Templates de PDF'
        ordering = ['tipo']

    @classmethod
    def get_for(cls, tipo):
        defaults = {
            PdfTemplateType.CHECKIN: {'titulo': 'Check-in de recepção do veículo'},
            PdfTemplateType.ORCAMENTO: {'titulo': 'Orçamento / aprovação da OS'},
        }.get(tipo, {})
        obj, _ = cls.objects.get_or_create(tipo=tipo, defaults=defaults)
        return obj

    def __str__(self):
        return self.get_tipo_display()


class WorkOrderStatus(models.TextChoices):
    ABERTA = 'aberta', 'Aberta'
    DIAGNOSTICO = 'diagnostico', 'Diagnóstico'
    ORCAMENTO = 'orcamento', 'Orçamento'
    AGUARDANDO_APROVACAO = 'aguardando_aprovacao', 'Aguardando aprovação'
    APROVADA = 'aprovada', 'Aprovada'
    EM_EXECUCAO = 'em_execucao', 'Em execução'
    AGUARDANDO_PECA = 'aguardando_peca', 'Aguardando peça'
    EM_TESTE = 'em_teste', 'Em teste'
    PRONTA = 'pronta', 'Pronta'
    PRONTO_PARA_RETIRAR = 'pronto_para_retirar', 'Pronto para retirar'
    ENTREGUE = 'entregue', 'Entregue'
    CANCELADA = 'cancelada', 'Cancelada'
    ARQUIVADA = 'arquivada', 'Arquivada'

    @classmethod
    def allowed_transitions(cls):
        return {
            cls.ABERTA: [cls.DIAGNOSTICO, cls.AGUARDANDO_APROVACAO, cls.CANCELADA],
            cls.DIAGNOSTICO: [cls.ORCAMENTO, cls.AGUARDANDO_PECA, cls.CANCELADA],
            cls.ORCAMENTO: [cls.AGUARDANDO_APROVACAO, cls.DIAGNOSTICO, cls.CANCELADA],
            cls.AGUARDANDO_APROVACAO: [cls.APROVADA, cls.ORCAMENTO, cls.CANCELADA],
            cls.APROVADA: [cls.ORCAMENTO, cls.EM_EXECUCAO, cls.AGUARDANDO_PECA, cls.CANCELADA],
            cls.EM_EXECUCAO: [cls.AGUARDANDO_PECA, cls.EM_TESTE, cls.CANCELADA],
            cls.AGUARDANDO_PECA: [cls.EM_EXECUCAO, cls.APROVADA, cls.DIAGNOSTICO, cls.CANCELADA],
            cls.EM_TESTE: [cls.PRONTA, cls.EM_EXECUCAO, cls.AGUARDANDO_PECA, cls.CANCELADA],
            cls.PRONTA: [cls.PRONTO_PARA_RETIRAR, cls.EM_TESTE, cls.EM_EXECUCAO],
            cls.PRONTO_PARA_RETIRAR: [cls.ENTREGUE, cls.PRONTA],
            cls.ENTREGUE: [cls.ARQUIVADA],
            cls.CANCELADA: [cls.ARQUIVADA],
            cls.ARQUIVADA: [],
        }

    @classmethod
    def next_statuses(cls, status):
        return cls.allowed_transitions().get(status, [])

    @classmethod
    def can_transition(cls, current_status, next_status):
        if current_status == next_status:
            return True
        return next_status in cls.next_statuses(current_status)

    @classmethod
    def terminal_statuses(cls):
        return {cls.ARQUIVADA}

    @classmethod
    def completed_statuses(cls):
        return {cls.PRONTA, cls.PRONTO_PARA_RETIRAR, cls.ENTREGUE, cls.ARQUIVADA}

    @classmethod
    def stock_out_statuses(cls):
        return {cls.EM_EXECUCAO, cls.AGUARDANDO_PECA, cls.EM_TESTE, cls.PRONTA, cls.PRONTO_PARA_RETIRAR, cls.ENTREGUE}

    @classmethod
    def workshop_capacity_statuses(cls):
        return {
            cls.ABERTA,
            cls.DIAGNOSTICO,
            cls.ORCAMENTO,
            cls.AGUARDANDO_APROVACAO,
            cls.APROVADA,
            cls.EM_EXECUCAO,
            cls.AGUARDANDO_PECA,
            cls.EM_TESTE,
            cls.PRONTA,
            cls.PRONTO_PARA_RETIRAR,
        }

    @classmethod
    def suggested_statuses(cls):
        return [
            (cls.ABERTA, 'Estado inicial da recepção e abertura da OS.'),
            (cls.EM_TESTE, 'Usado para teste e verificação antes da finalização interna.'),
            (cls.ARQUIVADA, 'Usado após entrega ou cancelamento para encerrar administrativamente o histórico.'),
        ]


class WorkOrderSettings(models.Model):
    prazo_estimativa_dias = models.PositiveIntegerField(
        'Prazo padrão da OS em dias',
        default=7,
        validators=[MinValueValidator(0), MaxValueValidator(365)],
        help_text='Quantidade de dias somada à data atual para preencher automaticamente a previsão de entrega da OS.',
    )
    vagas_oficina = models.PositiveIntegerField(
        'Vagas da oficina',
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(999)],
        help_text='Quantidade máxima de veículos/OS que podem ocupar vaga física simultaneamente na oficina.',
    )
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Configuração de OS'
        verbose_name_plural = 'Configurações de OS'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.prazo_estimativa_dias = 7
        self.vagas_oficina = 5
        self.save(update_fields=['prazo_estimativa_dias', 'vagas_oficina', 'atualizado_em'])

    def __str__(self):
        return 'Configurações de OS'


class WorkOrder(SoftDeleteModel):
    codigo = models.CharField('Código', max_length=20, unique=True, blank=True, null=True, editable=False, db_index=True)
    cliente = models.ForeignKey(
        'core.Customer',
        verbose_name='Cliente',
        on_delete=models.PROTECT,
        related_name='ordens_servico',
    )
    veiculo = models.ForeignKey(
        'core.Vehicle',
        verbose_name='Veículo',
        on_delete=models.PROTECT,
        related_name='ordens_servico',
        blank=True,
        null=True,
    )
    status = models.CharField('Status', max_length=30, choices=WorkOrderStatus.choices, default=WorkOrderStatus.ABERTA, db_index=True)
    data_abertura = models.DateTimeField('Data de abertura', default=timezone.now, db_index=True)
    previsao_entrega = models.DateTimeField('Previsão de entrega', blank=True, null=True)
    data_finalizacao = models.DateTimeField('Data de finalização', blank=True, null=True)
    km_atual = models.PositiveIntegerField('KM atual', blank=True, null=True, validators=[MinValueValidator(0)])
    problema_relatado = models.TextField('Problema relatado')
    diagnostico = models.TextField('Diagnóstico', blank=True)
    observacao = models.TextField('Observação', blank=True)
    desconto_percentual = models.DecimalField(
        'Desconto percentual',
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text='Opcional. Informe de 0 a 100.',
    )
    estoque_baixado = models.BooleanField('Estoque baixado?', default=False, db_index=True)
    estoque_baixado_em = models.DateTimeField('Estoque baixado em', blank=True, null=True)
    estoque_baixado_por = models.ForeignKey(
        'accounts.User',
        verbose_name='Estoque baixado por',
        on_delete=models.SET_NULL,
        related_name='baixas_estoque_os',
        blank=True,
        null=True,
    )
    tecnico_responsavel = models.ForeignKey(
        'accounts.User',
        verbose_name='Técnico responsável',
        on_delete=models.SET_NULL,
        related_name='ordens_servico_responsavel',
        blank=True,
        null=True,
        db_index=True,
    )

    class Meta:
        verbose_name = 'Ordem de serviço'
        verbose_name_plural = 'Ordens de serviço'
        ordering = ['-data_abertura', '-pk']

    def __str__(self):
        return f'{self.codigo or "Sem código"} - {self.cliente.nome_razao_social}'

    def get_absolute_url(self):
        return reverse('work_order_detail', kwargs={'pk': self.pk})

    @classmethod
    def workshop_occupied_queryset(cls):
        return cls.objects.filter(
            status__in=WorkOrderStatus.workshop_capacity_statuses(),
            ativo=True,
            excluido_em__isnull=True,
        )

    @classmethod
    def workshop_occupied_count(cls):
        return cls.workshop_occupied_queryset().count()

    @classmethod
    def workshop_available_slots(cls):
        settings = WorkOrderSettings.get_solo()
        return max(settings.vagas_oficina - cls.workshop_occupied_count(), 0)

    @property
    def ocupa_vaga_oficina(self):
        return self.status in WorkOrderStatus.workshop_capacity_statuses() and self.ativo and self.excluido_em is None

    @property
    def is_cancelled(self):
        return self.status == WorkOrderStatus.CANCELADA

    def get_current_approval_budget(self):
        if not self.pk:
            return None
        return self.orcamentos_aprovacao.exclude(
            status=WorkOrderApprovalStatus.SUPERSEDED,
        ).order_by('-versao', '-pk').first()

    def get_effective_approval_budget(self):
        if not self.pk:
            return None
        return self.orcamentos_aprovacao.filter(
            status__in=[WorkOrderApprovalStatus.APPROVED, WorkOrderApprovalStatus.PARTIALLY_APPROVED],
        ).order_by('-versao', '-pk').first()

    @property
    def has_approval_in_progress(self):
        budget = self.get_current_approval_budget()
        return bool(budget and budget.status == WorkOrderApprovalStatus.PENDING)

    @property
    def has_approved_budget(self):
        return self.get_effective_approval_budget() is not None

    @property
    def has_rejected_approval_budget(self):
        budget = self.get_current_approval_budget()
        return bool(budget and budget.status == WorkOrderApprovalStatus.REJECTED)

    @property
    def has_locked_approval(self):
        budget = self.get_current_approval_budget()
        return bool(budget and budget.status in WorkOrderApprovalStatus.locking_statuses())

    def get_or_create_pending_approval_budget(self, user=None, send_email=False, request=None):
        budget = self.get_current_approval_budget()
        if not budget or budget.status != WorkOrderApprovalStatus.PENDING:
            budget = WorkOrderApprovalBudget.create_from_work_order(self, user=user)
        if send_email:
            budget.send_to_customer(user=user, request=request)
        return budget

    def supersede_current_approval_budget(self, user=None, observacao=''):
        budget = self.get_current_approval_budget()
        if budget:
            budget.supersede(user=user, observacao=observacao)
        return budget

    def ensure_can_edit(self):
        from django.core.exceptions import ValidationError

        if self.is_cancelled:
            raise ValidationError('OS cancelada não pode ser editada.')
        if self.status == WorkOrderStatus.ARQUIVADA:
            raise ValidationError('OS arquivada não pode ser editada.')

    def generate_codigo(self):
        return f'OS-{self.pk:05d}'

    def save(self, *args, **kwargs):
        if self.status in WorkOrderStatus.completed_statuses() and not self.data_finalizacao:
            self.data_finalizacao = timezone.now()
        if self.status not in WorkOrderStatus.completed_statuses() and self.data_finalizacao and not self.pk:
            self.data_finalizacao = None
        super().save(*args, **kwargs)
        if not self.codigo:
            self.codigo = self.generate_codigo()
            type(self).all_objects.filter(pk=self.pk).update(codigo=self.codigo)

    def can_transition_to(self, new_status):
        if self.status == WorkOrderStatus.ORCAMENTO and new_status == WorkOrderStatus.EM_TESTE and self.has_rejected_approval_budget:
            return True
        return WorkOrderStatus.can_transition(self.status, new_status)

    def get_available_transitions(self):
        return WorkOrderStatus.next_statuses(self.status)

    def transition_to(self, new_status, user=None, observacao='', request=None):
        from operations.services.work_order_status import transition_to

        return transition_to(self, new_status, user=user, observacao=observacao, request=request)

    @property
    def status_badge_class(self):
        return {
            WorkOrderStatus.ABERTA: 'badge-info',
            WorkOrderStatus.DIAGNOSTICO: 'badge-info',
            WorkOrderStatus.ORCAMENTO: 'badge-warning',
            WorkOrderStatus.AGUARDANDO_APROVACAO: 'badge-warning',
            WorkOrderStatus.APROVADA: 'badge-success',
            WorkOrderStatus.EM_EXECUCAO: 'badge-primary',
            WorkOrderStatus.AGUARDANDO_PECA: 'badge-warning',
            WorkOrderStatus.EM_TESTE: 'badge-accent',
            WorkOrderStatus.PRONTA: 'badge-success',
            WorkOrderStatus.PRONTO_PARA_RETIRAR: 'badge-success',
            WorkOrderStatus.ENTREGUE: 'badge-neutral',
            WorkOrderStatus.CANCELADA: 'badge-error',
            WorkOrderStatus.ARQUIVADA: 'badge-ghost',
        }.get(self.status, 'badge-outline')

    @property
    def desconto_percentual_normalizado(self):
        return self.desconto_percentual or Decimal('0.00')

    @property
    def subtotal_servicos(self):
        from operations.services.work_order_totals import subtotal_servicos

        return subtotal_servicos(self)

    @property
    def subtotal_combos(self):
        from operations.services.work_order_totals import subtotal_combos

        return subtotal_combos(self)

    @property
    def subtotal_pecas_avulsas(self):
        from operations.services.work_order_totals import subtotal_pecas_avulsas

        return subtotal_pecas_avulsas(self)

    @property
    def subtotal_pecas(self):
        from operations.services.work_order_totals import subtotal_pecas

        return subtotal_pecas(self)

    @property
    def subtotal_insumos(self):
        from operations.services.work_order_totals import subtotal_insumos

        return subtotal_insumos(self)

    @property
    def custo_insumos(self):
        from operations.services.work_order_totals import custo_insumos

        return custo_insumos(self)

    @property
    def subtotal(self):
        from operations.services.work_order_totals import subtotal

        return subtotal(self)

    @property
    def valor_desconto(self):
        from operations.services.work_order_totals import valor_desconto

        return valor_desconto(self)

    @property
    def valor_total(self):
        from operations.services.work_order_totals import valor_total

        return valor_total(self)

    @property
    def duracao_total_minutos(self):
        from operations.services.work_order_totals import duracao_total_minutos

        return duracao_total_minutos(self)

    @property
    def duracao_formatada(self):
        horas, minutos = divmod(self.duracao_total_minutos or 0, 60)
        if horas and minutos:
            return f'{horas}h {minutos}min'
        if horas:
            return f'{horas}h'
        return f'{minutos}min'

    def get_stock_requirement_sources(self):
        from operations.services.work_order_stock import get_stock_requirement_sources

        return get_stock_requirement_sources(self)

    def get_base_stock_requirements(self):
        from operations.services.work_order_stock import get_base_stock_requirements

        return get_base_stock_requirements(self)

    def get_stock_requirement_overrides_map(self):
        from operations.services.work_order_stock import get_stock_requirement_overrides_map

        return get_stock_requirement_overrides_map(self)

    def get_stock_requirements(self):
        from operations.services.work_order_stock import get_stock_requirements

        return get_stock_requirements(self)

    def update_stock_requirement_overrides(self, quantities):
        from operations.services.work_order_stock import update_stock_requirement_overrides

        return update_stock_requirement_overrides(self, quantities)

    def get_stock_shortages(self):
        from operations.services.work_order_stock import get_stock_shortages

        return get_stock_shortages(self)

    def has_stock_shortage(self):
        from operations.services.work_order_stock import has_stock_shortage

        return has_stock_shortage(self)

    def stock_shortage_message(self):
        from operations.services.work_order_stock import stock_shortage_message

        return stock_shortage_message(self)

    def ensure_awaiting_parts_if_needed(self, user=None, observacao=''):
        from operations.services.work_order_stock import ensure_awaiting_parts_if_needed

        return ensure_awaiting_parts_if_needed(self, user=user, observacao=observacao)

    def baixar_estoque(self, user=None):
        from operations.services.work_order_stock import baixar_estoque

        return baixar_estoque(self, user=user)


class WorkOrderStockRequirementOverride(models.Model):
    ordem_servico = models.ForeignKey(
        WorkOrder,
        verbose_name='OS',
        on_delete=models.CASCADE,
        related_name='ajustes_pecas_previstas',
    )
    item = models.ForeignKey(
        InventoryItem,
        verbose_name='Peça/Insumo',
        on_delete=models.PROTECT,
        related_name='ajustes_pecas_previstas_os',
    )
    quantidade = models.PositiveIntegerField(
        'Quantidade ajustada',
        validators=[MinValueValidator(MIN_QUANTITY)],
        help_text='Quantidade efetiva que será considerada na baixa de estoque desta OS.',
    )
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Ajuste de peça prevista da OS'
        verbose_name_plural = 'Ajustes de peças previstas da OS'
        ordering = ['item__nome']
        constraints = [
            models.UniqueConstraint(fields=['ordem_servico', 'item'], name='unique_work_order_stock_requirement_override')
        ]

    def __str__(self):
        return f'{self.ordem_servico.codigo or self.ordem_servico_id} - {self.item.nome}: {self.quantidade}'


class WorkOrderStatusTransition(models.Model):
    ordem_servico = models.ForeignKey(
        WorkOrder,
        verbose_name='OS',
        on_delete=models.CASCADE,
        related_name='transicoes_status',
    )
    status_anterior = models.CharField('Status anterior', max_length=30, choices=WorkOrderStatus.choices)
    status_novo = models.CharField('Novo status', max_length=30, choices=WorkOrderStatus.choices)
    observacao = models.TextField('Observação', blank=True)
    criado_por = models.ForeignKey(
        'accounts.User',
        verbose_name='Alterado por',
        on_delete=models.SET_NULL,
        related_name='transicoes_status_os',
        blank=True,
        null=True,
    )
    criado_em = models.DateTimeField('Criado em', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Transição de status da OS'
        verbose_name_plural = 'Transições de status da OS'
        ordering = ['-criado_em', '-pk']

    def __str__(self):
        return f'{self.ordem_servico.codigo or self.ordem_servico_id}: {self.get_status_anterior_display()} → {self.get_status_novo_display()}'


class WorkOrderServiceItem(models.Model):
    ordem_servico = models.ForeignKey(
        WorkOrder,
        verbose_name='OS',
        on_delete=models.CASCADE,
        related_name='servicos_os',
    )
    service = models.ForeignKey(
        Service,
        verbose_name='Serviço',
        on_delete=models.PROTECT,
        related_name='itens_os',
    )
    quantidade = models.PositiveIntegerField('Quantidade', default=MIN_QUANTITY, validators=[MinValueValidator(MIN_QUANTITY)])
    valor_unitario = MoneyField('Valor unitário', blank=True, null=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Serviço da OS'
        verbose_name_plural = 'Serviços da OS'
        ordering = ['service__nome']
        constraints = [models.UniqueConstraint(fields=['ordem_servico', 'service'], name='unique_work_order_service')]

    def __str__(self):
        return f'{self.ordem_servico.codigo or self.ordem_servico_id} - {self.service.nome}'

    def save(self, *args, **kwargs):
        if self.valor_unitario is None and self.service_id:
            self.valor_unitario = self.service.valor
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return ((self.valor_unitario or Decimal('0.00')) * self.quantidade).quantize(Decimal('0.01'))


class WorkOrderComboItem(models.Model):
    ordem_servico = models.ForeignKey(
        WorkOrder,
        verbose_name='OS',
        on_delete=models.CASCADE,
        related_name='combos_os',
    )
    combo = models.ForeignKey(
        ServiceCombo,
        verbose_name='Combo',
        on_delete=models.PROTECT,
        related_name='itens_os',
    )
    quantidade = models.PositiveIntegerField('Quantidade', default=MIN_QUANTITY, validators=[MinValueValidator(MIN_QUANTITY)])
    valor_unitario = MoneyField('Valor unitário', blank=True, null=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Combo da OS'
        verbose_name_plural = 'Combos da OS'
        ordering = ['combo__nome']
        constraints = [models.UniqueConstraint(fields=['ordem_servico', 'combo'], name='unique_work_order_combo')]

    def __str__(self):
        return f'{self.ordem_servico.codigo or self.ordem_servico_id} - {self.combo.nome}'

    def save(self, *args, **kwargs):
        if self.valor_unitario is None and self.combo_id:
            self.valor_unitario = self.combo.valor_total
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return ((self.valor_unitario or Decimal('0.00')) * self.quantidade).quantize(Decimal('0.01'))


class WorkOrderPartItem(models.Model):
    ordem_servico = models.ForeignKey(
        WorkOrder,
        verbose_name='OS',
        on_delete=models.CASCADE,
        related_name='pecas_os',
    )
    item = models.ForeignKey(
        InventoryItem,
        verbose_name='Peça/Insumo',
        on_delete=models.PROTECT,
        related_name='itens_os',
    )
    quantidade = models.PositiveIntegerField('Quantidade', default=MIN_QUANTITY, validators=[MinValueValidator(MIN_QUANTITY)])
    valor_unitario = MoneyField('Valor unitário', blank=True, null=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Peça/Insumo da OS'
        verbose_name_plural = 'Peças/Insumos da OS'
        ordering = ['item__nome']
        constraints = [models.UniqueConstraint(fields=['ordem_servico', 'item'], name='unique_work_order_part')]

    def __str__(self):
        return f'{self.ordem_servico.codigo or self.ordem_servico_id} - {self.item.nome}'

    def save(self, *args, **kwargs):
        if self.item_id and self.item.tipo == InventoryItemType.INSUMO:
            self.valor_unitario = Decimal('0.00')
        elif self.valor_unitario is None and self.item_id:
            from operations.services.work_order_pricing import inventory_sale_price

            self.valor_unitario = inventory_sale_price(self.item)
        super().save(*args, **kwargs)

    @property
    def is_internal_supply(self):
        return bool(self.item_id and self.item.tipo == InventoryItemType.INSUMO)

    @property
    def subtotal(self):
        if self.is_internal_supply:
            return Decimal('0.00')
        return ((self.valor_unitario or Decimal('0.00')) * self.quantidade).quantize(Decimal('0.01'))

    @property
    def custo_total(self):
        if not self.item_id:
            return Decimal('0.00')
        return ((self.item.preco_custo or Decimal('0.00')) * self.quantidade).quantize(Decimal('0.01'))


class WorkOrderApprovalStatus(models.TextChoices):
    PENDING = 'pending', 'Aguardando resposta'
    APPROVED = 'approved', 'Aprovado integralmente'
    PARTIALLY_APPROVED = 'partially_approved', 'Aprovado parcialmente'
    REJECTED = 'rejected', 'Recusado integralmente'
    SUPERSEDED = 'superseded', 'Substituído'

    @classmethod
    def locking_statuses(cls):
        return {cls.PENDING, cls.APPROVED, cls.PARTIALLY_APPROVED}


class WorkOrderApprovalMethod(models.TextChoices):
    EMAIL = 'email', 'Email'
    WHATSAPP = 'whatsapp', 'WhatsApp'
    PRESENTIAL = 'presential', 'Cliente presencialmente'
    SHOP = 'shop', 'Oficina'


class WorkOrderApprovalDecision(models.TextChoices):
    APPROVE_ALL = 'approve_all', 'Aprovar tudo'
    APPROVE_PARTIAL = 'approve_partial', 'Aprovar parcialmente'
    REJECT_ALL = 'reject_all', 'Recusar tudo'


class WorkOrderApprovalItemType(models.TextChoices):
    SERVICE = 'service', 'Serviço'
    COMBO = 'combo', 'Combo'
    PART = 'part', 'Peça/Insumo'


class WorkOrderApprovalBudget(models.Model):
    ordem_servico = models.ForeignKey(
        WorkOrder,
        verbose_name='OS',
        on_delete=models.CASCADE,
        related_name='orcamentos_aprovacao',
    )
    versao = models.PositiveIntegerField('Versão', default=1, db_index=True)
    token = models.UUIDField('Token público', default=uuid.uuid4, unique=True, editable=False, db_index=True)
    status = models.CharField(
        'Status',
        max_length=30,
        choices=WorkOrderApprovalStatus.choices,
        default=WorkOrderApprovalStatus.PENDING,
        db_index=True,
    )
    snapshot = models.JSONField('Snapshot geral', default=dict, blank=True)
    desconto_percentual = models.DecimalField('Desconto percentual', max_digits=5, decimal_places=2, default=Decimal('0.00'))
    subtotal_snapshot = MoneyField('Subtotal snapshot', default=Decimal('0.00'))
    valor_desconto_snapshot = MoneyField('Desconto snapshot', default=Decimal('0.00'))
    valor_total_snapshot = MoneyField('Total snapshot', default=Decimal('0.00'))
    enviado_em = models.DateTimeField('Enviado em', blank=True, null=True)
    enviado_por = models.ForeignKey(
        'accounts.User',
        verbose_name='Enviado por',
        on_delete=models.SET_NULL,
        related_name='orcamentos_os_enviados',
        blank=True,
        null=True,
    )
    email_enviado = models.BooleanField('Email enviado?', default=False, db_index=True)
    email_erro = models.TextField('Erro de email', blank=True)
    criado_por = models.ForeignKey(
        'accounts.User',
        verbose_name='Criado por',
        on_delete=models.SET_NULL,
        related_name='orcamentos_os_criados',
        blank=True,
        null=True,
    )
    criado_em = models.DateTimeField('Criado em', auto_now_add=True, db_index=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Orçamento versionado da OS'
        verbose_name_plural = 'Orçamentos versionados da OS'
        ordering = ['-versao', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['ordem_servico', 'versao'], name='unique_work_order_approval_budget_version')
        ]

    def __str__(self):
        return f'{self.ordem_servico.codigo or self.ordem_servico_id} - v{self.versao}'

    @property
    def codigo(self):
        return f'{self.ordem_servico.codigo or self.ordem_servico_id}-ORC-v{self.versao}'

    @property
    def public_token_url_path(self):
        return reverse('work_order_public_approval', kwargs={'token': self.token})

    @property
    def public_token_url(self):
        return self.public_token_url_path

    @classmethod
    def create_from_work_order(cls, order, user=None):
        from operations.services.work_order_approval import create_budget_from_work_order

        return create_budget_from_work_order(cls, order, user=user)

    def snapshot_current_items(self, order):
        from operations.services.work_order_pricing import inventory_sale_price, money

        display_order = 0

        def next_order():
            nonlocal display_order
            display_order += 10
            return display_order

        def create_item(**kwargs):
            kwargs.setdefault('hierarquia_ordem', next_order())
            return WorkOrderApprovalBudgetItem.objects.create(orcamento=self, **kwargs)

        def create_stock_item(item, quantidade, *, parent=None, origem_tipo='', origem_codigo='', origem_nome='', origem_observacao='', obrigatoria=True):
            if not item or not quantidade:
                return None
            is_internal_supply = item.tipo == InventoryItemType.INSUMO
            valor_unitario = Decimal('0.00') if is_internal_supply else inventory_sale_price(item)
            quantidade = int(quantidade or 0)
            return create_item(
                tipo=WorkOrderApprovalItemType.PART,
                parent=parent,
                referencia_id=item.pk,
                codigo=item.sku or '',
                nome=item.nome,
                quantidade=quantidade,
                quantidade_base=quantidade,
                valor_unitario=valor_unitario,
                subtotal=Decimal('0.00') if is_internal_supply else money(valor_unitario * quantidade),
                origem_tipo='Insumo interno' if is_internal_supply else origem_tipo,
                origem_codigo=origem_codigo,
                origem_nome=origem_nome,
                origem_observacao=(
                    'Insumo interno da oficina. Fica oculto para o cliente, não compõe o valor da OS e serve apenas para rastrear despesa/estoque.'
                    if is_internal_supply
                    else origem_observacao
                ),
                peca_obrigatoria=bool(obrigatoria),
            )

        source_rows = list(order.get_stock_requirement_sources())
        for row in self._apply_stock_requirement_overrides_to_sources(order, source_rows):
            row['_quantidade_snapshot'] = row['quantidade']

        direct_part_rows = [row for row in source_rows if row.get('origem_tipo') == 'Peça avulsa']
        direct_service_rows = {}
        combo_service_rows = {}
        for row in source_rows:
            if row.get('origem_tipo') == 'Serviço' and row.get('service_id'):
                direct_service_rows.setdefault(row['service_id'], []).append(row)
            elif row.get('origem_tipo') == 'Combo' and row.get('combo_id'):
                combo_service_rows.setdefault(row['combo_id'], []).append(row)

        for service_item in order.servicos_os.select_related('service').order_by('service__nome'):
            service = service_item.service
            service_budget_item = create_item(
                tipo=WorkOrderApprovalItemType.SERVICE,
                referencia_id=service.pk,
                codigo=service.codigo or '',
                nome=service.nome,
                quantidade=service_item.quantidade,
                valor_unitario=service_item.valor_unitario or Decimal('0.00'),
                subtotal=service_item.subtotal,
                origem_tipo='Serviço',
                origem_codigo=service.codigo or '',
                origem_nome=service.nome,
            )
            for row in sorted(direct_service_rows.get(service.pk, []), key=lambda item: (item['item'].nome.lower(), item.get('service_default_part_id') or 0)):
                create_stock_item(
                    row['item'],
                    row.get('_quantidade_snapshot', row['quantidade']),
                    parent=service_budget_item,
                    origem_tipo='Peça do serviço',
                    origem_codigo=row.get('origem_codigo') or service.codigo or '',
                    origem_nome=row.get('origem_nome') or service.nome,
                    origem_observacao=row.get('origem_observacao') or 'Peça padrão vinculada ao serviço.',
                    obrigatoria=row.get('peca_obrigatoria', True),
                )
        for combo_item in order.combos_os.select_related('combo').order_by('combo__nome'):
            combo = combo_item.combo
            combo_budget_item = create_item(
                tipo=WorkOrderApprovalItemType.COMBO,
                referencia_id=combo.pk,
                codigo=combo.codigo or '',
                nome=combo.nome,
                quantidade=combo_item.quantidade,
                valor_unitario=combo_item.valor_unitario or Decimal('0.00'),
                subtotal=combo_item.subtotal,
                origem_tipo='Combo',
                origem_codigo=combo.codigo or '',
                origem_nome=combo.nome,
            )
            for row in sorted(combo_service_rows.get(combo.pk, []), key=lambda item: (item.get('service_nome') or '', item['item'].nome.lower(), item.get('service_default_part_id') or 0)):
                create_stock_item(
                    row['item'],
                    row.get('_quantidade_snapshot', row['quantidade']),
                    parent=combo_budget_item,
                    origem_tipo='Peça do combo',
                    origem_codigo=row.get('origem_codigo') or combo.codigo or '',
                    origem_nome=row.get('origem_nome') or combo.nome,
                    origem_observacao=row.get('origem_observacao') or 'Peça padrão vinculada ao serviço dentro do combo.',
                    obrigatoria=row.get('peca_obrigatoria', True),
                )

        for row in sorted(direct_part_rows, key=lambda item: item['item'].nome.lower()):
            create_stock_item(
                row['item'],
                row.get('_quantidade_snapshot', row['quantidade']),
                parent=None,
                origem_tipo='Peça',
                origem_codigo=row.get('origem_codigo') or row['item'].sku or '',
                origem_nome=row.get('origem_nome') or row['item'].nome,
                origem_observacao=row.get('origem_observacao') or 'Adicionada diretamente na OS.',
                obrigatoria=True,
            )

    def _apply_stock_requirement_overrides_to_sources(self, order, source_rows):
        requirements = {row['item'].pk: int(row['quantidade'] or 0) for row in order.get_stock_requirements()}
        grouped = {}
        for row in source_rows:
            grouped.setdefault(row['item'].pk, []).append(row)

        for item_id, rows in grouped.items():
            target_quantity = requirements.get(item_id)
            if target_quantity is None:
                continue
            base_quantity = sum(int(row.get('quantidade') or 0) for row in rows)
            diff = target_quantity - base_quantity
            if not diff:
                continue
            if diff > 0:
                rows[0]['quantidade'] = int(rows[0].get('quantidade') or 0) + diff
                continue
            remaining_to_remove = abs(diff)
            for row in reversed(rows):
                current = int(row.get('quantidade') or 0)
                reduction = min(current, remaining_to_remove)
                row['quantidade'] = current - reduction
                remaining_to_remove -= reduction
                if not remaining_to_remove:
                    break
        return source_rows

    @staticmethod
    def internal_supply_reference_ids_queryset():
        return InventoryItem.objects.filter(tipo=InventoryItemType.INSUMO).values('pk')

    def internal_supply_items_queryset(self):
        return self.itens.filter(
            tipo=WorkOrderApprovalItemType.PART,
            referencia_id__in=self.internal_supply_reference_ids_queryset(),
        )

    def customer_visible_items_queryset(self):
        return self.itens.exclude(
            tipo=WorkOrderApprovalItemType.PART,
            referencia_id__in=self.internal_supply_reference_ids_queryset(),
        )

    @property
    def customer_visible_items_ordered(self):
        return self.customer_visible_items_queryset().select_related('parent').order_by('hierarquia_ordem', 'pk')

    @property
    def internal_supply_items_ordered(self):
        return self.internal_supply_items_queryset().select_related('parent').order_by('hierarquia_ordem', 'pk')

    @staticmethod
    def _legacy_linked_part_matches_parent(item, parent):
        """Identify linked parts from budgets generated before hierarchy fields.

        Older pending approval budgets may have service default parts saved as
        top-level items because the parent field did not exist yet. They still
        carry origin metadata, so the approval rules must treat them as children
        of their service/combo instead of allowing the customer to uncheck a
        mandatory linked part independently.
        """
        if item.parent_id or item.tipo != WorkOrderApprovalItemType.PART:
            return False
        origem_tipo = (item.origem_tipo or '').lower()
        if parent.tipo == WorkOrderApprovalItemType.SERVICE and 'serv' not in origem_tipo:
            return False
        if parent.tipo == WorkOrderApprovalItemType.COMBO and 'combo' not in origem_tipo:
            return False

        child_origin_names = {value for value in [item.origem_nome, item.origem_codigo] if value}
        parent_origin_names = {value for value in [parent.nome, parent.codigo, parent.origem_nome, parent.origem_codigo] if value}
        return bool(child_origin_names & parent_origin_names)

    def _visible_children_for_parent(self, visible_items, parent):
        children = []
        for item in visible_items:
            if item.pk == parent.pk:
                continue
            if item.parent_id == parent.pk:
                children.append(item)
                continue
            if self._legacy_linked_part_matches_parent(item, parent):
                children.append(item)
        return children

    def _visible_unrelated_items_for_parent(self, visible_items, parent, children):
        child_ids = {item.pk for item in children}
        return [item for item in visible_items if item.pk != parent.pk and item.pk not in child_ids]

    def _single_visible_service_group(self):
        """Return the single visible service group when the budget is service-only.

        The approval screen uses this to treat a one-service OS as a package:
        the service itself and its mandatory linked parts cannot be removed
        independently. Optional linked parts remain selectable when they exist.
        """
        visible_items = list(self.customer_visible_items_ordered)
        service_parents = [
            item
            for item in visible_items
            if item.tipo == WorkOrderApprovalItemType.SERVICE and not item.parent_id
        ]
        if len(service_parents) != 1:
            return None

        parent = service_parents[0]
        children = self._visible_children_for_parent(visible_items, parent)
        unrelated_items = self._visible_unrelated_items_for_parent(visible_items, parent, children)
        if unrelated_items:
            return None

        child_parts = [item for item in children if item.tipo == WorkOrderApprovalItemType.PART]
        return {
            'parent': parent,
            'children': children,
            'child_parts': child_parts,
            'mandatory_parts': [item for item in child_parts if item.peca_obrigatoria],
            'optional_parts': [item for item in child_parts if not item.peca_obrigatoria],
        }

    def partial_approval_block_reason(self):
        """Return a human-readable reason when partial approval is indivisible.

        A single service with no customer-visible parts, or a single service
        whose visible linked parts are all mandatory, has no valid partial
        approval path for the customer. In this case the customer must either
        approve the complete budget or reject it entirely.
        """
        service_group = self._single_visible_service_group()
        if not service_group:
            return ''

        child_parts = service_group['child_parts']
        if not child_parts:
            return 'Este orçamento possui apenas um serviço sem peças. Aprove integralmente ou recuse tudo.'

        if all(child.peca_obrigatoria for child in child_parts):
            return 'Este orçamento possui apenas um serviço com peças obrigatórias. Aprove integralmente ou recuse tudo.'

        return ''

    @property
    def allows_partial_approval(self):
        return not bool(self.partial_approval_block_reason())

    def partial_approval_locked_item_ids(self):
        """IDs that must stay approved during partial approval.

        In a one-service budget with optional linked parts, partial approval is
        meant only to accept or reject optional parts. The service itself and
        mandatory linked parts stay locked as approved. This protects the same
        business rule in both the UI and POSTs crafted manually.
        """
        service_group = self._single_visible_service_group()
        if not service_group or not service_group['optional_parts']:
            return set()
        locked_ids = {service_group['parent'].pk}
        locked_ids.update(item.pk for item in service_group['mandatory_parts'])
        return locked_ids

    def partial_approval_lock_reason_for_item(self, item):
        locked_ids = self.partial_approval_locked_item_ids()
        if item.pk not in locked_ids:
            return ''
        if item.tipo == WorkOrderApprovalItemType.SERVICE:
            return 'Serviço único bloqueado na aprovação parcial; recuse tudo para rejeitar este serviço.'
        return 'Peça obrigatória vinculada ao serviço único; não pode ser removida separadamente.'

    def subtotal_by_type(self, item_type):
        total = Decimal('0.00')
        queryset = self.itens.filter(tipo=item_type, aprovado=True)
        if item_type == WorkOrderApprovalItemType.PART:
            queryset = queryset.exclude(referencia_id__in=self.internal_supply_reference_ids_queryset())
        for item in queryset:
            total += item.subtotal or Decimal('0.00')
        return total.quantize(Decimal('0.01'))

    @property
    def subtotal_aprovado(self):
        total = Decimal('0.00')
        for item in self.customer_visible_items_queryset().filter(aprovado=True):
            total += item.subtotal or Decimal('0.00')
        return total.quantize(Decimal('0.01'))

    @property
    def valor_desconto_aprovado(self):
        return (self.subtotal_aprovado * (self.desconto_percentual or Decimal('0.00')) / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def valor_total_aprovado(self):
        return (self.subtotal_aprovado - self.valor_desconto_aprovado).quantize(Decimal('0.01'))

    @property
    def total_itens(self):
        return self.itens.count()

    @property
    def total_itens_cliente(self):
        return self.customer_visible_items_queryset().count()

    @property
    def total_itens_internos(self):
        return self.internal_supply_items_queryset().count()

    @property
    def total_itens_aprovados(self):
        return self.itens.filter(aprovado=True).count()

    @property
    def total_itens_aprovados_cliente(self):
        return self.customer_visible_items_queryset().filter(aprovado=True).count()

    @property
    def total_itens_rejeitados(self):
        return self.itens.filter(aprovado=False).count()

    def get_stock_requirement_sources(self):
        rows = []
        part_items = self.itens.filter(tipo=WorkOrderApprovalItemType.PART, aprovado=True).order_by('nome', 'pk')
        inventory_map = {
            item.pk: item
            for item in InventoryItem.objects.filter(pk__in=[row.referencia_id for row in part_items if row.referencia_id]).select_related('unidade')
        }
        for row in part_items:
            inventory_item = inventory_map.get(row.referencia_id)
            if not inventory_item:
                continue
            is_internal_supply = inventory_item.tipo == InventoryItemType.INSUMO
            custo_unitario = (inventory_item.preco_custo or Decimal('0.00')).quantize(Decimal('0.01'))
            quantidade = int(row.quantidade or 0)
            rows.append({
                'item': inventory_item,
                'quantidade': quantidade,
                'valor_unitario': Decimal('0.00') if is_internal_supply else (row.valor_unitario or Decimal('0.00')).quantize(Decimal('0.01')),
                'subtotal': Decimal('0.00') if is_internal_supply else (row.subtotal or Decimal('0.00')).quantize(Decimal('0.01')),
                'custo_unitario': custo_unitario,
                'custo_total': (custo_unitario * quantidade).quantize(Decimal('0.01')),
                'is_internal_supply': is_internal_supply,
                'is_billable_to_customer': not is_internal_supply,
                'origem_tipo': 'Insumo interno' if is_internal_supply else 'Orçamento aprovado',
                'origem_nome': row.nome,
                'origem_codigo': row.codigo or '',
                'origem_observacao': f'{self.codigo}: item aprovado no snapshot versionado.' + (' Uso interno da oficina; não cobrado do cliente.' if is_internal_supply else ''),
            })
        return rows

    def apply_decision(self, decision, approved_item_ids=None, method=WorkOrderApprovalMethod.EMAIL, responsible_name='', document='', observation='Aprovado', ip='', user_agent='', location='', internal_user=None, signature_data='', signature_name=''):
        from operations.services.work_order_approval import apply_approval_decision

        return apply_approval_decision(
            self,
            decision=decision,
            approved_item_ids=approved_item_ids,
            method=method,
            responsible_name=responsible_name,
            document=document,
            observation=observation,
            ip=ip,
            user_agent=user_agent,
            location=location,
            internal_user=internal_user,
            signature_data=signature_data,
            signature_name=signature_name,
        )

    def supersede(self, user=None, observacao=''):
        if self.status == WorkOrderApprovalStatus.SUPERSEDED:
            return
        self.status = WorkOrderApprovalStatus.SUPERSEDED
        self.save(update_fields=['status', 'atualizado_em'])
        WorkOrderApprovalAudit.objects.create(
            orcamento=self,
            decisao=WorkOrderApprovalDecision.REJECT_ALL,
            metodo=WorkOrderApprovalMethod.SHOP,
            nome_responsavel='Sistema',
            documento='',
            documento_valido=False,
            observacao=observacao or 'Orçamento substituído por nova versão.',
            usuario_interno=user if getattr(user, 'is_authenticated', False) else None,
            itens_aprovados_snapshot=[],
            itens_rejeitados_snapshot=[],
        )

    def send_to_customer(self, user=None, request=None):
        from communications.services import send_work_order_approval_message
        log = send_work_order_approval_message(self, user=user, request=request)
        self.enviado_em = timezone.now()
        self.enviado_por = user if getattr(user, 'is_authenticated', False) else None
        self.email_enviado = bool(log and log.status == 'sent')
        self.email_erro = getattr(log, 'erro', '') if log else ''
        self.save(update_fields=['enviado_em', 'enviado_por', 'email_enviado', 'email_erro', 'atualizado_em'])
        return log


class WorkOrderApprovalBudgetItem(models.Model):
    orcamento = models.ForeignKey(
        WorkOrderApprovalBudget,
        verbose_name='Orçamento',
        on_delete=models.CASCADE,
        related_name='itens',
    )
    parent = models.ForeignKey(
        'self',
        verbose_name='Item pai',
        on_delete=models.CASCADE,
        related_name='filhos',
        blank=True,
        null=True,
    )
    tipo = models.CharField('Tipo', max_length=20, choices=WorkOrderApprovalItemType.choices, db_index=True)
    referencia_id = models.PositiveBigIntegerField('ID de referência', blank=True, null=True, db_index=True)
    codigo = models.CharField('Código/SKU', max_length=40, blank=True)
    nome = models.CharField('Nome', max_length=220)
    quantidade = models.PositiveIntegerField('Quantidade', default=MIN_QUANTITY, validators=[MinValueValidator(MIN_QUANTITY)])
    quantidade_base = models.PositiveIntegerField('Quantidade base', default=MIN_QUANTITY, validators=[MinValueValidator(MIN_QUANTITY)])
    valor_unitario = MoneyField('Valor unitário', default=Decimal('0.00'))
    subtotal = MoneyField('Subtotal', default=Decimal('0.00'))
    origem_tipo = models.CharField('Tipo de origem', max_length=60, blank=True)
    origem_codigo = models.CharField('Código de origem', max_length=40, blank=True)
    origem_nome = models.CharField('Nome da origem', max_length=220, blank=True)
    origem_observacao = models.CharField('Observação da origem', max_length=255, blank=True)
    peca_obrigatoria = models.BooleanField(
        'Peça obrigatória?',
        default=True,
        help_text='Usado para peças vinculadas a serviço/combo. Peças obrigatórias recusadas reprovam o item pai.',
    )
    hierarquia_ordem = models.PositiveIntegerField('Ordem hierárquica', default=0, db_index=True)
    aprovado = models.BooleanField('Aprovado?', blank=True, null=True, db_index=True)
    respondido_em = models.DateTimeField('Respondido em', blank=True, null=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Item do orçamento versionado'
        verbose_name_plural = 'Itens do orçamento versionado'
        ordering = ['hierarquia_ordem', 'pk']
        indexes = [models.Index(fields=['orcamento', 'tipo', 'aprovado'])]

    def __str__(self):
        return f'{self.orcamento.codigo} - {self.get_tipo_display()} - {self.nome}'

    @property
    def is_internal_supply(self):
        if self.tipo != WorkOrderApprovalItemType.PART or not self.referencia_id:
            return False
        return InventoryItem.objects.filter(pk=self.referencia_id, tipo=InventoryItemType.INSUMO).exists()

    @property
    def customer_visible(self):
        return not self.is_internal_supply

    @property
    def is_child_item(self):
        return bool(self.parent_id)

    @property
    def is_optional_part(self):
        return self.tipo == WorkOrderApprovalItemType.PART and self.parent_id and not self.peca_obrigatoria

    @property
    def display_tipo(self):
        if self.tipo == WorkOrderApprovalItemType.PART:
            return 'Insumo interno' if self.is_internal_supply else 'Peça'
        return self.get_tipo_display()

    def to_snapshot_dict(self):
        return {
            'id': self.pk,
            'tipo': self.tipo,
            'tipo_label': self.display_tipo,
            'interno_oficina': self.is_internal_supply,
            'visivel_cliente': self.customer_visible,
            'referencia_id': self.referencia_id,
            'codigo': self.codigo,
            'nome': self.nome,
            'quantidade': self.quantidade,
            'quantidade_base': self.quantidade_base,
            'valor_unitario': str(self.valor_unitario),
            'subtotal': str(self.subtotal),
            'origem_tipo': self.origem_tipo,
            'origem_codigo': self.origem_codigo,
            'origem_nome': self.origem_nome,
            'parent_id': self.parent_id,
            'peca_obrigatoria': self.peca_obrigatoria,
            'hierarquia_ordem': self.hierarquia_ordem,
            'aprovado': self.aprovado,
        }


class WorkOrderApprovalAudit(models.Model):
    orcamento = models.ForeignKey(
        WorkOrderApprovalBudget,
        verbose_name='Orçamento',
        on_delete=models.CASCADE,
        related_name='auditorias',
    )
    decisao = models.CharField('Decisão', max_length=30, choices=WorkOrderApprovalDecision.choices, db_index=True)
    metodo = models.CharField('Método', max_length=30, choices=WorkOrderApprovalMethod.choices, db_index=True)
    nome_responsavel = models.CharField('Responsável', max_length=180)
    documento = models.CharField('Documento informado', max_length=20, blank=True)
    documento_valido = models.BooleanField('Documento válido?', default=False)
    observacao = models.TextField('Observação', blank=True)
    ip = models.GenericIPAddressField('IP', blank=True, null=True)
    user_agent = models.TextField('User agent', blank=True)
    local = models.CharField('Local', max_length=180, blank=True)
    usuario_interno = models.ForeignKey(
        'accounts.User',
        verbose_name='Usuário interno',
        on_delete=models.SET_NULL,
        related_name='auditorias_aprovacao_os',
        blank=True,
        null=True,
    )
    itens_aprovados_snapshot = models.JSONField('Itens aprovados', default=list, blank=True)
    itens_rejeitados_snapshot = models.JSONField('Itens rejeitados', default=list, blank=True)
    assinatura_base64 = models.TextField('Assinatura digital', blank=True)
    assinatura_nome = models.CharField('Nome da assinatura', max_length=180, blank=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Auditoria de aprovação de orçamento'
        verbose_name_plural = 'Auditorias de aprovação de orçamento'
        ordering = ['-criado_em', '-pk']

    def __str__(self):
        return f'{self.orcamento.codigo} - {self.get_decisao_display()} - {self.nome_responsavel}'


class CustomerVehicleAccessToken(models.Model):
    token = models.UUIDField('Token público', default=uuid.uuid4, unique=True, editable=False, db_index=True)
    cliente = models.ForeignKey(
        'core.Customer',
        verbose_name='Cliente',
        on_delete=models.CASCADE,
        related_name='tokens_acesso_historico_veiculo',
    )
    veiculo = models.ForeignKey(
        'core.Vehicle',
        verbose_name='Veículo',
        on_delete=models.CASCADE,
        related_name='tokens_acesso_historico',
    )
    placa = models.CharField('Placa solicitada', max_length=8, db_index=True)
    email = models.EmailField('Email de envio')
    codigo_hash = models.CharField('Hash do código', max_length=128)
    tentativas = models.PositiveSmallIntegerField('Tentativas', default=0)
    expira_em = models.DateTimeField('Expira em', db_index=True)
    verificado_em = models.DateTimeField('Verificado em', blank=True, null=True)
    revogado_em = models.DateTimeField('Revogado em', blank=True, null=True)
    ip_solicitacao = models.GenericIPAddressField('IP da solicitação', blank=True, null=True)
    user_agent_solicitacao = models.TextField('User agent da solicitação', blank=True)
    ip_verificacao = models.GenericIPAddressField('IP da verificação', blank=True, null=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True, db_index=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Token de acesso ao histórico do veículo'
        verbose_name_plural = 'Tokens de acesso ao histórico do veículo'
        ordering = ['-criado_em', '-pk']
        indexes = [
            models.Index(fields=['token', 'expira_em']),
            models.Index(fields=['placa', 'email']),
        ]

    def __str__(self):
        return f'{self.placa} - {self.email} - expira {self.expira_em:%d/%m/%Y %H:%M}'

    @staticmethod
    def generate_code():
        return f'{secrets.randbelow(1_000_000):06d}'

    @classmethod
    def create_for_vehicle(cls, veiculo, code=None, validity_hours=5, request=None):
        def request_ip(req):
            if req is None:
                return None
            forwarded_for = req.META.get('HTTP_X_FORWARDED_FOR', '')
            if forwarded_for:
                return forwarded_for.split(',')[0].strip()
            return req.META.get('REMOTE_ADDR') or None

        def request_user_agent(req):
            if req is None:
                return ''
            return (req.META.get('HTTP_USER_AGENT', '') or '')[:1000]

        code = code or cls.generate_code()
        access = cls.objects.create(
            cliente=veiculo.cliente,
            veiculo=veiculo,
            placa=veiculo.placa,
            email=veiculo.cliente.email,
            codigo_hash=make_password(code),
            expira_em=timezone.now() + timedelta(hours=validity_hours),
            ip_solicitacao=request_ip(request),
            user_agent_solicitacao=request_user_agent(request),
        )
        access.raw_code = code
        return access

    @property
    def expirado(self):
        return timezone.now() >= self.expira_em

    @property
    def ativo_para_verificacao(self):
        return not self.revogado_em and not self.expirado and self.tentativas < 8

    @property
    def ativo_para_acesso(self):
        return bool(self.verificado_em and not self.revogado_em and not self.expirado)

    def revoke(self):
        self.revogado_em = timezone.now()
        self.save(update_fields=['revogado_em', 'atualizado_em'])

    def validate_code(self, code, request=None):
        if not self.ativo_para_verificacao:
            return False
        self.tentativas += 1
        is_valid = check_password(str(code or '').strip(), self.codigo_hash)
        update_fields = ['tentativas', 'atualizado_em']
        if is_valid:
            self.verificado_em = timezone.now()
            if request is not None:
                forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
                self.ip_verificacao = forwarded_for.split(',')[0].strip() if forwarded_for else (request.META.get('REMOTE_ADDR') or None)
            else:
                self.ip_verificacao = None
            update_fields.extend(['verificado_em', 'ip_verificacao'])
        self.save(update_fields=update_fields)
        return is_valid


class VehicleCheckInFuelLevel(models.TextChoices):
    VAZIO = 'vazio', 'Vazio'
    UM_QUARTO = '1_4', '1/4'
    MEIO = '1_2', '1/2'
    TRES_QUARTOS = '3_4', '3/4'
    CHEIO = 'cheio', 'Cheio'


class VehicleCheckIn(SoftDeleteModel):
    codigo = models.CharField('Código', max_length=20, unique=True, blank=True, null=True, editable=False, db_index=True)
    ordem_servico = models.ForeignKey(
        WorkOrder,
        verbose_name='Ordem de serviço',
        on_delete=models.PROTECT,
        related_name='checkins',
    )
    cliente = models.ForeignKey(
        'core.Customer',
        verbose_name='Cliente',
        on_delete=models.PROTECT,
        related_name='checkins_veiculo',
        editable=False,
    )
    veiculo = models.ForeignKey(
        'core.Vehicle',
        verbose_name='Veículo',
        on_delete=models.PROTECT,
        related_name='checkins',
        editable=False,
    )
    data_checkin = models.DateTimeField('Data do check-in', default=timezone.now, db_index=True)
    km = models.PositiveIntegerField('KM no check-in', blank=True, null=True, validators=[MinValueValidator(0)])
    nivel_combustivel = models.CharField(
        'Nível de combustível',
        max_length=20,
        choices=VehicleCheckInFuelLevel.choices,
        blank=True,
    )
    possui_estepe = models.BooleanField('Possui estepe?', default=False)
    possui_macaco = models.BooleanField('Possui macaco?', default=False)
    possui_chave_roda = models.BooleanField('Possui chave de roda?', default=False)
    possui_documento = models.BooleanField('Documento do veículo presente?', default=False)
    objetos_deixados = models.TextField('Objetos deixados no veículo', blank=True)
    avarias_observadas = models.TextField('Avarias observadas', blank=True)
    observacoes = models.TextField('Observações gerais', blank=True)
    criado_por = models.ForeignKey(
        'accounts.User',
        verbose_name='Criado por',
        on_delete=models.SET_NULL,
        related_name='checkins_criados',
        blank=True,
        null=True,
        editable=False,
    )
    email_enviado = models.BooleanField('PDF enviado ao cliente?', default=False, db_index=True)
    email_enviado_em = models.DateTimeField('PDF enviado em', blank=True, null=True)
    email_enviado_por = models.ForeignKey(
        'accounts.User',
        verbose_name='PDF enviado por',
        on_delete=models.SET_NULL,
        related_name='checkins_enviados',
        blank=True,
        null=True,
    )
    email_erro = models.TextField('Erro no envio do email', blank=True)

    class Meta:
        verbose_name = 'Check-in de veículo'
        verbose_name_plural = 'Check-ins de veículos'
        ordering = ['-data_checkin', '-pk']
        constraints = [
            models.UniqueConstraint(
                fields=['ordem_servico'],
                condition=Q(ativo=True) & Q(excluido_em__isnull=True),
                name='unique_active_checkin_per_work_order',
            )
        ]

    def __str__(self):
        return f'{self.codigo or "Sem código"} - {self.cliente.nome_razao_social}'

    def get_absolute_url(self):
        return reverse('vehicle_checkin_detail', kwargs={'pk': self.pk})

    def generate_codigo(self):
        return f'CHK-{self.pk:05d}'

    def save(self, *args, **kwargs):
        if self.ordem_servico_id:
            self.cliente = self.ordem_servico.cliente
            self.veiculo = self.ordem_servico.veiculo
            if self.km is None and self.ordem_servico.km_atual is not None:
                self.km = self.ordem_servico.km_atual
        super().save(*args, **kwargs)
        if not self.codigo:
            self.codigo = self.generate_codigo()
            type(self).all_objects.filter(pk=self.pk).update(codigo=self.codigo)


class VehicleCheckInPhoto(models.Model):
    checkin = models.ForeignKey(
        VehicleCheckIn,
        verbose_name='Check-in',
        on_delete=models.CASCADE,
        related_name='fotos',
    )
    imagem = models.ImageField('Foto', upload_to='checkins/%Y/%m/')
    legenda = models.CharField('Legenda', max_length=180, blank=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Foto do check-in'
        verbose_name_plural = 'Fotos do check-in'
        ordering = ['pk']

    def __str__(self):
        return f'Foto {self.pk} - {self.checkin.codigo or self.checkin_id}'
