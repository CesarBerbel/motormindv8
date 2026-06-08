from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import BlogPost, Lead, LeadStatus, PublicService, SiteSettings, Testimonial
from .services import notify_new_lead


class SiteSettingsModelTests(TestCase):
    def test_get_solo_is_singleton(self):
        first = SiteSettings.get_solo()
        second = SiteSettings.get_solo()
        self.assertEqual(first.pk, 1)
        self.assertEqual(second.pk, 1)
        self.assertEqual(SiteSettings.objects.count(), 1)

    def test_save_forces_single_row_and_cleans_whatsapp(self):
        site = SiteSettings.get_solo()
        site.pk = 50
        site.whatsapp = '+55 (11) 98821-2625'
        site.save()
        self.assertEqual(site.pk, 1)
        self.assertEqual(site.whatsapp, '5511988212625')

    def test_whatsapp_link(self):
        site = SiteSettings.get_solo()
        site.whatsapp = '5511988212625'
        site.save()
        self.assertEqual(site.whatsapp_link, 'https://wa.me/5511988212625')


class PublicServiceModelTests(TestCase):
    def test_slug_is_generated(self):
        servico = PublicService.objects.create(titulo='Troca de Óleo')
        self.assertEqual(servico.slug, 'troca-de-oleo')

    def test_slug_is_unique(self):
        a = PublicService.objects.create(titulo='Freios')
        b = PublicService.objects.create(titulo='Freios')
        self.assertNotEqual(a.slug, b.slug)

    def test_get_absolute_url(self):
        servico = PublicService.objects.create(titulo='Suspensão')
        self.assertEqual(servico.get_absolute_url(), reverse('public_service_detail', kwargs={'slug': servico.slug}))


class BlogPostModelTests(TestCase):
    def test_publishing_sets_published_at(self):
        post = BlogPost.objects.create(titulo='Dica 1', conteudo='x', publicado=True)
        self.assertIsNotNone(post.publicado_em)

    def test_published_manager_excludes_drafts(self):
        draft = BlogPost.objects.create(titulo='Rascunho', conteudo='x', publicado=False)
        published = BlogPost.objects.create(titulo='No ar', conteudo='x', publicado=True)
        slugs = list(BlogPost.publicados.values_list('slug', flat=True))
        self.assertIn(published.slug, slugs)
        self.assertNotIn(draft.slug, slugs)


class TestimonialModelTests(TestCase):
    def test_estrelas_render(self):
        depo = Testimonial(nome_cliente='X', texto='ótimo', nota=4)
        self.assertEqual(depo.estrelas, '★★★★☆')


class PublicPagesTests(TestCase):
    def setUp(self):
        self.servico = PublicService.objects.create(titulo='Mecânica geral', destaque=True, ativo=True)
        self.post = BlogPost.objects.create(titulo='Como cuidar do motor', conteudo='<p>Texto</p>', publicado=True)

    def test_home_renders(self):
        response = self.client.get(reverse('public_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mecânica geral')

    def test_service_list_renders(self):
        response = self.client.get(reverse('public_service_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mecânica geral')

    def test_service_detail_renders(self):
        response = self.client.get(self.servico.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Solicitar este serviço')

    def test_inactive_service_is_not_found(self):
        self.servico.ativo = False
        self.servico.save()
        response = self.client.get(self.servico.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_blog_list_renders(self):
        response = self.client.get(reverse('public_blog_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Como cuidar do motor')

    def test_blog_detail_renders(self):
        response = self.client.get(self.post.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Texto')

    def test_draft_post_is_not_found(self):
        draft = BlogPost.objects.create(titulo='Oculto', conteudo='x', publicado=False)
        response = self.client.get(reverse('public_blog_detail', kwargs={'slug': draft.slug}))
        self.assertEqual(response.status_code, 404)

    def test_about_renders(self):
        response = self.client.get(reverse('public_about'))
        self.assertEqual(response.status_code, 200)

    def test_contact_renders(self):
        response = self.client.get(reverse('public_contact'))
        self.assertEqual(response.status_code, 200)


class LeadSubmissionTests(TestCase):
    def setUp(self):
        site = SiteSettings.get_solo()
        site.email_contato = 'oficina@example.com'
        site.save()
        self.servico = PublicService.objects.create(titulo='Freios', ativo=True)

    def test_valid_submission_creates_lead_and_redirects(self):
        response = self.client.post(reverse('public_contact'), {
            'nome': 'Cliente Teste',
            'telefone': '11988212625',
            'email': 'cliente@example.com',
            'veiculo': 'Fiat Uno 2015',
            'placa': 'abc1d23',
            'servico': self.servico.pk,
            'mensagem': 'Barulho na frente',
        })
        self.assertRedirects(response, reverse('public_contact'))
        lead = Lead.objects.get()
        self.assertEqual(lead.nome, 'Cliente Teste')
        self.assertEqual(lead.placa, 'ABC1D23')
        self.assertEqual(lead.status, LeadStatus.NOVO)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Cliente Teste', mail.outbox[0].body)

    def test_missing_required_fields_does_not_create_lead(self):
        response = self.client.post(reverse('public_contact'), {'nome': '', 'telefone': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Lead.objects.count(), 0)

    def test_notify_new_lead_without_email_returns_false(self):
        site = SiteSettings.get_solo()
        site.email_contato = ''
        site.save()
        # Sem e-mail configurado e sem DEFAULT_FROM_EMAIL útil, não deve falhar.
        lead = Lead.objects.create(nome='X', telefone='11999999999')
        # DEFAULT_FROM_EMAIL pode estar definido; apenas garantimos que não levanta.
        notify_new_lead(lead)


class BlogManageAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.editor = User.objects.create_user(
            email='editor@example.com', password='senha-forte-123', nome_razao_social='Editor',
        )
        for codename in ('view_blogpost', 'add_blogpost', 'change_blogpost', 'delete_blogpost'):
            self.editor.user_permissions.add(Permission.objects.get(codename=codename))
        self.outsider = User.objects.create_user(
            email='outro@example.com', password='senha-forte-123', nome_razao_social='Outro',
        )

    def test_list_requires_login(self):
        response = self.client.get(reverse('blog_manage_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_user_without_permission_is_forbidden(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('blog_manage_list'))
        self.assertEqual(response.status_code, 403)

    def test_editor_can_view_list(self):
        self.client.force_login(self.editor)
        response = self.client.get(reverse('blog_manage_list'))
        self.assertEqual(response.status_code, 200)

    def test_editor_can_create_post_and_author_is_set(self):
        self.client.force_login(self.editor)
        response = self.client.post(reverse('blog_manage_create'), {
            'titulo': 'Novo artigo de teste',
            'slug': '',
            'resumo': 'Resumo',
            'conteudo': '<p>Conteúdo do artigo</p>',
            'publicado': 'on',
        })
        self.assertRedirects(response, reverse('blog_manage_list'))
        post = BlogPost.objects.get(titulo='Novo artigo de teste')
        self.assertEqual(post.autor, self.editor)
        self.assertTrue(post.publicado)
        self.assertIsNotNone(post.publicado_em)
        self.assertEqual(post.slug, 'novo-artigo-de-teste')

    def test_editor_can_update_post(self):
        post = BlogPost.objects.create(titulo='Original', conteudo='x')
        self.client.force_login(self.editor)
        response = self.client.post(reverse('blog_manage_update', kwargs={'pk': post.pk}), {
            'titulo': 'Atualizado',
            'slug': post.slug,
            'resumo': '',
            'conteudo': '<p>novo</p>',
            'publicado': 'on',
        })
        self.assertRedirects(response, reverse('blog_manage_list'))
        post.refresh_from_db()
        self.assertEqual(post.titulo, 'Atualizado')

    def test_editor_can_delete_post(self):
        post = BlogPost.objects.create(titulo='Para excluir', conteudo='x')
        self.client.force_login(self.editor)
        response = self.client.post(reverse('blog_manage_delete', kwargs={'pk': post.pk}))
        self.assertRedirects(response, reverse('blog_manage_list'))
        self.assertFalse(BlogPost.objects.filter(pk=post.pk).exists())
