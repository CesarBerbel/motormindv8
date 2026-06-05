from django.contrib import admin

from .models import MessageLog, MessageSettings, MessageTemplate, WorkOrderStatusMessageRule


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'padrao', 'criado_em', 'atualizado_em')
    list_filter = ('tipo', 'padrao', 'criado_em')
    search_fields = ('nome', 'assunto', 'corpo')
    readonly_fields = ('criado_em', 'atualizado_em', 'excluido_em')
    exclude = ('ativo',)


@admin.register(MessageSettings)
class MessageSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'enviar_aniversario_pessoa_fisica',
        'enviar_fundacao_pessoa_juridica',
        'enviar_status_os',
        'template_orcamento_os',
        'atualizado_em',
    )
    readonly_fields = ('atualizado_em',)

    def has_add_permission(self, request):
        return not MessageSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WorkOrderStatusMessageRule)
class WorkOrderStatusMessageRuleAdmin(admin.ModelAdmin):
    list_display = ('ordem', 'status', 'enviar_email', 'template', 'atualizado_em')
    list_filter = ('enviar_email', 'status')
    search_fields = ('status', 'template__nome')
    readonly_fields = ('ordem', 'atualizado_em')


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = (
        'criado_em',
        'tipo',
        'status',
        'destinatario_tipo',
        'destinatario_nome',
        'destinatario_email',
        'template',
        'ordem_servico_codigo',
        'ordem_servico_status',
        'assunto',
        'enviado_em',
    )
    list_filter = ('tipo', 'status', 'destinatario_tipo', 'template', 'ordem_servico_status', 'ano_referencia', 'criado_em')
    search_fields = ('destinatario_nome', 'destinatario_email', 'assunto', 'erro', 'ordem_servico_codigo')
    readonly_fields = ('criado_em', 'atualizado_em', 'enviado_em')
