from decimal import Decimal

from stock.models import InventoryItemType

from .work_order_pricing import money


def _is_customer_billable_stock_item(item):
    return getattr(item, 'tipo', None) == InventoryItemType.PECA


def subtotal_servicos(order):
    from operations.models import WorkOrderApprovalItemType

    budget = order.get_effective_approval_budget()
    if budget:
        return budget.subtotal_by_type(WorkOrderApprovalItemType.SERVICE)
    return money(sum((item.subtotal for item in order.servicos_os.all()), Decimal('0.00')))


def subtotal_combos(order):
    from operations.models import WorkOrderApprovalItemType

    budget = order.get_effective_approval_budget()
    if budget:
        return budget.subtotal_by_type(WorkOrderApprovalItemType.COMBO)
    return money(sum((item.subtotal for item in order.combos_os.all()), Decimal('0.00')))


def subtotal_pecas_avulsas(order):
    total = Decimal('0.00')
    for item in order.pecas_os.select_related('item'):
        if _is_customer_billable_stock_item(item.item):
            total += item.subtotal
    return money(total)


def subtotal_pecas(order):
    from operations.models import WorkOrderApprovalItemType

    budget = order.get_effective_approval_budget()
    if budget:
        return budget.subtotal_by_type(WorkOrderApprovalItemType.PART)
    return money(
        sum(
            (row['subtotal'] for row in order.get_stock_requirements() if row.get('is_billable_to_customer')),
            Decimal('0.00'),
        )
    )


def custo_insumos(order):
    return money(
        sum(
            (row.get('custo_total', Decimal('0.00')) for row in order.get_stock_requirements() if row.get('is_internal_supply')),
            Decimal('0.00'),
        )
    )


def subtotal_insumos(order):
    # Alias semântico para uso nas telas: insumo não é receita, é custo interno.
    return custo_insumos(order)


def custo_servicos(order):
    total = Decimal('0.00')
    for item in order.servicos_os.select_related('service'):
        total += item.custo_total
    for item in order.combos_os.select_related('combo').prefetch_related('combo__servicos_associados__service'):
        total += item.custo_total
    return money(total)


def custo_operacional(order):
    return money(order.custo_servicos + order.custo_insumos)


def subtotal(order):
    budget = order.get_effective_approval_budget()
    if budget:
        return budget.subtotal_aprovado
    return money(order.subtotal_servicos + order.subtotal_combos + order.subtotal_pecas)


def valor_desconto(order):
    budget = order.get_effective_approval_budget()
    if budget:
        return budget.valor_desconto_aprovado
    return money(order.subtotal * order.desconto_percentual_normalizado / Decimal('100'))


def valor_total(order):
    budget = order.get_effective_approval_budget()
    if budget:
        return budget.valor_total_aprovado
    return money(order.subtotal - order.valor_desconto)


def duracao_total_minutos(order):
    total = 0
    for item in order.servicos_os.select_related('service'):
        total += (item.service.duracao_minutos or 0) * item.quantidade
    for item in order.combos_os.select_related('combo').prefetch_related('combo__servicos_associados__service'):
        total += (item.combo.duracao_total_minutos or 0) * item.quantidade
    return total
