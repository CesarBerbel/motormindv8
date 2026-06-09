from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('criado_em', 'categoria', 'acao', 'usuario_email', 'objeto_modelo', 'objeto_descricao', 'caminho')
    list_filter = ('categoria', 'acao', 'criado_em', 'objeto_modelo')
    search_fields = ('usuario_email', 'descricao', 'objeto_descricao', 'objeto_id', 'caminho', 'ip')
    date_hierarchy = 'criado_em'
    ordering = ('-criado_em',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Apenas superusuário pode limpar manualmente; a rotina padrão é o comando audit_prune.
        return request.user.is_superuser

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]
