import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def transition_to(order, new_status, user=None, observacao='', request=None):
    from communications.services import send_work_order_status_change_message
    from operations.models import WorkOrderStatus, WorkOrderStatusTransition
    from stock.models import PurchaseOrder

    if new_status == order.status:
        return None
    if not order.can_transition_to(new_status):
        current_label = order.get_status_display()
        new_label = WorkOrderStatus(new_status).label if new_status in WorkOrderStatus.values else new_status
        raise ValidationError(f'Transição inválida: {current_label} → {new_label}.')

    if (
        order.status == WorkOrderStatus.AGUARDANDO_APROVACAO
        and new_status == WorkOrderStatus.APROVADA
        and order.has_approval_in_progress
    ):
        raise ValidationError('Use Registrar aprovação para aprovar uma OS com orçamento pendente.')

    if order.status == WorkOrderStatus.DIAGNOSTICO and not (order.diagnostico or '').strip():
        raise ValidationError('Preencha o campo Diagnóstico antes de mover a OS para outra coluna.')

    if new_status == WorkOrderStatus.EM_EXECUCAO and not order.checkins.filter(ativo=True, excluido_em__isnull=True).exists():
        raise ValidationError('Não é possível mover a OS para Em execução sem check-in associado.')

    if new_status == WorkOrderStatus.EM_EXECUCAO and order.has_stock_shortage():
        raise ValidationError(
            'Não é possível mover a OS para Em execução porque há peças sem estoque suficiente: '
            f'{order.stock_shortage_message()}.'
        )

    purchase_order_needed = False
    budget_to_send = None
    transition = None

    with transaction.atomic():
        locked_order = type(order).objects.select_for_update().get(pk=order.pk)
        if locked_order.status != order.status:
            order.refresh_from_db()
            raise ValidationError('A OS foi alterada por outro usuário. Atualize a página e tente novamente.')

        previous_status = locked_order.status
        locked_order.status = new_status
        if locked_order.status in WorkOrderStatus.completed_statuses() and not locked_order.data_finalizacao:
            locked_order.data_finalizacao = timezone.now()
        if locked_order.status not in WorkOrderStatus.completed_statuses():
            locked_order.data_finalizacao = None
        locked_order.save(update_fields=['status', 'data_finalizacao', 'atualizado_em'])

        transition = WorkOrderStatusTransition.objects.create(
            ordem_servico=locked_order,
            status_anterior=previous_status,
            status_novo=new_status,
            observacao=observacao or '',
            criado_por=user if getattr(user, 'is_authenticated', False) else None,
        )

        if new_status == WorkOrderStatus.AGUARDANDO_PECA and locked_order.has_stock_shortage():
            purchase_order_needed = True

        if new_status == WorkOrderStatus.AGUARDANDO_APROVACAO:
            budget_to_send = locked_order.get_or_create_pending_approval_budget(user=user, send_email=False)

    order.refresh_from_db(fields=['status', 'data_finalizacao', 'atualizado_em'])

    if purchase_order_needed:
        try:
            PurchaseOrder.create_or_update_from_work_order_shortages(order, user=user)
        except Exception:
            logger.exception('Erro ao criar/atualizar pedido de compra automático para OS %s.', order.pk)

    if budget_to_send is not None:
        try:
            budget_to_send.send_to_customer(user=user, request=request)
        except Exception:
            logger.exception('Erro ao enviar orçamento de aprovação da OS %s.', order.pk)

    try:
        send_work_order_status_change_message(order, transition, user=user)
    except Exception:
        logger.exception('Erro ao enviar mensagem de mudança de status da OS %s.', order.pk)

    return transition
