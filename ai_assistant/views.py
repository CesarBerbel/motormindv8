import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import UpdateView

from core.views import FormTitleMixin
from .forms import AISettingsForm
from .models import AIAssistantAction, AISettings
from .services import AIServiceError, generate_ai_text, sanitize_context, test_ai_connection


class AISettingsView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = AISettings
    form_class = AISettingsForm
    template_name = 'ai_assistant/ai_settings_form.html'
    success_url = reverse_lazy('ai_settings')
    permission_required = 'ai_assistant.change_aisettings'
    title = 'Configurações de IA'

    def get_object(self, queryset=None):
        return AISettings.get_solo()

    def form_valid(self, form):
        messages.success(self.request, 'Configurações de IA atualizadas com sucesso.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível salvar as configurações de IA. Confira os campos destacados.')
        return super().form_invalid(form)


class AIPermissionMixin(LoginRequiredMixin):
    def has_ai_permission(self):
        user = self.request.user
        return bool(user.is_superuser or user.has_perm('ai_assistant.use_ai_assistant'))

    def dispatch(self, request, *args, **kwargs):
        if not self.has_ai_permission():
            return JsonResponse({'ok': False, 'error': 'Sem permissão para usar o assistente de IA.'}, status=403)
        return super().dispatch(request, *args, **kwargs)


class AITextAssistView(AIPermissionMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'JSON inválido.'}, status=400)

        action = payload.get('action') or AIAssistantAction.GENERAL
        text = payload.get('text') or ''
        context = sanitize_context(payload.get('context') or {})

        if action not in AIAssistantAction.values:
            return JsonResponse({'ok': False, 'error': 'Ação de IA inválida.'}, status=400)

        settings = AISettings.get_solo()
        if action in {
            AIAssistantAction.IMPROVE_PROBLEM,
            AIAssistantAction.IMPROVE_DIAGNOSIS,
            AIAssistantAction.SUGGEST_OBSERVATION,
        } and not settings.habilitar_os:
            return JsonResponse({'ok': False, 'error': 'A IA para campos da OS está desabilitada nas configurações.'}, status=400)
        if action in {
            AIAssistantAction.IMPROVE_MESSAGE,
            AIAssistantAction.EMAIL_TEMPLATE,
            AIAssistantAction.WHATSAPP_TEMPLATE,
        } and not settings.habilitar_mensagens:
            return JsonResponse({'ok': False, 'error': 'A IA para mensagens/templates está desabilitada nas configurações.'}, status=400)

        try:
            result = generate_ai_text(action, text=text, context=context, user=request.user)
        except AIServiceError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        except Exception as exc:
            return JsonResponse({'ok': False, 'error': f'Erro inesperado ao chamar a IA: {exc}'}, status=500)

        return JsonResponse({
            'ok': True,
            'text': result.text,
            'provider': result.provider,
            'model': result.model,
        })


class AITestConnectionView(AIPermissionMixin, View):
    def post(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.has_perm('ai_assistant.change_aisettings')):
            return JsonResponse({'ok': False, 'error': 'Sem permissão para testar a configuração de IA.'}, status=403)
        try:
            result = test_ai_connection(user=request.user)
        except Exception as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'text': result.text, 'provider': result.provider, 'model': result.model})
