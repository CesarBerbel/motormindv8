import json
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Count, Q
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from ai_assistant.services import AIServiceError, check_ai_rate_limit, generate_blog_article
from core.forms import format_phone
from core.models import Customer, Vehicle, format_plate, only_digits
from core.views import FormTitleMixin
from .forms import BlogPostForm, LeadFilterForm, LeadForm, LeadStatusForm, SiteSettingsForm
from .models import BlogPost, Lead, LeadStatus, PublicService, SiteSettings, Testimonial
from .services import notify_new_lead


def _lead_phone_candidates(phone):
    formatted = format_phone(phone)
    digits = only_digits(phone)
    return {candidate for candidate in (phone, formatted, digits) if candidate}


def find_customer_for_lead(lead):
    filters = Q()
    nome = (lead.nome or '').strip()
    email = (lead.email or '').strip()
    phone_candidates = _lead_phone_candidates(lead.telefone)

    if nome:
        filters |= Q(nome_razao_social__iexact=nome)
    if email:
        filters |= Q(email__iexact=email)
    if phone_candidates:
        filters |= Q(whatsapp__in=phone_candidates)

    if not filters:
        return None

    return Customer.objects.filter(filters).order_by('nome_razao_social', 'pk').first()


def find_vehicle_for_lead(lead):
    placa = format_plate(lead.placa)
    if not placa:
        return None
    return Vehicle.objects.select_related('cliente').filter(placa__iexact=placa).order_by('pk').first()


def split_vehicle_description(description):
    parts = (description or '').strip().split()
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], ' '.join(parts[1:])


def build_url_with_query(url_name, **params):
    clean_params = {key: value for key, value in params.items() if value not in (None, '')}
    if not clean_params:
        return reverse(url_name)
    return f'{reverse(url_name)}?{urlencode(clean_params)}'



class PublicHomeView(TemplateView):
    template_name = 'website/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        servicos = PublicService.objects.filter(ativo=True)
        destaques = list(servicos.filter(destaque=True)[:6])
        context['servicos_destaque'] = destaques or list(servicos[:6])
        context['depoimentos'] = Testimonial.objects.filter(ativo=True)[:6]
        context['posts_recentes'] = BlogPost.publicados.all()[:3]
        context['form'] = LeadForm()
        return context


class PublicServiceListView(ListView):
    model = PublicService
    template_name = 'website/service_list.html'
    context_object_name = 'servicos'

    def get_queryset(self):
        return PublicService.objects.filter(ativo=True)


class PublicServiceDetailView(DetailView):
    model = PublicService
    template_name = 'website/service_detail.html'
    context_object_name = 'servico'

    def get_queryset(self):
        return PublicService.objects.filter(ativo=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['outros_servicos'] = (
            PublicService.objects.filter(ativo=True).exclude(pk=self.object.pk)[:4]
        )
        context['form'] = LeadForm(initial={'servico': self.object})
        return context


class PublicBlogListView(ListView):
    template_name = 'website/blog_list.html'
    context_object_name = 'posts'
    paginate_by = 9
    queryset = BlogPost.publicados.all()


class PublicBlogDetailView(DetailView):
    template_name = 'website/blog_detail.html'
    context_object_name = 'post'
    queryset = BlogPost.publicados.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['posts_recentes'] = (
            BlogPost.publicados.all().exclude(pk=self.object.pk)[:4]
        )
        return context


class PublicAboutView(TemplateView):
    template_name = 'website/about.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['servicos'] = PublicService.objects.filter(ativo=True)[:8]
        context['depoimentos'] = Testimonial.objects.filter(ativo=True)[:6]
        return context


class PublicContactView(FormView):
    template_name = 'website/contact.html'
    form_class = LeadForm
    success_url = reverse_lazy('public_contact')

    def form_valid(self, form):
        lead = form.save()
        notify_new_lead(lead)
        messages.success(
            self.request,
            'Pedido enviado com sucesso! Em breve entraremos em contato.',
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Revise os campos destacados e tente novamente.')
        return super().form_invalid(form)




# --------------------------------------------------------------------------- #
# Área restrita: pedidos de orçamento recebidos pelo site.
# --------------------------------------------------------------------------- #
class LeadManageListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name = 'website/manage/lead_list.html'
    context_object_name = 'leads'
    paginate_by = 20
    permission_required = 'website.view_lead'

    def get_filter_form(self):
        if not hasattr(self, '_filter_form'):
            self._filter_form = LeadFilterForm(self.request.GET or None)
            self._filter_form.is_valid()
        return self._filter_form

    def get_queryset(self):
        queryset = Lead.objects.select_related('servico').all()
        form = self.get_filter_form()
        if not form.is_valid():
            return queryset

        q = (form.cleaned_data.get('q') or '').strip()
        if q:
            queryset = queryset.filter(
                Q(nome__icontains=q)
                | Q(telefone__icontains=q)
                | Q(email__icontains=q)
                | Q(veiculo__icontains=q)
                | Q(placa__icontains=q)
                | Q(mensagem__icontains=q)
            )

        status = form.cleaned_data.get('status')
        if status:
            queryset = queryset.filter(status=status)

        servico = form.cleaned_data.get('servico')
        if servico:
            queryset = queryset.filter(servico=servico)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status_counts = {
            row['status']: row['total']
            for row in Lead.objects.values('status').annotate(total=Count('id'))
        }
        context['filter_form'] = self.get_filter_form()
        query_params = self.request.GET.copy()
        query_params.pop('page', None)
        context['querystring'] = query_params.urlencode()
        context['total_leads'] = Lead.objects.count()
        context['new_leads'] = status_counts.get(LeadStatus.NOVO, 0)
        context['in_contact_leads'] = status_counts.get(LeadStatus.EM_CONTATO, 0)
        context['completed_leads'] = status_counts.get(LeadStatus.CONCLUIDO, 0)
        context['discarded_leads'] = status_counts.get(LeadStatus.DESCARTADO, 0)
        context['status_counts'] = status_counts
        return context


class LeadManageDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Lead
    template_name = 'website/manage/lead_detail.html'
    context_object_name = 'lead'
    permission_required = 'website.view_lead'
    queryset = Lead.objects.select_related('servico')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lead = self.object
        customer = find_customer_for_lead(lead)
        vehicle = find_vehicle_for_lead(lead)
        customer_vehicle_match = bool(customer and vehicle and vehicle.cliente_id == customer.pk)
        vehicle_customer_mismatch = bool(customer and vehicle and vehicle.cliente_id != customer.pk)
        vehicle_brand, vehicle_model = split_vehicle_description(lead.veiculo)

        context['status_form'] = LeadStatusForm(instance=lead)
        context['matched_customer'] = customer
        context['matched_vehicle'] = vehicle
        context['customer_vehicle_match'] = customer_vehicle_match
        context['vehicle_customer_mismatch'] = vehicle_customer_mismatch
        context['customer_create_url'] = build_url_with_query(
            'customer_create',
            lead=lead.pk,
            nome=lead.nome,
            email=lead.email,
            whatsapp=lead.telefone,
        )
        context['vehicle_create_url'] = build_url_with_query(
            'vehicle_create',
            lead=lead.pk,
            cliente=customer.pk if customer else None,
            placa=format_plate(lead.placa),
            marca=vehicle_brand,
            modelo=vehicle_model,
        )
        context['work_order_create_url'] = build_url_with_query(
            'work_order_create',
            lead=lead.pk,
            cliente=customer.pk if customer_vehicle_match else None,
            veiculo=vehicle.pk if customer_vehicle_match else None,
        )
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not request.user.has_perm('website.change_lead'):
            messages.error(request, 'Você não tem permissão para alterar o status do pedido.')
            return HttpResponseRedirect(reverse('site_lead_detail', kwargs={'pk': self.object.pk}))

        form = LeadStatusForm(request.POST, instance=self.object)
        if form.is_valid():
            form.save()
            messages.success(request, 'Status do pedido atualizado com sucesso.')
            return HttpResponseRedirect(reverse('site_lead_detail', kwargs={'pk': self.object.pk}))

        context = self.get_context_data(object=self.object)
        context['status_form'] = form
        return self.render_to_response(context)


# --------------------------------------------------------------------------- #
# Área restrita: configurações do site (oficina).
# --------------------------------------------------------------------------- #
class SiteSettingsView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = SiteSettings
    form_class = SiteSettingsForm
    template_name = 'website/manage/site_settings_form.html'
    success_url = reverse_lazy('site_settings')
    permission_required = 'website.change_sitesettings'
    title = 'Configurações da oficina'

    def get_object(self, queryset=None):
        return SiteSettings.get_solo()

    def form_valid(self, form):
        messages.success(self.request, 'Configurações da oficina atualizadas com sucesso.')
        return super().form_valid(form)


# --------------------------------------------------------------------------- #
# Área restrita: gestão de artigos do blog.
# --------------------------------------------------------------------------- #
class BlogPostManageListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name = 'website/manage/blog_list.html'
    context_object_name = 'posts'
    paginate_by = 20
    permission_required = 'website.view_blogpost'
    queryset = BlogPost.objects.all()


class BlogPostCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, CreateView):
    model = BlogPost
    form_class = BlogPostForm
    template_name = 'website/manage/blog_form.html'
    success_url = reverse_lazy('blog_manage_list')
    permission_required = 'website.add_blogpost'
    title = 'Novo artigo do blog'

    def form_valid(self, form):
        if form.instance.autor_id is None:
            form.instance.autor = self.request.user
        messages.success(self.request, 'Artigo criado com sucesso.')
        return super().form_valid(form)


class BlogPostUpdateView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, UpdateView):
    model = BlogPost
    form_class = BlogPostForm
    template_name = 'website/manage/blog_form.html'
    success_url = reverse_lazy('blog_manage_list')
    permission_required = 'website.change_blogpost'
    title = 'Editar artigo do blog'
    queryset = BlogPost.objects.all()

    def form_valid(self, form):
        messages.success(self.request, 'Artigo atualizado com sucesso.')
        return super().form_valid(form)


class BlogPostDeleteView(LoginRequiredMixin, PermissionRequiredMixin, FormTitleMixin, DeleteView):
    model = BlogPost
    template_name = 'core/confirm_delete.html'
    success_url = reverse_lazy('blog_manage_list')
    permission_required = 'website.delete_blogpost'
    title = 'Excluir artigo do blog'
    queryset = BlogPost.objects.all()

    def form_valid(self, form):
        messages.success(self.request, 'Artigo excluído com sucesso.')
        return super().form_valid(form)


class BlogArticleGenerateView(LoginRequiredMixin, View):
    """Gera um rascunho completo de artigo a partir de um assunto, via IA."""

    def post(self, request, *args, **kwargs):
        user = request.user
        if not user.has_perm('website.add_blogpost'):
            return JsonResponse({'ok': False, 'error': 'Sem permissão para criar artigos.'}, status=403)
        if not (user.is_superuser or user.has_perm('ai_assistant.use_ai_assistant')):
            return JsonResponse({'ok': False, 'error': 'Sem permissão para usar o assistente de IA.'}, status=403)
        if not check_ai_rate_limit(user):
            return JsonResponse(
                {'ok': False, 'error': 'Muitas solicitações de IA em pouco tempo. Aguarde um instante.'},
                status=429,
            )

        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'JSON inválido.'}, status=400)

        subject = (payload.get('assunto') or payload.get('text') or '').strip()
        if not subject:
            return JsonResponse({'ok': False, 'error': 'Informe o assunto do artigo.'}, status=400)

        try:
            article = generate_blog_article(subject, user=user)
        except AIServiceError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        except Exception as exc:  # pragma: no cover - defensivo
            return JsonResponse({'ok': False, 'error': f'Erro inesperado ao chamar a IA: {exc}'}, status=500)

        return JsonResponse({'ok': True, **article})
