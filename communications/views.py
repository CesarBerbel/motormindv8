import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, FormView, ListView, UpdateView

from core.views import FormTitleMixin
from .forms import ManualMessageForm, MessageSettingsForm, MessageTemplateForm, WorkOrderStatusMessageRuleFormSet
from .models import MessageLog, MessageSettings, MessageTemplate, MessageTemplateType, WorkOrderStatusMessageRule
from .services import ensure_work_order_status_message_rules, send_manual_message


class MessageSettingsView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = MessageSettings
    form_class = MessageSettingsForm
    template_name = 'communications/message_settings_form.html'
    success_url = reverse_lazy('message_settings')
    permission_required = 'communications.change_messagesettings'
    title = 'Configurações de mensagens'

    def get_object(self, queryset=None):
        return MessageSettings.get_solo()

    def get_rule_formset(self, data=None):
        ensure_work_order_status_message_rules()
        return WorkOrderStatusMessageRuleFormSet(
            data=data,
            queryset=WorkOrderStatusMessageRule.objects.select_related('template').order_by('ordem', 'status'),
            prefix='status_rules',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'rule_formset' not in context:
            context['rule_formset'] = self.get_rule_formset()
        context['status_templates_count'] = MessageTemplate.objects.filter(tipo=MessageTemplateType.WORK_ORDER_STATUS).count()
        context['approval_templates_count'] = MessageTemplate.objects.filter(tipo=MessageTemplateType.WORK_ORDER_APPROVAL).count()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        rule_formset = self.get_rule_formset(data=request.POST)
        if form.is_valid() and rule_formset.is_valid():
            return self.forms_valid(form, rule_formset)
        return self.forms_invalid(form, rule_formset)

    def forms_valid(self, form, rule_formset):
        form.save()
        rule_formset.save()
        messages.success(self.request, 'Configurações de mensagens atualizadas com sucesso.')
        return HttpResponseRedirect(self.get_success_url())

    def forms_invalid(self, form, rule_formset):
        messages.error(self.request, 'Não foi possível salvar as configurações de mensagens. Confira os campos destacados.')
        return self.render_to_response(self.get_context_data(form=form, rule_formset=rule_formset))


class ManualMessageView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = 'communications/manual_message_form.html'
    form_class = ManualMessageForm
    success_url = reverse_lazy('message_history')
    permission_required = 'communications.add_messagelog'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        templates = MessageTemplate.objects.order_by('tipo', 'nome')
        context['templates_payload'] = json.dumps({
            str(template.pk): {
                'assunto': template.assunto,
                'corpo': template.corpo,
            }
            for template in templates
        })
        return context

    def form_valid(self, form):
        recipients = form.get_recipients()
        if not recipients:
            form.add_error(None, 'Nenhum destinatário ativo com email foi encontrado para os filtros selecionados.')
            messages.error(self.request, 'Nenhum destinatário ativo com email foi encontrado.')
            return self.form_invalid(form)

        logs = send_manual_message(
            recipients=recipients,
            subject=form.cleaned_data['assunto'],
            body=form.cleaned_data['corpo'],
            template=form.cleaned_data.get('template'),
            user=self.request.user,
        )
        sent_count = sum(1 for log in logs if log.status == 'sent')
        error_count = sum(1 for log in logs if log.status == 'error')

        if error_count:
            messages.warning(
                self.request,
                f'Mensagem processada: {sent_count} enviado(s), {error_count} com erro. Consulte o histórico.',
            )
        else:
            messages.success(self.request, f'Mensagem enviada para {sent_count} destinatário(s).')

        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Não foi possível enviar a mensagem. Confira os alertas do formulário.')
        return super().form_invalid(form)


class MessageHistoryView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = MessageLog
    template_name = 'communications/message_history.html'
    context_object_name = 'messages_history'
    paginate_by = 30
    permission_required = 'communications.view_messagelog'

    def get_queryset(self):
        queryset = MessageLog.objects.select_related('enviado_por', 'template').order_by('-criado_em')
        status = self.request.GET.get('status')
        message_type = self.request.GET.get('tipo')
        os_code = self.request.GET.get('os')

        if status:
            queryset = queryset.filter(status=status)
        if message_type:
            queryset = queryset.filter(tipo=message_type)
        if os_code:
            queryset = queryset.filter(ordem_servico_codigo__icontains=os_code)

        return queryset


class MessageTemplateListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = MessageTemplate
    template_name = 'communications/message_template_list.html'
    context_object_name = 'message_templates'
    paginate_by = 20
    permission_required = 'communications.view_messagetemplate'

    def get_queryset(self):
        return MessageTemplate.objects.order_by('tipo', 'nome')


class MessageTemplateCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, CreateView):
    model = MessageTemplate
    form_class = MessageTemplateForm
    template_name = 'communications/message_template_form.html'
    success_url = reverse_lazy('message_template_list')
    permission_required = 'communications.add_messagetemplate'
    title = 'Novo template de mensagem'

    def get_initial(self):
        initial = super().get_initial()
        requested_type = self.request.GET.get('tipo')
        valid_types = {choice[0] for choice in MessageTemplateType.choices}
        if requested_type in valid_types:
            initial['tipo'] = requested_type
        if requested_type == MessageTemplateType.WORK_ORDER_APPROVAL:
            initial.setdefault('nome', 'Orçamento / aprovação da OS')
            initial.setdefault('assunto', 'Orçamento da OS {{ ordem_servico.codigo }} aguardando aprovação')
            initial.setdefault(
                'corpo',
                '<p>Olá, {{ nome }}!</p>'
                '<p>O orçamento <strong>{{ orcamento.codigo }}</strong> da OS <strong>{{ ordem_servico.codigo }}</strong> está aguardando sua aprovação.</p>'
                '<p>Total do orçamento: <strong>{{ valor_total }}</strong>.</p>'
                '<p>Acesse: <a href="{{ link_aprovacao }}">{{ link_aprovacao }}</a></p>',
            )
        return initial

    def form_valid(self, form):
        messages.success(self.request, 'Template cadastrado com sucesso.')
        return super().form_valid(form)


class MessageTemplateUpdateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = MessageTemplate
    form_class = MessageTemplateForm
    template_name = 'communications/message_template_form.html'
    success_url = reverse_lazy('message_template_list')
    permission_required = 'communications.change_messagetemplate'
    title = 'Editar template de mensagem'

    def get_queryset(self):
        return MessageTemplate.objects.all()

    def form_valid(self, form):
        messages.success(self.request, 'Template atualizado com sucesso.')
        return super().form_valid(form)


class MessageTemplateDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, DeleteView):
    model = MessageTemplate
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('message_template_list')
    permission_required = 'communications.delete_messagetemplate'
    title = 'Excluir template de mensagem'

    def get_queryset(self):
        return MessageTemplate.objects.all()

    def form_valid(self, form):
        self.object.soft_delete()
        messages.success(self.request, 'Template excluído com sucesso.')
        return HttpResponseRedirect(self.get_success_url())
