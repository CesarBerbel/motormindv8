from datetime import date
from types import SimpleNamespace

from django.core import mail
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from core.models import Customer, PessoaTipo, Supplier
from .models import (
    MessageLog,
    MessageSettings,
    MessageStatus,
    MessageTemplate,
    MessageTemplateType,
    MessageType,
    RecipientKind,
    WorkOrderStatusMessageRule,
    WORK_ORDER_STATUS_CHOICES,
    get_work_order_status_label,
)
from . import services
from .services import (
    Recipient,
    already_sent_anniversary,
    build_anniversary_email,
    build_recipient_context,
    build_work_order_approval_url,
    build_work_order_status_context,
    customer_has_anniversary_today,
    ensure_work_order_status_message_rules,
    get_anniversary_customers,
    get_anniversary_message_type,
    get_anniversary_template_type,
    get_default_message_template,
    get_disabled_anniversary_features,
    get_public_base_url,
    is_anniversary_enabled_for_customer,
    render_message_content,
    render_subject_string,
    render_template_string,
    send_anniversary_messages,
    send_logged_email,
    send_manual_message,
    send_work_order_status_change_message,
)


def _physical_customer(**kwargs):
    defaults = {
        'tipo_pessoa': PessoaTipo.FISICA,
        'nome_razao_social': 'João da Silva',
        'email': 'joao@example.com',
        'data_nascimento_fundacao': date(1990, 6, 8),
    }
    defaults.update(kwargs)
    return Customer.objects.create(**defaults)


def _legal_customer(**kwargs):
    defaults = {
        'tipo_pessoa': PessoaTipo.JURIDICA,
        'nome_razao_social': 'Oficina LTDA',
        'email': 'contato@oficina.com',
        'data_nascimento_fundacao': date(2010, 6, 8),
    }
    defaults.update(kwargs)
    return Customer.objects.create(**defaults)


# --------------------------------------------------------------------------- #
# Pure helpers (no database).
# --------------------------------------------------------------------------- #
class RenderHelpersTests(SimpleTestCase):
    def test_render_template_string_substitutes_context(self):
        result = render_template_string('Olá, {{ nome }}!', {'nome': 'Ana'})
        self.assertEqual(result, 'Olá, Ana!')

    def test_render_template_string_handles_empty_template(self):
        self.assertEqual(render_template_string('', {}), '')
        self.assertEqual(render_template_string(None, {}), '')

    def test_render_subject_string_collapses_newlines(self):
        rendered = render_subject_string('Linha 1\nLinha 2', {})
        self.assertEqual(rendered, 'Linha 1 Linha 2')


class RecipientTests(SimpleTestCase):
    def test_recipient_exposes_object_fields(self):
        obj = SimpleNamespace(
            email='x@example.com',
            nome_razao_social='Fulano',
            tipo_pessoa=PessoaTipo.FISICA,
        )
        recipient = Recipient(kind=RecipientKind.CUSTOMER, obj=obj)
        self.assertEqual(recipient.email, 'x@example.com')
        self.assertEqual(recipient.name, 'Fulano')
        self.assertEqual(recipient.tipo_pessoa, PessoaTipo.FISICA)

    def test_build_recipient_context_for_customer(self):
        obj = SimpleNamespace(
            email='c@example.com',
            nome_razao_social='Cliente',
            tipo_pessoa=PessoaTipo.FISICA,
        )
        recipient = Recipient(kind=RecipientKind.CUSTOMER, obj=obj)
        context = build_recipient_context(recipient, target_date=date(2026, 6, 8))
        self.assertEqual(context['cliente'], obj)
        self.assertIsNone(context['fornecedor'])
        self.assertEqual(context['nome'], 'Cliente')
        self.assertEqual(context['data_envio'], date(2026, 6, 8))

    def test_build_recipient_context_for_supplier(self):
        obj = SimpleNamespace(
            email='f@example.com',
            nome_razao_social='Fornecedor',
            tipo_pessoa=PessoaTipo.JURIDICA,
        )
        recipient = Recipient(kind=RecipientKind.SUPPLIER, obj=obj)
        context = build_recipient_context(recipient)
        self.assertIsNone(context['cliente'])
        self.assertEqual(context['fornecedor'], obj)


class AnniversaryClassificationTests(SimpleTestCase):
    def test_message_type_depends_on_person_type(self):
        fisica = SimpleNamespace(tipo_pessoa=PessoaTipo.FISICA)
        juridica = SimpleNamespace(tipo_pessoa=PessoaTipo.JURIDICA)
        self.assertEqual(get_anniversary_message_type(fisica), MessageType.BIRTHDAY)
        self.assertEqual(get_anniversary_message_type(juridica), MessageType.FOUNDATION)

    def test_template_type_depends_on_person_type(self):
        fisica = SimpleNamespace(tipo_pessoa=PessoaTipo.FISICA)
        juridica = SimpleNamespace(tipo_pessoa=PessoaTipo.JURIDICA)
        self.assertEqual(
            get_anniversary_template_type(fisica),
            MessageTemplateType.CUSTOMER_BIRTHDAY_PHYSICAL,
        )
        self.assertEqual(
            get_anniversary_template_type(juridica),
            MessageTemplateType.CUSTOMER_FOUNDATION_LEGAL,
        )

    def test_customer_has_anniversary_today_matches_month_and_day(self):
        customer = SimpleNamespace(data_nascimento_fundacao=date(1990, 6, 8))
        self.assertTrue(customer_has_anniversary_today(customer, date(2026, 6, 8)))
        self.assertFalse(customer_has_anniversary_today(customer, date(2026, 6, 9)))

    def test_customer_without_date_has_no_anniversary(self):
        customer = SimpleNamespace(data_nascimento_fundacao=None)
        self.assertFalse(customer_has_anniversary_today(customer, date(2026, 6, 8)))


class PublicBaseUrlTests(SimpleTestCase):
    @override_settings(PUBLIC_BASE_URL='https://app.motormind.com/', SITE_URL='')
    def test_uses_public_base_url_first(self):
        self.assertEqual(get_public_base_url(), 'https://app.motormind.com')

    @override_settings(PUBLIC_BASE_URL='', SITE_URL='https://site.example/')
    def test_falls_back_to_site_url(self):
        self.assertEqual(get_public_base_url(), 'https://site.example')

    @override_settings(
        PUBLIC_BASE_URL='',
        SITE_URL='',
        ALLOWED_HOSTS=['*', 'localhost', 'oficina.com'],
        DEBUG=False,
    )
    def test_derives_https_from_allowed_hosts(self):
        self.assertEqual(get_public_base_url(), 'https://oficina.com')

    @override_settings(
        PUBLIC_BASE_URL='',
        SITE_URL='',
        ALLOWED_HOSTS=['localhost', '127.0.0.1'],
    )
    def test_returns_empty_when_only_local_hosts(self):
        self.assertEqual(get_public_base_url(), '')


class ApprovalUrlTests(SimpleTestCase):
    TOKEN = '12345678-1234-1234-1234-1234567890ab'

    @override_settings(PUBLIC_BASE_URL='https://app.example')
    def test_build_approval_url_with_base_url(self):
        budget = SimpleNamespace(token=self.TOKEN)
        url = build_work_order_approval_url(budget)
        self.assertEqual(url, f'https://app.example/aprovacao-os/{self.TOKEN}/')

    def test_build_approval_url_uses_request_when_available(self):
        budget = SimpleNamespace(token=self.TOKEN)
        request = SimpleNamespace(
            build_absolute_uri=lambda path: f'https://req.example{path}'
        )
        url = build_work_order_approval_url(budget, request=request)
        self.assertEqual(url, f'https://req.example/aprovacao-os/{self.TOKEN}/')


class WorkOrderStatusContextTests(SimpleTestCase):
    def _order(self, **kwargs):
        vehicle = SimpleNamespace(placa='ABC1D23', marca='Fiat', modelo='Uno')
        cliente = SimpleNamespace(
            nome_razao_social='Cliente OS',
            email='os@example.com',
            tipo_pessoa=PessoaTipo.FISICA,
        )
        defaults = dict(cliente=cliente, veiculo=vehicle, codigo='OS-00001', status='aberta')
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_context_includes_status_labels_and_vehicle(self):
        order = self._order()
        transition = SimpleNamespace(status_anterior='aberta', status_novo='diagnostico')
        context = build_work_order_status_context(order, transition)
        self.assertEqual(context['status_novo'], 'diagnostico')
        self.assertEqual(context['status_novo_label'], get_work_order_status_label('diagnostico'))
        self.assertEqual(context['veiculo'], 'ABC1D23 - Fiat Uno')
        self.assertIn('diagnóstico', context['mensagem_status'].lower())

    def test_context_handles_missing_vehicle(self):
        order = self._order(veiculo=None)
        transition = SimpleNamespace(status_anterior='', status_novo='aberta')
        context = build_work_order_status_context(order, transition)
        self.assertEqual(context['veiculo'], '-')
        self.assertEqual(context['placa'], '')


# --------------------------------------------------------------------------- #
# Model behaviour (database).
# --------------------------------------------------------------------------- #
class MessageTemplateModelTests(TestCase):
    def test_render_subject_collapses_newlines(self):
        template = MessageTemplate(assunto='Olá\n{{ nome }}', corpo='')
        self.assertEqual(template.render_subject({'nome': 'Ana'}), 'Olá Ana')

    def test_render_body_strips_whitespace(self):
        template = MessageTemplate(assunto='', corpo='  <p>{{ nome }}</p>  ')
        self.assertEqual(template.render_body({'nome': 'Ana'}), '<p>Ana</p>')

    def test_active_manager_excludes_soft_deleted(self):
        template = MessageTemplate.objects.create(
            nome='T', tipo=MessageTemplateType.MANUAL, assunto='s', corpo='c',
        )
        template.soft_delete()
        self.assertFalse(MessageTemplate.objects.filter(pk=template.pk).exists())
        self.assertTrue(MessageTemplate.all_objects.filter(pk=template.pk).exists())

        template.restore()
        self.assertTrue(MessageTemplate.objects.filter(pk=template.pk).exists())

    def test_get_default_message_template_returns_active_default(self):
        MessageTemplate.objects.create(
            nome='Padrão', tipo=MessageTemplateType.MANUAL, assunto='s', corpo='c', padrao=True,
        )
        non_default = MessageTemplate.objects.create(
            nome='Outro', tipo=MessageTemplateType.MANUAL, assunto='s', corpo='c', padrao=False,
        )
        found = get_default_message_template(MessageTemplateType.MANUAL)
        self.assertEqual(found.nome, 'Padrão')
        self.assertNotEqual(found.pk, non_default.pk)


class MessageSettingsModelTests(TestCase):
    def test_get_solo_is_singleton(self):
        first = MessageSettings.get_solo()
        second = MessageSettings.get_solo()
        self.assertEqual(first.pk, 1)
        self.assertEqual(second.pk, 1)
        self.assertEqual(MessageSettings.objects.count(), 1)

    def test_save_forces_single_row(self):
        settings_obj = MessageSettings.get_solo()
        settings_obj.pk = 99
        settings_obj.save()
        self.assertEqual(settings_obj.pk, 1)

    def test_delete_resets_flags_instead_of_removing(self):
        settings_obj = MessageSettings.get_solo()
        settings_obj.enviar_aniversario_pessoa_fisica = True
        settings_obj.enviar_status_os = True
        settings_obj.save()
        settings_obj.delete()
        settings_obj.refresh_from_db()
        self.assertFalse(settings_obj.enviar_aniversario_pessoa_fisica)
        self.assertFalse(settings_obj.enviar_status_os)
        self.assertTrue(MessageSettings.objects.filter(pk=1).exists())


class MessageLogModelTests(TestCase):
    def _log(self, **kwargs):
        defaults = dict(
            tipo=MessageType.MANUAL,
            destinatario_tipo=RecipientKind.CUSTOMER,
            destinatario_id=1,
            destinatario_nome='Cliente',
            destinatario_email='c@example.com',
            assunto='Assunto',
            corpo='Corpo',
        )
        defaults.update(kwargs)
        return MessageLog.objects.create(**defaults)

    def test_mark_sent_sets_status_and_timestamp(self):
        log = self._log()
        log.mark_sent()
        self.assertEqual(log.status, MessageStatus.SENT)
        self.assertIsNotNone(log.enviado_em)

    def test_mark_error_records_message(self):
        log = self._log()
        log.mark_error(ValueError('falhou'))
        self.assertEqual(log.status, MessageStatus.ERROR)
        self.assertEqual(log.erro, 'falhou')


class WorkOrderStatusRuleTests(TestCase):
    def test_ensure_rules_creates_missing_rules(self):
        # Migrations seed the rules; start from an empty table to exercise creation.
        WorkOrderStatusMessageRule.objects.all().delete()
        created = ensure_work_order_status_message_rules()
        self.assertEqual(len(created), len(WORK_ORDER_STATUS_CHOICES))
        self.assertEqual(
            WorkOrderStatusMessageRule.objects.count(),
            len(WORK_ORDER_STATUS_CHOICES),
        )

    def test_ensure_rules_is_idempotent(self):
        # Rules already exist from migrations, so nothing new is created.
        created = ensure_work_order_status_message_rules()
        self.assertEqual(created, [])
        self.assertEqual(
            WorkOrderStatusMessageRule.objects.count(),
            len(WORK_ORDER_STATUS_CHOICES),
        )

    def test_rule_order_follows_status_order(self):
        ensure_work_order_status_message_rules()
        rule = WorkOrderStatusMessageRule.objects.get(status='aberta')
        self.assertEqual(rule.ordem, 1)


# --------------------------------------------------------------------------- #
# Email sending (locmem backend).
# --------------------------------------------------------------------------- #
class SendLoggedEmailTests(TestCase):
    def setUp(self):
        self.customer = _physical_customer()
        self.recipient = Recipient(kind=RecipientKind.CUSTOMER, obj=self.customer)

    def test_send_logged_email_creates_sent_log_and_sends(self):
        log = send_logged_email(
            recipient=self.recipient,
            message_type=MessageType.MANUAL,
            subject='Olá',
            body='<p>Corpo</p>',
        )
        self.assertEqual(log.status, MessageStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.subject, 'Olá')
        self.assertEqual(sent.to, [self.customer.email])
        # HTML alternative attached because body differs from plain text.
        self.assertTrue(sent.alternatives)

    def test_send_logged_email_marks_error_on_failure(self):
        original = services.send_mail

        def boom(*args, **kwargs):
            raise RuntimeError('smtp down')

        services.send_mail = boom
        try:
            log = send_logged_email(
                recipient=self.recipient,
                message_type=MessageType.MANUAL,
                subject='Olá',
                body='Corpo',
            )
        finally:
            services.send_mail = original

        self.assertEqual(log.status, MessageStatus.ERROR)
        self.assertEqual(log.erro, 'smtp down')

    def test_send_manual_message_renders_and_sends_for_each_recipient(self):
        supplier = Supplier.objects.create(
            tipo_pessoa=PessoaTipo.JURIDICA,
            nome_razao_social='Fornecedor SA',
            email='fornecedor@example.com',
        )
        recipients = [
            self.recipient,
            Recipient(kind=RecipientKind.SUPPLIER, obj=supplier),
        ]
        logs = send_manual_message(recipients, 'Oi {{ nome }}', '<p>{{ nome }}</p>')
        self.assertEqual(len(logs), 2)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].subject, 'Oi João da Silva')


class AnniversarySelectionTests(TestCase):
    def setUp(self):
        self.settings = MessageSettings.get_solo()

    def test_is_anniversary_enabled_respects_person_type_flags(self):
        self.settings.enviar_aniversario_pessoa_fisica = False
        self.settings.enviar_fundacao_pessoa_juridica = True
        self.settings.save()
        fisica = _physical_customer()
        juridica = _legal_customer(email='outra@oficina.com')
        self.assertFalse(is_anniversary_enabled_for_customer(fisica, settings=self.settings))
        self.assertTrue(is_anniversary_enabled_for_customer(juridica, settings=self.settings))

    def test_disabled_features_lists_both_when_all_off(self):
        self.settings.enviar_aniversario_pessoa_fisica = False
        self.settings.enviar_fundacao_pessoa_juridica = False
        self.settings.save()
        disabled = get_disabled_anniversary_features(settings=self.settings)
        keys = {item['key'] for item in disabled}
        self.assertEqual(keys, {'physical_birthday', 'legal_foundation'})

    def test_get_anniversary_customers_filters_by_date_and_email(self):
        match = _physical_customer(email='match@example.com', data_nascimento_fundacao=date(1985, 6, 8))
        _physical_customer(email='other@example.com', data_nascimento_fundacao=date(1985, 1, 1))
        _physical_customer(email='', data_nascimento_fundacao=date(1985, 6, 8))
        selected = get_anniversary_customers(target_date=date(2026, 6, 8), settings=self.settings)
        self.assertEqual([c.pk for c in selected], [match.pk])

    def test_build_anniversary_email_uses_template_when_present(self):
        # The default physical-birthday template is seeded by migrations; replace
        # it with a known one to assert the rendered output deterministically.
        MessageTemplate.all_objects.filter(
            tipo=MessageTemplateType.CUSTOMER_BIRTHDAY_PHYSICAL,
        ).delete()
        MessageTemplate.objects.create(
            nome='Aniversário',
            tipo=MessageTemplateType.CUSTOMER_BIRTHDAY_PHYSICAL,
            assunto='Parabéns {{ nome }}',
            corpo='<p>Feliz dia, {{ nome }}</p>',
            padrao=True,
        )
        customer = _physical_customer()
        subject, body, template = build_anniversary_email(customer, date(2026, 6, 8))
        self.assertEqual(subject, 'Parabéns João da Silva')
        self.assertIn('Feliz dia, João da Silva', body)
        self.assertIsNotNone(template)

    def test_build_anniversary_email_falls_back_to_default_content(self):
        # With no template of this type, the hard-coded fallback content is used.
        MessageTemplate.all_objects.filter(
            tipo=MessageTemplateType.CUSTOMER_BIRTHDAY_PHYSICAL,
        ).delete()
        customer = _physical_customer()
        subject, body, template = build_anniversary_email(customer, date(2026, 6, 8))
        self.assertIn('João da Silva', subject)
        self.assertIsNone(template)


class SendAnniversaryMessagesTests(TestCase):
    def setUp(self):
        self.settings = MessageSettings.get_solo()

    def test_dry_run_selects_without_sending(self):
        _physical_customer(data_nascimento_fundacao=date(1990, 6, 8))
        selected, logs = send_anniversary_messages(target_date=date(2026, 6, 8), dry_run=True)
        self.assertEqual(len(selected), 1)
        self.assertEqual(logs, [])
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(MessageLog.objects.count(), 0)

    def test_sends_and_records_log(self):
        _physical_customer(data_nascimento_fundacao=date(1990, 6, 8))
        selected, logs = send_anniversary_messages(target_date=date(2026, 6, 8))
        self.assertEqual(len(selected), 1)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].status, MessageStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_does_not_resend_when_already_sent_this_year(self):
        customer = _physical_customer(data_nascimento_fundacao=date(1990, 6, 8))
        send_anniversary_messages(target_date=date(2026, 6, 8))
        self.assertTrue(
            already_sent_anniversary(customer, MessageType.BIRTHDAY, 2026)
        )
        mail.outbox.clear()
        selected, logs = send_anniversary_messages(target_date=date(2026, 6, 8))
        self.assertEqual(selected, [])
        self.assertEqual(logs, [])
        self.assertEqual(len(mail.outbox), 0)

    def test_limit_caps_number_of_customers(self):
        for i in range(3):
            _physical_customer(
                email=f'aniv{i}@example.com',
                data_nascimento_fundacao=date(1990, 6, 8),
            )
        selected, _ = send_anniversary_messages(target_date=date(2026, 6, 8), limit=2, dry_run=True)
        self.assertEqual(len(selected), 2)


class WorkOrderStatusMessageTests(TestCase):
    def setUp(self):
        self.customer = _physical_customer(email='os@example.com')
        self.order = SimpleNamespace(
            cliente=self.customer,
            veiculo=None,
            codigo='OS-00001',
            status='diagnostico',
            pk=1,
        )
        self.transition = SimpleNamespace(status_anterior='aberta', status_novo='diagnostico')
        self.settings = MessageSettings.get_solo()

    def test_no_message_when_status_emails_disabled(self):
        self.settings.enviar_status_os = False
        self.settings.save()
        result = send_work_order_status_change_message(self.order, self.transition)
        self.assertIsNone(result)
        self.assertEqual(len(mail.outbox), 0)

    def test_no_message_when_rule_disabled(self):
        self.settings.enviar_status_os = True
        self.settings.save()
        # ensure_work_order_status_message_rules defaults enviar_email=False
        result = send_work_order_status_change_message(self.order, self.transition)
        self.assertIsNone(result)

    def test_sends_when_enabled_and_rule_active(self):
        self.settings.enviar_status_os = True
        self.settings.save()
        ensure_work_order_status_message_rules()
        rule = WorkOrderStatusMessageRule.objects.get(status='diagnostico')
        rule.enviar_email = True
        rule.save()
        log = send_work_order_status_change_message(self.order, self.transition)
        self.assertIsNotNone(log)
        self.assertEqual(log.tipo, MessageType.WORK_ORDER_STATUS)
        self.assertEqual(log.ordem_servico_status, 'diagnostico')
        self.assertEqual(len(mail.outbox), 1)

    def test_no_message_when_customer_has_no_email(self):
        self.settings.enviar_status_os = True
        self.settings.save()
        self.order.cliente = SimpleNamespace(email='', nome_razao_social='Sem Email')
        result = send_work_order_status_change_message(self.order, self.transition)
        self.assertIsNone(result)


# --------------------------------------------------------------------------- #
# Management command.
# --------------------------------------------------------------------------- #
class SendAnniversaryCommandTests(TestCase):
    def test_dry_run_lists_selected_customers(self):
        _physical_customer(data_nascimento_fundacao=date(1990, 6, 8))
        call_command('send_anniversary_emails', '--date=2026-06-08', '--dry-run')
        self.assertEqual(MessageLog.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_command_sends_emails(self):
        _physical_customer(data_nascimento_fundacao=date(1990, 6, 8))
        call_command('send_anniversary_emails', '--date=2026-06-08')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(MessageLog.objects.filter(status=MessageStatus.SENT).count(), 1)

    def test_command_rejects_invalid_date(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command('send_anniversary_emails', '--date=08-06-2026')
