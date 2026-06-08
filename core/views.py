from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import json

from django.conf import settings as dj_settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.cache import cache
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView, View

from .forms import CategoryForm, CustomerForm, SupplierForm, VehicleForm, format_cep, format_cnpj, format_cpf, format_phone
from .models import (
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


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'


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
        cliente = self.request.GET.get('cliente')
        if cliente and cliente.isdigit():
            initial['cliente'] = int(cliente)
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
