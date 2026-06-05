from decimal import Decimal
import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from core.money import MoneyField
from stock.models import InventoryItem, MIN_QUANTITY


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

    def transition_to(self, new_status, user=None, observacao=''):
        from operations.services.work_order_status import transition_to

        return transition_to(self, new_status, user=user, observacao=observacao)

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
        if self.valor_unitario is None and self.item_id:
            from operations.services.work_order_pricing import inventory_sale_price

            self.valor_unitario = inventory_sale_price(self.item)
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return ((self.valor_unitario or Decimal('0.00')) * self.quantidade).quantize(Decimal('0.01'))


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
        items = []
        for service_item in order.servicos_os.select_related('service').order_by('service__nome'):
            service = service_item.service
            items.append(WorkOrderApprovalBudgetItem(
                orcamento=self,
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
            ))
        for combo_item in order.combos_os.select_related('combo').order_by('combo__nome'):
            combo = combo_item.combo
            items.append(WorkOrderApprovalBudgetItem(
                orcamento=self,
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
            ))
        for row in order.get_stock_requirements():
            item = row['item']
            items.append(WorkOrderApprovalBudgetItem(
                orcamento=self,
                tipo=WorkOrderApprovalItemType.PART,
                referencia_id=item.pk,
                codigo=item.sku or '',
                nome=item.nome,
                quantidade=row['quantidade'],
                quantidade_base=row.get('quantidade_base') or row['quantidade'],
                valor_unitario=row['valor_unitario'],
                subtotal=row['subtotal'],
                origem_tipo='Peça/Insumo',
                origem_codigo=item.sku or '',
                origem_nome=item.nome,
                origem_observacao='Peças avulsas e peças padrão consolidadas no momento do orçamento.',
            ))
        WorkOrderApprovalBudgetItem.objects.bulk_create(items)

    def subtotal_by_type(self, item_type):
        total = Decimal('0.00')
        for item in self.itens.filter(tipo=item_type, aprovado=True):
            total += item.subtotal or Decimal('0.00')
        return total.quantize(Decimal('0.01'))

    @property
    def subtotal_aprovado(self):
        total = Decimal('0.00')
        for item in self.itens.filter(aprovado=True):
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
    def total_itens_aprovados(self):
        return self.itens.filter(aprovado=True).count()

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
            rows.append({
                'item': inventory_item,
                'quantidade': int(row.quantidade or 0),
                'valor_unitario': (row.valor_unitario or Decimal('0.00')).quantize(Decimal('0.01')),
                'subtotal': (row.subtotal or Decimal('0.00')).quantize(Decimal('0.01')),
                'origem_tipo': 'Orçamento aprovado',
                'origem_nome': row.nome,
                'origem_codigo': row.codigo or '',
                'origem_observacao': f'{self.codigo}: item aprovado no snapshot versionado.',
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
    aprovado = models.BooleanField('Aprovado?', blank=True, null=True, db_index=True)
    respondido_em = models.DateTimeField('Respondido em', blank=True, null=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Item do orçamento versionado'
        verbose_name_plural = 'Itens do orçamento versionado'
        ordering = ['tipo', 'nome', 'pk']
        indexes = [models.Index(fields=['orcamento', 'tipo', 'aprovado'])]

    def __str__(self):
        return f'{self.orcamento.codigo} - {self.get_tipo_display()} - {self.nome}'

    def to_snapshot_dict(self):
        return {
            'id': self.pk,
            'tipo': self.tipo,
            'tipo_label': self.get_tipo_display(),
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
