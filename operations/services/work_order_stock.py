import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .work_order_pricing import inventory_sale_price, money

logger = logging.getLogger(__name__)


def get_stock_requirement_sources(order):
    budget = order.get_effective_approval_budget()
    if budget:
        return budget.get_stock_requirement_sources()

    rows = []

    def add_row(item, quantidade, origem_tipo, origem_nome, origem_codigo='', origem_observacao=''):
        if not item or not quantidade:
            return
        quantidade = int(quantidade)
        valor_unitario = inventory_sale_price(item)
        rows.append({
            'item': item,
            'quantidade': quantidade,
            'valor_unitario': valor_unitario,
            'subtotal': money(valor_unitario * quantidade),
            'origem_tipo': origem_tipo,
            'origem_nome': origem_nome,
            'origem_codigo': origem_codigo or '',
            'origem_observacao': origem_observacao or '',
        })

    for part in order.pecas_os.select_related('item', 'item__unidade'):
        add_row(
            part.item,
            part.quantidade,
            'Peça avulsa',
            part.item.nome,
            part.item.sku or '',
            'Adicionada diretamente na OS.',
        )

    for service_item in order.servicos_os.select_related('service').prefetch_related('service__pecas_associadas__item__unidade'):
        service = service_item.service
        for default_part in service.pecas_associadas.select_related('item', 'item__unidade'):
            add_row(
                default_part.item,
                service_item.quantidade * default_part.quantidade,
                'Serviço',
                service.nome,
                service.codigo or '',
                f'{service_item.quantidade} x serviço; {default_part.quantidade} x peça padrão.',
            )

    combo_queryset = order.combos_os.select_related('combo').prefetch_related(
        'combo__servicos_associados__service__pecas_associadas__item__unidade'
    )
    for combo_item in combo_queryset:
        combo = combo_item.combo
        for combo_service in combo.servicos_associados.select_related('service').prefetch_related('service__pecas_associadas__item__unidade'):
            service = combo_service.service
            for default_part in service.pecas_associadas.select_related('item', 'item__unidade'):
                add_row(
                    default_part.item,
                    combo_item.quantidade * default_part.quantidade,
                    'Combo',
                    f'{combo.nome} / {service.nome}',
                    combo.codigo or '',
                    f'{combo_item.quantidade} x combo; {default_part.quantidade} x peça padrão do serviço {service.codigo or service.nome}.',
                )

    return sorted(rows, key=lambda row: (row['item'].nome.lower(), row['origem_tipo'], row['origem_nome'].lower()))


def get_base_stock_requirements(order):
    requirements = {}

    for row in get_stock_requirement_sources(order):
        item = row['item']
        current = requirements.setdefault(item.pk, {
            'item': item,
            'quantidade': 0,
            'valor_unitario': row['valor_unitario'],
            'subtotal': Decimal('0.00'),
        })
        current['quantidade'] += int(row['quantidade'])
        current['subtotal'] += row['subtotal']

    for row in requirements.values():
        row['subtotal'] = money(row['subtotal'])

    return sorted(requirements.values(), key=lambda row: row['item'].nome.lower())


def get_stock_requirement_overrides_map(order):
    if not order.pk:
        return {}
    return {
        override.item_id: override
        for override in order.ajustes_pecas_previstas.select_related('item')
    }


def get_stock_requirements(order):
    overrides = get_stock_requirement_overrides_map(order)
    requirements = []

    for row in get_base_stock_requirements(order):
        item = row['item']
        quantidade_base = int(row['quantidade'] or 0)
        override = overrides.get(item.pk)
        quantidade = int(override.quantidade if override else quantidade_base)
        valor_unitario = row['valor_unitario']
        requirements.append({
            'item': item,
            'quantidade_base': quantidade_base,
            'quantidade': quantidade,
            'valor_unitario': valor_unitario,
            'subtotal_base': row['subtotal'],
            'subtotal': money(valor_unitario * quantidade),
            'ajustada': bool(override),
            'override': override,
        })

    return sorted(requirements, key=lambda row: row['item'].nome.lower())


def update_stock_requirement_overrides(order, quantities):
    from operations.models import WorkOrderStockRequirementOverride

    if order.estoque_baixado:
        raise ValidationError('Não é possível ajustar peças previstas de uma OS com estoque já baixado.')

    with transaction.atomic():
        locked_order = type(order).objects.select_for_update().get(pk=order.pk)
        base_requirements = {row['item'].pk: int(row['quantidade'] or 0) for row in get_base_stock_requirements(locked_order)}
        valid_item_ids = set(base_requirements)

        locked_order.ajustes_pecas_previstas.exclude(item_id__in=valid_item_ids).delete()

        for item_id, quantidade in quantities.items():
            if item_id not in valid_item_ids:
                continue
            quantidade = int(quantidade)
            quantidade_base = base_requirements[item_id]
            if quantidade == quantidade_base:
                locked_order.ajustes_pecas_previstas.filter(item_id=item_id).delete()
            else:
                WorkOrderStockRequirementOverride.objects.update_or_create(
                    ordem_servico=locked_order,
                    item_id=item_id,
                    defaults={'quantidade': quantidade},
                )


def get_stock_shortages(order):
    shortages = []
    for row in get_stock_requirements(order):
        item = row['item']
        required = int(row['quantidade'] or 0)
        current = int(item.estoque_atual or 0)
        if current < required:
            shortages.append({
                'item': item,
                'quantidade': required,
                'estoque_atual': current,
                'faltante': required - current,
            })
    return shortages


def has_stock_shortage(order):
    return bool(get_stock_shortages(order))


def stock_shortage_message(order):
    shortages = get_stock_shortages(order)
    if not shortages:
        return ''
    parts = []
    for row in shortages[:5]:
        item = row['item']
        unidade = item.unidade.sigla if item.unidade_id else ''
        parts.append(
            f'{item.sku or "Sem SKU"} - {item.nome}: necessário {row["quantidade"]} {unidade}, disponível {row["estoque_atual"]} {unidade}'
        )
    suffix = ''
    if len(shortages) > 5:
        suffix = f' e mais {len(shortages) - 5} item(ns)'
    return '; '.join(parts) + suffix


def ensure_awaiting_parts_if_needed(order, user=None, observacao=''):
    from operations.models import WorkOrderStatus
    from stock.models import PurchaseOrder

    if order.status == WorkOrderStatus.AGUARDANDO_PECA and has_stock_shortage(order):
        PurchaseOrder.create_or_update_from_work_order_shortages(order, user=user)
        return None
    if order.status not in {WorkOrderStatus.APROVADA, WorkOrderStatus.EM_EXECUCAO, WorkOrderStatus.EM_TESTE}:
        return None
    if not has_stock_shortage(order):
        return None
    return order.transition_to(
        WorkOrderStatus.AGUARDANDO_PECA,
        user=user,
        observacao=observacao or 'OS movida automaticamente para Aguardando peça por estoque insuficiente.',
    )


def baixar_estoque(order, user=None):
    from operations.models import WorkOrderStatus
    from stock.models import InventoryItem, StockMovement, StockMovementType

    if order.estoque_baixado:
        raise ValidationError('O estoque desta OS já foi baixado.')
    if order.status == WorkOrderStatus.CANCELADA:
        raise ValidationError('Não é possível baixar estoque de uma OS cancelada.')
    if order.status == WorkOrderStatus.ARQUIVADA:
        raise ValidationError('Não é possível baixar estoque de uma OS arquivada.')
    if order.status not in WorkOrderStatus.stock_out_statuses():
        raise ValidationError('A baixa de estoque só pode ser feita quando a OS estiver em execução, aguardando peça, em teste, pronta, pronto para retirar ou entregue.')

    with transaction.atomic():
        locked_order = type(order).objects.select_for_update().get(pk=order.pk)
        if locked_order.estoque_baixado:
            raise ValidationError('O estoque desta OS já foi baixado.')

        requirements = get_stock_requirements(locked_order)
        if not requirements:
            locked_order.estoque_baixado = True
            locked_order.estoque_baixado_em = timezone.now()
            locked_order.estoque_baixado_por = user if getattr(user, 'is_authenticated', False) else None
            locked_order.save(update_fields=['estoque_baixado', 'estoque_baixado_em', 'estoque_baixado_por', 'atualizado_em'])
            order.refresh_from_db(fields=['estoque_baixado', 'estoque_baixado_em', 'estoque_baixado_por', 'atualizado_em'])
            return []

        locked_items = {
            item.pk: item
            for item in InventoryItem.objects.select_for_update().filter(pk__in=[row['item'].pk for row in requirements])
        }

        movements = []
        for row in requirements:
            item = locked_items.get(row['item'].pk)
            if item is None:
                raise ValidationError(f'Peça/Insumo não encontrado para baixa: {row["item"]}.')
            quantidade = int(row['quantidade'] or 0)
            movement = StockMovement(
                item=item,
                tipo=StockMovementType.SAIDA,
                quantidade=quantidade,
                custo_unitario=item.preco_custo,
                observacao=f'Baixa automática da {locked_order.codigo}',
                criado_por=user if getattr(user, 'is_authenticated', False) else None,
            )
            movement.full_clean()
            movement.save()
            movements.append(movement)

        locked_order.estoque_baixado = True
        locked_order.estoque_baixado_em = timezone.now()
        locked_order.estoque_baixado_por = user if getattr(user, 'is_authenticated', False) else None
        locked_order.save(update_fields=['estoque_baixado', 'estoque_baixado_em', 'estoque_baixado_por', 'atualizado_em'])
        order.refresh_from_db(fields=['estoque_baixado', 'estoque_baixado_em', 'estoque_baixado_por', 'atualizado_em'])

    return movements
