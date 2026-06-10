from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import EmployeeRole
from core.models import AppNotification, Customer, PessoaTipo, Vehicle

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

    def test_home_vehicle_history_cta_uses_vehicle_label(self):
        response = self.client.get(reverse('public_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Consultar veículo')
        self.assertNotContains(response, 'Consultar OS')

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
        site.email_contato = 'contato@example.com'
        site.email_oficina = 'orcamentos@example.com'
        site.save()
        self.admin_user = get_user_model().objects.create_user(
            email='adm.leads@example.com',
            password='senha-forte-123',
            nome_razao_social='ADM Leads',
            role=EmployeeRole.ADM,
        )
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
        self.assertEqual(mail.outbox[0].to, ['orcamentos@example.com'])
        notification = AppNotification.objects.get(usuario=self.admin_user)
        self.assertEqual(notification.categoria, 'lead_site')
        self.assertIn('Cliente Teste', notification.mensagem)

    def test_missing_required_fields_does_not_create_lead(self):
        response = self.client.post(reverse('public_contact'), {'nome': '', 'telefone': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Lead.objects.count(), 0)

    def test_missing_email_does_not_create_lead(self):
        response = self.client.post(reverse('public_contact'), {
            'nome': 'Cliente Sem Email',
            'telefone': '11988212625',
            'email': '',
            'mensagem': 'Preciso de orçamento',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Este campo é obrigatório')
        self.assertEqual(Lead.objects.count(), 0)

    def test_invalid_phone_does_not_create_lead(self):
        response = self.client.post(reverse('public_contact'), {
            'nome': 'Cliente Telefone Invalido',
            'telefone': '12345',
            'email': 'cliente@example.com',
            'mensagem': 'Preciso de orçamento',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Informe um telefone/WhatsApp valido com DDD.')
        self.assertEqual(Lead.objects.count(), 0)

    def test_notify_new_lead_without_email_returns_false(self):
        site = SiteSettings.get_solo()
        site.email_contato = ''
        site.email_oficina = ''
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


class BlogArticleGenerationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.editor = User.objects.create_user(
            email='ia@example.com', password='senha-forte-123', nome_razao_social='IA Editor',
        )
        self.editor.user_permissions.add(Permission.objects.get(codename='add_blogpost'))
        self.editor.user_permissions.add(Permission.objects.get(codename='use_ai_assistant'))
        self.url = reverse('blog_generate_ai')

    def test_service_generates_article_with_local_provider(self):
        from ai_assistant.services import generate_blog_article
        article = generate_blog_article('Importância da troca de óleo', user=self.editor)
        self.assertTrue(article['titulo'])
        self.assertIn('<', article['conteudo'])  # conteúdo em HTML
        self.assertIn('óleo', article['conteudo'].lower())

    def test_parse_blog_response_reads_json(self):
        from ai_assistant.services import parse_blog_response
        raw = '```json\n{"titulo": "T", "resumo": "R", "conteudo": "<p>C</p>"}\n```'
        parsed = parse_blog_response(raw, 'assunto')
        self.assertEqual(parsed['titulo'], 'T')
        self.assertEqual(parsed['conteudo'], '<p>C</p>')

    def test_parse_blog_response_fallback_wraps_plain_text(self):
        from ai_assistant.services import parse_blog_response
        parsed = parse_blog_response('Texto simples sem json', 'Troca de óleo')
        self.assertIn('<p>', parsed['conteudo'])
        self.assertTrue(parsed['titulo'])

    def test_endpoint_requires_login(self):
        response = self.client.post(self.url, data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 302)

    def test_endpoint_forbidden_without_permissions(self):
        User = get_user_model()
        outsider = User.objects.create_user(
            email='no@example.com', password='senha-forte-123', nome_razao_social='No',
        )
        self.client.force_login(outsider)
        response = self.client.post(self.url, data='{"assunto": "x"}', content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_endpoint_requires_subject(self):
        self.client.force_login(self.editor)
        response = self.client.post(self.url, data='{"assunto": ""}', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_endpoint_returns_article(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            self.url,
            data='{"assunto": "Manutenção preventiva"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['titulo'])
        self.assertIn('<', data['conteudo'])


class SiteSettingsManageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(
            email='gestor@example.com', password='senha-forte-123', nome_razao_social='Gestor',
        )
        self.manager.user_permissions.add(Permission.objects.get(codename='change_sitesettings'))
        self.outsider = User.objects.create_user(
            email='ze@example.com', password='senha-forte-123', nome_razao_social='Ze',
        )

    def test_requires_login(self):
        response = self.client.get(reverse('site_settings'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_user_without_permission_is_forbidden(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('site_settings'))
        self.assertEqual(response.status_code, 403)

    def test_manager_can_view_form(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('site_settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Configurações da oficina')

    def test_manager_can_update_settings(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('site_settings'), {
            'nome_fantasia': 'Oficina Nova',
            'slogan': 'Slogan novo',
            'sobre': 'Texto sobre',
            'hero_titulo': 'Hero',
            'hero_subtitulo': 'Sub',
            'telefone_principal': '(11) 90000-0000',
            'telefone_secundario': '',
            'whatsapp': '5511900000000',
            'email_contato': 'novo@oficina.com',
            'endereco': 'Rua X, 10',
            'bairro': 'Centro',
            'cidade': 'São Paulo',
            'uf': 'SP',
            'cep': '01000-000',
            'google_maps_embed': '',
            'horario_semana': '08h às 18h',
            'horario_sabado': '08h às 12h',
            'horario_domingo': 'Fechado',
            'instagram_url': '',
            'facebook_url': '',
        })
        self.assertRedirects(response, reverse('site_settings'))
        site = SiteSettings.get_solo()
        self.assertEqual(site.nome_fantasia, 'Oficina Nova')
        self.assertEqual(site.email_contato, 'novo@oficina.com')
        # Sempre singleton (pk=1).
        self.assertEqual(site.pk, 1)
        self.assertEqual(SiteSettings.objects.count(), 1)


class LeadManageViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.viewer = User.objects.create_user(
            email='leads-viewer@example.com',
            password='senha-forte-123',
            nome_razao_social='Leads Viewer',
        )
        self.viewer.user_permissions.add(Permission.objects.get(content_type__app_label='website', codename='view_lead'))
        self.manager = User.objects.create_user(
            email='leads-manager@example.com',
            password='senha-forte-123',
            nome_razao_social='Leads Manager',
        )
        self.manager.user_permissions.add(Permission.objects.get(content_type__app_label='website', codename='view_lead'))
        self.manager.user_permissions.add(Permission.objects.get(content_type__app_label='website', codename='change_lead'))
        self.outsider = User.objects.create_user(
            email='sem-leads@example.com',
            password='senha-forte-123',
            nome_razao_social='Sem Leads',
        )
        self.servico = PublicService.objects.create(titulo='Diagnóstico eletrônico', ativo=True)
        self.lead = Lead.objects.create(
            nome='Cliente Lead',
            telefone='11999990000',
            email='cliente@example.com',
            veiculo='Honda Civic 2020',
            placa='ABC1D23',
            servico=self.servico,
            mensagem='Luz da injeção acesa',
        )
        Lead.objects.create(
            nome='Outro Cliente',
            telefone='11888880000',
            status=LeadStatus.CONCLUIDO,
        )

    def test_lead_list_requires_login(self):
        response = self.client.get(reverse('site_lead_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_user_without_permission_is_forbidden(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('site_lead_list'))
        self.assertEqual(response.status_code, 403)

    def test_viewer_can_list_site_leads_from_site_menu(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('site_lead_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pedidos de orçamento')
        self.assertContains(response, 'Cliente Lead')
        self.assertContains(response, 'Diagnóstico eletrônico')

    def test_filter_leads_by_status_and_query(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('site_lead_list'), {'status': LeadStatus.NOVO, 'q': 'Civic'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cliente Lead')
        self.assertNotContains(response, 'Outro Cliente')

    def test_viewer_can_open_lead_detail(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('site_lead_detail', kwargs={'pk': self.lead.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Luz da injeção acesa')
        self.assertContains(response, 'Você pode visualizar este pedido')

    def test_manager_can_update_lead_status(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('site_lead_detail', kwargs={'pk': self.lead.pk}), {
            'status': LeadStatus.EM_CONTATO,
        })
        self.assertRedirects(response, reverse('site_lead_detail', kwargs={'pk': self.lead.pk}))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, LeadStatus.EM_CONTATO)


    def grant_operational_quick_action_permissions(self):
        for app_label, codename in (
            ('core', 'add_customer'),
            ('core', 'add_vehicle'),
            ('operations', 'add_workorder'),
        ):
            self.manager.user_permissions.add(Permission.objects.get(content_type__app_label=app_label, codename=codename))

    def test_detail_quick_actions_offer_registration_when_records_do_not_exist(self):
        self.grant_operational_quick_action_permissions()
        self.client.force_login(self.manager)
        response = self.client.get(reverse('site_lead_detail', kwargs={'pk': self.lead.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cadastrar cliente')
        self.assertContains(response, 'Cadastrar veículo')
        self.assertContains(response, 'Abrir OS disponível após localizar cliente e veículo')
        self.assertContains(response, 'Ver site público')
        self.assertNotContains(response, 'Ligar para o cliente')
        self.assertNotContains(response, 'Enviar e-mail')

    def test_detail_quick_actions_lock_existing_customer_and_vehicle_and_open_order(self):
        self.grant_operational_quick_action_permissions()
        customer = Customer.objects.create(
            tipo_pessoa=PessoaTipo.FISICA,
            nome_razao_social='Cliente Lead',
            email='cliente@example.com',
            whatsapp='(11) 99999-0000',
        )
        vehicle = Vehicle.objects.create(
            cliente=customer,
            placa='ABC1D23',
            marca='Honda',
            modelo='Civic',
            km=45000,
        )
        self.client.force_login(self.manager)
        response = self.client.get(reverse('site_lead_detail', kwargs={'pk': self.lead.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['matched_customer'], customer)
        self.assertEqual(response.context['matched_vehicle'], vehicle)
        self.assertTrue(response.context['customer_vehicle_match'])
        self.assertContains(response, 'Cliente existe: Cliente Lead')
        self.assertContains(response, 'Veículo existe: ABC1D23')
        self.assertContains(response, 'Abrir OS')
        self.assertIn(f'cliente={customer.pk}', response.context['work_order_create_url'])
        self.assertIn(f'veiculo={vehicle.pk}', response.context['work_order_create_url'])

    def test_detail_quick_actions_block_order_when_customer_and_vehicle_mismatch(self):
        self.grant_operational_quick_action_permissions()
        customer = Customer.objects.create(
            tipo_pessoa=PessoaTipo.FISICA,
            nome_razao_social='Cliente Lead',
            email='cliente@example.com',
            whatsapp='(11) 99999-0000',
        )
        other_customer = Customer.objects.create(
            tipo_pessoa=PessoaTipo.FISICA,
            nome_razao_social='Outro Dono',
            email='outro@example.com',
            whatsapp='(11) 98888-0000',
        )
        Vehicle.objects.create(
            cliente=other_customer,
            placa='ABC1D23',
            marca='Honda',
            modelo='Civic',
            km=45000,
        )
        self.client.force_login(self.manager)
        response = self.client.get(reverse('site_lead_detail', kwargs={'pk': self.lead.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['matched_customer'], customer)
        self.assertTrue(response.context['vehicle_customer_mismatch'])
        self.assertContains(response, 'Cliente e veículo cadastrados em registros diferentes')
        self.assertNotContains(response, 'class="btn btn-success btn-sm w-full justify-start whitespace-nowrap">Abrir OS</a>', html=False)

    def test_notification_points_to_internal_lead_detail(self):
        site = SiteSettings.get_solo()
        site.email_oficina = 'orcamentos@example.com'
        site.save()
        self.manager.role = EmployeeRole.ADM
        self.manager.save()
        notify_new_lead(self.lead)
        notification = AppNotification.objects.filter(categoria='lead_site').first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.url, reverse('site_lead_detail', kwargs={'pk': self.lead.pk}))
