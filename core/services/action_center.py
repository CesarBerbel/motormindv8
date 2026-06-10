from dataclasses import dataclass, field
from datetime import timedelta
from typing import Iterable

from django.urls import NoReverseMatch, reverse
from django.utils import timezone


PRIORITY_CRITICAL = 'critical'
PRIORITY_HIGH = 'high'
PRIORITY_NORMAL = 'normal'
PRIORITY_LOW = 'low'

PRIORITY_LABELS = {
    PRIORITY_CRITICAL: 'Crítica',
    PRIORITY_HIGH: 'Alta',
    PRIORITY_NORMAL: 'Normal',
    PRIORITY_LOW: 'Baixa',
}

PRIORITY_ORDER = {
    PRIORITY_CRITICAL: 0,
    PRIORITY_HIGH: 1,
    PRIORITY_NORMAL: 2,
    PRIORITY_LOW: 3,
}

TYPE_LABELS = {
    'site': 'Site',
    'os': 'OS',
    'aprovacao': 'Aprovação',
    'estoque': 'Estoque',
    'compra': 'Compra',
    'mensagem': 'Mensagem',
}

PRIORITY_BADGE_CLASSES = {
    PRIORITY_CRITICAL: 'badge-error',
    PRIORITY_HIGH: 'badge-warning',
    PRIORITY_NORMAL: 'badge-info badge-outline',
    PRIORITY_LOW: 'badge-ghost',
}


@dataclass
class ActionCenterItem:
    key: str
    title: str
    description: str
    type: str
    priority: str
    url: str
    primary_label: str = 'Abrir'
    created_at: object | None = None
    responsible: str = ''
    status: str = ''
    object_label: str = ''
    metadata: list[tuple[str, str]] = field(default_factory=list)
    secondary_actions: list[dict] = field(default_factory=list)

    @property
    def type_label(self):
        return TYPE_LABELS.get(self.type, self.type.title())

    @property
    def priority_label(self):
        return PRIORITY_LABELS.get(self.priority, self.priority.title())

    @property
    def priority_badge_class(self):
        return PRIORITY_BADGE_CLASSES.get(self.priority, 'badge-outline')

    @property
    def age_label(self):
        if not self.created_at:
            return '-'
        delta = timezone.localtime() - self.created_at
        total_minutes = max(int(delta.total_seconds() // 60), 0)
        if total_minutes < 60:
            return f'{total_minutes} min'
        total_hours = total_minutes // 60
        if total_hours < 24:
            return f'{total_hours} h'
        total_days = total_hours // 24
        return f'{total_days} d'


def safe_reverse(name, *args, fallback='#', **kwargs):
    try:
        return reverse(name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return fallback


def _is_admin_manager(user):
    return bool(getattr(user, 'is_superuser', False) or getattr(user, 'role', '') == 'adm')


def _can_access_technical_area(user):
    try:
        from accounts.permissions import can_access_technical_area

        return can_access_technical_area(user)
    except Exception:
        return False


def _work_order_url(order, user):
    if _can_access_technical_area(user):
        return safe_reverse('mechanic_work_order_detail', order.pk)
    return safe_reverse('work_order_detail', order.pk)


def _work_order_action_url(order, user):
    from operations.models import WorkOrderStatus

    if order.status == WorkOrderStatus.DIAGNOSTICO and _can_access_technical_area(user):
        return safe_reverse('mechanic_work_order_diagnosis', order.pk)
    if order.status in {WorkOrderStatus.APROVADA, WorkOrderStatus.EM_EXECUCAO, WorkOrderStatus.EM_TESTE} and _can_access_technical_area(user):
        return safe_reverse('mechanic_kanban')
    if order.status == WorkOrderStatus.AGUARDANDO_APROVACAO:
        return safe_reverse('work_order_register_approval', order.pk)
    return _work_order_url(order, user)


def _work_order_primary_label(order, user):
    from operations.models import WorkOrderStatus

    if order.status == WorkOrderStatus.DIAGNOSTICO and _can_access_technical_area(user):
        return 'Adicionar diagnóstico'
    if order.status == WorkOrderStatus.ORCAMENTO:
        return 'Preparar orçamento'
    if order.status == WorkOrderStatus.AGUARDANDO_APROVACAO:
        return 'Registrar aprovação'
    if order.status == WorkOrderStatus.APROVADA:
        return 'Iniciar execução'
    if order.status == WorkOrderStatus.EM_TESTE:
        return 'Registrar teste'
    if order.status in {WorkOrderStatus.PRONTA, WorkOrderStatus.PRONTO_PARA_RETIRAR}:
        return 'Finalizar entrega'
    return 'Abrir OS'


def _format_vehicle(order):
    if not order.veiculo_id:
        return '-'
    return f'{order.veiculo.placa} · {order.veiculo.marca} {order.veiculo.modelo}'.strip()


def _collect_site_lead_actions(user, now):
    if not user.has_perm('website.view_lead'):
        return []

    from website.models import Lead, LeadStatus

    actions = []
    leads = Lead.objects.select_related('servico').filter(
        status__in=[LeadStatus.NOVO, LeadStatus.EM_CONTATO],
    ).order_by('criado_em', 'pk')[:30]

    stale_threshold = now - timedelta(days=2)
    for lead in leads:
        priority = PRIORITY_HIGH if lead.status == LeadStatus.NOVO else PRIORITY_NORMAL
        if lead.criado_em and lead.criado_em <= stale_threshold and lead.status != LeadStatus.CONCLUIDO:
            priority = PRIORITY_CRITICAL
        metadata = [
            ('Cliente', lead.nome),
            ('Contato', lead.telefone),
        ]
        if lead.placa:
            metadata.append(('Placa', lead.placa))
        if lead.servico_id:
            metadata.append(('Serviço', lead.servico.titulo))
        actions.append(ActionCenterItem(
            key=f'site-lead-{lead.pk}',
            title='Pedido de orçamento recebido',
            description=lead.mensagem or 'Pedido enviado pelo formulário público do site.',
            type='site',
            priority=priority,
            url=safe_reverse('site_lead_detail', lead.pk),
            primary_label='Ver pedido',
            created_at=lead.criado_em,
            responsible='Atendimento',
            status=lead.get_status_display(),
            object_label=lead.nome,
            metadata=metadata,
            secondary_actions=[{'label': 'Lista de pedidos', 'url': safe_reverse('site_lead_list')}],
        ))
    return actions


def _visible_work_orders(user):
    from operations.models import WorkOrder, WorkOrderStatus

    qs = WorkOrder.objects.select_related('cliente', 'veiculo', 'tecnico_responsavel').filter(
        status__in=WorkOrderStatus.workshop_capacity_statuses(),
        ativo=True,
        excluido_em__isnull=True,
    )

    if _is_admin_manager(user) or user.has_perm('operations.view_workorder'):
        return qs

    if _can_access_technical_area(user):
        return qs.filter(
            tecnico_responsavel=user,
        ) | qs.filter(
            tecnico_responsavel__isnull=True,
            status__in=[WorkOrderStatus.ABERTA, WorkOrderStatus.DIAGNOSTICO],
        )

    return qs.none()


def _collect_work_order_actions(user, now):
    from operations.models import WorkOrderStatus

    qs = _visible_work_orders(user).distinct()
    actions = []

    delayed = qs.filter(previsao_entrega__lt=now).exclude(status__in=WorkOrderStatus.completed_statuses()).order_by('previsao_entrega', '-data_abertura')[:20]
    for order in delayed:
        actions.append(ActionCenterItem(
            key=f'wo-delayed-{order.pk}',
            title=f'{order.codigo} atrasada',
            description=f'Previsão vencida para {order.previsao_entrega:%d/%m/%Y %H:%M}.',
            type='os',
            priority=PRIORITY_CRITICAL,
            url=_work_order_url(order, user),
            primary_label='Ver OS',
            created_at=order.previsao_entrega,
            responsible=order.tecnico_responsavel.nome_razao_social if order.tecnico_responsavel_id else 'Sem técnico',
            status=order.get_status_display(),
            object_label=order.codigo,
            metadata=[('Cliente', order.cliente.nome_razao_social), ('Veículo', _format_vehicle(order)), ('Status', order.get_status_display())],
        ))

    diagnosis_qs = qs.filter(status=WorkOrderStatus.DIAGNOSTICO).filter(diagnostico='').order_by('data_abertura', 'pk')[:20]
    for order in diagnosis_qs:
        actions.append(ActionCenterItem(
            key=f'wo-diagnosis-{order.pk}',
            title=f'{order.codigo} aguardando diagnóstico',
            description=order.problema_relatado[:180],
            type='os',
            priority=PRIORITY_HIGH,
            url=_work_order_action_url(order, user),
            primary_label=_work_order_primary_label(order, user),
            created_at=order.data_abertura,
            responsible=order.tecnico_responsavel.nome_razao_social if order.tecnico_responsavel_id else 'Disponível',
            status=order.get_status_display(),
            object_label=order.codigo,
            metadata=[('Cliente', order.cliente.nome_razao_social), ('Veículo', _format_vehicle(order)), ('Responsável', order.tecnico_responsavel.nome_razao_social if order.tecnico_responsavel_id else 'Livre')],
            secondary_actions=[{'label': 'Kanban técnico', 'url': safe_reverse('mechanic_kanban')}],
        ))

    status_specs = [
        (WorkOrderStatus.ORCAMENTO, PRIORITY_HIGH, 'preparar orçamento', 'Preparar orçamento'),
        (WorkOrderStatus.AGUARDANDO_APROVACAO, PRIORITY_NORMAL, 'aguardando aprovação do cliente', 'Registrar aprovação'),
        (WorkOrderStatus.APROVADA, PRIORITY_HIGH, 'aprovada para execução', 'Iniciar execução'),
        (WorkOrderStatus.AGUARDANDO_PECA, PRIORITY_CRITICAL, 'aguardando peça/insumo', 'Resolver falta'),
        (WorkOrderStatus.EM_TESTE, PRIORITY_NORMAL, 'em teste final', 'Registrar teste'),
        (WorkOrderStatus.PRONTA, PRIORITY_HIGH, 'pronta para entrega', 'Entregar'),
        (WorkOrderStatus.PRONTO_PARA_RETIRAR, PRIORITY_NORMAL, 'pronta para retirada', 'Finalizar'),
    ]
    for status, priority, phrase, label in status_specs:
        for order in qs.filter(status=status).order_by('previsao_entrega', 'data_abertura', 'pk')[:12]:
            actions.append(ActionCenterItem(
                key=f'wo-status-{status}-{order.pk}',
                title=f'{order.codigo} {phrase}',
                description=order.problema_relatado[:180],
                type='os',
                priority=priority,
                url=_work_order_action_url(order, user),
                primary_label=label,
                created_at=order.data_abertura,
                responsible=order.tecnico_responsavel.nome_razao_social if order.tecnico_responsavel_id else 'Sem técnico',
                status=order.get_status_display(),
                object_label=order.codigo,
                metadata=[('Cliente', order.cliente.nome_razao_social), ('Veículo', _format_vehicle(order)), ('Status', order.get_status_display())],
                secondary_actions=[{'label': 'Detalhes da OS', 'url': _work_order_url(order, user)}],
            ))
    return actions


def _collect_approval_actions(user, now):
    if not user.has_perm('operations.view_workorder'):
        return []

    from operations.models import WorkOrderApprovalBudget, WorkOrderApprovalStatus

    budgets = WorkOrderApprovalBudget.objects.select_related('ordem_servico', 'ordem_servico__cliente', 'ordem_servico__veiculo').filter(
        status=WorkOrderApprovalStatus.PENDING,
    ).order_by('criado_em', 'pk')[:25]
    actions = []
    stale_threshold = now - timedelta(days=3)
    for budget in budgets:
        order = budget.ordem_servico
        actions.append(ActionCenterItem(
            key=f'approval-{budget.pk}',
            title=f'Orçamento pendente {order.codigo}',
            description='Cliente ainda não aprovou nem recusou este orçamento.',
            type='aprovacao',
            priority=PRIORITY_HIGH if budget.criado_em and budget.criado_em <= stale_threshold else PRIORITY_NORMAL,
            url=safe_reverse('work_order_approval_detail', budget.pk),
            primary_label='Ver aprovação',
            created_at=budget.criado_em,
            responsible='Atendimento',
            status=budget.get_status_display(),
            object_label=order.codigo,
            metadata=[('Cliente', order.cliente.nome_razao_social), ('Total', f'R$ {budget.valor_total_snapshot}'), ('OS', order.codigo)],
            secondary_actions=[{'label': 'OS', 'url': safe_reverse('work_order_detail', order.pk)}],
        ))
    return actions


def _collect_stock_actions(user, now):
    if not user.has_perm('stock.view_inventoryitem'):
        return []

    from stock.models import InventoryItem

    items = [item for item in InventoryItem.objects.select_related('categoria', 'marca', 'unidade') if item.abaixo_estoque_minimo]
    items.sort(key=lambda item: (item.estoque_atual, item.estoque_minimo, item.nome.lower()))
    actions = []
    for item in items[:25]:
        priority = PRIORITY_CRITICAL if item.estoque_atual <= 0 else PRIORITY_HIGH
        actions.append(ActionCenterItem(
            key=f'stock-low-{item.pk}',
            title=f'{item.nome} abaixo do mínimo',
            description='Item precisa de reposição ou conferência de estoque.',
            type='estoque',
            priority=priority,
            url=safe_reverse('inventory_item_detail', item.pk),
            primary_label='Ver estoque',
            created_at=getattr(item, 'atualizado_em', None) or getattr(item, 'criado_em', None),
            responsible='Estoque',
            status='Crítico' if priority == PRIORITY_CRITICAL else 'Abaixo do mínimo',
            object_label=item.sku or item.nome,
            metadata=[('SKU', item.sku or '-'), ('Atual', str(item.estoque_atual)), ('Mínimo', str(item.estoque_minimo)), ('Tipo', item.get_tipo_display())],
            secondary_actions=[{'label': 'Criar compra', 'url': safe_reverse('purchase_order_create')}],
        ))
    return actions


def _collect_purchase_actions(user, now):
    if not user.has_perm('stock.view_purchaseorder'):
        return []

    from stock.models import PurchaseOrder, PurchaseOrderStatus

    orders = PurchaseOrder.objects.select_related('fornecedor', 'ordem_servico').filter(
        status__in=[PurchaseOrderStatus.PENDENTE, PurchaseOrderStatus.SOLICITADO],
        ativo=True,
        excluido_em__isnull=True,
    ).order_by('criado_em', 'pk')[:20]
    actions = []
    stale_threshold = now - timedelta(days=2)
    for purchase in orders:
        priority = PRIORITY_HIGH if purchase.criado_em and purchase.criado_em <= stale_threshold else PRIORITY_NORMAL
        actions.append(ActionCenterItem(
            key=f'purchase-{purchase.pk}',
            title=f'{purchase.codigo} aguardando compra/entrada',
            description=purchase.observacao or 'Pedido de compra ainda aberto.',
            type='compra',
            priority=priority,
            url=safe_reverse('purchase_order_detail', purchase.pk),
            primary_label='Ver pedido',
            created_at=purchase.criado_em,
            responsible='Estoque',
            status=purchase.get_status_display(),
            object_label=purchase.codigo,
            metadata=[('Fornecedor', purchase.fornecedor.nome_razao_social if purchase.fornecedor_id else '-'), ('Origem', purchase.get_origem_display()), ('Status', purchase.get_status_display())],
            secondary_actions=[{'label': 'Receber', 'url': safe_reverse('purchase_order_receive', purchase.pk)}] if purchase.can_receive else [],
        ))
    return actions


def _collect_message_actions(user, now):
    if not user.has_perm('communications.view_messagelog'):
        return []

    from communications.models import MessageLog, MessageStatus

    logs = MessageLog.objects.filter(status=MessageStatus.ERROR).order_by('-atualizado_em', '-pk')[:20]
    actions = []
    for log in logs:
        actions.append(ActionCenterItem(
            key=f'message-error-{log.pk}',
            title=f'Falha de mensagem para {log.destinatario_nome}',
            description=log.erro or log.assunto,
            type='mensagem',
            priority=PRIORITY_HIGH,
            url=safe_reverse('message_history') + f'?q={log.destinatario_nome}',
            primary_label='Ver histórico',
            created_at=log.atualizado_em,
            responsible='Atendimento',
            status=log.get_status_display(),
            object_label=log.assunto,
            metadata=[('Destinatário', log.destinatario_nome), ('Assunto', log.assunto), ('OS', log.ordem_servico_codigo or '-')],
        ))
    return actions


def get_action_center_items(user, limit=None):
    if not getattr(user, 'is_authenticated', False):
        return []

    now = timezone.localtime()
    collectors = [
        _collect_site_lead_actions,
        _collect_work_order_actions,
        _collect_approval_actions,
        _collect_stock_actions,
        _collect_purchase_actions,
        _collect_message_actions,
    ]
    items = []
    for collector in collectors:
        try:
            items.extend(collector(user, now))
        except Exception:
            # A central não deve derrubar o dashboard se uma app opcional ou migration
            # ainda não estiver disponível em um ambiente intermediário de deploy.
            continue

    deduped = {}
    for item in items:
        deduped.setdefault(item.key, item)
    sorted_items = sorted(
        deduped.values(),
        key=lambda item: (
            PRIORITY_ORDER.get(item.priority, 9),
            item.created_at or now,
            item.type,
            item.title,
        ),
    )
    if limit is not None:
        return sorted_items[:limit]
    return sorted_items


def get_action_center_summary(items: Iterable[ActionCenterItem]):
    items = list(items)
    by_priority = {key: 0 for key in PRIORITY_LABELS}
    by_type = {key: 0 for key in TYPE_LABELS}
    for item in items:
        by_priority[item.priority] = by_priority.get(item.priority, 0) + 1
        by_type[item.type] = by_type.get(item.type, 0) + 1
    return {
        'total': len(items),
        'critical': by_priority.get(PRIORITY_CRITICAL, 0),
        'high': by_priority.get(PRIORITY_HIGH, 0),
        'normal': by_priority.get(PRIORITY_NORMAL, 0),
        'low': by_priority.get(PRIORITY_LOW, 0),
        'by_priority': by_priority,
        'by_type': by_type,
    }


def filter_action_center_items(items, query='', priority='', type_name=''):
    query = (query or '').strip().lower()
    priority = (priority or '').strip()
    type_name = (type_name or '').strip()

    filtered = []
    for item in items:
        if priority and item.priority != priority:
            continue
        if type_name and item.type != type_name:
            continue
        if query:
            haystack = ' '.join([
                item.title,
                item.description,
                item.object_label,
                item.status,
                item.responsible,
                ' '.join(f'{label} {value}' for label, value in item.metadata),
            ]).lower()
            if query not in haystack:
                continue
        filtered.append(item)
    return filtered
