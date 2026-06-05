import logging
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View

from accounts.models import EmployeeRole
from core.money import format_money_br, normalize_money
from core.views import FormTitleMixin, SoftDeleteMixin
from stock.models import InventoryItem
from core.models import Customer, Vehicle

from .forms import (
    ServiceCategoryForm,
    ServiceComboForm,
    ServiceComboItemFormSet,
    ServiceDefaultPartFormSet,
    ServiceForm,
    WorkOrderComboItemFormSet,
    WorkOrderForm,
    WorkOrderPartItemFormSet,
    WorkOrderServiceItemFormSet,
    WorkOrderSettingsForm,
    WorkOrderApprovalDecisionForm,
    PdfSettingsForm,
    PdfTemplateSettingsForm,
)
logger = logging.getLogger(__name__)

from .models import (
    Service,
    ServiceCategory,
    ServiceCombo,
    WorkOrder,
    WorkOrderApprovalBudget,
    WorkOrderApprovalDecision,
    WorkOrderApprovalMethod,
    WorkOrderApprovalStatus,
    WorkOrderSettings,
    WorkOrderStatus,
    WorkOrderStatusTransition,
    PdfSettings,
    PdfTemplateSettings,
    PdfTemplateType,
)



def get_request_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or ''


def get_request_user_agent(request):
    return request.META.get('HTTP_USER_AGENT', '')[:1000]


class TechnicianRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        user = self.request.user
        return bool(
            user.is_authenticated
            and (user.is_superuser or getattr(user, 'role', None) == EmployeeRole.TECNICO)
        )


class OperationsSearchMixin:
    def parse_integer_filter(self, value):
        if not value:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def parse_money_filter(self, value):
        if not value:
            return None
        try:
            return normalize_money(value)
        except Exception:
            return None



class ServiceCategoryListView(LoginRequiredMixin, PermissionRequiredMixin, OperationsSearchMixin, ListView):
    model = ServiceCategory
    template_name = 'operations/service_category_list.html'
    context_object_name = 'categories'
    paginate_by = 20
    permission_required = 'operations.view_servicecategory'

    def get_search_filters(self):
        return {'q': (self.request.GET.get('q') or '').strip()}

    def get_queryset(self):
        queryset = ServiceCategory.objects.filter(excluido_em__isnull=True)
        term = self.get_search_filters()['q']
        if term:
            queryset = queryset.filter(Q(nome__icontains=term) | Q(descricao__icontains=term))
        return queryset.order_by(Lower('nome'), 'pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self.get_search_filters()
        querydict = self.request.GET.copy()
        querydict.pop('page', None)
        context['filters'] = filters
        context['querystring'] = querydict.urlencode()
        context['has_active_filters'] = any(filters.values())
        return context


class ServiceCategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, CreateView):
    model = ServiceCategory
    form_class = ServiceCategoryForm
    template_name = 'operations/object_form.html'
    success_url = reverse_lazy('service_category_list')
    permission_required = 'operations.add_servicecategory'
    title = 'Nova categoria de serviço'

    def form_valid(self, form):
        messages.success(self.request, 'Categoria de serviço cadastrada com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível salvar a categoria de serviço.')
        return super().form_invalid(form)


class ServiceCategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = ServiceCategory
    form_class = ServiceCategoryForm
    template_name = 'operations/object_form.html'
    success_url = reverse_lazy('service_category_list')
    permission_required = 'operations.change_servicecategory'
    title = 'Editar categoria de serviço'

    def get_queryset(self):
        return ServiceCategory.objects.filter(excluido_em__isnull=True)

    def form_valid(self, form):
        messages.success(self.request, 'Categoria de serviço atualizada com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível atualizar a categoria de serviço.')
        return super().form_invalid(form)


class ServiceCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, SoftDeleteMixin, DeleteView):
    model = ServiceCategory
    template_name = 'operations/confirm_delete.html'
    success_url = reverse_lazy('service_category_list')
    permission_required = 'operations.delete_servicecategory'
    title = 'Excluir categoria de serviço'
    delete_success_message = 'Categoria de serviço excluída com sucesso.'

    def get_queryset(self):
        return ServiceCategory.objects.filter(excluido_em__isnull=True)


class ServiceSearchMixin(OperationsSearchMixin):
    search_param_names = ('q', 'categoria', 'duracao_min', 'duracao_max', 'valor_min', 'valor_max', 'peca')

    def get_search_filters(self):
        return {name: (self.request.GET.get(name) or '').strip() for name in self.search_param_names}

    def build_service_search_q(self, term):
        return (
            Q(codigo__icontains=term)
            | Q(nome__icontains=term)
            | Q(descricao__icontains=term)
            | Q(categoria__nome__icontains=term)
            | Q(categoria__descricao__icontains=term)
            | Q(pecas_associadas__item__sku__icontains=term)
            | Q(pecas_associadas__item__nome__icontains=term)
            | Q(pecas_associadas__item__categoria__nome__icontains=term)
            | Q(pecas_associadas__item__marca__nome__icontains=term)
        )

    def apply_service_filters(self, queryset):
        filters = self.get_search_filters()
        term = filters['q']

        if term:
            queryset = queryset.filter(self.build_service_search_q(term))

        duracao_min = self.parse_integer_filter(filters['duracao_min'])
        duracao_max = self.parse_integer_filter(filters['duracao_max'])
        valor_min = self.parse_money_filter(filters['valor_min'])
        valor_max = self.parse_money_filter(filters['valor_max'])

        if duracao_min is not None:
            queryset = queryset.filter(duracao_minutos__gte=duracao_min)
        if duracao_max is not None:
            queryset = queryset.filter(duracao_minutos__lte=duracao_max)
        if valor_min is not None:
            queryset = queryset.filter(valor__gte=valor_min)
        if valor_max is not None:
            queryset = queryset.filter(valor__lte=valor_max)
        if filters['categoria'].isdigit():
            queryset = queryset.filter(categoria_id=int(filters['categoria']))
        if filters['peca'].isdigit():
            queryset = queryset.filter(pecas_associadas__item_id=int(filters['peca']))

        return queryset.distinct().order_by(Lower('nome'), 'pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self.get_search_filters()
        querydict = self.request.GET.copy()
        querydict.pop('page', None)
        context['filters'] = filters
        context['querystring'] = querydict.urlencode()
        context['has_active_filters'] = any(filters.values())
        context['category_choices'] = ServiceCategory.objects.order_by(Lower('nome'), 'pk')
        context['item_choices'] = InventoryItem.objects.select_related('categoria', 'marca', 'unidade').order_by(Lower('nome'), 'pk')
        return context


class ServiceListView(LoginRequiredMixin, PermissionRequiredMixin, ServiceSearchMixin, ListView):
    model = Service
    template_name = 'operations/service_list.html'
    context_object_name = 'services'
    paginate_by = 20
    permission_required = 'operations.view_service'

    def get_queryset(self):
        queryset = Service.objects.select_related('categoria').prefetch_related('pecas_associadas__item__categoria', 'pecas_associadas__item__marca', 'pecas_associadas__item__unidade')
        return self.apply_service_filters(queryset)


class ServiceAutocompleteView(LoginRequiredMixin, PermissionRequiredMixin, ServiceSearchMixin, View):
    permission_required = 'operations.view_service'
    limit = 10

    def get(self, request, *args, **kwargs):
        term = (request.GET.get('q') or '').strip()
        if len(term) < 2:
            return JsonResponse({'results': []})

        queryset = Service.objects.select_related('categoria').prefetch_related('pecas_associadas__item')
        queryset = queryset.filter(self.build_service_search_q(term)).distinct().order_by(Lower('nome'), 'pk')[: self.limit]

        results = []
        for service in queryset:
            parts = ', '.join(part.item.nome for part in service.pecas_associadas.all()[:3])
            subtitle_parts = []
            if service.categoria_id:
                subtitle_parts.append(service.categoria.nome)
            subtitle_parts.extend([service.duracao_formatada, format_money_br(service.valor)])
            if parts:
                subtitle_parts.append(parts)
            results.append({
                'id': service.pk,
                'label': f'{service.codigo} - {service.nome}',
                'value': service.codigo or service.nome,
                'subtitle': ' | '.join(part for part in subtitle_parts if part),
                'url': service.get_absolute_url(),
            })

        return JsonResponse({'results': results})


class ServiceDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Service
    template_name = 'operations/service_detail.html'
    context_object_name = 'service'
    permission_required = 'operations.view_service'

    def get_queryset(self):
        return Service.objects.select_related('categoria').prefetch_related('pecas_associadas__item__categoria', 'pecas_associadas__item__marca', 'pecas_associadas__item__unidade')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_change'] = self.request.user.has_perm('operations.change_service')
        context['can_delete'] = self.request.user.has_perm('operations.delete_service')
        return context


class ServiceFormsetMixin:
    formset_class = ServiceDefaultPartFormSet

    def get_formset(self):
        if self.request.method in ('POST', 'PUT'):
            return self.formset_class(self.request.POST, instance=getattr(self, 'object', None), prefix='parts')
        return self.formset_class(instance=getattr(self, 'object', None), prefix='parts')

    def get_service_part_items_json(self):
        items = InventoryItem.objects.select_related('categoria', 'marca', 'unidade').order_by(Lower('nome'), 'pk')
        payload = []

        for item in items:
            payload.append({
                'id': item.pk,
                'sku': item.sku or '',
                'nome': item.nome,
                'descricao': item.descricao or '',
                'categoria': item.categoria.nome if item.categoria_id else '',
                'marca': item.marca.nome if item.marca_id else '',
                'unidade': item.unidade.sigla if item.unidade_id else '',
                'estoque_atual': str(item.estoque_atual),
                'estoque_minimo': str(item.estoque_minimo),
                'preco_custo': format_money_br(item.preco_custo),
                'preco_venda': format_money_br(item.valor_venda),
                'tipo': item.get_tipo_display(),
                'label': f'{item.sku or "Sem SKU"} - {item.nome}',
                'search': ' '.join([
                    item.sku or '',
                    item.nome or '',
                    item.descricao or '',
                    item.categoria.nome if item.categoria_id else '',
                    item.marca.nome if item.marca_id else '',
                    item.unidade.sigla if item.unidade_id else '',
                    item.get_tipo_display(),
                ]).lower(),
            })

        return payload

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'parts_formset' not in context:
            context['parts_formset'] = self.get_formset()
        context['service_part_items_json'] = self.get_service_part_items_json()
        return context

    def form_valid(self, form):
        parts_formset = self.get_formset()
        if not parts_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, parts_formset=parts_formset))

        self.object = form.save()
        parts_formset.instance = self.object
        parts_formset.save()
        return redirect(self.get_success_url())


class ServiceCreateView(LoginRequiredMixin, PermissionRequiredMixin, ServiceFormsetMixin, FormTitleMixin, CreateView):
    model = Service
    form_class = ServiceForm
    template_name = 'operations/service_form.html'
    success_url = reverse_lazy('service_list')
    permission_required = 'operations.add_service'
    title = 'Novo serviço'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Serviço cadastrado com sucesso.')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível salvar o serviço. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class ServiceUpdateView(LoginRequiredMixin, PermissionRequiredMixin, ServiceFormsetMixin, FormTitleMixin, UpdateView):
    model = Service
    form_class = ServiceForm
    template_name = 'operations/service_form.html'
    success_url = reverse_lazy('service_list')
    permission_required = 'operations.change_service'
    title = 'Editar serviço'

    def get_queryset(self):
        return Service.objects.select_related('categoria').prefetch_related('pecas_associadas__item')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Serviço atualizado com sucesso.')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível atualizar o serviço. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class ServiceDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, SoftDeleteMixin, DeleteView):
    model = Service
    template_name = 'operations/confirm_delete.html'
    success_url = reverse_lazy('service_list')
    permission_required = 'operations.delete_service'
    title = 'Excluir serviço'
    delete_success_message = 'Serviço excluído com sucesso.'

    def get_queryset(self):
        return Service.objects.filter(excluido_em__isnull=True)


class ServiceComboSearchMixin(OperationsSearchMixin):
    search_param_names = ('q', 'desconto_min', 'desconto_max', 'valor_min', 'valor_max', 'servico')

    def get_search_filters(self):
        return {name: (self.request.GET.get(name) or '').strip() for name in self.search_param_names}

    def build_combo_search_q(self, term):
        return (
            Q(codigo__icontains=term)
            | Q(nome__icontains=term)
            | Q(descricao__icontains=term)
            | Q(servicos_associados__service__codigo__icontains=term)
            | Q(servicos_associados__service__nome__icontains=term)
            | Q(servicos_associados__service__descricao__icontains=term)
        )

    def parse_percentage_filter(self, value):
        return self.parse_money_filter(value)

    def apply_combo_filters(self, queryset):
        filters = self.get_search_filters()
        term = filters['q']

        if term:
            queryset = queryset.filter(self.build_combo_search_q(term))

        desconto_min = self.parse_percentage_filter(filters['desconto_min'])
        desconto_max = self.parse_percentage_filter(filters['desconto_max'])

        if desconto_min is not None:
            queryset = queryset.filter(desconto_percentual__gte=desconto_min)
        if desconto_max is not None:
            queryset = queryset.filter(desconto_percentual__lte=desconto_max)
        if filters['servico'].isdigit():
            queryset = queryset.filter(servicos_associados__service_id=int(filters['servico']))

        # Filtros por valor total são calculados em memória porque o total do combo depende
        # da soma dos serviços associados e do desconto percentual opcional.
        valor_min = self.parse_money_filter(filters['valor_min'])
        valor_max = self.parse_money_filter(filters['valor_max'])
        queryset = queryset.distinct().order_by(Lower('nome'), 'pk')

        if valor_min is not None or valor_max is not None:
            filtered_pks = []
            for combo in queryset.prefetch_related('servicos_associados__service'):
                total = combo.valor_total
                if valor_min is not None and total < valor_min:
                    continue
                if valor_max is not None and total > valor_max:
                    continue
                filtered_pks.append(combo.pk)
            queryset = ServiceCombo.objects.filter(pk__in=filtered_pks).prefetch_related('servicos_associados__service').order_by(Lower('nome'), 'pk')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self.get_search_filters()
        querydict = self.request.GET.copy()
        querydict.pop('page', None)
        context['filters'] = filters
        context['querystring'] = querydict.urlencode()
        context['has_active_filters'] = any(filters.values())
        context['service_choices'] = Service.objects.order_by(Lower('nome'), 'pk')
        return context


class ServiceComboListView(LoginRequiredMixin, PermissionRequiredMixin, ServiceComboSearchMixin, ListView):
    model = ServiceCombo
    template_name = 'operations/service_combo_list.html'
    context_object_name = 'combos'
    paginate_by = 20
    permission_required = 'operations.view_servicecombo'

    def get_queryset(self):
        queryset = ServiceCombo.objects.prefetch_related('servicos_associados__service')
        return self.apply_combo_filters(queryset)


class ServiceComboAutocompleteView(LoginRequiredMixin, PermissionRequiredMixin, ServiceComboSearchMixin, View):
    permission_required = 'operations.view_servicecombo'
    limit = 10

    def get(self, request, *args, **kwargs):
        term = (request.GET.get('q') or '').strip()
        if len(term) < 2:
            return JsonResponse({'results': []})

        queryset = ServiceCombo.objects.prefetch_related('servicos_associados__service')
        queryset = queryset.filter(self.build_combo_search_q(term)).distinct().order_by(Lower('nome'), 'pk')[: self.limit]

        results = []
        for combo in queryset:
            services = ', '.join(item.service.nome for item in combo.servicos_associados.all()[:3])
            subtitle_parts = [combo.duracao_formatada, format_money_br(combo.valor_total)]
            if combo.desconto_percentual:
                subtitle_parts.append(f'{combo.desconto_percentual}% de desconto')
            if services:
                subtitle_parts.append(services)
            results.append({
                'id': combo.pk,
                'label': f'{combo.codigo} - {combo.nome}',
                'value': combo.codigo or combo.nome,
                'subtitle': ' | '.join(part for part in subtitle_parts if part),
                'url': combo.get_absolute_url(),
            })

        return JsonResponse({'results': results})


class ServiceComboDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ServiceCombo
    template_name = 'operations/service_combo_detail.html'
    context_object_name = 'combo'
    permission_required = 'operations.view_servicecombo'

    def get_queryset(self):
        return ServiceCombo.objects.prefetch_related('servicos_associados__service__pecas_associadas__item__unidade')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_change'] = self.request.user.has_perm('operations.change_servicecombo')
        context['can_delete'] = self.request.user.has_perm('operations.delete_servicecombo')
        return context


class ServiceComboFormsetMixin:
    formset_class = ServiceComboItemFormSet

    def get_formset(self):
        if self.request.method in ('POST', 'PUT'):
            return self.formset_class(self.request.POST, instance=getattr(self, 'object', None), prefix='services')
        return self.formset_class(instance=getattr(self, 'object', None), prefix='services')

    def get_combo_services_json(self):
        services = Service.objects.select_related('categoria').prefetch_related('pecas_associadas__item').order_by(Lower('nome'), 'pk')
        payload = []

        for service in services:
            parts = ', '.join(part.item.nome for part in service.pecas_associadas.all()[:3])
            payload.append({
                'id': service.pk,
                'codigo': service.codigo or '',
                'sku': service.codigo or '',
                'nome': service.nome,
                'descricao': service.descricao or '',
                'categoria': service.categoria.nome if service.categoria_id else '',
                'tipo': 'Serviço',
                'duracao': service.duracao_formatada,
                'valor': format_money_br(service.valor),
                'pecas': parts,
                'label': f'{service.codigo or "Sem código"} - {service.nome}',
                'card_fields': [
                    {'label': 'Categoria', 'value': service.categoria.nome if service.categoria_id else '-'},
                    {'label': 'Duração', 'value': service.duracao_formatada},
                    {'label': 'Valor', 'value': format_money_br(service.valor)},
                    {'label': 'Peças padrão', 'value': parts or '-'},
                    {'label': 'Código', 'value': service.codigo or '-'},
                ],
                'search': ' '.join([
                    service.codigo or '',
                    service.nome or '',
                    service.descricao or '',
                    service.categoria.nome if service.categoria_id else '',
                    service.duracao_formatada,
                    format_money_br(service.valor),
                    parts,
                ]).lower(),
            })

        return payload

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'services_formset' not in context:
            context['services_formset'] = self.get_formset()
        context['combo_services_json'] = self.get_combo_services_json()
        return context

    def form_valid(self, form):
        services_formset = self.get_formset()
        if not services_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, services_formset=services_formset))

        self.object = form.save()
        services_formset.instance = self.object
        services_formset.save()
        return redirect(self.get_success_url())


class ServiceComboCreateView(LoginRequiredMixin, PermissionRequiredMixin, ServiceComboFormsetMixin, FormTitleMixin, CreateView):
    model = ServiceCombo
    form_class = ServiceComboForm
    template_name = 'operations/service_combo_form.html'
    success_url = reverse_lazy('service_combo_list')
    permission_required = 'operations.add_servicecombo'
    title = 'Novo combo'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Combo cadastrado com sucesso.')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível salvar o combo. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class ServiceComboUpdateView(LoginRequiredMixin, PermissionRequiredMixin, ServiceComboFormsetMixin, FormTitleMixin, UpdateView):
    model = ServiceCombo
    form_class = ServiceComboForm
    template_name = 'operations/service_combo_form.html'
    success_url = reverse_lazy('service_combo_list')
    permission_required = 'operations.change_servicecombo'
    title = 'Editar combo'

    def get_queryset(self):
        return ServiceCombo.objects.prefetch_related('servicos_associados__service__pecas_associadas__item__unidade')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Combo atualizado com sucesso.')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível atualizar o combo. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class ServiceComboDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, SoftDeleteMixin, DeleteView):
    model = ServiceCombo
    template_name = 'operations/confirm_delete.html'
    success_url = reverse_lazy('service_combo_list')
    permission_required = 'operations.delete_servicecombo'
    title = 'Excluir combo'
    delete_success_message = 'Combo excluído com sucesso.'

    def get_queryset(self):
        return ServiceCombo.objects.filter(excluido_em__isnull=True)


class WorkOrderSettingsView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = WorkOrderSettings
    form_class = WorkOrderSettingsForm
    template_name = 'operations/work_order_settings_form.html'
    success_url = reverse_lazy('work_order_settings')
    permission_required = 'operations.change_workordersettings'
    title = 'Configurações de OS'

    def get_object(self, queryset=None):
        return WorkOrderSettings.get_solo()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['vagas_ocupadas'] = WorkOrder.workshop_occupied_count()
        context['vagas_disponiveis'] = WorkOrder.workshop_available_slots()
        context['capacity_statuses'] = [
            dict(WorkOrderStatus.choices).get(status, status)
            for status in WorkOrderStatus.workshop_capacity_statuses()
        ]
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Configurações de OS atualizadas com sucesso.')
        return super().form_valid(form)


class PdfSettingsView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, View):
    permission_required = 'operations.change_pdfsettings'
    template_name = 'operations/pdf_settings_form.html'
    title = 'Configurações de PDF'

    def get_objects(self):
        return (
            PdfSettings.get_solo(),
            PdfTemplateSettings.get_for(PdfTemplateType.CHECKIN),
            PdfTemplateSettings.get_for(PdfTemplateType.ORCAMENTO),
        )

    def build_forms(self, data=None, files=None):
        settings_obj, checkin_obj, budget_obj = self.get_objects()
        return {
            'global_form': PdfSettingsForm(data, files, instance=settings_obj, prefix='global'),
            'checkin_form': PdfTemplateSettingsForm(data, instance=checkin_obj, prefix='checkin'),
            'budget_form': PdfTemplateSettingsForm(data, instance=budget_obj, prefix='budget'),
        }

    def get(self, request, *args, **kwargs):
        context = self.build_forms()
        context['title'] = self.title
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        context = self.build_forms(request.POST, request.FILES)
        if all(form.is_valid() for form in context.values()):
            for form in context.values():
                form.save()
            messages.success(request, 'Configurações de PDF atualizadas com sucesso.')
            return redirect('pdf_settings')
        messages.error(request, 'Não foi possível salvar as configurações de PDF. Confira os campos destacados.')
        context['title'] = self.title
        return render(request, self.template_name, context)


class WorkOrderCustomerVehiclesView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if not (
            request.user.has_perm('operations.add_workorder')
            or request.user.has_perm('operations.change_workorder')
            or request.user.has_perm('operations.view_workorder')
        ):
            return JsonResponse({'results': []}, status=403)

        customer_id = (request.GET.get('cliente') or '').strip()
        if not customer_id.isdigit():
            return JsonResponse({'results': []})

        vehicles = Vehicle.objects.filter(cliente_id=int(customer_id)).order_by('placa', 'pk')
        results = []
        for vehicle in vehicles:
            label_parts = [vehicle.placa, f'{vehicle.marca} {vehicle.modelo}'.strip()]
            if vehicle.versao:
                label_parts.append(vehicle.versao)
            results.append({
                'id': vehicle.pk,
                'label': ' - '.join(part for part in label_parts if part),
                'placa': vehicle.placa,
                'marca': vehicle.marca,
                'modelo': vehicle.modelo,
                'versao': vehicle.versao,
                'km': vehicle.km,
            })

        return JsonResponse({'results': results})


class WorkOrderSearchMixin(OperationsSearchMixin):
    search_param_names = ('q', 'status', 'cliente', 'veiculo', 'data_inicial', 'data_final', 'valor_min', 'valor_max')

    def get_search_filters(self):
        return {name: (self.request.GET.get(name) or '').strip() for name in self.search_param_names}

    def build_work_order_search_q(self, term):
        return (
            Q(codigo__icontains=term)
            | Q(cliente__nome_razao_social__icontains=term)
            | Q(cliente__email__icontains=term)
            | Q(veiculo__placa__icontains=term)
            | Q(veiculo__marca__icontains=term)
            | Q(veiculo__modelo__icontains=term)
            | Q(problema_relatado__icontains=term)
            | Q(diagnostico__icontains=term)
            | Q(servicos_os__service__nome__icontains=term)
            | Q(combos_os__combo__nome__icontains=term)
            | Q(pecas_os__item__nome__icontains=term)
            | Q(pecas_os__item__sku__icontains=term)
        )

    def apply_work_order_filters(self, queryset):
        filters = self.get_search_filters()
        term = filters['q']

        if term:
            queryset = queryset.filter(self.build_work_order_search_q(term))
        if filters['status']:
            queryset = queryset.filter(status=filters['status'])
        if filters['cliente'].isdigit():
            queryset = queryset.filter(cliente_id=int(filters['cliente']))
        if filters['veiculo'].isdigit():
            queryset = queryset.filter(veiculo_id=int(filters['veiculo']))
        if filters['data_inicial']:
            queryset = queryset.filter(data_abertura__date__gte=filters['data_inicial'])
        if filters['data_final']:
            queryset = queryset.filter(data_abertura__date__lte=filters['data_final'])

        queryset = queryset.distinct().order_by('-data_abertura', '-pk')

        valor_min = self.parse_money_filter(filters['valor_min'])
        valor_max = self.parse_money_filter(filters['valor_max'])
        if valor_min is not None or valor_max is not None:
            filtered_pks = []
            queryset = queryset.prefetch_related('servicos_os__service', 'combos_os__combo', 'pecas_os__item')
            for order in queryset:
                total = order.valor_total
                if valor_min is not None and total < valor_min:
                    continue
                if valor_max is not None and total > valor_max:
                    continue
                filtered_pks.append(order.pk)
            queryset = WorkOrder.objects.filter(pk__in=filtered_pks).select_related('cliente', 'veiculo').prefetch_related('servicos_os__service', 'combos_os__combo', 'pecas_os__item').order_by('-data_abertura', '-pk')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self.get_search_filters()
        querydict = self.request.GET.copy()
        querydict.pop('page', None)
        context['filters'] = filters
        context['querystring'] = querydict.urlencode()
        context['has_active_filters'] = any(filters.values())
        context['status_choices'] = WorkOrderStatus.choices
        context['customer_choices'] = Customer.objects.order_by('nome_razao_social', 'pk')
        context['vehicle_choices'] = Vehicle.objects.select_related('cliente').order_by('placa', 'pk')
        context['workshop_settings'] = WorkOrderSettings.get_solo()
        context['vagas_ocupadas'] = WorkOrder.workshop_occupied_count()
        context['vagas_disponiveis'] = WorkOrder.workshop_available_slots()
        return context


class WorkOrderListView(LoginRequiredMixin, PermissionRequiredMixin, WorkOrderSearchMixin, ListView):
    model = WorkOrder
    template_name = 'operations/work_order_list.html'
    context_object_name = 'orders'
    paginate_by = 20
    permission_required = 'operations.view_workorder'

    def get_queryset(self):
        queryset = WorkOrder.objects.select_related('cliente', 'veiculo').prefetch_related('servicos_os__service', 'combos_os__combo', 'pecas_os__item')
        return self.apply_work_order_filters(queryset)


class WorkOrderAutocompleteView(LoginRequiredMixin, PermissionRequiredMixin, WorkOrderSearchMixin, View):
    permission_required = 'operations.view_workorder'
    limit = 10

    def get(self, request, *args, **kwargs):
        term = (request.GET.get('q') or '').strip()
        if len(term) < 2:
            return JsonResponse({'results': []})

        queryset = WorkOrder.objects.select_related('cliente', 'veiculo').prefetch_related('servicos_os__service', 'combos_os__combo', 'pecas_os__item')
        queryset = queryset.filter(self.build_work_order_search_q(term)).distinct().order_by('-data_abertura', '-pk')[: self.limit]

        results = []
        for order in queryset:
            subtitle_parts = [order.cliente.nome_razao_social, order.get_status_display(), format_money_br(order.valor_total)]
            if order.veiculo_id:
                subtitle_parts.insert(1, f'{order.veiculo.placa} - {order.veiculo.marca} {order.veiculo.modelo}')
            results.append({
                'id': order.pk,
                'label': f'{order.codigo} - {order.cliente.nome_razao_social}',
                'value': order.codigo or order.cliente.nome_razao_social,
                'subtitle': ' | '.join(part for part in subtitle_parts if part),
                'url': order.get_absolute_url(),
            })

        return JsonResponse({'results': results})


class WorkOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = WorkOrder
    template_name = 'operations/work_order_detail.html'
    context_object_name = 'order'
    permission_required = 'operations.view_workorder'

    def get_queryset(self):
        return WorkOrder.objects.select_related('cliente', 'veiculo', 'estoque_baixado_por').prefetch_related(
            'servicos_os__service',
            'combos_os__combo__servicos_associados__service',
            'pecas_os__item__categoria',
            'pecas_os__item__marca',
            'pecas_os__item__unidade',
            'transicoes_status__criado_por',
            'orcamentos_aprovacao__itens',
            'orcamentos_aprovacao__auditorias__usuario_interno',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        has_work_order_change = self.request.user.has_perm('operations.change_workorder')
        can_edit_order = has_work_order_change and self.object.status != WorkOrderStatus.CANCELADA and not self.object.has_locked_approval
        context['can_change'] = can_edit_order
        context['can_transition_status'] = has_work_order_change
        context['can_delete'] = self.request.user.has_perm('operations.delete_workorder')
        context['can_stock_out'] = (
            self.request.user.has_perm('stock.add_stockmovement')
            and can_edit_order
            and self.object.status in WorkOrderStatus.stock_out_statuses()
        )
        context['stock_requirements'] = self.object.get_stock_requirements()
        context['stock_requirement_sources'] = self.object.get_stock_requirement_sources()
        context['can_adjust_stock_requirements'] = context['can_change'] and not self.object.estoque_baixado and not self.object.has_locked_approval
        context['vehicle_checkin'] = self.object.checkins.filter(ativo=True, excluido_em__isnull=True).first()
        available_transitions = list(self.object.get_available_transitions())
        if self.object.has_rejected_approval_budget and WorkOrderStatus.EM_TESTE not in available_transitions:
            available_transitions.append(WorkOrderStatus.EM_TESTE)
        if self.object.has_approval_in_progress:
            available_transitions = [status for status in available_transitions if status != WorkOrderStatus.APROVADA]
        context['available_status_transitions'] = [
            {'value': status.value, 'label': status.label}
            for status in available_transitions
        ]
        context['status_history'] = self.object.transicoes_status.select_related('criado_por').all()[:20]
        context['purchase_orders'] = self.object.pedidos_compra.select_related('fornecedor').prefetch_related('itens').all()
        context['can_view_purchase_orders'] = self.request.user.has_perm('stock.view_purchaseorder')
        context['suggested_statuses'] = WorkOrderStatus.suggested_statuses()
        context['current_approval_budget'] = self.object.get_current_approval_budget()
        context['effective_approval_budget'] = self.object.get_effective_approval_budget()
        context['approval_budgets'] = self.object.orcamentos_aprovacao.prefetch_related('itens', 'auditorias__usuario_interno').all()
        context['can_send_approval_budget'] = has_work_order_change and self.object.status == WorkOrderStatus.AGUARDANDO_APROVACAO
        context['can_register_approval'] = has_work_order_change and bool(context['current_approval_budget'] and context['current_approval_budget'].status == WorkOrderApprovalStatus.PENDING)
        context['can_generate_new_approval_budget'] = has_work_order_change and bool(
            context['current_approval_budget']
            and context['current_approval_budget'].status in {
                *WorkOrderApprovalStatus.locking_statuses(),
                WorkOrderApprovalStatus.REJECTED,
            }
        )
        context['can_move_rejected_budget_to_test'] = (
            has_work_order_change
            and self.object.status == WorkOrderStatus.ORCAMENTO
            and self.object.has_rejected_approval_budget
        )
        return context


class WorkOrderFormsetMixin:
    service_formset_class = WorkOrderServiceItemFormSet
    combo_formset_class = WorkOrderComboItemFormSet
    part_formset_class = WorkOrderPartItemFormSet

    def get_service_formset(self):
        if self.request.method in ('POST', 'PUT'):
            return self.service_formset_class(self.request.POST, instance=getattr(self, 'object', None), prefix='services')
        return self.service_formset_class(instance=getattr(self, 'object', None), prefix='services')

    def get_combo_formset(self):
        if self.request.method in ('POST', 'PUT'):
            return self.combo_formset_class(self.request.POST, instance=getattr(self, 'object', None), prefix='combos')
        return self.combo_formset_class(instance=getattr(self, 'object', None), prefix='combos')

    def get_part_formset(self):
        if self.request.method in ('POST', 'PUT'):
            return self.part_formset_class(self.request.POST, instance=getattr(self, 'object', None), prefix='parts')
        return self.part_formset_class(instance=getattr(self, 'object', None), prefix='parts')

    def get_work_order_services_json(self):
        payload = []
        services = Service.objects.select_related('categoria').prefetch_related('pecas_associadas__item').order_by(Lower('nome'), 'pk')
        for service in services:
            parts = ', '.join(part.item.nome for part in service.pecas_associadas.all()[:3])
            payload.append({
                'id': service.pk,
                'codigo': service.codigo or '',
                'sku': service.codigo or '',
                'nome': service.nome,
                'tipo': 'Serviço',
                'duracao': service.duracao_formatada,
                'valor': format_money_br(service.valor),
                'pecas': parts,
                'label': f'{service.codigo or "Sem código"} - {service.nome}',
                'card_fields': [
                    {'label': 'Categoria', 'value': service.categoria.nome if service.categoria_id else '-'},
                    {'label': 'Duração', 'value': service.duracao_formatada},
                    {'label': 'Valor', 'value': format_money_br(service.valor)},
                    {'label': 'Peças padrão', 'value': parts or '-'},
                    {'label': 'Código', 'value': service.codigo or '-'},
                ],
                'search': ' '.join([service.codigo or '', service.nome or '', service.descricao or '', service.duracao_formatada, format_money_br(service.valor), parts]).lower(),
            })
        return payload

    def get_work_order_combos_json(self):
        payload = []
        combos = ServiceCombo.objects.prefetch_related(
            'servicos_associados__service__pecas_associadas__item'
        ).order_by(Lower('nome'), 'pk')
        for combo in combos:
            service_items = list(combo.servicos_associados.all())
            services = ', '.join(item.service.nome for item in service_items[:3])
            if len(service_items) > 3:
                services = f'{services} e mais {len(service_items) - 3}'

            parts_counter = {}
            for combo_service in service_items:
                service = combo_service.service
                for default_part in service.pecas_associadas.select_related('item'):
                    item = default_part.item
                    current = parts_counter.setdefault(item.pk, {
                        'sku': item.sku or '',
                        'nome': item.nome,
                        'quantidade': 0,
                    })
                    current['quantidade'] += int(default_part.quantidade or 0)

            parts = ', '.join(
                f'{row["sku"]} - {row["nome"]} ({row["quantidade"]}x)' if row['sku'] else f'{row["nome"]} ({row["quantidade"]}x)'
                for row in sorted(parts_counter.values(), key=lambda item: item['nome'].lower())[:4]
            )
            if len(parts_counter) > 4:
                parts = f'{parts} e mais {len(parts_counter) - 4}'

            payload.append({
                'id': combo.pk,
                'codigo': combo.codigo or '',
                'sku': combo.codigo or '',
                'nome': combo.nome,
                'tipo': 'Combo',
                'duracao': combo.duracao_formatada,
                'valor': format_money_br(combo.valor_total),
                'servicos': services,
                'pecas': parts,
                'label': f'{combo.codigo or "Sem código"} - {combo.nome}',
                'card_fields': [
                    {'label': 'Duração', 'value': combo.duracao_formatada},
                    {'label': 'Valor', 'value': format_money_br(combo.valor_total)},
                    {'label': 'Serviços', 'value': services or '-'},
                    {'label': 'Peças padrão', 'value': parts or '-'},
                    {'label': 'Desconto', 'value': f'{combo.desconto_percentual or 0}%'},
                ],
                'search': ' '.join([combo.codigo or '', combo.nome or '', combo.descricao or '', combo.duracao_formatada, format_money_br(combo.valor_total), services, parts]).lower(),
            })
        return payload

    def get_work_order_parts_json(self):
        payload = []
        items = InventoryItem.objects.select_related('categoria', 'marca', 'unidade').order_by(Lower('nome'), 'pk')
        for item in items:
            payload.append({
                'id': item.pk,
                'sku': item.sku or '',
                'nome': item.nome,
                'descricao': item.descricao or '',
                'categoria': item.categoria.nome if item.categoria_id else '',
                'marca': item.marca.nome if item.marca_id else '',
                'unidade': item.unidade.sigla if item.unidade_id else '',
                'estoque_atual': str(item.estoque_atual),
                'estoque_minimo': str(item.estoque_minimo),
                'preco_custo': format_money_br(item.preco_custo),
                'preco_venda': format_money_br(item.valor_venda),
                'valor': format_money_br(item.valor_venda),
                'tipo': item.get_tipo_display(),
                'label': f'{item.sku or "Sem SKU"} - {item.nome}',
                'search': ' '.join([item.sku or '', item.nome or '', item.descricao or '', item.categoria.nome if item.categoria_id else '', item.marca.nome if item.marca_id else '', item.unidade.sigla if item.unidade_id else '', item.get_tipo_display()]).lower(),
            })
        return payload

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'services_formset' not in context:
            context['services_formset'] = self.get_service_formset()
        if 'combos_formset' not in context:
            context['combos_formset'] = self.get_combo_formset()
        if 'parts_formset' not in context:
            context['parts_formset'] = self.get_part_formset()
        context['work_order_services_json'] = self.get_work_order_services_json()
        context['work_order_combos_json'] = self.get_work_order_combos_json()
        context['work_order_parts_json'] = self.get_work_order_parts_json()
        return context

    def form_valid(self, form):
        if getattr(self, 'object', None) is not None and self.object.status == WorkOrderStatus.CANCELADA:
            messages.error(self.request, 'OS cancelada não pode ser editada.')
            return redirect(self.object.get_absolute_url())
        if getattr(self, 'object', None) is not None and self.object.has_locked_approval:
            messages.error(self.request, 'Itens com orçamento em aprovação ou aprovado não podem ser alterados diretamente. Use Gerar novo orçamento.')
            return redirect(self.object.get_absolute_url())

        services_formset = self.get_service_formset()
        combos_formset = self.get_combo_formset()
        parts_formset = self.get_part_formset()

        if not all([services_formset.is_valid(), combos_formset.is_valid(), parts_formset.is_valid()]):
            return self.render_to_response(self.get_context_data(
                form=form,
                services_formset=services_formset,
                combos_formset=combos_formset,
                parts_formset=parts_formset,
            ))

        with transaction.atomic():
            self.object = form.save()
            for formset in (services_formset, combos_formset, parts_formset):
                formset.instance = self.object
                formset.save()

        if self.object.ensure_awaiting_parts_if_needed(self.request.user):
            messages.warning(
                self.request,
                'A OS foi movida para Aguardando peça porque há itens sem estoque suficiente.'
            )

        return redirect(self.get_success_url())


class WorkOrderCreateView(LoginRequiredMixin, PermissionRequiredMixin, WorkOrderFormsetMixin, FormTitleMixin, CreateView):
    model = WorkOrder
    form_class = WorkOrderForm
    template_name = 'operations/work_order_form.html'
    success_url = reverse_lazy('work_order_list')
    permission_required = 'operations.add_workorder'
    title = 'Nova OS'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Ordem de serviço cadastrada com sucesso.')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível salvar a OS. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class WorkOrderUpdateView(LoginRequiredMixin, PermissionRequiredMixin, WorkOrderFormsetMixin, FormTitleMixin, UpdateView):
    model = WorkOrder
    form_class = WorkOrderForm
    template_name = 'operations/work_order_form.html'
    success_url = reverse_lazy('work_order_list')
    permission_required = 'operations.change_workorder'
    title = 'Editar OS'

    def get_queryset(self):
        return WorkOrder.objects.select_related('cliente', 'veiculo').prefetch_related('servicos_os__service', 'combos_os__combo', 'pecas_os__item')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.status == WorkOrderStatus.CANCELADA:
            messages.error(request, 'OS cancelada não pode ser editada.')
            return redirect(self.object.get_absolute_url())
        if self.object.has_locked_approval:
            messages.error(request, 'Esta OS possui orçamento em aprovação ou aprovado. Use Gerar novo orçamento para alterar itens.')
            return redirect(self.object.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        previous_status = WorkOrder.all_objects.get(pk=form.instance.pk).status
        target_status = form.cleaned_data.get('status') or previous_status

        # A gravação do formulário não deve pular a máquina de estados.
        # Salvamos os demais campos mantendo o status anterior e, em seguida,
        # aplicamos a transição pelo serviço de domínio atômico.
        form.instance.status = previous_status
        response = super().form_valid(form)

        if target_status != previous_status:
            try:
                self.object.transition_to(
                    target_status,
                    user=self.request.user,
                    observacao='Alteração realizada no formulário da OS.',
                )
            except ValidationError as exc:
                messages.error(self.request, ' '.join(exc.messages) if hasattr(exc, 'messages') else str(exc))
                return redirect(self.object.get_absolute_url())

        messages.success(self.request, 'Ordem de serviço atualizada com sucesso.')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível atualizar a OS. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class WorkOrderDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, SoftDeleteMixin, DeleteView):
    model = WorkOrder
    template_name = 'operations/confirm_delete.html'
    success_url = reverse_lazy('work_order_list')
    permission_required = 'operations.delete_workorder'
    title = 'Excluir OS'
    delete_success_message = 'OS excluída com sucesso.'

    def get_queryset(self):
        return WorkOrder.objects.filter(excluido_em__isnull=True)


class WorkOrderStockOutView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'operations.change_workorder'

    def post(self, request, pk, *args, **kwargs):
        if not request.user.has_perm('stock.add_stockmovement'):
            messages.error(request, 'Você não tem permissão para movimentar estoque.')
            return redirect('work_order_detail', pk=pk)

        order = WorkOrder.objects.get(pk=pk)
        try:
            movements = order.baixar_estoque(user=request.user)
        except ValidationError as exc:
            if hasattr(exc, 'messages'):
                message = ' '.join(exc.messages)
            else:
                message = str(exc)
            messages.error(request, message)
            return redirect(order.get_absolute_url())

        if movements:
            messages.success(request, f'Estoque baixado com sucesso. {len(movements)} movimentação(ões) criada(s).')
        else:
            messages.warning(request, 'A OS não tinha peças para baixar. Marcada como estoque baixado.')
        return redirect(order.get_absolute_url())



class WorkOrderStockRequirementUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'operations.change_workorder'

    def post(self, request, pk, *args, **kwargs):
        order = get_object_or_404(WorkOrder, pk=pk, ativo=True, excluido_em__isnull=True)
        next_url = request.POST.get('next') or order.get_absolute_url()

        if order.status == WorkOrderStatus.CANCELADA:
            messages.error(request, 'OS cancelada não pode ser editada.')
            return redirect(next_url)
        if order.estoque_baixado:
            messages.error(request, 'Não é possível ajustar peças previstas de uma OS com estoque já baixado.')
            return redirect(next_url)
        if order.has_locked_approval:
            messages.error(request, 'Peças de OS com orçamento em aprovação ou aprovado não podem ser alteradas diretamente. Use Gerar novo orçamento.')
            return redirect(next_url)

        quantities = {}
        errors = []
        for requirement in order.get_base_stock_requirements():
            item = requirement['item']
            field_name = f'quantidade_prevista_{item.pk}'
            raw_value = (request.POST.get(field_name) or '').strip()
            if not raw_value:
                errors.append(f'Informe a quantidade de {item.nome}.')
                continue
            try:
                quantity = int(raw_value)
            except (TypeError, ValueError):
                errors.append(f'A quantidade de {item.nome} deve ser um número inteiro.')
                continue
            if quantity < 1:
                errors.append(f'A quantidade de {item.nome} deve ser maior que zero.')
                continue
            quantities[item.pk] = quantity

        if errors:
            messages.error(request, ' '.join(errors[:3]))
            return redirect(next_url)

        try:
            order.update_stock_requirement_overrides(quantities)
        except ValidationError as exc:
            if hasattr(exc, 'messages'):
                message = ' '.join(exc.messages)
            else:
                message = str(exc)
            messages.error(request, message)
            return redirect(next_url)

        auto_transition = order.ensure_awaiting_parts_if_needed(
            request.user,
            observacao='OS movida automaticamente para Aguardando peça após ajuste das quantidades previstas.',
        )
        if auto_transition:
            messages.warning(request, 'Quantidades previstas ajustadas, mas a OS ficou como Aguardando peça por estoque insuficiente.')
        else:
            messages.success(request, 'Quantidades previstas ajustadas com sucesso.')
        return redirect(next_url)


MECHANIC_QUEUE_STATUSES = (
    WorkOrderStatus.ABERTA,
    WorkOrderStatus.DIAGNOSTICO,
    WorkOrderStatus.APROVADA,
    WorkOrderStatus.EM_EXECUCAO,
    WorkOrderStatus.AGUARDANDO_PECA,
    WorkOrderStatus.EM_TESTE,
)


class MechanicWorkOrderListView(TechnicianRequiredMixin, ListView):
    model = WorkOrder
    template_name = 'operations/mechanic_work_order_list.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        return (
            WorkOrder.objects.select_related('cliente', 'veiculo')
            .prefetch_related('servicos_os__service', 'combos_os__combo', 'pecas_os__item')
            .filter(status__in=MECHANIC_QUEUE_STATUSES, ativo=True, excluido_em__isnull=True)
            .order_by('previsao_entrega', 'data_abertura', 'pk')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for order in context['orders']:
            order.stock_shortages_cached = order.get_stock_shortages()
        context['queue_statuses'] = MECHANIC_QUEUE_STATUSES
        return context


class MechanicWorkOrderDetailView(TechnicianRequiredMixin, WorkOrderFormsetMixin, DetailView):
    model = WorkOrder
    template_name = 'operations/mechanic_work_order_detail.html'
    context_object_name = 'order'

    def get_queryset(self):
        return WorkOrder.objects.select_related('cliente', 'veiculo').prefetch_related(
            'servicos_os__service',
            'combos_os__combo__servicos_associados__service',
            'pecas_os__item__categoria',
            'pecas_os__item__marca',
            'pecas_os__item__unidade',
            'transicoes_status__criado_por',
        ).filter(status__in=MECHANIC_QUEUE_STATUSES, ativo=True, excluido_em__isnull=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stock_requirements'] = self.object.get_stock_requirements()
        context['stock_requirement_sources'] = self.object.get_stock_requirement_sources()
        context['stock_shortages'] = self.object.get_stock_shortages()
        context['can_adjust_stock_requirements'] = not self.object.estoque_baixado and not self.object.has_locked_approval
        context['can_start_service'] = self.object.status in {WorkOrderStatus.APROVADA, WorkOrderStatus.AGUARDANDO_PECA}
        context['status_history'] = self.object.transicoes_status.select_related('criado_por').all()[:10]
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.status == WorkOrderStatus.CANCELADA:
            messages.error(request, 'OS cancelada não pode ser editada.')
            return redirect('mechanic_work_order_detail', pk=self.object.pk)
        if self.object.estoque_baixado:
            messages.error(request, 'Não é possível alterar itens de uma OS com estoque já baixado.')
            return redirect('mechanic_work_order_detail', pk=self.object.pk)
        if self.object.has_locked_approval:
            messages.error(request, 'Itens com orçamento em aprovação ou aprovado não podem ser alterados diretamente. Use Gerar novo orçamento.')
            return redirect('mechanic_work_order_detail', pk=self.object.pk)

        services_formset = self.get_service_formset()
        combos_formset = self.get_combo_formset()
        parts_formset = self.get_part_formset()

        if not all([services_formset.is_valid(), combos_formset.is_valid(), parts_formset.is_valid()]):
            messages.error(request, 'Não foi possível atualizar os itens da OS. Confira os alertas do formulário.')
            return self.render_to_response(self.get_context_data(
                services_formset=services_formset,
                combos_formset=combos_formset,
                parts_formset=parts_formset,
            ))

        for formset in (services_formset, combos_formset, parts_formset):
            formset.instance = self.object
            formset.save()

        auto_transition = self.object.ensure_awaiting_parts_if_needed(
            request.user,
            observacao='OS movida automaticamente para Aguardando peça após alteração de itens pela mecânica.',
        )
        if auto_transition:
            messages.warning(request, 'Itens atualizados, mas a OS ficou como Aguardando peça porque há itens sem estoque suficiente.')
        else:
            messages.success(request, 'Itens da OS atualizados com sucesso.')
        return redirect('mechanic_work_order_detail', pk=self.object.pk)


class MechanicWorkOrderStartView(TechnicianRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        order = get_object_or_404(WorkOrder, pk=pk, ativo=True, excluido_em__isnull=True)
        if order.status not in {WorkOrderStatus.APROVADA, WorkOrderStatus.AGUARDANDO_PECA}:
            messages.error(request, 'Apenas OS aprovada ou aguardando peça pode ser iniciada pela mecânica.')
            return redirect('mechanic_work_order_detail', pk=order.pk)

        shortages = order.get_stock_shortages()
        if shortages:
            if order.status == WorkOrderStatus.APROVADA:
                order.transition_to(
                    WorkOrderStatus.AGUARDANDO_PECA,
                    user=request.user,
                    observacao='Tentativa de iniciar serviço bloqueada por estoque insuficiente.',
                )
            messages.error(
                request,
                'Não é possível iniciar o serviço porque há peças sem estoque suficiente: '
                f'{order.stock_shortage_message()}.'
            )
            return redirect('mechanic_work_order_detail', pk=order.pk)

        try:
            order.transition_to(
                WorkOrderStatus.EM_EXECUCAO,
                user=request.user,
                observacao='Serviço iniciado pela área de mecânica.',
            )
        except ValidationError as exc:
            if not order.checkins.filter(ativo=True, excluido_em__isnull=True).exists():
                checkin_url = f'{reverse('vehicle_checkin_create')}?ordem_servico={order.pk}'
                messages.error(
                    request,
                    format_html(
                        'Não é possível iniciar a OS sem check-in associado. <a class="link link-primary font-semibold" href="{}">Fazer check-in agora</a>.',
                        checkin_url,
                    )
                )
            else:
                messages.error(request, ' '.join(exc.messages) if hasattr(exc, 'messages') else str(exc))
        else:
            messages.success(request, 'Serviço iniciado. A OS foi movida para Em execução.')
        return redirect('mechanic_work_order_detail', pk=order.pk)

class WorkOrderStatusTransitionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'operations.change_workorder'

    def post(self, request, pk, *args, **kwargs):
        order = get_object_or_404(WorkOrder, pk=pk, ativo=True, excluido_em__isnull=True)
        new_status = (request.POST.get('status') or '').strip()
        observacao = (request.POST.get('observacao') or '').strip()

        if new_status not in WorkOrderStatus.values:
            messages.error(request, 'Status informado é inválido.')
            return redirect(order.get_absolute_url())

        try:
            transition = order.transition_to(new_status, user=request.user, observacao=observacao)
        except ValidationError as exc:
            if new_status == WorkOrderStatus.EM_EXECUCAO and not order.checkins.filter(ativo=True, excluido_em__isnull=True).exists():
                checkin_url = f'{reverse('vehicle_checkin_create')}?ordem_servico={order.pk}'
                messages.error(
                    request,
                    format_html(
                        'Não é possível mover a OS para Em execução sem check-in associado. <a class="link link-primary font-semibold" href="{}">Fazer check-in agora</a>.',
                        checkin_url,
                    )
                )
                return redirect(order.get_absolute_url())

            if new_status == WorkOrderStatus.EM_EXECUCAO and order.status == WorkOrderStatus.APROVADA and order.has_stock_shortage():
                order.transition_to(
                    WorkOrderStatus.AGUARDANDO_PECA,
                    user=request.user,
                    observacao='Tentativa de mover para Em execução bloqueada por estoque insuficiente.',
                )
                messages.error(
                    request,
                    'Não é possível mover a OS para Em execução por estoque insuficiente. A OS foi movida para Aguardando peça.'
                )
                return redirect(order.get_absolute_url())

            if hasattr(exc, 'messages'):
                message = ' '.join(exc.messages)
            else:
                message = str(exc)
            messages.error(request, message)
            return redirect(order.get_absolute_url())

        auto_transition = None
        if transition is not None:
            auto_transition = order.ensure_awaiting_parts_if_needed(
                user=request.user,
                observacao='OS movida automaticamente para Aguardando peça após validação de estoque.',
            )

        if transition is None:
            messages.info(request, 'A OS já estava neste status.')
        elif auto_transition is not None:
            messages.warning(request, 'Status alterado, mas a OS ficou como Aguardando peça porque há itens sem estoque suficiente.')
        else:
            messages.success(request, f'Status alterado para {order.get_status_display()}.')
        return redirect(order.get_absolute_url())


class WorkOrderSendApprovalBudgetView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'operations.change_workorder'

    def post(self, request, pk, *args, **kwargs):
        order = get_object_or_404(WorkOrder, pk=pk, ativo=True, excluido_em__isnull=True)
        if order.status == WorkOrderStatus.CANCELADA:
            messages.error(request, 'OS cancelada não pode enviar orçamento.')
            return redirect(order.get_absolute_url())
        if order.status != WorkOrderStatus.AGUARDANDO_APROVACAO:
            try:
                order.transition_to(
                    WorkOrderStatus.AGUARDANDO_APROVACAO,
                    user=request.user,
                    observacao='Orçamento enviado ao cliente.',
                )
            except ValidationError as exc:
                messages.error(request, ' '.join(exc.messages) if hasattr(exc, 'messages') else str(exc))
                return redirect(order.get_absolute_url())

        budget = order.get_or_create_pending_approval_budget(user=request.user, send_email=True, request=request)
        if budget.email_enviado:
            messages.success(request, 'Orçamento enviado ao cliente por email.')
        else:
            messages.warning(request, 'Orçamento gerado, mas o email não foi confirmado como enviado. Verifique o histórico de mensagens.')
        return redirect(order.get_absolute_url())


class WorkOrderRegisterApprovalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'operations.change_workorder'
    template_name = 'operations/work_order_register_approval.html'

    def get_budget(self, pk):
        order = get_object_or_404(WorkOrder, pk=pk, ativo=True, excluido_em__isnull=True)
        budget = order.get_current_approval_budget()
        if not budget or budget.status != WorkOrderApprovalStatus.PENDING:
            return order, None
        return order, budget

    def get(self, request, pk, *args, **kwargs):
        order, budget = self.get_budget(pk)
        if not budget:
            messages.error(request, 'Não há orçamento pendente de aprovação para esta OS.')
            return redirect(order.get_absolute_url())
        form = WorkOrderApprovalDecisionForm(budget=budget, initial={'observacao': 'Aprovado'})
        return render(request, self.template_name, {'order': order, 'budget': budget, 'form': form})

    def post(self, request, pk, *args, **kwargs):
        order, budget = self.get_budget(pk)
        if not budget:
            messages.error(request, 'Não há orçamento pendente de aprovação para esta OS.')
            return redirect(order.get_absolute_url())
        form = WorkOrderApprovalDecisionForm(request.POST, budget=budget)
        if not form.is_valid():
            messages.error(request, 'Não foi possível registrar a aprovação. Confira os campos obrigatórios.')
            return render(request, self.template_name, {'order': order, 'budget': budget, 'form': form})
        audit = budget.apply_decision(
            decision=form.cleaned_data['decisao'],
            approved_item_ids=[item.pk for item in form.cleaned_data.get('itens_aprovados')],
            method=form.cleaned_data['metodo'],
            responsible_name=form.cleaned_data['nome_responsavel'],
            document=form.cleaned_data['documento'],
            observation=form.cleaned_data['observacao'],
            ip=get_request_ip(request),
            user_agent=get_request_user_agent(request),
            location=form.cleaned_data.get('local') or 'Registro interno',
            internal_user=request.user,
            signature_data=form.cleaned_data.get('assinatura_base64') or '',
            signature_name=form.cleaned_data.get('nome_responsavel') or '',
        )
        messages.success(request, f'Aprovação registrada com auditoria #{audit.pk}.')
        return redirect(order.get_absolute_url())


class WorkOrderNewApprovalBudgetView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'operations.change_workorder'

    def post(self, request, pk, *args, **kwargs):
        order = get_object_or_404(WorkOrder, pk=pk, ativo=True, excluido_em__isnull=True)
        if order.status in {WorkOrderStatus.CANCELADA, WorkOrderStatus.ARQUIVADA}:
            messages.error(request, 'Não é possível gerar novo orçamento para OS cancelada ou arquivada.')
            return redirect(order.get_absolute_url())
        order.supersede_current_approval_budget(user=request.user, observacao='Novo orçamento solicitado pela oficina.')
        if order.status != WorkOrderStatus.ORCAMENTO:
            try:
                order.transition_to(
                    WorkOrderStatus.ORCAMENTO,
                    user=request.user,
                    observacao='Novo orçamento solicitado; itens liberados para revisão antes de nova aprovação.',
                )
            except ValidationError:
                previous_status = order.status
                order.status = WorkOrderStatus.ORCAMENTO
                order.save(update_fields=['status', 'atualizado_em'])
                WorkOrderStatusTransition.objects.create(
                    ordem_servico=order,
                    status_anterior=previous_status,
                    status_novo=WorkOrderStatus.ORCAMENTO,
                    observacao='Novo orçamento solicitado; retorno forçado para Orçamento.',
                    criado_por=request.user if request.user.is_authenticated else None,
                )
        messages.success(request, 'Novo orçamento iniciado. Revise os itens e envie novamente para aprovação.')
        return redirect(order.get_absolute_url())


class WorkOrderApprovalDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = WorkOrderApprovalBudget
    template_name = 'operations/work_order_approval_detail.html'
    context_object_name = 'budget'
    permission_required = 'operations.view_workorderapprovalbudget'

    def get_queryset(self):
        return WorkOrderApprovalBudget.objects.select_related('ordem_servico', 'ordem_servico__cliente', 'ordem_servico__veiculo', 'criado_por', 'enviado_por').prefetch_related('itens', 'auditorias__usuario_interno')


class PublicWorkOrderApprovalView(View):
    template_name = 'operations/public_work_order_approval.html'

    def get_budget(self, token):
        return get_object_or_404(
            WorkOrderApprovalBudget.objects.select_related('ordem_servico', 'ordem_servico__cliente', 'ordem_servico__veiculo').prefetch_related('itens'),
            token=token,
        )

    def build_context(self, budget, form=None, **extra):
        order = budget.ordem_servico
        selected_item_ids = set()
        selected_decision = WorkOrderApprovalDecision.APPROVE_ALL

        if form is not None:
            raw_decision = None
            raw_selected_items = []
            if form.is_bound:
                raw_decision = form.data.get(form.add_prefix('decisao')) or form.data.get('decisao')
                raw_selected_items = form.data.getlist(form.add_prefix('itens_aprovados')) or form.data.getlist('itens_aprovados')
            else:
                raw_decision = form.initial.get('decisao') or form.fields['decisao'].initial
                raw_selected_items = form.initial.get('itens_aprovados') or []
            selected_decision = raw_decision or WorkOrderApprovalDecision.APPROVE_ALL
            selected_item_ids = {str(item_id) for item_id in raw_selected_items}

        approval_item_rows = [
            {'item': item, 'selected': str(item.pk) in selected_item_ids}
            for item in budget.itens.all().order_by('tipo', 'nome', 'pk')
        ]

        context = {
            'budget': budget,
            'order': order,
            'form': form,
            'approval_item_rows': approval_item_rows,
            'selected_decision': selected_decision,
            'decision_approve_all': WorkOrderApprovalDecision.APPROVE_ALL,
            'decision_approve_partial': WorkOrderApprovalDecision.APPROVE_PARTIAL,
            'decision_reject_all': WorkOrderApprovalDecision.REJECT_ALL,
        }
        context.update(extra)
        return context

    def get(self, request, token, *args, **kwargs):
        budget = self.get_budget(token)
        form = None
        if budget.status == WorkOrderApprovalStatus.PENDING:
            form = WorkOrderApprovalDecisionForm(budget=budget, public=True, initial={
                'decisao': WorkOrderApprovalDecision.APPROVE_ALL,
                'observacao': 'Aprovado',
                'metodo': WorkOrderApprovalMethod.EMAIL,
                'local': 'e-mail',
            })
        return render(request, self.template_name, self.build_context(budget, form=form))

    def post(self, request, token, *args, **kwargs):
        budget = self.get_budget(token)
        if budget.status != WorkOrderApprovalStatus.PENDING:
            return render(request, self.template_name, self.build_context(budget, form=None, already_answered=True))
        form = WorkOrderApprovalDecisionForm(request.POST, budget=budget, public=True)
        if not form.is_valid():
            messages.error(request, 'Não foi possível registrar sua resposta. Confira os campos obrigatórios.')
            return render(request, self.template_name, self.build_context(budget, form=form))
        audit = budget.apply_decision(
            decision=form.cleaned_data['decisao'],
            approved_item_ids=[item.pk for item in form.cleaned_data.get('itens_aprovados')],
            method=WorkOrderApprovalMethod.EMAIL,
            responsible_name=form.cleaned_data['nome_responsavel'],
            document=form.cleaned_data['documento'],
            observation=form.cleaned_data['observacao'],
            ip=get_request_ip(request),
            user_agent=get_request_user_agent(request),
            location='e-mail',
            internal_user=None,
        )
        return render(request, self.template_name, self.build_context(budget, form=None, audit=audit, answered=True))


from django.core.mail import EmailMessage
from .forms import VehicleCheckInForm
from .models import VehicleCheckIn, VehicleCheckInPhoto
from .pdf import generate_vehicle_checkin_pdf


class VehicleCheckInSearchMixin(OperationsSearchMixin):
    search_param_names = ('q', 'status_email', 'data_inicial', 'data_final')

    def get_search_filters(self):
        return {name: (self.request.GET.get(name) or '').strip() for name in self.search_param_names}

    def build_checkin_search_q(self, term):
        return (
            Q(codigo__icontains=term)
            | Q(ordem_servico__codigo__icontains=term)
            | Q(cliente__nome_razao_social__icontains=term)
            | Q(cliente__email__icontains=term)
            | Q(veiculo__placa__icontains=term)
            | Q(veiculo__marca__icontains=term)
            | Q(veiculo__modelo__icontains=term)
            | Q(veiculo__versao__icontains=term)
            | Q(avarias_observadas__icontains=term)
            | Q(observacoes__icontains=term)
        )

    def apply_checkin_filters(self, queryset):
        filters = self.get_search_filters()
        term = filters['q']
        if term:
            queryset = queryset.filter(self.build_checkin_search_q(term))
        if filters['status_email'] == 'enviado':
            queryset = queryset.filter(email_enviado=True)
        elif filters['status_email'] == 'pendente':
            queryset = queryset.filter(email_enviado=False)
        if filters['data_inicial']:
            queryset = queryset.filter(data_checkin__date__gte=filters['data_inicial'])
        if filters['data_final']:
            queryset = queryset.filter(data_checkin__date__lte=filters['data_final'])
        return queryset.distinct().order_by('-data_checkin', '-pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self.get_search_filters()
        querydict = self.request.GET.copy()
        querydict.pop('page', None)
        context['filters'] = filters
        context['querystring'] = querydict.urlencode()
        context['has_active_filters'] = any(filters.values())
        return context


class VehicleCheckInListView(LoginRequiredMixin, PermissionRequiredMixin, VehicleCheckInSearchMixin, ListView):
    model = VehicleCheckIn
    template_name = 'operations/vehicle_checkin_list.html'
    context_object_name = 'checkins'
    paginate_by = 20
    permission_required = 'operations.view_vehiclecheckin'

    def get_queryset(self):
        queryset = VehicleCheckIn.objects.select_related('ordem_servico', 'cliente', 'veiculo', 'criado_por')
        return self.apply_checkin_filters(queryset)


class VehicleCheckInAutocompleteView(LoginRequiredMixin, PermissionRequiredMixin, VehicleCheckInSearchMixin, View):
    permission_required = 'operations.view_vehiclecheckin'
    limit = 10

    def get(self, request, *args, **kwargs):
        term = (request.GET.get('q') or '').strip()
        if len(term) < 2:
            return JsonResponse({'results': []})
        queryset = VehicleCheckIn.objects.select_related('ordem_servico', 'cliente', 'veiculo')
        queryset = queryset.filter(self.build_checkin_search_q(term)).distinct().order_by('-data_checkin', '-pk')[: self.limit]
        results = []
        for checkin in queryset:
            results.append({
                'id': checkin.pk,
                'label': f'{checkin.codigo} - {checkin.cliente.nome_razao_social}',
                'value': checkin.codigo or checkin.cliente.nome_razao_social,
                'subtitle': f'{checkin.ordem_servico.codigo} | {checkin.veiculo.placa} - {checkin.veiculo.marca} {checkin.veiculo.modelo}',
                'url': checkin.get_absolute_url(),
            })
        return JsonResponse({'results': results})


class VehicleCheckInPhotoFileView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'operations.view_vehiclecheckin'

    def get(self, request, pk, *args, **kwargs):
        import mimetypes

        photo = get_object_or_404(
            VehicleCheckInPhoto.objects.select_related('checkin'),
            pk=pk,
            checkin__ativo=True,
            checkin__excluido_em__isnull=True,
        )
        if not photo.imagem:
            raise Http404('Foto não encontrada.')
        content_type = mimetypes.guess_type(photo.imagem.name)[0] or 'application/octet-stream'
        response = FileResponse(photo.imagem.open('rb'), content_type=content_type, as_attachment=False)
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class VehicleCheckInDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = VehicleCheckIn
    template_name = 'operations/vehicle_checkin_detail.html'
    context_object_name = 'checkin'
    permission_required = 'operations.view_vehiclecheckin'

    def get_queryset(self):
        return VehicleCheckIn.objects.select_related('ordem_servico', 'cliente', 'veiculo', 'criado_por', 'email_enviado_por').prefetch_related('fotos')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_change'] = self.request.user.has_perm('operations.change_vehiclecheckin')
        context['can_delete'] = self.request.user.has_perm('operations.delete_vehiclecheckin')
        context['can_send_email'] = self.request.user.has_perm('operations.change_vehiclecheckin')
        return context


class VehicleCheckInCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, CreateView):
    model = VehicleCheckIn
    form_class = VehicleCheckInForm
    template_name = 'operations/vehicle_checkin_form.html'
    success_url = reverse_lazy('vehicle_checkin_list')
    permission_required = 'operations.add_vehiclecheckin'
    title = 'Novo check-in'

    def get_initial(self):
        initial = super().get_initial()
        ordem_servico = self.request.GET.get('ordem_servico')
        if ordem_servico and ordem_servico.isdigit():
            initial['ordem_servico'] = int(ordem_servico)
            try:
                order = WorkOrder.objects.get(pk=ordem_servico)
                if order.km_atual is not None:
                    initial['km'] = order.km_atual
            except WorkOrder.DoesNotExist:
                logger.warning('Tentativa de iniciar check-in com OS inexistente: %s.', ordem_servico)
        return initial

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.criado_por = self.request.user if self.request.user.is_authenticated else None
        self.object.save()
        form.save_photos(self.object)
        messages.success(self.request, 'Check-in cadastrado com sucesso.')
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível salvar o check-in. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class VehicleCheckInUpdateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = VehicleCheckIn
    form_class = VehicleCheckInForm
    template_name = 'operations/vehicle_checkin_form.html'
    success_url = reverse_lazy('vehicle_checkin_list')
    permission_required = 'operations.change_vehiclecheckin'
    title = 'Editar check-in'

    def get_queryset(self):
        return VehicleCheckIn.objects.select_related('ordem_servico', 'cliente', 'veiculo').prefetch_related('fotos')

    def form_valid(self, form):
        self.object = form.save()
        form.save_photos(self.object)
        messages.success(self.request, 'Check-in atualizado com sucesso.')
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível atualizar o check-in. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class VehicleCheckInDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, SoftDeleteMixin, DeleteView):
    model = VehicleCheckIn
    template_name = 'operations/confirm_delete.html'
    success_url = reverse_lazy('vehicle_checkin_list')
    permission_required = 'operations.delete_vehiclecheckin'
    title = 'Excluir check-in'
    delete_success_message = 'Check-in excluído com sucesso.'

    def get_queryset(self):
        return VehicleCheckIn.objects.filter(excluido_em__isnull=True)


class VehicleCheckInPdfView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = VehicleCheckIn
    permission_required = 'operations.view_vehiclecheckin'

    def get_queryset(self):
        return VehicleCheckIn.objects.select_related('ordem_servico', 'cliente', 'veiculo').prefetch_related('fotos')

    def get(self, request, *args, **kwargs):
        checkin = self.get_object()
        pdf_bytes = generate_vehicle_checkin_pdf(checkin)
        filename = f'{checkin.codigo or "checkin"}.pdf'
        return FileResponse(bytes_to_file(pdf_bytes), content_type='application/pdf', as_attachment=False, filename=filename)


class VehicleCheckInSendEmailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'operations.change_vehiclecheckin'

    def post(self, request, pk, *args, **kwargs):
        checkin = VehicleCheckIn.objects.select_related('ordem_servico', 'cliente', 'veiculo').prefetch_related('fotos').get(pk=pk)
        if not checkin.cliente.email:
            messages.error(request, 'O cliente não possui email cadastrado.')
            return redirect(checkin.get_absolute_url())

        try:
            pdf_bytes = generate_vehicle_checkin_pdf(checkin)
            subject = f'Check-in do veículo - {checkin.codigo}'
            body = (
                f'Olá, {checkin.cliente.nome_razao_social}.\n\n'
                f'Segue em anexo o PDF do check-in de recepção do veículo '
                f'{checkin.veiculo.placa} referente à {checkin.ordem_servico.codigo}.\n\n'
                'Atenciosamente,\nMotorMind'
            )
            email = EmailMessage(subject=subject, body=body, to=[checkin.cliente.email])
            email.attach(f'{checkin.codigo}.pdf', pdf_bytes, 'application/pdf')
            email.send(fail_silently=False)
            checkin.email_enviado = True
            checkin.email_enviado_em = timezone.now()
            checkin.email_enviado_por = request.user if request.user.is_authenticated else None
            checkin.email_erro = ''
            checkin.save(update_fields=['email_enviado', 'email_enviado_em', 'email_enviado_por', 'email_erro', 'atualizado_em'])
            messages.success(request, 'PDF do check-in enviado ao cliente por email.')
        except Exception as exc:
            checkin.email_enviado = False
            checkin.email_erro = str(exc)
            checkin.save(update_fields=['email_enviado', 'email_erro', 'atualizado_em'])
            messages.error(request, f'Erro ao enviar email do check-in: {exc}')
        return redirect(checkin.get_absolute_url())


def bytes_to_file(content):
    from io import BytesIO
    file_obj = BytesIO(content)
    file_obj.seek(0)
    return file_obj
