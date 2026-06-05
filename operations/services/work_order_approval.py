import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .work_order_pricing import money

logger = logging.getLogger(__name__)


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
        items = list(locked_budget.itens.select_for_update().order_by('pk'))
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
            if not approved_item_ids:
                raise ValueError('Selecione ao menos um item para aprovação parcial.')
            for item in items:
                item.aprovado = item.pk in approved_item_ids
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
