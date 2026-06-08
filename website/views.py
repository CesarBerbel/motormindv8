from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView, ListView, TemplateView

from .forms import LeadForm
from .models import BlogPost, PublicService, Testimonial
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
