from django.contrib import admin

from .models import (
    Brand,
    InventoryItem,
    PurchaseOrder,
    PurchaseOrderItem,
    StockCategory,
    StockMovement,
    UnitOfMeasure,
)


@admin.register(StockCategory)
class StockCategoryAdmin(admin.ModelAdmin):
    list_display = ('nome', 'criado_em', 'atualizado_em')
    search_fields = ('nome', 'descricao')
    exclude = ('ativo', 'excluido_em')

    def get_queryset(self, request):
        return StockCategory.objects.filter(excluido_em__isnull=True)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('nome', 'criado_em', 'atualizado_em')
    search_fields = ('nome',)
    exclude = ('ativo', 'excluido_em')

    def get_queryset(self, request):
        return Brand.objects.filter(excluido_em__isnull=True)


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ('nome', 'sigla', 'permite_fracionado', 'ativo')
    list_filter = ('ativo', 'permite_fracionado')
    search_fields = ('nome', 'sigla')


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('sku', 'nome', 'tipo', 'categoria', 'marca', 'unidade', 'estoque_minimo', 'preco_custo')
    list_filter = ('tipo', 'categoria', 'marca', 'unidade')
    search_fields = ('sku', 'nome', 'descricao')
    readonly_fields = ('sku',)
    exclude = ('ativo', 'excluido_em')

    def get_queryset(self, request):
        return InventoryItem.objects.select_related('categoria', 'marca', 'unidade')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('criado_em', 'item', 'fornecedor', 'tipo', 'quantidade', 'saldo_apos_movimentacao', 'custo_unitario', 'valor_total', 'criado_por')
    list_filter = ('tipo', 'fornecedor', 'criado_em')
    search_fields = ('item__sku', 'item__nome', 'fornecedor__nome_razao_social', 'fornecedor__email', 'observacao')
    readonly_fields = ('quantidade_assinada', 'saldo_apos_movimentacao', 'valor_total', 'criado_em')


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1
    autocomplete_fields = ('item',)


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'status', 'origem', 'fornecedor', 'ordem_servico', 'valor_total', 'criado_em', 'recebido_em')
    list_filter = ('status', 'origem', 'fornecedor', 'criado_em', 'recebido_em')
    search_fields = ('codigo', 'fornecedor__nome_razao_social', 'ordem_servico__codigo', 'itens__item__sku', 'itens__item__nome')
    readonly_fields = ('codigo', 'origem', 'ordem_servico', 'criado_por', 'recebido_por', 'recebido_em', 'criado_em', 'atualizado_em')
    inlines = (PurchaseOrderItemInline,)
    exclude = ('ativo', 'excluido_em')

    def get_queryset(self, request):
        return PurchaseOrder.objects.select_related('fornecedor', 'ordem_servico', 'criado_por', 'recebido_por').prefetch_related('itens')
