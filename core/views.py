from datetime import timedelta
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import json

from django.apps import apps
from django.conf import settings as dj_settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView, View

from .forms import CategoryForm, CustomerForm, SupplierForm, VehicleForm, format_cep, format_cnpj, format_cpf, format_phone
from .models import (
    AppNotification,
    Category,
    CategoryAudience,
    Customer,
    PessoaTipo,
    Supplier,
    Vehicle,
    VehicleDirectionType,
    VehicleFipeType,
    VehicleFuelType,
    format_plate,
    only_alnum_upper,
    only_digits,
)


class ServiceWorkerView(TemplateView):
    template_name = 'pwa/sw.js'
    content_type = 'application/javascript'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pwa_enabled'] = bool(getattr(dj_settings, 'PWA_ENABLED', False))
        context['pwa_cache_prefix'] = getattr(dj_settings, 'PWA_CACHE_PREFIX', 'motormind')
        return context

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        response['Service-Worker-Allowed'] = '/'
        return response


def get_website_lead_from_request(request):
    lead_id = request.GET.get('lead')
    if not (lead_id and lead_id.isdigit()):
        return None

    Lead = apps.get_model('website', 'Lead')
    return Lead.objects.filter(pk=int(lead_id)).first()


def split_vehicle_description(description):
    parts = (description or '').strip().split()
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], ' '.join(parts[1:])



class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'

    def user_is_admin_manager(self):
        user = self.request.user
        return user.is_superuser or getattr(user, 'role', '') == 'adm'

    def safe_reverse(self, url_name, fallback='#'):
        try:
            return reverse(url_name)
        except Exception:
            return fallback

    def money_sum(self, queryset, field_name):
        value = queryset.aggregate(total=Sum(field_name)).get('total')
        return (value or Decimal('0.00')).quantize(Decimal('0.01'))

    def format_percent(self, numerator, denominator):
        if not denominator:
            return 0
        return round((numerator / denominator) * 100)

    def get_quick_actions(self, is_admin):
        user = self.request.user
        actions = []

        def add(label, description, url_name, permission=None, admin_only=False, tone='btn-primary'):
            if admin_only and not is_admin:
                return
            if permission and not user.has_perm(permission):
                return
            actions.append({
                'label': label,
                'description': description,
                'url': self.safe_reverse(url_name),
                'tone': tone,
            })

        add('Nova OS', 'Abrir ordem de serviço', 'work_order_create', 'operations.add_workorder')
        add('Kanban técnico', 'Fila da mecânica', 'mechanic_kanban', None, tone='btn-secondary')
        add('Novo check-in', 'Receber veículo', 'vehicle_checkin_create', 'operations.add_vehiclecheckin', tone='btn-outline')
        add('Novo cliente', 'Cadastrar cliente', 'customer_create', 'core.add_customer', tone='btn-outline')
        add('Nova peça/insumo', 'Cadastrar estoque', 'inventory_item_create', 'stock.add_inventoryitem', tone='btn-outline')
        add('Pedido de compra', 'Criar pedido manual', 'purchase_order_create', 'stock.add_purchaseorder', tone='btn-outline')
        add('Mensagem manual', 'Contato com cliente', 'message_manual', 'communications.add_messagelog', tone='btn-outline')
        add('Auditoria', 'Ver rastreabilidade', 'audit_list', 'audit.view_auditlog', admin_only=True, tone='btn-ghost')
        return actions

    def get_admin_dashboard_context(self, now):
        from accounts.models import EmployeeRole, User
        from ai_assistant.models import AIInteractionLog
        from audit.models import AuditAction, AuditLog
        from communications.models import MessageLog, MessageStatus
        from core.models import Customer, Supplier, Vehicle
        from operations.models import (
            VehicleCheckIn,
            WorkOrder,
            WorkOrderApprovalBudget,
            WorkOrderApprovalStatus,
            WorkOrderServiceItem,
            WorkOrderSettings,
            WorkOrderStatus,
        )
        from stock.models import (
            InventoryItem,
            InventoryItemType,
            PurchaseOrder,
            PurchaseOrderStatus,
            StockMovement,
        )
        from website.models import Lead, LeadStatus

        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        work_orders = WorkOrder.objects.select_related('cliente', 'veiculo', 'tecnico_responsavel')
        active_work_orders = work_orders.filter(status__in=WorkOrderStatus.workshop_capacity_statuses())
        completed_30d = work_orders.filter(status__in=WorkOrderStatus.completed_statuses(), data_finalizacao__gte=thirty_days_ago)
        delayed_orders = active_work_orders.filter(previsao_entrega__lt=now).exclude(status__in=WorkOrderStatus.completed_statuses())

        status_counts_raw = dict(work_orders.values('status').annotate(total=Count('id')).values_list('status', 'total'))
        status_cards = []
        for value, label in WorkOrderStatus.choices:
            count = status_counts_raw.get(value, 0)
            if count:
                status_cards.append({'status': value, 'label': label, 'count': count})

        settings = WorkOrderSettings.get_solo()
        occupied_slots = WorkOrder.workshop_occupied_count()
        capacity_percent = min(self.format_percent(occupied_slots, settings.vagas_oficina), 100)

        pending_budgets = WorkOrderApprovalBudget.objects.select_related('ordem_servico', 'ordem_servico__cliente').filter(
            status=WorkOrderApprovalStatus.PENDING,
        )
        approved_budgets_30d = WorkOrderApprovalBudget.objects.filter(
            status__in=[WorkOrderApprovalStatus.APPROVED, WorkOrderApprovalStatus.PARTIALLY_APPROVED],
            atualizado_em__gte=thirty_days_ago,
        )
        rejected_budgets_30d = WorkOrderApprovalBudget.objects.filter(
            status=WorkOrderApprovalStatus.REJECTED,
            atualizado_em__gte=thirty_days_ago,
        )

        stock_items = list(InventoryItem.objects.select_related('categoria', 'marca', 'unidade'))
        low_stock_items = [item for item in stock_items if item.abaixo_estoque_minimo]
        low_stock_items.sort(key=lambda item: (item.estoque_atual - item.estoque_minimo, item.nome.lower()))
        inventory_cost_value = sum((item.preco_custo or Decimal('0.00')) * item.estoque_atual for item in stock_items)
        inventory_sale_value = sum((item.valor_venda or Decimal('0.00')) * item.estoque_atual for item in stock_items if item.tipo == InventoryItemType.PECA)

        purchase_orders_open = PurchaseOrder.objects.filter(status__in=[PurchaseOrderStatus.PENDENTE, PurchaseOrderStatus.SOLICITADO])
        purchase_orders_recent = PurchaseOrder.objects.select_related('fornecedor', 'ordem_servico').order_by('-criado_em', '-pk')[:6]
        purchase_open_value = sum((pedido.valor_total or Decimal('0.00')) for pedido in purchase_orders_open.prefetch_related('itens'))

        message_logs_7d = MessageLog.objects.filter(criado_em__gte=seven_days_ago)
        ai_logs_7d = AIInteractionLog.objects.filter(criado_em__gte=seven_days_ago)
        audit_logs_24h = AuditLog.objects.filter(criado_em__gte=now - timedelta(hours=24))

        technicians_raw = active_work_orders.values(
            'tecnico_responsavel_id',
            'tecnico_responsavel__nome_razao_social',
            'tecnico_responsavel__email',
        ).annotate(total=Count('id')).order_by('-total', 'tecnico_responsavel__nome_razao_social')[:8]
        technician_workload = []
        for row in technicians_raw:
            technician_workload.append({
                'name': row['tecnico_responsavel__nome_razao_social'] or row['tecnico_responsavel__email'] or 'Sem técnico',
                'count': row['total'],
            })

        top_services = WorkOrderServiceItem.objects.select_related('service').filter(
            ordem_servico__data_abertura__gte=thirty_days_ago,
            ordem_servico__ativo=True,
            ordem_servico__excluido_em__isnull=True,
        ).values('service__nome').annotate(total=Sum('quantidade')).order_by('-total', 'service__nome')[:8]

        employee_role_counts = []
        role_count_map = dict(User.objects.filter(is_superuser=False).values('role').annotate(total=Count('id')).values_list('role', 'total'))
        for value, label in EmployeeRole.choices:
            employee_role_counts.append({'label': label, 'count': role_count_map.get(value, 0)})

        lead_count_map = dict(Lead.objects.values('status').annotate(total=Count('id')).values_list('status', 'total'))

        return {
            'admin_kpis': [
                {'label': 'OS ativas na oficina', 'value': active_work_orders.count(), 'hint': f'{occupied_slots}/{settings.vagas_oficina} vagas ocupadas', 'url': self.safe_reverse('work_order_list')},
                {'label': 'Aguardando aprovação', 'value': work_orders.filter(status=WorkOrderStatus.AGUARDANDO_APROVACAO).count(), 'hint': 'OS paradas no aceite do cliente', 'url': self.safe_reverse('work_order_list')},
                {'label': 'Em execução', 'value': work_orders.filter(status=WorkOrderStatus.EM_EXECUCAO).count(), 'hint': 'Serviço em andamento', 'url': self.safe_reverse('mechanic_kanban')},
                {'label': 'Atrasadas', 'value': delayed_orders.count(), 'hint': 'Previsão vencida', 'url': self.safe_reverse('work_order_list'), 'danger': delayed_orders.exists()},
                {'label': 'Orçamentos pendentes', 'value': pending_budgets.count(), 'hint': f'R$ {self.money_sum(pending_budgets, "valor_total_snapshot")}', 'url': self.safe_reverse('work_order_list')},
                {'label': 'Aprovado 30 dias', 'value': f'R$ {self.money_sum(approved_budgets_30d, "valor_total_snapshot")}', 'hint': 'Snapshots aprovados', 'url': self.safe_reverse('work_order_list')},
                {'label': 'Peças/insumos críticos', 'value': len(low_stock_items), 'hint': 'Abaixo do estoque mínimo', 'url': self.safe_reverse('inventory_item_list'), 'warning': bool(low_stock_items)},
                {'label': 'Leads novos', 'value': lead_count_map.get(LeadStatus.NOVO, 0), 'hint': 'Pedidos do site', 'url': self.safe_reverse('public_home')},
            ],
            'capacity': {
                'occupied': occupied_slots,
                'total': settings.vagas_oficina,
                'available': max(settings.vagas_oficina - occupied_slots, 0),
                'percent': capacity_percent,
            },
            'operations_summary': {
                'opened_today': work_orders.filter(data_abertura__gte=today_start).count(),
                'opened_30d': work_orders.filter(data_abertura__gte=thirty_days_ago).count(),
                'completed_30d': completed_30d.count(),
                'approved_30d': approved_budgets_30d.count(),
                'rejected_30d': rejected_budgets_30d.count(),
                'checkins_today': VehicleCheckIn.objects.filter(criado_em__gte=today_start).count(),
                'checkins_7d': VehicleCheckIn.objects.filter(criado_em__gte=seven_days_ago).count(),
            },
            'status_cards': status_cards,
            'delayed_orders': delayed_orders.order_by('previsao_entrega', '-data_abertura')[:6],
            'pending_budgets': pending_budgets.order_by('criado_em')[:6],
            'recent_work_orders': work_orders.order_by('-data_abertura', '-pk')[:8],
            'financial_summary': {
                'pending_budget_value': self.money_sum(pending_budgets, 'valor_total_snapshot'),
                'approved_budget_value_30d': self.money_sum(approved_budgets_30d, 'valor_total_snapshot'),
                'rejected_budget_value_30d': self.money_sum(rejected_budgets_30d, 'valor_total_snapshot'),
                'inventory_cost_value': Decimal(inventory_cost_value).quantize(Decimal('0.01')),
                'inventory_sale_value': Decimal(inventory_sale_value).quantize(Decimal('0.01')),
                'purchase_open_value': Decimal(purchase_open_value).quantize(Decimal('0.01')),
            },
            'stock_summary': {
                'items': len(stock_items),
                'pieces': sum(1 for item in stock_items if item.tipo == InventoryItemType.PECA),
                'supplies': sum(1 for item in stock_items if item.tipo == InventoryItemType.INSUMO),
                'low_stock': len(low_stock_items),
                'purchase_open': purchase_orders_open.count(),
                'movements_7d': StockMovement.objects.filter(criado_em__gte=seven_days_ago).count(),
            },
            'low_stock_items': low_stock_items[:8],
            'purchase_orders_recent': purchase_orders_recent,
            'recent_stock_movements': StockMovement.objects.select_related('item').order_by('-criado_em', '-pk')[:6],
            'customer_summary': {
                'customers': Customer.objects.count(),
                'suppliers': Supplier.objects.count(),
                'vehicles': Vehicle.objects.count(),
                'vehicles_without_fipe': Vehicle.objects.filter(codigo_fipe='').count(),
            },
            'employee_summary': {
                'active': User.objects.filter(is_active=True).count(),
                'inactive': User.objects.filter(is_active=False).count(),
                'roles': employee_role_counts,
            },
            'lead_summary': [
                {'label': label, 'count': lead_count_map.get(value, 0)}
                for value, label in LeadStatus.choices
            ],
            'message_summary': {
                'total_7d': message_logs_7d.count(),
                'sent_7d': message_logs_7d.filter(status=MessageStatus.SENT).count(),
                'error_7d': message_logs_7d.filter(status=MessageStatus.ERROR).count(),
                'pending': MessageLog.objects.filter(status=MessageStatus.PENDING).count(),
            },
            'message_errors': MessageLog.objects.filter(status=MessageStatus.ERROR).order_by('-atualizado_em', '-pk')[:5],
            'ai_summary': {
                'total_7d': ai_logs_7d.count(),
                'success_7d': ai_logs_7d.filter(sucesso=True).count(),
                'error_7d': ai_logs_7d.filter(sucesso=False).count(),
            },
            'audit_summary': {
                'events_24h': audit_logs_24h.count(),
                'failed_logins_24h': audit_logs_24h.filter(acao=AuditAction.LOGIN_FALHA).count(),
                'actions_24h': audit_logs_24h.filter(acao=AuditAction.ACAO).count(),
            },
            'recent_audit_logs': AuditLog.objects.select_related('usuario').order_by('-criado_em', '-pk')[:6],
            'technician_workload': technician_workload,
            'top_services': top_services,
        }

    def get_staff_dashboard_context(self, now):
        from accounts.permissions import can_access_technical_area
        from operations.models import WorkOrder, WorkOrderStatus

        user = self.request.user
        active_statuses = WorkOrderStatus.workshop_capacity_statuses()
        can_use_technical_area = can_access_technical_area(user)
        board_url = self.safe_reverse('mechanic_kanban' if can_use_technical_area else 'work_order_list')
        board_label = 'Abrir Kanban' if can_use_technical_area else 'Ver OS'

        my_orders = WorkOrder.objects.select_related('cliente', 'veiculo').filter(
            status__in=active_statuses,
            tecnico_responsavel=user,
        )
        available_orders = WorkOrder.objects.select_related('cliente', 'veiculo').filter(
            status__in=[WorkOrderStatus.ABERTA, WorkOrderStatus.DIAGNOSTICO],
            tecnico_responsavel__isnull=True,
        )
        visible_orders = (my_orders if can_use_technical_area else WorkOrder.objects.select_related('cliente', 'veiculo').filter(status__in=active_statuses))

        return {
            'staff_can_access_technical_area': can_use_technical_area,
            'staff_board_url': board_url,
            'staff_board_label': board_label,
            'staff_kpis': [
                {'label': 'Minhas OS ativas' if can_use_technical_area else 'OS ativas', 'value': visible_orders.count(), 'url': board_url},
                {'label': 'Em diagnóstico', 'value': visible_orders.filter(status=WorkOrderStatus.DIAGNOSTICO).count(), 'url': board_url},
                {'label': 'Em execução', 'value': visible_orders.filter(status=WorkOrderStatus.EM_EXECUCAO).count(), 'url': board_url},
                {'label': 'OS disponíveis' if can_use_technical_area else 'Aguardando aprovação', 'value': available_orders.count() if can_use_technical_area else visible_orders.filter(status=WorkOrderStatus.AGUARDANDO_APROVACAO).count(), 'url': board_url},
            ],
            'my_orders': visible_orders.order_by('previsao_entrega', '-data_abertura')[:8],
            'available_orders': available_orders.order_by('data_abertura', 'pk')[:6],
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.localtime()
        is_admin = self.user_is_admin_manager()

        context.update({
            'dashboard_is_admin': is_admin,
            'dashboard_updated_at': now,
            'quick_actions': self.get_quick_actions(is_admin),
        })

        if is_admin:
            context.update(self.get_admin_dashboard_context(now))
        else:
            context.update(self.get_staff_dashboard_context(now))

        return context


class FormTitleMixin:
    title = ''
    cancel_url = None

    def get_cancel_url(self):
        if self.cancel_url is not None:
            return self.cancel_url
        return getattr(self, 'success_url', reverse_lazy('dashboard'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = self.title
        context['cancel_url'] = self.get_cancel_url()
        return context


class SoftDeleteMixin:
    delete_success_message = 'Registro excluído com sucesso.'

    def form_valid(self, form):
        self.object = self.get_object()
        self.object.soft_delete()
        messages.success(self.request, self.delete_success_message)
        return redirect(self.get_success_url())


class SimpleSearchContextMixin:
    search_param_names = ('q',)

    def get_search_filters(self):
        return {name: (self.request.GET.get(name) or '').strip() for name in self.search_param_names}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self.get_search_filters()
        querydict = self.request.GET.copy()
        querydict.pop('page', None)
        context['filters'] = filters
        context['querystring'] = querydict.urlencode()
        context['has_active_filters'] = any(filters.values())
        return context


class CategorySearchMixin(SimpleSearchContextMixin):
    def build_category_search_q(self, term):
        return Q(nome__icontains=term) | Q(aplicacao__icontains=term)

    def apply_category_filters(self, queryset):
        term = self.get_search_filters()['q']

        if term:
            queryset = queryset.filter(self.build_category_search_q(term))

        return queryset.distinct().order_by('aplicacao', Lower('nome'), 'pk')


class PersonSearchMixin:
    category_audience = None
    category_context_name = 'category_choices'
    search_param_names = ('q', 'tipo_pessoa', 'categoria', 'marketing', 'cidade', 'uf')

    def get_search_filters(self):
        data = {}
        for name in self.search_param_names:
            data[name] = (self.request.GET.get(name) or '').strip()
        data['uf'] = data['uf'].upper()[:2]
        return data

    def get_category_queryset(self):
        return Category.objects.filter(
            aplicacao=self.category_audience,
            ativa=True,
            excluido_em__isnull=True,
        ).order_by(Lower('nome'), 'pk')

    def get_query_candidates(self, term):
        candidates = {term}
        digits = only_digits(term)

        if digits:
            candidates.update({
                digits,
                format_cpf(digits),
                format_cnpj(digits),
                format_phone(digits),
                format_cep(digits),
            })

        return {candidate for candidate in candidates if candidate}

    def build_search_q(self, term):
        search_q = Q()

        for candidate in self.get_query_candidates(term):
            search_q |= (
                Q(nome_razao_social__icontains=candidate)
                | Q(email__icontains=candidate)
                | Q(whatsapp__icontains=candidate)
                | Q(documento__icontains=candidate)
                | Q(cep__icontains=candidate)
                | Q(logradouro__icontains=candidate)
                | Q(numero__icontains=candidate)
                | Q(complemento__icontains=candidate)
                | Q(bairro__icontains=candidate)
                | Q(cidade__icontains=candidate)
                | Q(uf__icontains=candidate)
                | Q(categorias__nome__icontains=candidate)
            )

        return search_q

    def apply_advanced_filters(self, queryset):
        filters = self.get_search_filters()
        term = filters['q']

        if term:
            queryset = queryset.filter(self.build_search_q(term))

        if filters['tipo_pessoa'] in dict(PessoaTipo.choices):
            queryset = queryset.filter(tipo_pessoa=filters['tipo_pessoa'])

        if filters['categoria'].isdigit():
            queryset = queryset.filter(categorias__id=int(filters['categoria']))

        if filters['marketing'] == 'sim':
            queryset = queryset.filter(aceita_marketing=True)
        elif filters['marketing'] == 'nao':
            queryset = queryset.filter(aceita_marketing=False)

        if filters['cidade']:
            queryset = queryset.filter(cidade__icontains=filters['cidade'])

        if filters['uf']:
            queryset = queryset.filter(uf__iexact=filters['uf'])

        return queryset.distinct().order_by(Lower('nome_razao_social'), 'pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self.get_search_filters()
        querydict = self.request.GET.copy()
        querydict.pop('page', None)

        context['filters'] = filters
        context['querystring'] = querydict.urlencode()
        context['has_active_filters'] = any(filters.values())
        context['tipo_pessoa_choices'] = PessoaTipo.choices
        context[self.category_context_name] = self.get_category_queryset()
        return context


class PersonAutocompleteView(LoginRequiredMixin, PermissionRequiredMixin, PersonSearchMixin, View):
    model = None
    permission_required = None
    limit = 10

    def get(self, request, *args, **kwargs):
        term = (request.GET.get('q') or '').strip()

        if len(term) < 2:
            return JsonResponse({'results': []})

        queryset = self.model.objects.prefetch_related('categorias')
        queryset = queryset.filter(self.build_search_q(term)).distinct().order_by(Lower('nome_razao_social'), 'pk')[: self.limit]

        results = []
        for person in queryset:
            categories = ', '.join(category.nome for category in person.categorias.all()[:3])
            subtitle_parts = [person.email, person.whatsapp, f'{person.cidade}/{person.uf}']
            if categories:
                subtitle_parts.append(categories)

            results.append({
                'id': person.pk,
                'label': person.nome_razao_social,
                'subtitle': ' | '.join(part for part in subtitle_parts if part),
                'url': person.get_absolute_url(),
            })

        return JsonResponse({'results': results})


class CustomerListView(LoginRequiredMixin, PermissionRequiredMixin, PersonSearchMixin, ListView):
    model = Customer
    template_name = 'core/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20
    permission_required = 'core.view_customer'
    category_audience = CategoryAudience.CLIENTE

    def get_queryset(self):
        queryset = Customer.objects.prefetch_related('categorias')
        return self.apply_advanced_filters(queryset)


class CustomerAutocompleteView(PersonAutocompleteView):
    model = Customer
    permission_required = 'core.view_customer'
    category_audience = CategoryAudience.CLIENTE


class CustomerDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Customer
    template_name = 'core/person_detail.html'
    context_object_name = 'person'
    permission_required = 'core.view_customer'

    def get_queryset(self):
        return Customer.objects.prefetch_related('categorias', 'veiculos')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Detalhes do cliente'
        context['list_url'] = reverse_lazy('customer_list')
        context['edit_url'] = reverse_lazy('customer_update', kwargs={'pk': self.object.pk})
        context['delete_url'] = reverse_lazy('customer_delete', kwargs={'pk': self.object.pk})
        context['can_change'] = self.request.user.has_perm('core.change_customer')
        context['can_delete'] = self.request.user.has_perm('core.delete_customer')
        return context


class CustomerCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'core/object_form.html'
    success_url = reverse_lazy('customer_list')
    permission_required = 'core.add_customer'
    title = 'Novo cliente'

    def get_initial(self):
        initial = super().get_initial()
        lead = get_website_lead_from_request(self.request)
        if lead:
            initial.setdefault('nome_razao_social', lead.nome)
            initial.setdefault('email', lead.email)
            initial.setdefault('whatsapp', lead.telefone)

        query_initial_map = {
            'nome': 'nome_razao_social',
            'email': 'email',
            'whatsapp': 'whatsapp',
        }
        for query_name, field_name in query_initial_map.items():
            value = (self.request.GET.get(query_name) or '').strip()
            if value:
                initial[field_name] = value
        return initial

    def form_valid(self, form):
        messages.success(self.request, 'Cliente cadastrado com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível salvar o cliente. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class CustomerUpdateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'core/object_form.html'
    success_url = reverse_lazy('customer_list')
    permission_required = 'core.change_customer'
    title = 'Editar cliente'

    def get_queryset(self):
        return Customer.objects.prefetch_related('categorias')

    def form_valid(self, form):
        messages.success(self.request, 'Cliente atualizado com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível atualizar o cliente. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class CustomerDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, SoftDeleteMixin, DeleteView):
    model = Customer
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('customer_list')
    permission_required = 'core.delete_customer'
    title = 'Excluir cliente'
    delete_success_message = 'Cliente excluído com sucesso.'

    def get_queryset(self):
        return Customer.objects.all()


class SupplierListView(LoginRequiredMixin, PermissionRequiredMixin, PersonSearchMixin, ListView):
    model = Supplier
    template_name = 'core/supplier_list.html'
    context_object_name = 'suppliers'
    paginate_by = 20
    permission_required = 'core.view_supplier'
    category_audience = CategoryAudience.FORNECEDOR

    def get_queryset(self):
        queryset = Supplier.objects.prefetch_related('categorias')
        return self.apply_advanced_filters(queryset)


class SupplierAutocompleteView(PersonAutocompleteView):
    model = Supplier
    permission_required = 'core.view_supplier'
    category_audience = CategoryAudience.FORNECEDOR


class SupplierDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Supplier
    template_name = 'core/person_detail.html'
    context_object_name = 'person'
    permission_required = 'core.view_supplier'

    def get_queryset(self):
        return Supplier.objects.prefetch_related('categorias')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Detalhes do fornecedor'
        context['list_url'] = reverse_lazy('supplier_list')
        context['edit_url'] = reverse_lazy('supplier_update', kwargs={'pk': self.object.pk})
        context['delete_url'] = reverse_lazy('supplier_delete', kwargs={'pk': self.object.pk})
        context['can_change'] = self.request.user.has_perm('core.change_supplier')
        context['can_delete'] = self.request.user.has_perm('core.delete_supplier')
        return context


class SupplierCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'core/object_form.html'
    success_url = reverse_lazy('supplier_list')
    permission_required = 'core.add_supplier'
    title = 'Novo fornecedor'

    def form_valid(self, form):
        messages.success(self.request, 'Fornecedor cadastrado com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível salvar o fornecedor. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class SupplierUpdateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'core/object_form.html'
    success_url = reverse_lazy('supplier_list')
    permission_required = 'core.change_supplier'
    title = 'Editar fornecedor'

    def get_queryset(self):
        return Supplier.objects.prefetch_related('categorias')

    def form_valid(self, form):
        messages.success(self.request, 'Fornecedor atualizado com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível atualizar o fornecedor. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class SupplierDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, SoftDeleteMixin, DeleteView):
    model = Supplier
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('supplier_list')
    permission_required = 'core.delete_supplier'
    title = 'Excluir fornecedor'
    delete_success_message = 'Fornecedor excluído com sucesso.'

    def get_queryset(self):
        return Supplier.objects.all()


class VehicleSearchMixin:
    search_param_names = ('q', 'cliente', 'marca', 'combustivel', 'tipo_direcao', 'ar_condicionado', 'modificado')

    def get_search_filters(self):
        data = {name: (self.request.GET.get(name) or '').strip() for name in self.search_param_names}
        return data

    def get_query_candidates(self, term):
        candidates = {term, term.upper(), format_plate(term), only_alnum_upper(term)}
        return {candidate for candidate in candidates if candidate}

    def build_vehicle_search_q(self, term):
        search_q = Q()
        for candidate in self.get_query_candidates(term):
            search_q |= (
                Q(placa__icontains=candidate)
                | Q(cliente__nome_razao_social__icontains=candidate)
                | Q(cliente__email__icontains=candidate)
                | Q(marca__icontains=candidate)
                | Q(modelo__icontains=candidate)
                | Q(versao__icontains=candidate)
                | Q(combustivel__icontains=candidate)
                | Q(chassi__icontains=candidate)
                | Q(codigo_fipe__icontains=candidate)
                | Q(mes_referencia_fipe__icontains=candidate)
            )
        return search_q

    def apply_vehicle_filters(self, queryset):
        filters = self.get_search_filters()
        term = filters['q']

        if term:
            queryset = queryset.filter(self.build_vehicle_search_q(term))
        if filters['cliente'].isdigit():
            queryset = queryset.filter(cliente_id=int(filters['cliente']))
        if filters['marca']:
            queryset = queryset.filter(marca__icontains=filters['marca'])
        if filters['combustivel'] in dict(VehicleFuelType.choices):
            queryset = queryset.filter(combustivel=filters['combustivel'])
        if filters['tipo_direcao'] in dict(VehicleDirectionType.choices):
            queryset = queryset.filter(tipo_direcao=filters['tipo_direcao'])
        if filters['ar_condicionado'] == 'sim':
            queryset = queryset.filter(ar_condicionado=True)
        elif filters['ar_condicionado'] == 'nao':
            queryset = queryset.filter(ar_condicionado=False)
        if filters['modificado'] == 'sim':
            queryset = queryset.filter(modificado=True)
        elif filters['modificado'] == 'nao':
            queryset = queryset.filter(modificado=False)

        return queryset.distinct().order_by(Lower('cliente__nome_razao_social'), Lower('marca'), Lower('modelo'), 'placa', 'pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self.get_search_filters()
        querydict = self.request.GET.copy()
        querydict.pop('page', None)
        context['filters'] = filters
        context['querystring'] = querydict.urlencode()
        context['has_active_filters'] = any(filters.values())
        context['customer_choices'] = Customer.objects.order_by(Lower('nome_razao_social'), 'pk')
        context['fuel_choices'] = VehicleFuelType.choices
        context['direction_choices'] = VehicleDirectionType.choices
        return context


class VehicleListView(LoginRequiredMixin, PermissionRequiredMixin, VehicleSearchMixin, ListView):
    model = Vehicle
    template_name = 'core/vehicle_list.html'
    context_object_name = 'vehicles'
    paginate_by = 20
    permission_required = 'core.view_vehicle'

    def get_queryset(self):
        queryset = Vehicle.objects.select_related('cliente')
        return self.apply_vehicle_filters(queryset)


class VehicleAutocompleteView(LoginRequiredMixin, PermissionRequiredMixin, VehicleSearchMixin, View):
    permission_required = 'core.view_vehicle'
    limit = 10

    def get(self, request, *args, **kwargs):
        term = (request.GET.get('q') or '').strip()
        if len(term) < 2:
            return JsonResponse({'results': []})

        queryset = Vehicle.objects.select_related('cliente')
        queryset = queryset.filter(self.build_vehicle_search_q(term)).distinct().order_by(Lower('cliente__nome_razao_social'), Lower('marca'), Lower('modelo'), 'placa', 'pk')[: self.limit]

        results = []
        for vehicle in queryset:
            subtitle_parts = [vehicle.cliente.nome_razao_social, vehicle.versao, vehicle.get_combustivel_display() if vehicle.combustivel else '', f'{vehicle.km} km']
            results.append({
                'id': vehicle.pk,
                'label': f'{vehicle.placa} - {vehicle.marca} {vehicle.modelo}',
                'value': vehicle.placa,
                'subtitle': ' | '.join(part for part in subtitle_parts if part),
                'url': vehicle.get_absolute_url(),
            })

        return JsonResponse({'results': results})


class VehicleDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Vehicle
    template_name = 'core/vehicle_detail.html'
    context_object_name = 'vehicle'
    permission_required = 'core.view_vehicle'

    def get_queryset(self):
        return Vehicle.objects.select_related('cliente')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_change'] = self.request.user.has_perm('core.change_vehicle')
        context['can_delete'] = self.request.user.has_perm('core.delete_vehicle')
        return context


class VehicleCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'core/vehicle_form.html'
    success_url = reverse_lazy('vehicle_list')
    permission_required = 'core.add_vehicle'
    title = 'Novo veículo'

    def get_initial(self):
        initial = super().get_initial()
        lead = get_website_lead_from_request(self.request)
        if lead:
            marca, modelo = split_vehicle_description(lead.veiculo)
            initial.setdefault('placa', format_plate(lead.placa))
            if marca:
                initial.setdefault('marca', marca)
            if modelo:
                initial.setdefault('modelo', modelo)

        cliente = self.request.GET.get('cliente')
        if cliente and cliente.isdigit():
            initial['cliente'] = int(cliente)

        query_initial_map = {
            'placa': 'placa',
            'marca': 'marca',
            'modelo': 'modelo',
        }
        for query_name, field_name in query_initial_map.items():
            value = (self.request.GET.get(query_name) or '').strip()
            if value:
                initial[field_name] = format_plate(value) if field_name == 'placa' else value
        return initial

    def form_valid(self, form):
        messages.success(self.request, 'Veículo cadastrado com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível salvar o veículo. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class VehicleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'core/vehicle_form.html'
    success_url = reverse_lazy('vehicle_list')
    permission_required = 'core.change_vehicle'
    title = 'Editar veículo'

    def get_queryset(self):
        return Vehicle.objects.select_related('cliente')

    def form_valid(self, form):
        messages.success(self.request, 'Veículo atualizado com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível atualizar o veículo. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class VehicleDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, SoftDeleteMixin, DeleteView):
    model = Vehicle
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('vehicle_list')
    permission_required = 'core.delete_vehicle'
    title = 'Excluir veículo'
    delete_success_message = 'Veículo excluído com sucesso.'

    def get_queryset(self):
        return Vehicle.objects.select_related('cliente')


class FipeProxyBaseView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'core.add_vehicle'
    base_url = 'https://fipe.parallelum.com.br/api/v2'

    def get_tipo(self):
        tipo = (self.request.GET.get('tipo') or VehicleFipeType.CARRO).strip()
        if tipo not in dict(VehicleFipeType.choices):
            tipo = VehicleFipeType.CARRO
        return tipo

    def fetch_json(self, path):
        # As tabelas FIPE mudam mensalmente, por isso as respostas sao cacheadas
        # para evitar repetir chamadas externas a cada interacao do utilizador.
        cache_key = f'fipe:{path}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        url = f'{self.base_url}{path}'
        request = Request(url, headers={'User-Agent': 'MotorMind/1.0'})
        with urlopen(request, timeout=12) as response:
            charset = response.headers.get_content_charset() or 'utf-8'
            data = json.loads(response.read().decode(charset))

        cache.set(cache_key, data, getattr(dj_settings, 'FIPE_CACHE_TIMEOUT', 24 * 60 * 60))
        return data

    def error_response(self, message, status=502):
        return JsonResponse({'results': [], 'error': message}, status=status)


class FipeBrandsView(FipeProxyBaseView):
    def get(self, request, *args, **kwargs):
        tipo = self.get_tipo()
        try:
            data = self.fetch_json(f'/{quote(tipo)}/brands')
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            return self.error_response(f'Não foi possível consultar marcas na FIPE: {exc}')

        results = [{'code': str(item.get('code', '')), 'name': item.get('name', '')} for item in data]
        results = sorted((item for item in results if item['code'] and item['name']), key=lambda item: item['name'].lower())
        return JsonResponse({'results': results})


class FipeModelsView(FipeProxyBaseView):
    def get(self, request, *args, **kwargs):
        tipo = self.get_tipo()
        marca = (request.GET.get('marca') or '').strip()
        if not marca:
            return self.error_response('Informe a marca FIPE.', status=400)
        try:
            data = self.fetch_json(f'/{quote(tipo)}/brands/{quote(marca)}/models')
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            return self.error_response(f'Não foi possível consultar modelos na FIPE: {exc}')

        results = [{'code': str(item.get('code', '')), 'name': item.get('name', '')} for item in data]
        results = sorted((item for item in results if item['code'] and item['name']), key=lambda item: item['name'].lower())
        return JsonResponse({'results': results})


class FipeYearsView(FipeProxyBaseView):
    def get(self, request, *args, **kwargs):
        tipo = self.get_tipo()
        marca = (request.GET.get('marca') or '').strip()
        modelo = (request.GET.get('modelo') or '').strip()
        if not marca or not modelo:
            return self.error_response('Informe a marca e o modelo FIPE.', status=400)
        try:
            data = self.fetch_json(f'/{quote(tipo)}/brands/{quote(marca)}/models/{quote(modelo)}/years')
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            return self.error_response(f'Não foi possível consultar anos/versões na FIPE: {exc}')

        results = [{'code': str(item.get('code', '')), 'name': item.get('name', '')} for item in data]
        return JsonResponse({'results': [item for item in results if item['code'] and item['name']]})


class FipeValueView(FipeProxyBaseView):
    def get(self, request, *args, **kwargs):
        tipo = self.get_tipo()
        marca = (request.GET.get('marca') or '').strip()
        modelo = (request.GET.get('modelo') or '').strip()
        ano = (request.GET.get('ano') or '').strip()
        if not marca or not modelo or not ano:
            return self.error_response('Informe marca, modelo e ano/versão FIPE.', status=400)
        try:
            data = self.fetch_json(f'/{quote(tipo)}/brands/{quote(marca)}/models/{quote(modelo)}/years/{quote(ano)}')
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            return self.error_response(f'Não foi possível consultar detalhes na FIPE: {exc}')

        return JsonResponse({
            'brand': data.get('brand', ''),
            'model': data.get('model', ''),
            'modelYear': data.get('modelYear', ''),
            'fuel': data.get('fuel', ''),
            'codeFipe': data.get('codeFipe', ''),
            'referenceMonth': data.get('referenceMonth', ''),
            'price': data.get('price', ''),
            'raw': data,
        })


class CategoryListView(LoginRequiredMixin, PermissionRequiredMixin, CategorySearchMixin, ListView):
    model = Category
    template_name = 'core/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20
    permission_required = 'core.view_category'

    def get_queryset(self):
        queryset = Category.objects.filter(excluido_em__isnull=True)
        return self.apply_category_filters(queryset)


class CategoryAutocompleteView(LoginRequiredMixin, PermissionRequiredMixin, CategorySearchMixin, View):
    permission_required = 'core.view_category'
    limit = 10

    def get(self, request, *args, **kwargs):
        term = (request.GET.get('q') or '').strip()

        if len(term) < 2:
            return JsonResponse({'results': []})

        queryset = Category.objects.filter(excluido_em__isnull=True)
        queryset = queryset.filter(self.build_category_search_q(term)).distinct().order_by('aplicacao', Lower('nome'), 'pk')[: self.limit]

        results = [
            {
                'id': category.pk,
                'label': category.nome,
                'value': category.nome,
                'subtitle': category.get_aplicacao_display(),
                'url': category.get_absolute_url(),
            }
            for category in queryset
        ]

        return JsonResponse({'results': results})


class CategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'core/object_form.html'
    success_url = reverse_lazy('category_list')
    permission_required = 'core.add_category'
    title = 'Nova categoria'

    def form_valid(self, form):
        messages.success(self.request, 'Categoria cadastrada com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível salvar a categoria. Confira os alertas do formulário.')
        return super().form_invalid(form)


class CategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'core/object_form.html'
    success_url = reverse_lazy('category_list')
    permission_required = 'core.change_category'
    title = 'Editar categoria'

    def get_queryset(self):
        return Category.objects.filter(excluido_em__isnull=True)

    def form_valid(self, form):
        messages.success(self.request, 'Categoria atualizada com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível atualizar a categoria. Confira os alertas do formulário.')
        return super().form_invalid(form)


class CategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, SoftDeleteMixin, DeleteView):
    model = Category
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('category_list')
    permission_required = 'core.delete_category'
    title = 'Excluir categoria'
    delete_success_message = 'Categoria excluída com sucesso.'

    def get_queryset(self):
        return Category.objects.filter(excluido_em__isnull=True)


class HealthCheckView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'status': 'ok', 'service': 'motormind'})


class NotificationFeedView(LoginRequiredMixin, View):
    """Retorna notificações internas pendentes para exibição no navegador."""

    def get(self, request, *args, **kwargs):
        notifications = list(
            AppNotification.objects.filter(usuario=request.user, lida_em__isnull=True, exibida_em__isnull=True)
            .order_by('criado_em', 'pk')[:5]
        )
        unread_count = AppNotification.objects.filter(usuario=request.user, lida_em__isnull=True).count()
        payload = []
        for notification in notifications:
            payload.append({
                'id': notification.pk,
                'title': notification.titulo,
                'message': notification.mensagem,
                'url': notification.url,
                'level': notification.nivel,
                'category': notification.categoria,
                'created_at': notification.criado_em.isoformat(),
            })
            notification.mark_displayed()

        return JsonResponse({'ok': True, 'unread_count': unread_count, 'notifications': payload})


class NotificationReadView(LoginRequiredMixin, View):
    """Marca uma notificação interna como lida."""

    def post(self, request, *args, **kwargs):
        try:
            notification = AppNotification.objects.get(pk=kwargs['pk'], usuario=request.user)
        except AppNotification.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Notificação não encontrada.'}, status=404)
        notification.mark_read()
        unread_count = AppNotification.objects.filter(usuario=request.user, lida_em__isnull=True).count()
        return JsonResponse({'ok': True, 'unread_count': unread_count})
