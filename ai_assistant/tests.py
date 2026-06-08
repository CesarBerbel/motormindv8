from django.core.cache import cache
from django.db import connection
from django.test import SimpleTestCase, TestCase

from ai_assistant.models import AIAssistantAction, AISettings
from ai_assistant import services


class AISettingsSingletonTests(TestCase):
    def test_get_solo_always_returns_pk_1(self):
        settings = AISettings.get_solo()
        self.assertEqual(settings.pk, 1)

    def test_save_forces_single_row(self):
        AISettings.get_solo()
        extra = AISettings(provedor='openai')
        extra.save()
        self.assertEqual(AISettings.objects.count(), 1)

    def test_delete_clears_secrets_and_deactivates(self):
        settings = AISettings.get_solo()
        settings.api_key = 'sk-secret-123456'
        settings.endpoint_base = 'https://example.com'
        settings.ativo = True
        settings.save()
        settings.delete()

        settings.refresh_from_db()
        self.assertFalse(settings.ativo)
        self.assertEqual(settings.api_key, '')
        self.assertEqual(settings.endpoint_base, '')


class ApiKeyEncryptionTests(TestCase):
    def _raw_api_key(self):
        table = AISettings._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT api_key FROM {table} WHERE id = 1')
            return cursor.fetchone()[0]

    def test_api_key_roundtrips_through_orm(self):
        settings = AISettings.get_solo()
        settings.api_key = 'sk-super-secret-key'
        settings.save()

        reloaded = AISettings.objects.get(pk=1)
        self.assertEqual(reloaded.api_key, 'sk-super-secret-key')

    def test_api_key_is_encrypted_at_rest(self):
        settings = AISettings.get_solo()
        settings.api_key = 'sk-super-secret-key'
        settings.save()

        stored = self._raw_api_key()
        self.assertNotEqual(stored, 'sk-super-secret-key')
        self.assertNotIn('sk-super-secret-key', stored)
        # Fernet tokens sao base64 urlsafe e comecam por 'gAAAA'.
        self.assertTrue(stored.startswith('gAAAA'))

    def test_empty_api_key_stays_empty(self):
        settings = AISettings.get_solo()
        settings.api_key = ''
        settings.save()
        self.assertEqual(self._raw_api_key(), '')
        self.assertEqual(AISettings.objects.get(pk=1).api_key, '')

    def test_legacy_plaintext_value_is_readable(self):
        AISettings.get_solo()
        table = AISettings._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                f'UPDATE {table} SET api_key = %s WHERE id = 1', ['legacy-plaintext']
            )

        self.assertEqual(AISettings.objects.get(pk=1).api_key, 'legacy-plaintext')


class ValidateProviderUrlTests(SimpleTestCase):
    def test_https_is_allowed(self):
        self.assertEqual(
            services.validate_provider_url('https://api.openai.com/v1'),
            'https://api.openai.com/v1',
        )

    def test_http_loopback_is_allowed(self):
        services.validate_provider_url('http://127.0.0.1:11434/api/generate')
        services.validate_provider_url('http://localhost:11434')

    def test_http_external_is_rejected(self):
        with self.assertRaises(services.AIServiceError):
            services.validate_provider_url('http://api.exemplo.com')

    def test_non_http_scheme_is_rejected(self):
        for url in ('file:///etc/passwd', 'ftp://x', 'gopher://x'):
            with self.assertRaises(services.AIServiceError):
                services.validate_provider_url(url)

    def test_empty_is_rejected(self):
        with self.assertRaises(services.AIServiceError):
            services.validate_provider_url('')


class ClampTimeoutTests(SimpleTestCase):
    def test_within_range_is_preserved(self):
        self.assertEqual(services.clamp_timeout(5), 5)

    def test_above_max_is_capped(self):
        self.assertEqual(services.clamp_timeout(999), services.MAX_TIMEOUT)

    def test_zero_falls_back_to_default(self):
        self.assertEqual(services.clamp_timeout(0), services.DEFAULT_TIMEOUT)

    def test_invalid_falls_back_to_default(self):
        self.assertEqual(services.clamp_timeout('abc'), services.DEFAULT_TIMEOUT)

    def test_negative_is_floored_to_min(self):
        self.assertEqual(services.clamp_timeout(-3), services.MIN_TIMEOUT)


class MaskSecretTests(SimpleTestCase):
    def test_empty(self):
        self.assertEqual(services.mask_secret(''), '')

    def test_short(self):
        self.assertEqual(services.mask_secret('1234'), '••••')

    def test_long(self):
        self.assertEqual(services.mask_secret('sk-secret-123456'), 'sk-s••••3456')


class EnsureActionEnabledTests(SimpleTestCase):
    def test_os_action_blocked_when_disabled(self):
        settings = AISettings(habilitar_os=False, habilitar_mensagens=True)
        with self.assertRaises(services.AIServiceError):
            services.ensure_action_enabled(settings, AIAssistantAction.IMPROVE_PROBLEM)

    def test_message_action_blocked_when_disabled(self):
        settings = AISettings(habilitar_os=True, habilitar_mensagens=False)
        with self.assertRaises(services.AIServiceError):
            services.ensure_action_enabled(settings, AIAssistantAction.EMAIL_TEMPLATE)

    def test_general_action_always_allowed(self):
        settings = AISettings(habilitar_os=False, habilitar_mensagens=False)
        services.ensure_action_enabled(settings, AIAssistantAction.GENERAL)


class RateLimitTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_requests_within_limit_are_allowed(self):
        user = type('U', (), {'pk': 555})()
        for _ in range(3):
            self.assertTrue(services.check_ai_rate_limit(user, limit=3, window=60))

    def test_request_over_limit_is_blocked(self):
        user = type('U', (), {'pk': 777})()
        for _ in range(3):
            services.check_ai_rate_limit(user, limit=3, window=60)
        self.assertFalse(services.check_ai_rate_limit(user, limit=3, window=60))

    def test_limit_is_per_user(self):
        user_a = type('U', (), {'pk': 1})()
        user_b = type('U', (), {'pk': 2})()
        for _ in range(3):
            services.check_ai_rate_limit(user_a, limit=3, window=60)
        self.assertTrue(services.check_ai_rate_limit(user_b, limit=3, window=60))


class MaskedApiKeyTests(TestCase):
    def test_not_configured_when_empty(self):
        settings = AISettings(api_key='')
        self.assertEqual(settings.masked_api_key, 'Não configurada')

    def test_masks_long_key(self):
        settings = AISettings(api_key='sk-secret-123456')
        self.assertEqual(settings.masked_api_key, 'sk-s••••3456')

    def test_short_key_fully_masked(self):
        settings = AISettings(api_key='1234')
        self.assertEqual(settings.masked_api_key, '••••')
