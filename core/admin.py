from django.contrib import admin

from .models import Category, Customer, Supplier, Vehicle


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('nome', 'aplicacao', 'excluido_em', 'criado_em')
    list_filter = ('aplicacao', 'excluido_em')
    search_fields = ('nome',)
    readonly_fields = ('criado_em', 'atualizado_em', 'excluido_em')
    exclude = ('ativa',)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        'nome_razao_social',
        'tipo_pessoa',
        'documento',
        'data_nascimento_fundacao',
        'email',
        'whatsapp',
        'cidade',
        'uf',
        'ativo',
        'excluido_em',
    )
    list_filter = ('tipo_pessoa', 'ativo', 'aceita_marketing', 'cidade', 'uf', 'categorias')
    search_fields = ('nome_razao_social', 'documento', 'email', 'whatsapp')
    filter_horizontal = ('categorias',)
    readonly_fields = ('criado_em', 'atualizado_em', 'excluido_em')

    def get_queryset(self, request):
        return Customer.all_objects.prefetch_related('categorias')


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = (
        'nome_razao_social',
        'tipo_pessoa',
        'documento',
        'data_nascimento_fundacao',
        'email',
        'whatsapp',
        'cidade',
        'uf',
        'ativo',
        'excluido_em',
    )
    list_filter = ('tipo_pessoa', 'ativo', 'aceita_marketing', 'cidade', 'uf', 'categorias')
    search_fields = ('nome_razao_social', 'documento', 'email', 'whatsapp')
    filter_horizontal = ('categorias',)
    readonly_fields = ('criado_em', 'atualizado_em', 'excluido_em')

    def get_queryset(self, request):
        return Supplier.all_objects.prefetch_related('categorias')


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        'placa',
        'cliente',
        'marca',
        'modelo',
        'versao',
        'combustivel',
        'km',
        'ativo',
        'excluido_em',
    )
    list_filter = ('fipe_tipo', 'combustivel', 'tipo_direcao', 'ar_condicionado', 'modificado', 'ativo', 'excluido_em')
    search_fields = ('placa', 'cliente__nome_razao_social', 'marca', 'modelo', 'versao', 'chassi', 'codigo_fipe')
    readonly_fields = ('criado_em', 'atualizado_em', 'excluido_em')

    def get_queryset(self, request):
        return Vehicle.all_objects.select_related('cliente')
