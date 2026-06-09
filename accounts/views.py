import logging
import unicodedata

from django.contrib import messages
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from .forms import EmailAuthenticationForm, EmployeeCreateForm, EmployeeUpdateForm
from .models import EmployeeRole
from .utils import sync_user_role_group
from .security import clear_login_attempt, get_client_ip, get_login_lock, record_failed_login

User = get_user_model()
logger = logging.getLogger(__name__)


class SecureLoginView(auth_views.LoginView):
    template_name = 'registration/login.html'
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        email = (request.POST.get('username') or '').strip().lower()
        ip_address = get_client_ip(request)
        lock = get_login_lock(email, ip_address)

        if lock:
            messages.error(
                request,
                'Muitas tentativas de login. Tente novamente mais tarde ou solicite redefinição de senha.',
            )
            logger.warning('Tentativa de login bloqueada. email=%s ip=%s', email, ip_address)
            return redirect('login')

        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)

        attempt = record_failed_login(request, email)
        remaining = max(settings.LOGIN_ATTEMPT_LIMIT - attempt.failure_count, 0)
        if remaining and remaining <= 2:
            messages.warning(request, f'Atenção: restam {remaining} tentativa(s) antes do bloqueio temporário.')
        elif attempt.is_locked:
            messages.error(request, 'Login temporariamente bloqueado por excesso de tentativas inválidas.')

        return self.form_invalid(form)

    def form_valid(self, form):
        clear_login_attempt(self.request, form.cleaned_data.get('username'))
        logger.info('Login realizado com sucesso. user_id=%s ip=%s', form.get_user().pk, get_client_ip(self.request))
        return super().form_valid(form)


def normalize_search_text(value):
    text = unicodedata.normalize('NFKD', str(value or '').lower())
    return ''.join(char for char in text if not unicodedata.combining(char)).strip()


class EmployeeSearchMixin:
    search_param_names = ('q',)

    def get_search_filters(self):
        return {name: (self.request.GET.get(name) or '').strip() for name in self.search_param_names}

    def build_employee_search_q(self, term):
        search_q = (
            Q(nome_razao_social__icontains=term)
            | Q(email__icontains=term)
            | Q(role__icontains=term)
            | Q(documento__icontains=term)
            | Q(whatsapp__icontains=term)
            | Q(cidade__icontains=term)
            | Q(uf__icontains=term)
        )

        normalized_term = normalize_search_text(term)
        for value, label in EmployeeRole.choices:
            if normalized_term in normalize_search_text(value) or normalized_term in normalize_search_text(label):
                search_q |= Q(role=value)

        return search_q

    def apply_employee_filters(self, queryset):
        term = self.get_search_filters()['q']

        if term:
            queryset = queryset.filter(self.build_employee_search_q(term))

        return queryset.distinct().order_by(Lower('nome_razao_social'), Lower('email'), 'pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = self.get_search_filters()
        querydict = self.request.GET.copy()
        querydict.pop('page', None)
        context['filters'] = filters
        context['querystring'] = querydict.urlencode()
        context['has_active_filters'] = any(filters.values())
        return context


class EmployeeListView(LoginRequiredMixin, PermissionRequiredMixin, EmployeeSearchMixin, ListView):
    model = User
    template_name = 'accounts/employee_list.html'
    context_object_name = 'employees'
    paginate_by = 20
    permission_required = 'accounts.view_user'

    def get_queryset(self):
        queryset = User.objects.filter(is_superuser=False)
        return self.apply_employee_filters(queryset)


class EmployeeAutocompleteView(LoginRequiredMixin, PermissionRequiredMixin, EmployeeSearchMixin, View):
    permission_required = 'accounts.view_user'
    limit = 10

    def get(self, request, *args, **kwargs):
        term = (request.GET.get('q') or '').strip()

        if len(term) < 2:
            return JsonResponse({'results': []})

        queryset = User.objects.filter(is_superuser=False)
        queryset = queryset.filter(self.build_employee_search_q(term)).distinct().order_by(Lower('nome_razao_social'), Lower('email'), 'pk')[: self.limit]

        results = []
        for employee in queryset:
            city_state = f'{employee.cidade}/{employee.uf}' if employee.cidade and employee.uf else employee.cidade or employee.uf
            subtitle_parts = [employee.email, employee.get_role_display(), employee.whatsapp, city_state]
            results.append({
                'id': employee.pk,
                'label': employee.nome_razao_social or employee.email,
                'value': employee.nome_razao_social or employee.email,
                'subtitle': ' | '.join(part for part in subtitle_parts if part),
                'url': reverse_lazy('employee_update', kwargs={'pk': employee.pk}),
            })

        return JsonResponse({'results': results})


class EmployeeFormTitleMixin:
    title = ''
    cancel_url = reverse_lazy('employee_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = self.title
        context['cancel_url'] = self.cancel_url
        return context


class EmployeeCreateView(LoginRequiredMixin, PermissionRequiredMixin, EmployeeFormTitleMixin, CreateView):
    model = User
    form_class = EmployeeCreateForm
    template_name = 'core/object_form.html'
    success_url = reverse_lazy('employee_list')
    permission_required = 'accounts.add_user'
    title = 'Novo funcionário'

    def form_valid(self, form):
        response = super().form_valid(form)
        sync_user_role_group(self.object)
        messages.success(self.request, 'Funcionário cadastrado com sucesso.')
        return response


class EmployeeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, EmployeeFormTitleMixin, UpdateView):
    model = User
    form_class = EmployeeUpdateForm
    template_name = 'core/object_form.html'
    success_url = reverse_lazy('employee_list')
    permission_required = 'accounts.change_user'
    title = 'Editar funcionário'

    def get_queryset(self):
        return User.objects.filter(is_superuser=False)

    def form_valid(self, form):
        response = super().form_valid(form)
        sync_user_role_group(self.object)
        messages.success(self.request, 'Funcionário atualizado com sucesso.')
        return response


class EmployeeDeleteView(LoginRequiredMixin, PermissionRequiredMixin, EmployeeFormTitleMixin, DeleteView):
    model = User
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('employee_list')
    permission_required = 'accounts.delete_user'
    title = 'Excluir funcionário'

    def get_queryset(self):
        return User.objects.filter(is_superuser=False)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        if self.object == request.user:
            messages.error(request, 'Você não pode excluir seu próprio usuário.')
            return redirect('employee_list')

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Funcionário excluído com sucesso.')
        return super().form_valid(form)
