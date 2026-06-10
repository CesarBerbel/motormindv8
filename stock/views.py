from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import BooleanField, Case, F, IntegerField, Q, Sum, Value, When
from django.db.models.functions import Coalesce, Lower
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView, View

from core.models import Supplier, only_digits
from core.money import format_money_br, normalize_money
from core.views import FormTitleMixin, SoftDeleteMixin

from .forms import BrandForm, InventoryItemForm, InventoryXmlImportItemFormSet, InventoryXmlImportOptionsForm, InventoryXmlUploadForm, PurchaseOrderForm, PurchaseOrderItemFormSet, StockCategoryForm, StockMovementForm
from .models import (
    Brand,
    InventoryItem,
    InventoryItemType,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderSource,
    PurchaseOrderStatus,
    StockCategory,
    StockMovement,
    StockMovementType,
    UnitOfMeasure,
    ZERO_QUANTITY,
)

from .services.xml_inventory_import import InventoryXmlImportError, parse_inventory_xml_upload


class SearchContextMixin:
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


class InventoryItemSearchMixin(SearchContextMixin):
    search_param_names = (
        'q',
        'tipo',
        'categoria',
        'marca',
        'estoque',
        'custo_min',
        'custo_max',
    )
    stock_status_choices = (
        ('com_estoque', 'Com estoque'),
        ('zerado', 'Estoque zerado'),
        ('sem_estoque', 'Sem estoque ou negativo'),
        ('abaixo_minimo', 'Abaixo do estoque mínimo'),
        ('acima_minimo', 'Dentro/acima do estoque mínimo'),
    )

    def parse_money_filter(self, value):
        if not value:
            return None
        try:
            return normalize_money(value)
        except Exception:
            return None

    def annotate_stock_balance(self, queryset):
        quantity_output = IntegerField()
        return queryset.annotate(
            saldo_atual=Coalesce(
                Sum('movimentacoes__quantidade_assinada'),
                Value(ZERO_QUANTITY),
                output_field=quantity_output,
            )
        ).annotate(
            estoque_abaixo_minimo=Case(
                When(saldo_atual__lt=F('estoque_minimo'), then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            )
        )

    def build_item_search_q(self, term):
        return (
            Q(sku__icontains=term)
            | Q(nome__icontains=term)
            | Q(descricao__icontains=term)
            | Q(categoria__nome__icontains=term)
            | Q(marca__nome__icontains=term)
        )

    def apply_inventory_filters(self, queryset):
        filters = self.get_search_filters()
        term = filters['q']

        queryset = self.annotate_stock_balance(queryset)

        if term:
            queryset = queryset.filter(self.build_item_search_q(term))

        if filters['tipo'] in dict(InventoryItemType.choices):
            queryset = queryset.filter(tipo=filters['tipo'])

        if filters['categoria'].isdigit():
            queryset = queryset.filter(categoria_id=int(filters['categoria']))

        if filters['marca'].isdigit():
            queryset = queryset.filter(marca_id=int(filters['marca']))


        custo_min = self.parse_money_filter(filters['custo_min'])
        custo_max = self.parse_money_filter(filters['custo_max'])

        if custo_min is not None:
            queryset = queryset.filter(preco_custo__gte=custo_min)

        if custo_max is not None:
            queryset = queryset.filter(preco_custo__lte=custo_max)

        if filters['estoque'] == 'com_estoque':
            queryset = queryset.filter(saldo_atual__gt=ZERO_QUANTITY)
        elif filters['estoque'] == 'zerado':
            queryset = queryset.filter(saldo_atual=ZERO_QUANTITY)
        elif filters['estoque'] == 'sem_estoque':
            queryset = queryset.filter(saldo_atual__lte=ZERO_QUANTITY)
        elif filters['estoque'] == 'abaixo_minimo':
            queryset = queryset.filter(saldo_atual__lt=F('estoque_minimo'))
        elif filters['estoque'] == 'acima_minimo':
            queryset = queryset.filter(saldo_atual__gte=F('estoque_minimo'))

        return queryset.distinct().order_by(Lower('nome'), 'pk')


class StockCategoryListView(LoginRequiredMixin, PermissionRequiredMixin, SearchContextMixin, ListView):
    model = StockCategory
    template_name = 'stock/stock_category_list.html'
    context_object_name = 'categories'
    paginate_by = 20
    permission_required = 'stock.view_stockcategory'

    def get_queryset(self):
        queryset = StockCategory.objects.filter(excluido_em__isnull=True)
        term = self.get_search_filters()['q']
        if term:
            queryset = queryset.filter(Q(nome__icontains=term) | Q(descricao__icontains=term))
        return queryset.order_by(Lower('nome'), 'pk')


class StockCategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, CreateView):
    model = StockCategory
    form_class = StockCategoryForm
    template_name = 'stock/object_form.html'
    success_url = reverse_lazy('stock_category_list')
    permission_required = 'stock.add_stockcategory'
    title = 'Nova categoria de estoque'

    def form_valid(self, form):
        messages.success(self.request, 'Categoria de estoque cadastrada com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível salvar a categoria de estoque.')
        return super().form_invalid(form)


class StockCategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = StockCategory
    form_class = StockCategoryForm
    template_name = 'stock/object_form.html'
    success_url = reverse_lazy('stock_category_list')
    permission_required = 'stock.change_stockcategory'
    title = 'Editar categoria de estoque'

    def get_queryset(self):
        return StockCategory.objects.filter(excluido_em__isnull=True)

    def form_valid(self, form):
        messages.success(self.request, 'Categoria de estoque atualizada com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível atualizar a categoria de estoque.')
        return super().form_invalid(form)


class StockCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, SoftDeleteMixin, DeleteView):
    model = StockCategory
    template_name = 'stock/confirm_delete.html'
    success_url = reverse_lazy('stock_category_list')
    permission_required = 'stock.delete_stockcategory'
    title = 'Excluir categoria de estoque'
    delete_success_message = 'Categoria de estoque excluída com sucesso.'

    def get_queryset(self):
        return StockCategory.objects.filter(excluido_em__isnull=True)


class BrandListView(LoginRequiredMixin, PermissionRequiredMixin, SearchContextMixin, ListView):
    model = Brand
    template_name = 'stock/brand_list.html'
    context_object_name = 'brands'
    paginate_by = 20
    permission_required = 'stock.view_brand'

    def get_queryset(self):
        queryset = Brand.objects.filter(excluido_em__isnull=True)
        term = self.get_search_filters()['q']
        if term:
            queryset = queryset.filter(nome__icontains=term)
        return queryset.order_by(Lower('nome'), 'pk')


class BrandCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, CreateView):
    model = Brand
    form_class = BrandForm
    template_name = 'stock/object_form.html'
    success_url = reverse_lazy('brand_list')
    permission_required = 'stock.add_brand'
    title = 'Nova marca'

    def form_valid(self, form):
        messages.success(self.request, 'Marca cadastrada com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível salvar a marca.')
        return super().form_invalid(form)


class BrandUpdateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = Brand
    form_class = BrandForm
    template_name = 'stock/object_form.html'
    success_url = reverse_lazy('brand_list')
    permission_required = 'stock.change_brand'
    title = 'Editar marca'

    def get_queryset(self):
        return Brand.objects.filter(excluido_em__isnull=True)

    def form_valid(self, form):
        messages.success(self.request, 'Marca atualizada com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível atualizar a marca.')
        return super().form_invalid(form)


class BrandDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, SoftDeleteMixin, DeleteView):
    model = Brand
    template_name = 'stock/confirm_delete.html'
    success_url = reverse_lazy('brand_list')
    permission_required = 'stock.delete_brand'
    title = 'Excluir marca'
    delete_success_message = 'Marca excluída com sucesso.'

    def get_queryset(self):
        return Brand.objects.filter(excluido_em__isnull=True)


class InventoryItemListView(LoginRequiredMixin, PermissionRequiredMixin, InventoryItemSearchMixin, ListView):
    model = InventoryItem
    template_name = 'stock/inventory_item_list.html'
    context_object_name = 'items'
    paginate_by = 20
    permission_required = 'stock.view_inventoryitem'

    def get_queryset(self):
        queryset = InventoryItem.objects.select_related('categoria', 'marca', 'unidade')
        return self.apply_inventory_filters(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category_choices'] = StockCategory.objects.order_by(Lower('nome'), 'pk')
        context['brand_choices'] = Brand.objects.order_by(Lower('nome'), 'pk')
        context['tipo_choices'] = InventoryItemType.choices
        context['stock_status_choices'] = self.stock_status_choices
        return context


class InventoryItemAutocompleteView(LoginRequiredMixin, PermissionRequiredMixin, InventoryItemSearchMixin, View):
    permission_required = 'stock.view_inventoryitem'
    limit = 10

    def get(self, request, *args, **kwargs):
        term = (request.GET.get('q') or '').strip()

        if len(term) < 2:
            return JsonResponse({'results': []})

        queryset = InventoryItem.objects.select_related('categoria', 'marca', 'unidade')
        queryset = self.annotate_stock_balance(queryset).filter(self.build_item_search_q(term)).distinct().order_by(Lower('nome'), 'pk')[: self.limit]

        results = []
        for item in queryset:
            brand_name = item.marca.nome if item.marca_id else 'Sem marca'
            subtitle_parts = [
                item.get_tipo_display(),
                item.categoria.nome,
                brand_name,
                f'Estoque: {item.saldo_atual} {item.unidade.sigla}',
                f'Custo: {format_money_br(item.preco_custo)}',
                f'Venda: {format_money_br(item.valor_venda)}',
            ]
            results.append({
                'id': item.pk,
                'label': f'{item.sku} - {item.nome}',
                'value': item.sku or item.nome,
                'subtitle': ' | '.join(part for part in subtitle_parts if part),
                'url': item.get_absolute_url(),
            })

        return JsonResponse({'results': results})


class InventoryItemDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = InventoryItem
    template_name = 'stock/inventory_item_detail.html'
    context_object_name = 'item'
    permission_required = 'stock.view_inventoryitem'

    def get_queryset(self):
        return InventoryItem.objects.select_related('categoria', 'marca', 'unidade')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['movements'] = self.object.movimentacoes.select_related('fornecedor', 'criado_por').order_by('-criado_em', '-pk')[:10]
        context['can_change'] = self.request.user.has_perm('stock.change_inventoryitem')
        context['can_delete'] = self.request.user.has_perm('stock.delete_inventoryitem')
        context['can_add_movement'] = self.request.user.has_perm('stock.add_stockmovement')
        return context


class InventoryItemCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, CreateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = 'stock/object_form.html'
    success_url = reverse_lazy('inventory_item_list')
    permission_required = 'stock.add_inventoryitem'
    title = 'Nova peça/insumo'

    def form_valid(self, form):
        messages.success(self.request, 'Peça/insumo cadastrado com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível salvar a peça/insumo. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class InventoryItemUpdateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = 'stock/object_form.html'
    success_url = reverse_lazy('inventory_item_list')
    permission_required = 'stock.change_inventoryitem'
    title = 'Editar peça/insumo'

    def get_queryset(self):
        return InventoryItem.objects.select_related('categoria', 'marca', 'unidade')

    def form_valid(self, form):
        messages.success(self.request, 'Peça/insumo atualizado com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível atualizar a peça/insumo. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class InventoryItemDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, SoftDeleteMixin, DeleteView):
    model = InventoryItem
    template_name = 'stock/confirm_delete.html'
    success_url = reverse_lazy('inventory_item_list')
    permission_required = 'stock.delete_inventoryitem'
    title = 'Excluir peça/insumo'
    delete_success_message = 'Peça/insumo excluído com sucesso.'

    def get_queryset(self):
        return InventoryItem.objects.all()


def _find_supplier_by_document(documento):
    digits = only_digits(documento or '')
    if not digits:
        return None

    for supplier in Supplier.objects.exclude(documento__isnull=True).exclude(documento=''):
        if only_digits(supplier.documento) == digits:
            return supplier

    return None


def _default_import_category():
    category, _ = StockCategory.objects.get_or_create(
        nome='Importado XML',
        defaults={'descricao': 'Categoria criada automaticamente para itens importados por XML de NF-e.'},
    )
    return category


def _first_active_unit():
    return (
        UnitOfMeasure.objects.filter(ativo=True, sigla__iexact='UN').first()
        or UnitOfMeasure.objects.filter(ativo=True).order_by(Lower('nome'), 'pk').first()
    )


def _unit_by_xml_sigla(sigla):
    normalized = (sigla or 'UN').strip()
    return (
        UnitOfMeasure.objects.filter(ativo=True, sigla__iexact=normalized).first()
        or _first_active_unit()
    )


class InventoryItemXmlImportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    template_name = 'stock/inventory_item_xml_import.html'
    permission_required = 'stock.add_inventoryitem'
    formset_prefix = 'items'

    def get(self, request, *args, **kwargs):
        return self.render_upload(request, upload_form=InventoryXmlUploadForm())

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')

        if action == 'preview':
            return self.preview(request)

        if action == 'import':
            return self.import_items(request)

        messages.error(request, 'Ação de importação inválida.')
        return redirect('inventory_item_import_xml')

    def render_upload(self, request, **context):
        context.setdefault('upload_form', InventoryXmlUploadForm())
        context.setdefault('mapping_rows', self.mapping_rows())
        return render(request, self.template_name, context)

    def mapping_rows(self):
        return [
            ('cProd', 'Código da peça/SKU', 'Preenche o código da peça. O usuário pode editar antes de importar.'),
            ('cEAN / cEANTrib', 'Código alternativo/EAN', 'Usado como fallback quando o cProd não vem preenchido.'),
            ('xProd', 'Nome e descrição', 'Preenche o nome do item e compõe a descrição.'),
            ('uCom / uTrib', 'Unidade', 'Tenta encontrar a unidade cadastrada pela sigla; se não encontrar, usa UN.'),
            ('qCom / qTrib', 'Quantidade', 'Pode registrar entrada de estoque quando um fornecedor é selecionado.'),
            ('vUnCom / vUnTrib', 'Preço de custo', 'Preenche o custo unitário do item.'),
            ('vProd', 'Valor total XML', 'Exibido como referência na prévia.'),
            ('NCM / CEST / CFOP', 'Descrição', 'Guardados na descrição para rastreabilidade fiscal.'),
            ('emit/CNPJ e emit/xNome', 'Fornecedor', 'Tenta localizar fornecedor já cadastrado pelo CNPJ.'),
        ]

    def preview(self, request):
        upload_form = InventoryXmlUploadForm(request.POST, request.FILES)
        if not upload_form.is_valid():
            messages.error(request, 'Não foi possível ler o arquivo. Confira o XML/ZIP enviado.')
            return self.render_upload(request, upload_form=upload_form)

        try:
            documents = parse_inventory_xml_upload(upload_form.cleaned_data['arquivo'])
        except InventoryXmlImportError as exc:
            messages.error(request, str(exc))
            return self.render_upload(request, upload_form=upload_form)

        rows = self.build_initial_rows(documents)
        if not rows:
            messages.error(request, 'Nenhum produto foi encontrado nos XMLs enviados.')
            return self.render_upload(request, upload_form=upload_form)

        supplier = self.guess_supplier(documents)
        payload = signing.dumps({
            'documents': [document.to_dict() for document in documents],
            'rows_count': len(rows),
        })

        return self.render_upload(
            request,
            upload_form=InventoryXmlUploadForm(),
            options_form=InventoryXmlImportOptionsForm(fornecedor_initial=supplier),
            formset=InventoryXmlImportItemFormSet(initial=rows, prefix=self.formset_prefix),
            preview=True,
            payload=payload,
            parsed_documents=documents,
            total_rows=len(rows),
        )

    def build_initial_rows(self, documents):
        rows = []
        for document in documents:
            for produto in document.produtos:
                unit = _unit_by_xml_sigla(produto.unidade_sigla)
                existing = InventoryItem.objects.filter(sku__iexact=produto.codigo).first() if produto.codigo else None
                rows.append({
                    'line_id': f'{produto.document_index}:{produto.line_index}',
                    'xml_codigo': produto.codigo,
                    'xml_ean': produto.codigo_barras,
                    'xml_ncm': produto.ncm,
                    'xml_cfop': produto.cfop,
                    'xml_unidade': produto.unidade_sigla,
                    'quantidade_original': produto.quantidade_original,
                    'importar': True,
                    'sku': existing.sku if existing else produto.codigo,
                    'nome': existing.nome if existing else produto.nome,
                    'tipo': existing.tipo if existing else produto.tipo_sugerido,
                    'categoria': existing.categoria_id if existing else None,
                    'marca': existing.marca_id if existing else None,
                    'unidade': existing.unidade_id if existing else (unit.pk if unit else None),
                    'estoque_minimo': existing.estoque_minimo if existing else ZERO_QUANTITY,
                    'quantidade': produto.quantidade,
                    'preco_custo': existing.preco_custo if existing else produto.preco_unitario,
                    'preco_venda': existing.preco_venda if existing else produto.preco_unitario,
                    'descricao': existing.descricao if existing else produto.descricao,
                })
        return rows

    def guess_supplier(self, documents):
        for document in documents:
            supplier = _find_supplier_by_document(document.fornecedor.documento)
            if supplier:
                return supplier
        return None

    def import_items(self, request):
        payload = request.POST.get('payload') or ''
        try:
            signing.loads(payload, max_age=60 * 60)
        except signing.BadSignature:
            messages.error(request, 'A prévia da importação expirou ou foi alterada. Envie o XML novamente.')
            return redirect('inventory_item_import_xml')

        options_form = InventoryXmlImportOptionsForm(request.POST)
        formset = InventoryXmlImportItemFormSet(request.POST, prefix=self.formset_prefix)

        if not options_form.is_valid() or not formset.is_valid():
            messages.error(request, 'Revise os campos marcados antes de concluir a importação.')
            return self.render_upload(
                request,
                upload_form=InventoryXmlUploadForm(),
                options_form=options_form,
                formset=formset,
                preview=True,
                payload=payload,
                total_rows=formset.total_form_count(),
            )

        stats = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'movements': 0,
            'errors': [],
        }

        fornecedor = options_form.cleaned_data.get('fornecedor')
        registrar_entrada = options_form.cleaned_data.get('registrar_entrada')
        atualizar_existentes = options_form.cleaned_data.get('atualizar_existentes')

        for index, form in enumerate(formset.forms, start=1):
            data = form.cleaned_data
            if not data.get('importar'):
                stats['skipped'] += 1
                continue

            try:
                item, created = self.create_or_update_item(data, atualizar_existentes)
                if item is None:
                    stats['skipped'] += 1
                    continue

                if created:
                    stats['created'] += 1
                else:
                    stats['updated'] += 1

                if registrar_entrada and fornecedor and data.get('quantidade', 0) > 0:
                    self.create_stock_entry(item, fornecedor, data, request.user)
                    stats['movements'] += 1
            except (ValidationError, IntegrityError) as exc:
                stats['errors'].append(f'Linha {index}: {exc}')
                continue

        self.add_result_messages(request, stats)
        return redirect('inventory_item_list')

    def create_or_update_item(self, data, atualizar_existentes):
        sku = data.get('sku')
        category = data.get('categoria') or _default_import_category()
        brand = data.get('marca')

        item = None
        if sku:
            item = InventoryItem.objects.filter(sku__iexact=sku).first()

        if item is None:
            item = InventoryItem.objects.filter(
                nome__iexact=data['nome'],
                categoria=category,
                marca=brand,
            ).first()

        if item is not None and not atualizar_existentes:
            return None, False

        created = item is None
        if created:
            item = InventoryItem()

        item.sku = sku or item.sku
        item.tipo = data['tipo']
        item.nome = data['nome']
        item.descricao = data.get('descricao') or ''
        item.categoria = category
        item.marca = brand
        item.estoque_minimo = data.get('estoque_minimo') or ZERO_QUANTITY
        item.unidade = data['unidade']
        item.preco_custo = data.get('preco_custo') or 0
        item.preco_venda = data.get('preco_venda') or 0

        with transaction.atomic():
            item.full_clean()
            item.save()

        return item, created

    def create_stock_entry(self, item, fornecedor, data, user):
        movement = StockMovement(
            item=item,
            fornecedor=fornecedor,
            tipo=StockMovementType.ENTRADA,
            quantidade=data['quantidade'],
            custo_unitario=data.get('preco_custo') or item.preco_custo,
            observacao=(
                'Entrada automática por importação XML'
                f' | Código XML: {data.get("xml_codigo") or "-"}'
                f' | NCM: {data.get("xml_ncm") or "-"}'
                f' | CFOP: {data.get("xml_cfop") or "-"}'
            ),
            criado_por=user if getattr(user, 'is_authenticated', False) else None,
        )
        with transaction.atomic():
            movement.full_clean()
            movement.save()
        return movement

    def add_result_messages(self, request, stats):
        messages.success(
            request,
            (
                'Importação XML concluída: '
                f'{stats["created"]} criado(s), '
                f'{stats["updated"]} atualizado(s), '
                f'{stats["skipped"]} ignorado(s), '
                f'{stats["movements"]} entrada(s) de estoque.'
            ),
        )

        if stats['errors']:
            preview = ' '.join(stats['errors'][:5])
            if len(stats['errors']) > 5:
                preview += f' Mais {len(stats["errors"]) - 5} erro(s) não exibido(s).'
            messages.warning(request, f'Alguns itens não foram importados. {preview}')


class StockMovementSearchMixin(SearchContextMixin):
    search_param_names = (
        'q',
        'tipo',
        'item',
        'fornecedor',
        'usuario',
        'data_inicio',
        'data_fim',
        'quantidade_min',
        'quantidade_max',
        'custo_min',
        'custo_max',
        'total_min',
        'total_max',
    )

    def parse_integer_filter(self, value):
        if not value:
            return None

        text = str(value).strip().replace(' ', '')
        if not text.isdigit():
            return None

        try:
            return int(text)
        except (TypeError, ValueError):
            return None

    def parse_money_filter(self, value):
        if not value:
            return None
        try:
            return normalize_money(value)
        except Exception:
            return None

    def build_movement_search_q(self, term):
        return (
            Q(item__sku__icontains=term)
            | Q(item__nome__icontains=term)
            | Q(item__descricao__icontains=term)
            | Q(item__categoria__nome__icontains=term)
            | Q(item__marca__nome__icontains=term)
            | Q(item__unidade__nome__icontains=term)
            | Q(item__unidade__sigla__icontains=term)
            | Q(fornecedor__nome_razao_social__icontains=term)
            | Q(fornecedor__email__icontains=term)
            | Q(fornecedor__whatsapp__icontains=term)
            | Q(fornecedor__documento__icontains=term)
            | Q(fornecedor__cidade__icontains=term)
            | Q(criado_por__email__icontains=term)
            | Q(observacao__icontains=term)
        )

    def apply_movement_filters(self, queryset):
        filters = self.get_search_filters()
        term = filters['q']

        if term:
            queryset = queryset.filter(self.build_movement_search_q(term))

        if filters['tipo'] in dict(StockMovementType.choices):
            queryset = queryset.filter(tipo=filters['tipo'])

        if filters['item'].isdigit():
            queryset = queryset.filter(item_id=int(filters['item']))

        if filters['fornecedor'].isdigit():
            queryset = queryset.filter(fornecedor_id=int(filters['fornecedor']))

        if filters['usuario'].isdigit():
            queryset = queryset.filter(criado_por_id=int(filters['usuario']))

        data_inicio = parse_date(filters['data_inicio'])
        data_fim = parse_date(filters['data_fim'])

        if data_inicio:
            queryset = queryset.filter(criado_em__date__gte=data_inicio)

        if data_fim:
            queryset = queryset.filter(criado_em__date__lte=data_fim)

        quantidade_min = self.parse_integer_filter(filters['quantidade_min'])
        quantidade_max = self.parse_integer_filter(filters['quantidade_max'])

        if quantidade_min is not None:
            queryset = queryset.filter(quantidade__gte=quantidade_min)

        if quantidade_max is not None:
            queryset = queryset.filter(quantidade__lte=quantidade_max)

        custo_min = self.parse_money_filter(filters['custo_min'])
        custo_max = self.parse_money_filter(filters['custo_max'])
        total_min = self.parse_money_filter(filters['total_min'])
        total_max = self.parse_money_filter(filters['total_max'])

        if custo_min is not None:
            queryset = queryset.filter(custo_unitario__gte=custo_min)

        if custo_max is not None:
            queryset = queryset.filter(custo_unitario__lte=custo_max)

        if total_min is not None:
            queryset = queryset.filter(valor_total__gte=total_min)

        if total_max is not None:
            queryset = queryset.filter(valor_total__lte=total_max)

        return queryset.distinct().order_by('-criado_em', '-pk')


class StockMovementListView(LoginRequiredMixin, PermissionRequiredMixin, StockMovementSearchMixin, ListView):
    model = StockMovement
    template_name = 'stock/stock_movement_list.html'
    context_object_name = 'movements'
    paginate_by = 20
    permission_required = 'stock.view_stockmovement'

    def get_queryset(self):
        queryset = StockMovement.objects.select_related(
            'item',
            'item__categoria',
            'item__marca',
            'item__unidade',
            'fornecedor',
            'criado_por',
        )
        return self.apply_movement_filters(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        UserModel = get_user_model()
        context['item_choices'] = InventoryItem.objects.select_related('unidade').order_by(Lower('nome'), 'pk')
        context['supplier_choices'] = Supplier.objects.order_by(Lower('nome_razao_social'), 'pk')
        context['user_choices'] = UserModel.objects.filter(movimentacoes_estoque__isnull=False).distinct().order_by(Lower('email'), 'pk')
        context['movement_type_choices'] = StockMovementType.choices
        return context


class StockMovementAutocompleteView(LoginRequiredMixin, PermissionRequiredMixin, StockMovementSearchMixin, View):
    permission_required = 'stock.view_stockmovement'
    limit = 10

    def get(self, request, *args, **kwargs):
        term = (request.GET.get('q') or '').strip()

        if len(term) < 2:
            return JsonResponse({'results': []})

        queryset = StockMovement.objects.select_related(
            'item',
            'item__unidade',
            'fornecedor',
            'criado_por',
        ).filter(self.build_movement_search_q(term)).distinct().order_by('-criado_em', '-pk')[: self.limit]

        results = []
        for movement in queryset:
            fornecedor_nome = movement.fornecedor.nome_razao_social if movement.fornecedor_id else 'Sem fornecedor'
            subtitle_parts = [
                movement.get_tipo_display(),
                f'Fornecedor: {fornecedor_nome}',
                f'Qtd: {movement.quantidade_assinada} {movement.item.unidade.sigla}',
                f'Total: {format_money_br(movement.valor_total)}',
                movement.criado_em.strftime('%d/%m/%Y %H:%M'),
            ]
            results.append({
                'id': movement.pk,
                'label': f'{movement.item.sku} - {movement.item.nome}',
                'value': movement.item.sku or movement.item.nome,
                'subtitle': ' | '.join(part for part in subtitle_parts if part),
                'url': movement.get_absolute_url(),
            })

        return JsonResponse({'results': results})


class StockMovementDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = StockMovement
    template_name = 'stock/stock_movement_detail.html'
    context_object_name = 'movement'
    permission_required = 'stock.view_stockmovement'

    def get_queryset(self):
        return StockMovement.objects.select_related('item', 'item__unidade', 'fornecedor', 'criado_por')


class StockMovementCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, CreateView):
    model = StockMovement
    form_class = StockMovementForm
    template_name = 'stock/object_form.html'
    success_url = reverse_lazy('stock_movement_list')
    permission_required = 'stock.add_stockmovement'
    title = 'Nova movimentação de estoque'

    def get_initial(self):
        initial = super().get_initial()
        item_id = self.request.GET.get('item')
        if item_id and item_id.isdigit():
            initial['item'] = int(item_id)
        return initial

    def form_valid(self, form):
        form.instance.criado_por = self.request.user
        messages.success(self.request, 'Movimentação de estoque registrada com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível registrar a movimentação. Confira os alertas do formulário.')
        return super().form_invalid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class PurchaseOrderSearchMixin(SearchContextMixin):
    search_param_names = (
        'q',
        'status',
        'origem',
        'fornecedor',
        'data_inicio',
        'data_fim',
    )

    def build_purchase_order_search_q(self, term):
        return (
            Q(codigo__icontains=term)
            | Q(fornecedor__nome_razao_social__icontains=term)
            | Q(fornecedor__email__icontains=term)
            | Q(ordem_servico__codigo__icontains=term)
            | Q(ordem_servico__cliente__nome_razao_social__icontains=term)
            | Q(itens__item__sku__icontains=term)
            | Q(itens__item__nome__icontains=term)
            | Q(observacao__icontains=term)
        )

    def apply_purchase_order_filters(self, queryset):
        filters = self.get_search_filters()
        term = filters['q']

        if term:
            queryset = queryset.filter(self.build_purchase_order_search_q(term))

        if filters['status'] in dict(PurchaseOrderStatus.choices):
            queryset = queryset.filter(status=filters['status'])

        if filters['origem'] in dict(PurchaseOrderSource.choices):
            queryset = queryset.filter(origem=filters['origem'])

        if filters['fornecedor'].isdigit():
            queryset = queryset.filter(fornecedor_id=int(filters['fornecedor']))

        data_inicio = parse_date(filters['data_inicio'])
        data_fim = parse_date(filters['data_fim'])

        if data_inicio:
            queryset = queryset.filter(criado_em__date__gte=data_inicio)

        if data_fim:
            queryset = queryset.filter(criado_em__date__lte=data_fim)

        return queryset.distinct().order_by('-criado_em', '-pk')


class PurchaseOrderListView(LoginRequiredMixin, PermissionRequiredMixin, PurchaseOrderSearchMixin, ListView):
    model = PurchaseOrder
    template_name = 'stock/purchase_order_list.html'
    context_object_name = 'orders'
    paginate_by = 20
    permission_required = 'stock.view_purchaseorder'

    def get_queryset(self):
        queryset = PurchaseOrder.objects.select_related('fornecedor', 'ordem_servico', 'criado_por').prefetch_related('itens')
        return self.apply_purchase_order_filters(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = PurchaseOrderStatus.choices
        context['source_choices'] = PurchaseOrderSource.choices
        context['supplier_choices'] = Supplier.objects.order_by(Lower('nome_razao_social'), 'pk')
        return context


class PurchaseOrderAutocompleteView(LoginRequiredMixin, PermissionRequiredMixin, PurchaseOrderSearchMixin, View):
    permission_required = 'stock.view_purchaseorder'
    limit = 10

    def get(self, request, *args, **kwargs):
        term = (request.GET.get('q') or '').strip()
        if len(term) < 2:
            return JsonResponse({'results': []})

        queryset = PurchaseOrder.objects.select_related('fornecedor', 'ordem_servico').filter(
            self.build_purchase_order_search_q(term)
        ).distinct().order_by('-criado_em', '-pk')[: self.limit]

        results = []
        for order in queryset:
            subtitle_parts = [
                order.get_status_display(),
                order.get_origem_display(),
                f'Fornecedor: {order.fornecedor.nome_razao_social}' if order.fornecedor_id else 'Sem fornecedor',
                f'OS: {order.ordem_servico.codigo}' if order.ordem_servico_id else '',
                f'Total: {format_money_br(order.valor_total)}',
            ]
            results.append({
                'id': order.pk,
                'label': order.codigo or f'Pedido #{order.pk}',
                'value': order.codigo or '',
                'subtitle': ' | '.join(part for part in subtitle_parts if part),
                'url': order.get_absolute_url(),
            })
        return JsonResponse({'results': results})


class PurchaseOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = 'stock/purchase_order_detail.html'
    context_object_name = 'order'
    permission_required = 'stock.view_purchaseorder'

    def get_queryset(self):
        return PurchaseOrder.objects.select_related('fornecedor', 'ordem_servico', 'criado_por', 'recebido_por').prefetch_related(
            'itens__item__unidade',
            'itens__item__categoria',
            'itens__item__marca',
        )


class PurchaseOrderFormSetMixin:
    formset_class = PurchaseOrderItemFormSet

    def get_formset(self):
        if self.request.method == 'POST':
            return self.formset_class(self.request.POST, instance=self.object)
        return self.formset_class(instance=self.object)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'formset' not in context:
            context['formset'] = self.get_formset()
        return context

    def form_valid(self, form):
        formset = self.get_formset()
        if not formset.is_valid():
            messages.error(self.request, 'Não foi possível salvar o pedido. Confira os itens informados.')
            return self.render_to_response(self.get_context_data(form=form, formset=formset))

        if self.object is None:
            form.instance.criado_por = self.request.user
            form.instance.origem = PurchaseOrderSource.MANUAL

        self.object = form.save()
        formset.instance = self.object
        formset.save()
        messages.success(self.request, self.success_message)
        return redirect(self.get_success_url())


class PurchaseOrderCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, PurchaseOrderFormSetMixin, CreateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'stock/purchase_order_form.html'
    success_url = reverse_lazy('purchase_order_list')
    permission_required = 'stock.add_purchaseorder'
    title = 'Novo pedido de compra'
    success_message = 'Pedido de compra cadastrado com sucesso.'

    def get_initial(self):
        initial = super().get_initial()
        fornecedor_id = self.request.GET.get('fornecedor')
        if fornecedor_id and fornecedor_id.isdigit():
            initial['fornecedor'] = int(fornecedor_id)
        return initial

    def get_success_url(self):
        return self.object.get_absolute_url()


class PurchaseOrderUpdateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, PurchaseOrderFormSetMixin, UpdateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'stock/purchase_order_form.html'
    success_url = reverse_lazy('purchase_order_list')
    permission_required = 'stock.change_purchaseorder'
    title = 'Editar pedido de compra'
    success_message = 'Pedido de compra atualizado com sucesso.'

    def get_queryset(self):
        return PurchaseOrder.objects.select_related('fornecedor', 'ordem_servico')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.is_editable:
            messages.error(request, 'Pedido recebido ou cancelado não pode ser editado.')
            return redirect(self.object.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return self.object.get_absolute_url()


class PurchaseOrderDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, SoftDeleteMixin, DeleteView):
    model = PurchaseOrder
    template_name = 'stock/confirm_delete.html'
    success_url = reverse_lazy('purchase_order_list')
    permission_required = 'stock.delete_purchaseorder'
    title = 'Excluir pedido de compra'
    delete_success_message = 'Pedido de compra excluído com sucesso.'

    def get_queryset(self):
        return PurchaseOrder.objects.all()


class PurchaseOrderReceiveView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'stock.change_purchaseorder'

    def post(self, request, pk, *args, **kwargs):
        order = get_object_or_404(PurchaseOrder.objects.prefetch_related('itens__item'), pk=pk)
        try:
            movements = order.receber(user=request.user)
        except ValidationError as exc:
            message = '; '.join(exc.messages) if hasattr(exc, 'messages') else str(exc)
            messages.error(request, message)
            return redirect(order.get_absolute_url())

        messages.success(request, f'Pedido recebido com sucesso. {len(movements)} entrada(s) registrada(s) no estoque.')
        return redirect(order.get_absolute_url())
