from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.urls import reverse
from django.utils import timezone

from core.money import MoneyField, normalize_money

ZERO_QUANTITY = 0
MIN_QUANTITY = 1


class ActiveStockManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(ativo=True, excluido_em__isnull=True)


class SoftDeleteModel(models.Model):
    ativo = models.BooleanField('Ativo?', default=True, db_index=True)
    excluido_em = models.DateTimeField('Excluído em', blank=True, null=True, db_index=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    objects = ActiveStockManager()
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


class StockCategory(SoftDeleteModel):
    nome = models.CharField('Nome', max_length=120)
    descricao = models.TextField('Descrição', blank=True)

    class Meta:
        verbose_name = 'Categoria de estoque'
        verbose_name_plural = 'Categorias de estoque'
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(
                fields=['nome'],
                condition=Q(ativo=True) & Q(excluido_em__isnull=True),
                name='unique_active_stock_category_name',
            )
        ]

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse('stock_category_list')


class Brand(SoftDeleteModel):
    nome = models.CharField('Nome', max_length=120)

    class Meta:
        verbose_name = 'Marca'
        verbose_name_plural = 'Marcas'
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(
                fields=['nome'],
                condition=Q(ativo=True) & Q(excluido_em__isnull=True),
                name='unique_active_brand_name',
            )
        ]

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse('brand_list')


class UnitOfMeasure(models.Model):
    nome = models.CharField('Nome', max_length=80, unique=True)
    sigla = models.CharField('Sigla', max_length=12, unique=True)
    permite_fracionado = models.BooleanField('Permite fracionado?', default=True)
    ativo = models.BooleanField('Ativo?', default=True, db_index=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Unidade de medida'
        verbose_name_plural = 'Unidades de medida'
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} ({self.sigla})'


class InventoryItemType(models.TextChoices):
    PECA = 'peca', 'Peça'
    INSUMO = 'insumo', 'Insumo'


class InventoryItem(SoftDeleteModel):
    tipo = models.CharField('Tipo', max_length=20, choices=InventoryItemType.choices, default=InventoryItemType.PECA)
    sku = models.CharField('Código da peça/SKU', max_length=60, unique=True, blank=True, null=True, db_index=True)
    nome = models.CharField('Nome', max_length=180)
    descricao = models.TextField('Descrição', blank=True)
    categoria = models.ForeignKey(
        StockCategory,
        verbose_name='Categoria',
        on_delete=models.PROTECT,
        related_name='itens',
    )
    marca = models.ForeignKey(
        Brand,
        verbose_name='Marca',
        on_delete=models.PROTECT,
        related_name='itens',
        blank=True,
        null=True,
    )
    estoque_minimo = models.PositiveIntegerField(
        'Estoque mínimo',
        default=ZERO_QUANTITY,
        validators=[MinValueValidator(0)],
    )
    unidade = models.ForeignKey(
        UnitOfMeasure,
        verbose_name='Unidade',
        on_delete=models.PROTECT,
        related_name='itens',
    )
    preco_custo = MoneyField('Preço de custo', default=Decimal('0.00'))
    preco_venda = MoneyField('Preço de venda', default=Decimal('0.00'))

    class Meta:
        verbose_name = 'Peça/Insumo'
        verbose_name_plural = 'Peças e insumos'
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(
                fields=['nome', 'categoria', 'marca'],
                condition=Q(ativo=True) & Q(excluido_em__isnull=True),
                name='unique_active_inventory_item_by_name_category_brand',
            )
        ]

    def __str__(self):
        return f'{self.sku or "Sem SKU"} - {self.nome}'

    def get_absolute_url(self):
        return reverse('inventory_item_detail', kwargs={'pk': self.pk})

    def get_sku_prefix(self):
        return 'PCA' if self.tipo == InventoryItemType.PECA else 'INS'

    def generate_sku(self):
        return f'{self.get_sku_prefix()}-{self.pk:06d}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.sku:
            self.sku = self.generate_sku()
            type(self).all_objects.filter(pk=self.pk).update(sku=self.sku)

    @property
    def estoque_atual(self):
        total = self.movimentacoes.aggregate(total=Sum('quantidade_assinada'))['total']
        return total or ZERO_QUANTITY

    @property
    def abaixo_estoque_minimo(self):
        return self.estoque_atual < self.estoque_minimo

    @property
    def valor_venda(self):
        from operations.services.work_order_pricing import inventory_sale_price

        return inventory_sale_price(self)

    @property
    def margem_bruta(self):
        from operations.services.work_order_pricing import inventory_margin_value

        return inventory_margin_value(self)

    @property
    def margem_percentual(self):
        from operations.services.work_order_pricing import inventory_margin_percent

        return inventory_margin_percent(self)


class StockMovementType(models.TextChoices):
    ENTRADA = 'entrada', 'Entrada'
    SAIDA = 'saida', 'Saída'
    AJUSTE_POSITIVO = 'ajuste_positivo', 'Ajuste positivo'
    AJUSTE_NEGATIVO = 'ajuste_negativo', 'Ajuste negativo'


class StockMovement(models.Model):
    item = models.ForeignKey(
        InventoryItem,
        verbose_name='Peça/Insumo',
        on_delete=models.PROTECT,
        related_name='movimentacoes',
    )
    fornecedor = models.ForeignKey(
        'core.Supplier',
        verbose_name='Fornecedor',
        on_delete=models.PROTECT,
        related_name='movimentacoes_estoque',
        blank=True,
        null=True,
    )
    tipo = models.CharField('Tipo de movimentação', max_length=30, choices=StockMovementType.choices)
    quantidade = models.PositiveIntegerField(
        'Quantidade',
        validators=[MinValueValidator(MIN_QUANTITY)],
    )
    quantidade_assinada = models.IntegerField(
        'Quantidade assinada',
        editable=False,
    )
    saldo_apos_movimentacao = models.PositiveIntegerField(
        'Saldo após movimentação',
        editable=False,
    )
    custo_unitario = MoneyField('Custo unitário', blank=True, null=True)
    valor_total = MoneyField('Valor total', default=Decimal('0.00'), editable=False)
    observacao = models.TextField('Observação', blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Criado por',
        on_delete=models.SET_NULL,
        related_name='movimentacoes_estoque',
        blank=True,
        null=True,
    )
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Movimentação de estoque'
        verbose_name_plural = 'Movimentações de estoque'
        ordering = ['-criado_em', '-pk']

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.item.nome} - {self.quantidade}'

    def get_absolute_url(self):
        return reverse('stock_movement_detail', kwargs={'pk': self.pk})

    @property
    def is_outflow(self):
        return self.tipo in {StockMovementType.SAIDA, StockMovementType.AJUSTE_NEGATIVO}

    @property
    def signed_quantity_value(self):
        quantity = self.quantidade or ZERO_QUANTITY
        if self.is_outflow:
            return -quantity
        return quantity

    def clean(self):
        super().clean()
        if self.pk:
            return

        if self.tipo == StockMovementType.ENTRADA and not self.fornecedor_id:
            raise ValidationError({'fornecedor': 'Informe o fornecedor para movimentações de entrada.'})

        if self.tipo and self.tipo != StockMovementType.ENTRADA and self.fornecedor_id:
            raise ValidationError({'fornecedor': 'Fornecedor deve ser informado apenas para movimentações de entrada.'})

        if not self.item_id or not self.quantidade:
            return

        saldo = self.item.estoque_atual + self.signed_quantity_value
        if saldo < ZERO_QUANTITY:
            raise ValidationError({'quantidade': 'A movimentação não pode deixar o estoque negativo.'})

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('Movimentações de estoque não podem ser alteradas depois de salvas.')

        if self.tipo == StockMovementType.ENTRADA and not self.fornecedor_id:
            raise ValidationError({'fornecedor': 'Informe o fornecedor para movimentações de entrada.'})

        if self.tipo != StockMovementType.ENTRADA:
            self.fornecedor = None

        self.quantidade_assinada = self.signed_quantity_value
        self.saldo_apos_movimentacao = self.item.estoque_atual + self.quantidade_assinada
        if self.saldo_apos_movimentacao < ZERO_QUANTITY:
            raise ValidationError('A movimentação não pode deixar o estoque negativo.')

        if self.custo_unitario is None:
            self.custo_unitario = self.item.preco_custo

        unit_cost = normalize_money(self.custo_unitario) or Decimal('0.00')
        self.valor_total = normalize_money(abs(self.quantidade) * unit_cost) or Decimal('0.00')
        super().save(*args, **kwargs)


class PurchaseOrderStatus(models.TextChoices):
    PENDENTE = 'pendente', 'Pendente'
    SOLICITADO = 'solicitado', 'Solicitado'
    RECEBIDO = 'recebido', 'Recebido'
    CANCELADO = 'cancelado', 'Cancelado'


class PurchaseOrderSource(models.TextChoices):
    MANUAL = 'manual', 'Manual'
    AUTOMATICO_OS = 'automatico_os', 'Automático por OS'


class PurchaseOrder(SoftDeleteModel):
    codigo = models.CharField('Código', max_length=20, unique=True, blank=True, null=True, editable=False, db_index=True)
    fornecedor = models.ForeignKey(
        'core.Supplier',
        verbose_name='Fornecedor',
        on_delete=models.PROTECT,
        related_name='pedidos_compra',
        blank=True,
        null=True,
        help_text='Obrigatório para receber o pedido e dar entrada no estoque.',
    )
    ordem_servico = models.ForeignKey(
        'operations.WorkOrder',
        verbose_name='OS de origem',
        on_delete=models.SET_NULL,
        related_name='pedidos_compra',
        blank=True,
        null=True,
    )
    origem = models.CharField('Origem', max_length=30, choices=PurchaseOrderSource.choices, default=PurchaseOrderSource.MANUAL, db_index=True)
    status = models.CharField('Status', max_length=20, choices=PurchaseOrderStatus.choices, default=PurchaseOrderStatus.PENDENTE, db_index=True)
    observacao = models.TextField('Observação', blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Criado por',
        on_delete=models.SET_NULL,
        related_name='pedidos_compra_criados',
        blank=True,
        null=True,
    )
    recebido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Recebido por',
        on_delete=models.SET_NULL,
        related_name='pedidos_compra_recebidos',
        blank=True,
        null=True,
    )
    recebido_em = models.DateTimeField('Recebido em', blank=True, null=True)

    class Meta:
        verbose_name = 'Pedido de compra'
        verbose_name_plural = 'Pedidos de compra'
        ordering = ['-criado_em', '-pk']

    def __str__(self):
        return f'{self.codigo or "Sem código"} - {self.get_status_display()}'

    def get_absolute_url(self):
        return reverse('purchase_order_detail', kwargs={'pk': self.pk})

    def generate_codigo(self):
        return f'PC-{self.pk:05d}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.codigo:
            self.codigo = self.generate_codigo()
            type(self).all_objects.filter(pk=self.pk).update(codigo=self.codigo)

    @property
    def is_editable(self):
        return self.status in {PurchaseOrderStatus.PENDENTE, PurchaseOrderStatus.SOLICITADO}

    @property
    def can_receive(self):
        return self.status in {PurchaseOrderStatus.PENDENTE, PurchaseOrderStatus.SOLICITADO}

    @property
    def valor_total(self):
        total = Decimal('0.00')
        for item in self.itens.all():
            total += item.subtotal
        return total.quantize(Decimal('0.01'))

    @property
    def total_itens(self):
        return self.itens.count()

    @property
    def quantidade_total(self):
        total = self.itens.aggregate(total=Sum('quantidade'))['total']
        return total or ZERO_QUANTITY

    def clean(self):
        super().clean()
        if self.status == PurchaseOrderStatus.RECEBIDO and not self.fornecedor_id:
            raise ValidationError({'fornecedor': 'Informe o fornecedor antes de receber o pedido.'})

    def receber(self, user=None):
        from django.db import transaction

        if not self.can_receive:
            raise ValidationError('Somente pedidos pendentes ou solicitados podem ser recebidos.')
        if not self.fornecedor_id:
            raise ValidationError('Informe o fornecedor antes de receber o pedido.')

        itens = list(self.itens.select_related('item'))
        if not itens:
            raise ValidationError('Inclua ao menos um item antes de receber o pedido.')

        movements = []
        with transaction.atomic():
            for order_item in itens:
                movement = StockMovement(
                    item=order_item.item,
                    fornecedor=self.fornecedor,
                    tipo=StockMovementType.ENTRADA,
                    quantidade=order_item.quantidade,
                    custo_unitario=order_item.custo_unitario,
                    observacao=f'Entrada automática do pedido {self.codigo}',
                    criado_por=user if getattr(user, 'is_authenticated', False) else None,
                )
                movement.full_clean()
                movement.save()
                movements.append(movement)

            self.status = PurchaseOrderStatus.RECEBIDO
            self.recebido_em = timezone.now()
            self.recebido_por = user if getattr(user, 'is_authenticated', False) else None
            self.save(update_fields=['status', 'recebido_em', 'recebido_por', 'atualizado_em'])

        return movements

    @classmethod
    def create_or_update_from_work_order_shortages(cls, order, user=None):
        shortages = order.get_stock_shortages()
        if not shortages:
            return None

        pedido = cls.objects.filter(
            ordem_servico=order,
            origem=PurchaseOrderSource.AUTOMATICO_OS,
            status__in=[PurchaseOrderStatus.PENDENTE, PurchaseOrderStatus.SOLICITADO],
        ).first()

        created = False
        if pedido is None:
            pedido = cls.objects.create(
                ordem_servico=order,
                origem=PurchaseOrderSource.AUTOMATICO_OS,
                status=PurchaseOrderStatus.PENDENTE,
                criado_por=user if getattr(user, 'is_authenticated', False) else None,
                observacao=f'Criado automaticamente por falta de estoque na {order.codigo}.',
            )
            created = True

        for shortage in shortages:
            item = shortage['item']
            quantidade = int(shortage['faltante'] or 0)
            if quantidade <= 0:
                continue
            order_item, item_created = PurchaseOrderItem.objects.get_or_create(
                pedido=pedido,
                item=item,
                defaults={
                    'quantidade': quantidade,
                    'custo_unitario': item.preco_custo,
                    'observacao': f'Falta de estoque na {order.codigo}: necessário {shortage["quantidade"]}, disponível {shortage["estoque_atual"]}.',
                },
            )
            if not item_created and order_item.quantidade < quantidade:
                order_item.quantidade = quantidade
                order_item.custo_unitario = item.preco_custo
                order_item.observacao = f'Atualizado automaticamente pela {order.codigo}: falta atual {quantidade}.'
                order_item.save(update_fields=['quantidade', 'custo_unitario', 'observacao', 'atualizado_em'])

        if not created:
            pedido.observacao = f'Atualizado automaticamente por falta de estoque na {order.codigo}.'
            pedido.save(update_fields=['observacao', 'atualizado_em'])

        return pedido


class PurchaseOrderItem(models.Model):
    pedido = models.ForeignKey(
        PurchaseOrder,
        verbose_name='Pedido de compra',
        on_delete=models.CASCADE,
        related_name='itens',
    )
    item = models.ForeignKey(
        InventoryItem,
        verbose_name='Peça/Insumo',
        on_delete=models.PROTECT,
        related_name='itens_pedido_compra',
    )
    quantidade = models.PositiveIntegerField('Quantidade', validators=[MinValueValidator(MIN_QUANTITY)])
    custo_unitario = MoneyField('Custo unitário', blank=True, null=True)
    observacao = models.CharField('Observação', max_length=255, blank=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Item do pedido de compra'
        verbose_name_plural = 'Itens do pedido de compra'
        ordering = ['item__nome']
        constraints = [
            models.UniqueConstraint(fields=['pedido', 'item'], name='unique_purchase_order_item')
        ]

    def __str__(self):
        return f'{self.pedido.codigo or self.pedido_id} - {self.item.nome}'

    def save(self, *args, **kwargs):
        if self.custo_unitario is None and self.item_id:
            self.custo_unitario = self.item.preco_custo
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        unit_cost = self.custo_unitario or Decimal('0.00')
        return (unit_cost * self.quantidade).quantize(Decimal('0.01'))
