from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from accounts.security import (
    clear_login_attempt,
    get_client_ip,
    is_login_locked,
    normalize_login_email,
    record_failed_login,
)

User = get_user_model()


class UserManagerTests(TestCase):
    def test_create_user_sets_password_and_email(self):
        user = User.objects.create_user(
            email='pessoa@example.com',
            password='segredo-forte-123',
            nome_razao_social='Pessoa Teste',
        )
        self.assertEqual(user.email, 'pessoa@example.com')
        self.assertTrue(user.check_password('segredo-forte-123'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password='x', nome_razao_social='Sem Email')

    def test_create_superuser_flags(self):
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='segredo-forte-123',
            nome_razao_social='Admin',
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, 'adm')


class NormalizeLoginEmailTests(TestCase):
    def test_trims_and_lowercases(self):
        self.assertEqual(normalize_login_email('  Pessoa@Example.COM '), 'pessoa@example.com')

    def test_handles_none(self):
        self.assertEqual(normalize_login_email(None), '')


@override_settings(
    LOGIN_ATTEMPT_LIMIT=3,
    LOGIN_ATTEMPT_WINDOW_MINUTES=15,
    LOGIN_LOCKOUT_MINUTES=15,
)
class LoginLockoutTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.post('/login/')
        self.email = 'alvo@example.com'
        self.ip = get_client_ip(self.request)

    def test_not_locked_below_limit(self):
        record_failed_login(self.request, self.email)
        record_failed_login(self.request, self.email)
        self.assertFalse(is_login_locked(self.email, self.ip))

    def test_locked_when_limit_reached(self):
        for _ in range(3):
            record_failed_login(self.request, self.email)
        self.assertTrue(is_login_locked(self.email, self.ip))

    def test_clear_removes_lock(self):
        for _ in range(3):
            record_failed_login(self.request, self.email)
        self.assertTrue(is_login_locked(self.email, self.ip))

        clear_login_attempt(self.request, self.email)
        self.assertFalse(is_login_locked(self.email, self.ip))


class RolePermissionSetupTests(TestCase):
    def test_setup_roles_gives_admin_all_application_permissions_without_django_admin_access(self):
        admin = User.objects.create_user(
            email='adm@example.com',
            password='segredo-forte-123',
            nome_razao_social='Administrador',
            role='adm',
        )

        from django.core.management import call_command
        call_command('setup_roles', verbosity=0)

        admin.refresh_from_db()
        self.assertFalse(admin.is_staff)
        self.assertFalse(admin.is_superuser)
        self.assertTrue(admin.has_perm('website.change_sitesettings'))
        self.assertTrue(admin.has_perm('website.add_blogpost'))
        self.assertTrue(admin.has_perm('audit.view_auditlog'))
        self.assertTrue(admin.has_perm('ai_assistant.use_ai_assistant'))
        self.assertTrue(admin.has_perm('operations.change_workorder'))

    def test_setup_roles_allows_technician_to_use_technical_flow(self):
        technician = User.objects.create_user(
            email='tecnico.perm@example.com',
            password='segredo-forte-123',
            nome_razao_social='Técnico Permissão',
            role='tecnico',
        )

        from django.core.management import call_command
        call_command('setup_roles', verbosity=0)

        technician.refresh_from_db()
        self.assertTrue(technician.has_perm('operations.view_workorder'))
        self.assertTrue(technician.has_perm('operations.change_workorder'))
        self.assertTrue(technician.has_perm('operations.add_vehiclecheckin'))
        self.assertTrue(technician.has_perm('operations.change_vehiclecheckin'))
        self.assertTrue(technician.has_perm('ai_assistant.use_ai_assistant'))
        self.assertFalse(technician.has_perm('accounts.change_user'))


class LoginRedirectTests(TestCase):
    def test_logged_user_cannot_access_login_page(self):
        user = User.objects.create_user(
            email='logado@example.com',
            password='segredo-forte-123',
            nome_razao_social='Usuário Logado',
        )
        self.client.force_login(user)

        response = self.client.get('/login/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/dashboard/')
