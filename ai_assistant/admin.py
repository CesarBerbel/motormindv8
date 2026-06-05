from django.contrib import admin

from .models import AIInteractionLog, AISettings


@admin.register(AISettings)
class AISettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'ativo', 'provedor', 'modelo', 'masked_api_key', 'habilitar_os', 'habilitar_mensagens', 'atualizado_em')
    readonly_fields = ('atualizado_em', 'masked_api_key')
    fieldsets = (
        ('Provedor', {
            'fields': ('ativo', 'provedor', 'modelo', 'api_key', 'masked_api_key', 'endpoint_base', 'temperatura', 'timeout_segundos')
        }),
        ('Comportamento geral', {
            'fields': ('tom_resposta', 'caracteristicas_oficina', 'instrucoes_gerais', 'limite_caracteres_resposta')
        }),
        ('Instruções específicas por campo', {
            'fields': (
                'instrucao_problema_relatado',
                'instrucao_diagnostico',
                'instrucao_observacao',
                'instrucao_template_mensagem',
            )
        }),
        ('Exibição no sistema', {
            'fields': ('habilitar_os', 'habilitar_mensagens')
        }),
        ('Controle', {
            'fields': ('atualizado_em',)
        }),
    )

    def has_add_permission(self, request):
        return not AISettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AIInteractionLog)
class AIInteractionLogAdmin(admin.ModelAdmin):
    list_display = ('acao', 'provedor', 'modelo', 'sucesso', 'usuario', 'criado_em')
    list_filter = ('acao', 'provedor', 'sucesso', 'criado_em')
    search_fields = ('entrada', 'resposta', 'erro', 'usuario__email')
    readonly_fields = ('acao', 'provedor', 'modelo', 'entrada', 'contexto', 'resposta', 'sucesso', 'erro', 'usuario', 'criado_em')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
