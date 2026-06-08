from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audit'
    verbose_name = 'Auditoria'

    def ready(self):
        # Liga os signals de autenticação e de alterações de modelos.
        from . import signals  # noqa: F401
