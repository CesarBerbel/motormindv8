from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Customer, PessoaTipo
from .models import AuditAction, AuditCategory, AuditLog

User = get_user_model()


def _user(email='u@example.com', **extra):
    return User.objects.create_user(email=email, password='senha-forte-123', nome_razao_social='User', **extra)


class ModelAuditSignalTests(TestCase):
    def test_create_is_audited(self):
        AuditLog.objects.all().delete()
        c = Customer.objects.create(tipo_pessoa=PessoaTipo.FISICA, nome_razao_social='Ana', email='ana@example.com')
        log = AuditLog.objects.filter(acao=AuditAction.CRIAR, objeto_modelo='Customer', objeto_id=str(c.pk)).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.categoria, AuditCategory.DADOS)

    def test_update_records_changes(self):
        c = Customer.objects.create(tipo_pessoa=PessoaTipo.FISICA, nome_razao_social='Ana', email='ana@example.com')
        AuditLog.objects.all().delete()
        c.nome_razao_social = 'Ana Maria'
        c.save()
        log = AuditLog.objects.filter(acao=AuditAction.EDITAR, objeto_id=str(c.pk)).first()
        self.assertIsNotNone(log)
        self.assertIn('nome_razao_social', log.alteracoes)
        self.assertEqual(log.alteracoes['nome_razao_social']['de'], 'Ana')
        self.assertEqual(log.alteracoes['nome_razao_social']['para'], 'Ana Maria')

    def test_soft_delete_is_audited_as_logical_deletion(self):
        c = Customer.objects.create(tipo_pessoa=PessoaTipo.FISICA, nome_razao_social='Ana', email='ana@example.com')
        AuditLog.objects.all().delete()
        c.soft_delete()
        log = AuditLog.objects.filter(objeto_id=str(c.pk)).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.acao, AuditAction.EXCLUIR)
        self.assertIn('excluido_em', log.alteracoes)

    def test_restore_is_audited(self):
        c = Customer.objects.create(tipo_pessoa=PessoaTipo.FISICA, nome_razao_social='Ana', email='ana@example.com')
        c.soft_delete()
        AuditLog.objects.all().delete()
        c.restore()
        log = AuditLog.objects.filter(objeto_id=str(c.pk)).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.acao, AuditAction.RESTAURAR)

    def test_unchanged_save_is_not_audited(self):
        c = Customer.objects.create(tipo_pessoa=PessoaTipo.FISICA, nome_razao_social='Ana', email='ana@example.com')
        AuditLog.objects.all().delete()
        c.save()  # nada relevante muda (apenas atualizado_em, que é ignorado)
        self.assertFalse(AuditLog.objects.filter(acao=AuditAction.EDITAR).exists())

    def test_sensitive_field_is_masked(self):
        u = _user(email='sec@example.com')
        AuditLog.objects.all().delete()
        u.set_password('outra-senha-forte')
        u.save()
        log = AuditLog.objects.filter(objeto_modelo='User', objeto_id=str(u.pk), acao=AuditAction.EDITAR).first()
        self.assertIsNotNone(log)
        self.assertIn('password', log.alteracoes)
        self.assertEqual(log.alteracoes['password']['para'], '***')


class AuthAuditTests(TestCase):
    def test_successful_login_is_audited(self):
        _user(email='login@example.com')
        AuditLog.objects.all().delete()
        ok = self.client.login(username='login@example.com', password='senha-forte-123')
        self.assertTrue(ok)
        self.assertTrue(AuditLog.objects.filter(acao=AuditAction.LOGIN, usuario_email='login@example.com').exists())

    def test_failed_login_is_audited(self):
        _user(email='login@example.com')
        AuditLog.objects.all().delete()
        ok = self.client.login(username='login@example.com', password='senha-errada')
        self.assertFalse(ok)
        self.assertTrue(AuditLog.objects.filter(acao=AuditAction.LOGIN_FALHA).exists())


class RequestAuditMiddlewareTests(TestCase):
    def test_authenticated_page_view_is_audited(self):
        u = _user(email='nav@example.com')
        self.client.force_login(u)
        AuditLog.objects.all().delete()
        self.client.get('/dashboard/')
        log = AuditLog.objects.filter(acao=AuditAction.ACESSO, caminho='/dashboard/').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.usuario_id, u.pk)

    def test_static_like_paths_are_not_audited(self):
        u = _user(email='nav2@example.com')
        self.client.force_login(u)
        AuditLog.objects.all().delete()
        self.client.get('/healthz/')
        self.assertFalse(AuditLog.objects.filter(caminho='/healthz/').exists())


class AuditListViewTests(TestCase):
    def setUp(self):
        self.viewer = _user(email='viewer@example.com')
        self.viewer.user_permissions.add(Permission.objects.get(codename='view_auditlog'))
        self.outsider = _user(email='out@example.com')

    def test_requires_login(self):
        response = self.client.get(reverse('audit_list'))
        self.assertEqual(response.status_code, 302)

    def test_forbidden_without_permission(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse('audit_list')).status_code, 403)

    def test_viewer_can_open_and_filter(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse('audit_list')).status_code, 200)
        self.assertEqual(
            self.client.get(reverse('audit_list'), {'categoria': 'autenticacao', 'acao': 'login'}).status_code,
            200,
        )


class AuditPruneCommandTests(TestCase):
    def test_prune_removes_old_records(self):
        AuditLog.objects.all().delete()
        recente = AuditLog.objects.create(acao=AuditAction.ACESSO, categoria=AuditCategory.NAVEGACAO)
        antigo = AuditLog.objects.create(acao=AuditAction.ACESSO, categoria=AuditCategory.NAVEGACAO)
        AuditLog.objects.filter(pk=antigo.pk).update(criado_em=timezone.now() - timezone.timedelta(days=400))
        call_command('audit_prune', '--dias=365')
        self.assertTrue(AuditLog.objects.filter(pk=recente.pk).exists())
        self.assertFalse(AuditLog.objects.filter(pk=antigo.pk).exists())
