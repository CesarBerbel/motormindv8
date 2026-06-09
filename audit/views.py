from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.views import View
from django.views.generic import ListView

from .models import AuditAction, AuditCategory, AuditLog


class AuditSearchMixin:
    """Centraliza a busca textual para lista e autocomplete da auditoria."""

    searchable_fields = (
        'descricao',
        'objeto_descricao',
        'objeto_id',
        'objeto_modelo',
        'caminho',
        'usuario_email',
        'ip',
    )

    def build_audit_search_q(self, term):
        search_q = Q()
        for field in self.searchable_fields:
            search_q |= Q(**{f'{field}__icontains': term})
        return search_q


class AuditLogListView(LoginRequiredMixin, PermissionRequiredMixin, AuditSearchMixin, ListView):
    template_name = 'audit/audit_list.html'
    context_object_name = 'registros'
    paginate_by = 50
    permission_required = 'audit.view_auditlog'

    def get_queryset(self):
        qs = AuditLog.objects.select_related('usuario')
        params = self.request.GET

        busca = (params.get('q') or '').strip()
        if busca:
            qs = qs.filter(self.build_audit_search_q(busca))

        categoria = params.get('categoria')
        if categoria in AuditCategory.values:
            qs = qs.filter(categoria=categoria)

        acao = params.get('acao')
        if acao in AuditAction.values:
            qs = qs.filter(acao=acao)

        usuario = params.get('usuario')
        if usuario:
            if str(usuario).isdigit():
                qs = qs.filter(usuario_id=usuario)
            else:
                qs = qs.none()

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
        filters = {
            'q': self.request.GET.get('q', ''),
            'categoria': self.request.GET.get('categoria', ''),
            'acao': self.request.GET.get('acao', ''),
            'usuario': self.request.GET.get('usuario', ''),
            'modelo': self.request.GET.get('modelo', ''),
            'de': self.request.GET.get('de', ''),
            'ate': self.request.GET.get('ate', ''),
        }
        querydict = self.request.GET.copy()
        querydict.pop('page', None)

        usuarios = User.objects.filter(auditorias__isnull=False).distinct().order_by('email')
        categorias_dict = dict(AuditCategory.choices)
        acoes_dict = dict(AuditAction.choices)
        selected_user = usuarios.filter(pk=filters['usuario']).first() if str(filters['usuario']).isdigit() else None

        context['categorias'] = AuditCategory.choices
        context['acoes'] = AuditAction.choices
        context['usuarios'] = usuarios
        context['modelos'] = (
            AuditLog.objects.exclude(objeto_modelo='')
            .values_list('objeto_modelo', flat=True)
            .distinct()
            .order_by('objeto_modelo')
        )
        context['filters'] = filters
        context['querystring'] = querydict.urlencode()
        context['has_active_filters'] = any(filters.values())
        context['selected_filters'] = {
            'categoria': categorias_dict.get(filters['categoria'], filters['categoria']),
            'acao': acoes_dict.get(filters['acao'], filters['acao']),
            'usuario': selected_user.email if selected_user else '',
        }
        return context


class AuditLogAutocompleteView(LoginRequiredMixin, PermissionRequiredMixin, AuditSearchMixin, View):
    permission_required = 'audit.view_auditlog'
    limit = 10
    scan_limit = 80

    def get(self, request, *args, **kwargs):
        term = (request.GET.get('q') or '').strip()
        if len(term) < 2:
            return JsonResponse({'results': []})

        term_lower = term.lower()
        queryset = (
            AuditLog.objects.select_related('usuario')
            .filter(self.build_audit_search_q(term))
            .order_by('-criado_em')[: self.scan_limit]
        )

        results = []
        seen = set()

        def add_result(*, value, label, subtitle, log_id):
            value = (value or '').strip()
            label = (label or value).strip()
            if not value or not label:
                return
            normalized = value.lower()
            if normalized in seen or len(results) >= self.limit:
                return
            seen.add(normalized)
            results.append({
                'id': log_id,
                'label': label,
                'value': value,
                'subtitle': subtitle,
            })

        for log in queryset:
            data = log.criado_em.strftime('%d/%m/%Y %H:%M')
            acao = log.get_acao_display()
            base_subtitle = f'{data} | {acao}'

            candidates = [
                ('usuario', log.usuario_email, f'Usuário | {base_subtitle}'),
                ('objeto', log.objeto_descricao, f'Objeto | {base_subtitle}'),
                ('descricao', log.descricao, f'Descrição | {base_subtitle}'),
                ('modelo', log.objeto_modelo, f'Modelo | {base_subtitle}'),
                ('id', log.objeto_id, f'ID do objeto | {base_subtitle}'),
                ('caminho', log.caminho, f'Caminho | {base_subtitle}'),
                ('ip', str(log.ip or ''), f'IP | {base_subtitle}'),
            ]

            matched = False
            for _, value, subtitle in candidates:
                if value and term_lower in str(value).lower():
                    add_result(value=str(value), label=str(value), subtitle=subtitle, log_id=log.pk)
                    matched = True

            if not matched:
                fallback = log.objeto_descricao or log.descricao or log.usuario_email or log.caminho
                add_result(value=fallback, label=fallback, subtitle=base_subtitle, log_id=log.pk)

            if len(results) >= self.limit:
                break

        return JsonResponse({'results': results})
