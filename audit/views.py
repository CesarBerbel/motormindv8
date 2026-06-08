from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.views.generic import ListView

from .models import AuditAction, AuditCategory, AuditLog


class AuditLogListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name = 'audit/audit_list.html'
    context_object_name = 'registros'
    paginate_by = 50
    permission_required = 'audit.view_auditlog'

    def get_queryset(self):
        qs = AuditLog.objects.select_related('usuario')
        params = self.request.GET

        busca = (params.get('q') or '').strip()
        if busca:
            qs = qs.filter(
                Q(descricao__icontains=busca)
                | Q(objeto_descricao__icontains=busca)
                | Q(objeto_id__icontains=busca)
                | Q(caminho__icontains=busca)
                | Q(usuario_email__icontains=busca)
                | Q(ip__icontains=busca)
            )

        categoria = params.get('categoria')
        if categoria in AuditCategory.values:
            qs = qs.filter(categoria=categoria)

        acao = params.get('acao')
        if acao in AuditAction.values:
            qs = qs.filter(acao=acao)

        usuario = params.get('usuario')
        if usuario:
            qs = qs.filter(usuario_id=usuario)

        modelo = (params.get('modelo') or '').strip()
        if modelo:
            qs = qs.filter(objeto_modelo=modelo)

        data_de = (params.get('de') or '').strip()
        if data_de:
            qs = qs.filter(criado_em__date__gte=data_de)
        data_ate = (params.get('ate') or '').strip()
        if data_ate:
            qs = qs.filter(criado_em__date__lte=data_ate)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        User = get_user_model()
        context['categorias'] = AuditCategory.choices
        context['acoes'] = AuditAction.choices
        context['usuarios'] = User.objects.filter(auditorias__isnull=False).distinct().order_by('email')
        context['modelos'] = (
            AuditLog.objects.exclude(objeto_modelo='')
            .values_list('objeto_modelo', flat=True)
            .distinct()
            .order_by('objeto_modelo')
        )
        context['filters'] = {
            'q': self.request.GET.get('q', ''),
            'categoria': self.request.GET.get('categoria', ''),
            'acao': self.request.GET.get('acao', ''),
            'usuario': self.request.GET.get('usuario', ''),
            'modelo': self.request.GET.get('modelo', ''),
            'de': self.request.GET.get('de', ''),
            'ate': self.request.GET.get('ate', ''),
        }
        return context
