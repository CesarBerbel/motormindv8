from django.contrib import admin

from .models import (
    Service,
    ServiceCategory,
    ServiceCombo,
    ServiceComboItem,
    ServiceDefaultPart,
    WorkOrder,
    WorkOrderApprovalAudit,
    WorkOrderApprovalBudget,
    WorkOrderApprovalBudgetItem,
    WorkOrderSettings,
    WorkOrderStatusTransition,
    WorkOrderStockRequirementOverride,
    CustomerVehicleAccessToken,
    WorkOrderComboItem,
    WorkOrderPartItem,
    WorkOrderServiceItem,
    VehicleCheckIn,
    VehicleCheckInPhoto,
)



@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('nome', 'descricao', 'criado_em', 'atualizado_em')
    search_fields = ('nome', 'descricao')
    exclude = ('ativo', 'excluido_em')


class ServiceDefaultPartInline(admin.TabularInline):
    model = ServiceDefaultPart
    extra = 1
    autocomplete_fields = ('item',)
    fields = ('item', 'quantidade', 'obrigatoria', 'observacao')


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'categoria', 'duracao_minutos', 'valor', 'custo', 'criado_em', 'atualizado_em')
    list_filter = ('categoria',)
    search_fields = ('codigo', 'nome', 'categoria__nome', 'descricao', 'pecas_associadas__item__sku', 'pecas_associadas__item__nome')
    readonly_fields = ('codigo',)
    exclude = ('ativo', 'excluido_em')
    inlines = [ServiceDefaultPartInline]

    def get_queryset(self, request):
        return Service.objects.select_related('categoria').prefetch_related('pecas_associadas__item')


@admin.register(ServiceDefaultPart)
class ServiceDefaultPartAdmin(admin.ModelAdmin):
    list_display = ('service', 'item', 'quantidade', 'obrigatoria', 'observacao')
    list_filter = ('obrigatoria',)
    search_fields = ('service__codigo', 'service__nome', 'item__sku', 'item__nome', 'observacao')
    autocomplete_fields = ('service', 'item')


class ServiceComboItemInline(admin.TabularInline):
    model = ServiceComboItem
    extra = 1
    autocomplete_fields = ('service',)


@admin.register(ServiceCombo)
class ServiceComboAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'desconto_percentual', 'criado_em', 'atualizado_em')
    search_fields = ('codigo', 'nome', 'descricao', 'servicos_associados__service__codigo', 'servicos_associados__service__nome')
    readonly_fields = ('codigo',)
    exclude = ('ativo', 'excluido_em')
    inlines = [ServiceComboItemInline]

    def get_queryset(self, request):
        return ServiceCombo.objects.prefetch_related('servicos_associados__service')


@admin.register(ServiceComboItem)
class ServiceComboItemAdmin(admin.ModelAdmin):
    list_display = ('combo', 'service')
    search_fields = ('combo__codigo', 'combo__nome', 'service__codigo', 'service__nome')
    autocomplete_fields = ('combo', 'service')


class WorkOrderApprovalBudgetItemInline(admin.TabularInline):
    model = WorkOrderApprovalBudgetItem
    extra = 0
    readonly_fields = ('parent', 'tipo', 'referencia_id', 'codigo', 'nome', 'quantidade', 'quantidade_base', 'valor_unitario', 'subtotal', 'peca_obrigatoria', 'hierarquia_ordem', 'aprovado', 'respondido_em')
    can_delete = False


class WorkOrderApprovalAuditInline(admin.TabularInline):
    model = WorkOrderApprovalAudit
    extra = 0
    readonly_fields = ('decisao', 'metodo', 'nome_responsavel', 'documento', 'documento_valido', 'ip', 'user_agent', 'local', 'usuario_interno', 'criado_em')
    can_delete = False


@admin.register(WorkOrderApprovalBudget)
class WorkOrderApprovalBudgetAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'ordem_servico', 'versao', 'status', 'valor_total_snapshot', 'email_enviado', 'enviado_em', 'criado_em')
    list_filter = ('status', 'email_enviado', 'criado_em', 'enviado_em')
    search_fields = ('ordem_servico__codigo', 'ordem_servico__cliente__nome_razao_social', 'token')
    autocomplete_fields = ('ordem_servico', 'criado_por', 'enviado_por')
    readonly_fields = ('token', 'snapshot', 'subtotal_snapshot', 'valor_desconto_snapshot', 'valor_total_snapshot', 'criado_em', 'atualizado_em')
    inlines = [WorkOrderApprovalBudgetItemInline, WorkOrderApprovalAuditInline]


@admin.register(WorkOrderApprovalBudgetItem)
class WorkOrderApprovalBudgetItemAdmin(admin.ModelAdmin):
    list_display = ('orcamento', 'parent', 'tipo', 'codigo', 'nome', 'quantidade', 'peca_obrigatoria', 'valor_unitario', 'subtotal', 'aprovado')
    list_filter = ('tipo', 'peca_obrigatoria', 'aprovado')
    search_fields = ('orcamento__ordem_servico__codigo', 'codigo', 'nome')
    autocomplete_fields = ('orcamento', 'parent')


@admin.register(WorkOrderApprovalAudit)
class WorkOrderApprovalAuditAdmin(admin.ModelAdmin):
    list_display = ('orcamento', 'decisao', 'metodo', 'nome_responsavel', 'documento_valido', 'usuario_interno', 'criado_em')
    list_filter = ('decisao', 'metodo', 'documento_valido', 'criado_em')
    search_fields = ('orcamento__ordem_servico__codigo', 'nome_responsavel', 'documento', 'observacao', 'ip')
    autocomplete_fields = ('orcamento', 'usuario_interno')
    readonly_fields = ('itens_aprovados_snapshot', 'itens_rejeitados_snapshot', 'assinatura_base64', 'assinatura_nome', 'criado_em')


@admin.register(CustomerVehicleAccessToken)
class CustomerVehicleAccessTokenAdmin(admin.ModelAdmin):
    list_display = ('placa', 'cliente', 'veiculo', 'email', 'expira_em', 'verificado_em', 'tentativas', 'criado_em')
    list_filter = ('verificado_em', 'revogado_em', 'expira_em', 'criado_em')
    search_fields = ('placa', 'email', 'cliente__nome_razao_social', 'veiculo__placa')
    autocomplete_fields = ('cliente', 'veiculo')
    readonly_fields = (
        'token',
        'codigo_hash',
        'tentativas',
        'expira_em',
        'verificado_em',
        'revogado_em',
        'ip_solicitacao',
        'user_agent_solicitacao',
        'ip_verificacao',
        'criado_em',
        'atualizado_em',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(WorkOrderSettings)
class WorkOrderSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'prazo_estimativa_dias', 'vagas_oficina', 'atualizado_em')
    readonly_fields = ('atualizado_em',)

    def has_add_permission(self, request):
        return not WorkOrderSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class WorkOrderServiceItemInline(admin.TabularInline):
    model = WorkOrderServiceItem
    extra = 1
    autocomplete_fields = ('service',)
    readonly_fields = ('valor_unitario',)


class WorkOrderComboItemInline(admin.TabularInline):
    model = WorkOrderComboItem
    extra = 1
    autocomplete_fields = ('combo',)
    readonly_fields = ('valor_unitario',)


class WorkOrderPartItemInline(admin.TabularInline):
    model = WorkOrderPartItem
    extra = 1
    autocomplete_fields = ('item',)
    readonly_fields = ('valor_unitario',)


class WorkOrderStockRequirementOverrideInline(admin.TabularInline):
    model = WorkOrderStockRequirementOverride
    extra = 0
    autocomplete_fields = ('item',)


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'cliente', 'veiculo', 'status', 'tecnico_responsavel', 'data_abertura', 'data_finalizacao', 'valor_total', 'estoque_baixado')
    list_filter = ('status', 'tecnico_responsavel', 'estoque_baixado', 'data_abertura')
    search_fields = ('codigo', 'cliente__nome_razao_social', 'veiculo__placa', 'problema_relatado', 'diagnostico', 'tecnico_responsavel__email', 'tecnico_responsavel__nome_razao_social')
    autocomplete_fields = ('cliente', 'veiculo', 'tecnico_responsavel')
    readonly_fields = ('codigo', 'data_abertura', 'estoque_baixado', 'estoque_baixado_em', 'estoque_baixado_por')
    exclude = ('ativo', 'excluido_em')
    inlines = [WorkOrderServiceItemInline, WorkOrderComboItemInline, WorkOrderPartItemInline, WorkOrderStockRequirementOverrideInline]

    def get_queryset(self, request):
        return WorkOrder.objects.select_related('cliente', 'veiculo', 'tecnico_responsavel').prefetch_related('servicos_os__service', 'combos_os__combo', 'pecas_os__item')


@admin.register(WorkOrderStatusTransition)
class WorkOrderStatusTransitionAdmin(admin.ModelAdmin):
    list_display = ('ordem_servico', 'status_anterior', 'status_novo', 'criado_por', 'criado_em')
    list_filter = ('status_anterior', 'status_novo', 'criado_em')
    search_fields = ('ordem_servico__codigo', 'ordem_servico__cliente__nome_razao_social', 'observacao')
    autocomplete_fields = ('ordem_servico', 'criado_por')
    readonly_fields = ('criado_em',)


@admin.register(WorkOrderServiceItem)
class WorkOrderServiceItemAdmin(admin.ModelAdmin):
    list_display = ('ordem_servico', 'service', 'quantidade', 'valor_unitario', 'subtotal')
    search_fields = ('ordem_servico__codigo', 'service__codigo', 'service__nome')
    autocomplete_fields = ('ordem_servico', 'service')


@admin.register(WorkOrderComboItem)
class WorkOrderComboItemAdmin(admin.ModelAdmin):
    list_display = ('ordem_servico', 'combo', 'quantidade', 'valor_unitario', 'subtotal')
    search_fields = ('ordem_servico__codigo', 'combo__codigo', 'combo__nome')
    autocomplete_fields = ('ordem_servico', 'combo')


@admin.register(WorkOrderPartItem)
class WorkOrderPartItemAdmin(admin.ModelAdmin):
    list_display = ('ordem_servico', 'item', 'quantidade', 'valor_unitario', 'subtotal')
    search_fields = ('ordem_servico__codigo', 'item__sku', 'item__nome')
    autocomplete_fields = ('ordem_servico', 'item')



@admin.register(WorkOrderStockRequirementOverride)
class WorkOrderStockRequirementOverrideAdmin(admin.ModelAdmin):
    list_display = ('ordem_servico', 'item', 'quantidade', 'atualizado_em')
    search_fields = ('ordem_servico__codigo', 'item__sku', 'item__nome')
    autocomplete_fields = ('ordem_servico', 'item')
    readonly_fields = ('criado_em', 'atualizado_em')


class VehicleCheckInPhotoInline(admin.TabularInline):
    model = VehicleCheckInPhoto
    extra = 1
    readonly_fields = ('criado_em',)


@admin.register(VehicleCheckIn)
class VehicleCheckInAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'ordem_servico', 'cliente', 'veiculo', 'km', 'email_enviado', 'data_checkin')
    list_filter = ('email_enviado', 'nivel_combustivel', 'data_checkin')
    search_fields = ('codigo', 'ordem_servico__codigo', 'cliente__nome_razao_social', 'cliente__email', 'veiculo__placa', 'veiculo__marca', 'veiculo__modelo')
    autocomplete_fields = ('ordem_servico',)
    readonly_fields = ('codigo', 'cliente', 'veiculo', 'data_checkin', 'criado_por', 'email_enviado', 'email_enviado_em', 'email_enviado_por', 'email_erro')
    exclude = ('ativo', 'excluido_em')
    inlines = [VehicleCheckInPhotoInline]

    def get_queryset(self, request):
        return VehicleCheckIn.objects.select_related('ordem_servico', 'cliente', 'veiculo')


@admin.register(VehicleCheckInPhoto)
class VehicleCheckInPhotoAdmin(admin.ModelAdmin):
    list_display = ('checkin', 'imagem', 'legenda', 'criado_em')
    search_fields = ('checkin__codigo', 'checkin__cliente__nome_razao_social', 'legenda')
    autocomplete_fields = ('checkin',)
    readonly_fields = ('criado_em',)
