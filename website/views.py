import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse_lazy
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
from core.views import FormTitleMixin
from .forms import BlogPostForm, LeadForm, SiteSettingsForm
from .models import BlogPost, PublicService, SiteSettings, Testimonial
from .services import notify_new_lead


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
