from decimal import Decimal

from .work_order_pricing import money


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
    return money(sum((item.subtotal for item in order.pecas_os.all()), Decimal('0.00')))


def subtotal_pecas(order):
    from operations.models import WorkOrderApprovalItemType

    budget = order.get_effective_approval_budget()
    if budget:
        return budget.subtotal_by_type(WorkOrderApprovalItemType.PART)
    return money(sum((row['subtotal'] for row in order.get_stock_requirements()), Decimal('0.00')))


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
