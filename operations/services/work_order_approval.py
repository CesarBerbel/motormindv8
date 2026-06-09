import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .work_order_pricing import money

logger = logging.getLogger(__name__)


def _legacy_linked_part_matches_parent(item, parent):
    if item.parent_id or item.tipo != 'part':
        return False
    origem_tipo = (item.origem_tipo or '').lower()
    if parent.tipo == 'service' and 'serv' not in origem_tipo:
        return False
    if parent.tipo == 'combo' and 'combo' not in origem_tipo:
        return False
    child_origin_names = {value for value in [item.origem_nome, item.origem_codigo] if value}
    parent_origin_names = {value for value in [parent.nome, parent.codigo, parent.origem_nome, parent.origem_codigo] if value}
    return bool(child_origin_names & parent_origin_names)


def _build_children_by_parent(visible_items):
    children_by_parent = {}
    parent_items = [item for item in visible_items if item.tipo in {'service', 'combo'} and not item.parent_id]
    for item in visible_items:
        if item.parent_id:
            children_by_parent.setdefault(item.parent_id, []).append(item)
            continue
        for parent in parent_items:
            if parent.pk != item.pk and _legacy_linked_part_matches_parent(item, parent):
                children_by_parent.setdefault(parent.pk, []).append(item)
                break
    return children_by_parent


def _single_visible_service_group(visible_items, children_by_parent):
    service_parents = [item for item in visible_items if item.tipo == 'service' and not item.parent_id]
    if len(service_parents) != 1:
        return None
    parent = service_parents[0]
    children = children_by_parent.get(parent.pk, [])
    child_ids = {child.pk for child in children}
    unrelated_items = [item for item in visible_items if item.pk != parent.pk and item.pk not in child_ids]
    if unrelated_items:
        return None
    child_parts = [item for item in children if item.tipo == 'part']
    optional_parts = [item for item in child_parts if not item.peca_obrigatoria]
    if not optional_parts:
        return None
    mandatory_parts = [item for item in child_parts if item.peca_obrigatoria]
    return parent, mandatory_parts


def _locked_item_ids_for_single_service_partial(visible_items, children_by_parent):
    group = _single_visible_service_group(visible_items, children_by_parent)
    if not group:
        return set()
    parent, mandatory_parts = group
    locked_ids = {parent.pk}
    locked_ids.update(item.pk for item in mandatory_parts)
    return locked_ids


def normalize_partial_approval_item_ids(items, approved_item_ids):
    """Apply hierarchy rules to a partial approval selection.

    Parent service/combo items protect their mandatory child parts. If a
    mandatory child part is not approved, the parent and all child parts from
    that parent are rejected. Optional child parts can be rejected individually.
    Existing pending budgets generated before the hierarchy fields are also
    protected by inferring legacy child parts from origin metadata.
    """
    selected = {int(item_id) for item_id in approved_item_ids or []}
    visible_items = [item for item in items if item.customer_visible]
    visible_ids = {item.pk for item in visible_items}
    selected &= visible_ids
    visible_by_id = {item.pk: item for item in visible_items}
    children_by_parent = _build_children_by_parent(visible_items)

    for item in visible_items:
        if item.parent_id and item.parent_id not in visible_by_id:
            selected.discard(item.pk)

    selected |= _locked_item_ids_for_single_service_partial(visible_items, children_by_parent)

    for parent_id, children in children_by_parent.items():
        parent = visible_by_id.get(parent_id)
        if not parent:
            selected -= {child.pk for child in children}
            continue
        child_ids = {child.pk for child in children}
        mandatory_child_ids = {child.pk for child in children if child.peca_obrigatoria}

        if parent.pk not in selected:
            selected -= child_ids
            continue

        if mandatory_child_ids and not mandatory_child_ids.issubset(selected):
            selected.discard(parent.pk)
            selected -= child_ids
            continue

        selected |= mandatory_child_ids

    return selected


def create_budget_from_work_order(budget_model, order, user=None):
    from operations.models import WorkOrderApprovalStatus

    with transaction.atomic():
        type(order).objects.select_for_update().get(pk=order.pk)
        latest = order.orcamentos_aprovacao.select_for_update().order_by('-versao', '-pk').first()
        if latest and latest.status == WorkOrderApprovalStatus.PENDING:
            latest.status = WorkOrderApprovalStatus.SUPERSEDED
            latest.save(update_fields=['status', 'atualizado_em'])
        next_version = (latest.versao + 1) if latest else 1
        subtotal = money(order.subtotal_servicos + order.subtotal_combos + order.subtotal_pecas)
        discount_percent = order.desconto_percentual_normalizado
        discount_value = money(subtotal * discount_percent / Decimal('100'))
        total_value = money(subtotal - discount_value)
        vehicle = order.veiculo
        budget = budget_model.objects.create(
            ordem_servico=order,
            versao=next_version,
            status=WorkOrderApprovalStatus.PENDING,
            desconto_percentual=discount_percent,
            subtotal_snapshot=subtotal,
            valor_desconto_snapshot=discount_value,
            valor_total_snapshot=total_value,
            criado_por=user if getattr(user, 'is_authenticated', False) else None,
            snapshot={
                'ordem_servico_id': order.pk,
                'ordem_servico_codigo': order.codigo,
                'cliente_id': order.cliente_id,
                'cliente_nome': order.cliente.nome_razao_social,
                'cliente_email': order.cliente.email,
                'veiculo_id': order.veiculo_id,
                'veiculo': f'{vehicle.placa} - {vehicle.marca} {vehicle.modelo}' if vehicle else '',
                'status_os': order.status,
                'desconto_percentual': str(discount_percent),
                'subtotal': str(subtotal),
                'valor_desconto': str(discount_value),
                'valor_total': str(total_value),
                'criado_em': timezone.now().isoformat(),
            },
        )
        budget.snapshot_current_items(order)
        return budget


def apply_approval_decision(budget, decision, approved_item_ids=None, method=None, responsible_name='', document='', observation='Aprovado', ip='', user_agent='', location='', internal_user=None, signature_data='', signature_name=''):
    from operations.models import (
        WorkOrderApprovalAudit,
        WorkOrderApprovalDecision,
        WorkOrderApprovalMethod,
        WorkOrderApprovalStatus,
        WorkOrderStatus,
    )
    from stock.models import PurchaseOrder

    method = method or WorkOrderApprovalMethod.EMAIL
    approved_item_ids = {int(item_id) for item_id in (approved_item_ids or []) if str(item_id).isdigit()}

    with transaction.atomic():
        locked_budget = type(budget).objects.select_for_update().select_related('ordem_servico').get(pk=budget.pk)
        items = list(locked_budget.itens.select_for_update().select_related('parent').order_by('hierarquia_ordem', 'pk'))
        items_by_id = {item.pk: item for item in items}
        internal_supply_item_ids = set(
            locked_budget.internal_supply_items_queryset().select_for_update().values_list('pk', flat=True)
        )
        visible_items = [item for item in items if item.pk not in internal_supply_item_ids]

        if decision == WorkOrderApprovalDecision.APPROVE_ALL:
            for item in items:
                item.aprovado = True
                item.respondido_em = timezone.now()
                item.save(update_fields=['aprovado', 'respondido_em', 'atualizado_em'])
            locked_budget.status = WorkOrderApprovalStatus.APPROVED
        elif decision == WorkOrderApprovalDecision.REJECT_ALL:
            for item in items:
                item.aprovado = False
                item.respondido_em = timezone.now()
                item.save(update_fields=['aprovado', 'respondido_em', 'atualizado_em'])
            locked_budget.status = WorkOrderApprovalStatus.REJECTED
        else:
            if not locked_budget.allows_partial_approval:
                raise ValueError(
                    locked_budget.partial_approval_block_reason()
                    or 'Este orçamento não permite aprovação parcial. Aprove integralmente ou recuse tudo.'
                )
            if not approved_item_ids:
                raise ValueError('Selecione ao menos um item para aprovação parcial.')
            approved_item_ids = normalize_partial_approval_item_ids(items, approved_item_ids)
            if not approved_item_ids:
                raise ValueError('Selecione ao menos um item válido para aprovação parcial.')
            visible_approved = False
            for item in visible_items:
                item.aprovado = item.pk in approved_item_ids
                visible_approved = visible_approved or bool(item.aprovado)
                item.respondido_em = timezone.now()
                item.save(update_fields=['aprovado', 'respondido_em', 'atualizado_em'])
            for item in items:
                if item.pk in internal_supply_item_ids:
                    # Insumos são decisão interna da oficina: não aparecem para o cliente.
                    # Quando pertencem a serviço/combo, acompanham o item pai; quando são
                    # avulsos internos, acompanham a OS se houver algum item visível aprovado.
                    parent = items_by_id.get(item.parent_id) if item.parent_id else None
                    item.aprovado = bool(parent.aprovado) if parent else visible_approved
                    item.respondido_em = timezone.now()
                    item.save(update_fields=['aprovado', 'respondido_em', 'atualizado_em'])
            locked_budget.status = WorkOrderApprovalStatus.PARTIALLY_APPROVED

        locked_budget.save(update_fields=['status', 'atualizado_em'])

        approved_snapshot = [item.to_snapshot_dict() for item in items if item.aprovado is True]
        rejected_snapshot = [item.to_snapshot_dict() for item in items if item.aprovado is False]
        audit = WorkOrderApprovalAudit.objects.create(
            orcamento=locked_budget,
            decisao=decision,
            metodo=method,
            nome_responsavel=responsible_name,
            documento=document,
            documento_valido=bool(document),
            observacao=observation or '',
            ip=ip or '',
            user_agent=user_agent or '',
            local=location or '',
            usuario_interno=internal_user if getattr(internal_user, 'is_authenticated', False) else None,
            assinatura_base64=signature_data or '',
            assinatura_nome=signature_name or '',
            itens_aprovados_snapshot=approved_snapshot,
            itens_rejeitados_snapshot=rejected_snapshot,
        )

    budget.refresh_from_db(fields=['status', 'atualizado_em'])
    approved_statuses = {WorkOrderApprovalStatus.APPROVED, WorkOrderApprovalStatus.PARTIALLY_APPROVED}
    target_status = WorkOrderStatus.APROVADA if budget.status in approved_statuses else WorkOrderStatus.ORCAMENTO
    if budget.ordem_servico.status != target_status:
        budget.ordem_servico.transition_to(
            target_status,
            user=internal_user,
            observacao=f'Resposta do orçamento {budget.codigo}: {budget.get_status_display()}.',
        )

    if budget.status in approved_statuses:
        try:
            PurchaseOrder.create_or_update_from_work_order_shortages(budget.ordem_servico, user=internal_user)
        except Exception:
            logger.exception('Erro ao criar/atualizar pedido de compra automático após aprovação do orçamento %s.', budget.pk)

    return audit
