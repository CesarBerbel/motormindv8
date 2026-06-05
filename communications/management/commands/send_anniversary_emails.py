from datetime import date

from django.core.management.base import BaseCommand, CommandError

from communications.models import MessageStatus
from communications.services import get_disabled_anniversary_features, send_anniversary_messages


class Command(BaseCommand):
    help = 'Envia emails de aniversario/fundacao para clientes com data preenchida no dia informado.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            dest='target_date',
            help='Data de referencia no formato YYYY-MM-DD. Se omitida, usa hoje.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Lista os clientes selecionados sem enviar emails e sem gravar historico.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limita a quantidade de clientes processados.',
        )

    def handle(self, *args, **options):
        target_date = date.today()
        if options.get('target_date'):
            try:
                target_date = date.fromisoformat(options['target_date'])
            except ValueError as exc:
                raise CommandError('Use --date no formato YYYY-MM-DD.') from exc

        disabled_features = get_disabled_anniversary_features()
        for feature in disabled_features:
            self.stderr.write(self.style.ERROR(feature['message']))

        if len(disabled_features) == 2:
            self.stderr.write(self.style.ERROR(
                'ERRO: nenhum envio automatico sera processado porque pessoa fisica e pessoa juridica estao desabilitadas.'
            ))
            return

        selected_customers, logs = send_anniversary_messages(
            target_date=target_date,
            dry_run=options.get('dry_run'),
            limit=options.get('limit'),
        )

        if options.get('dry_run'):
            self.stdout.write(f'Clientes selecionados para {target_date:%Y-%m-%d}: {len(selected_customers)}')
            for customer in selected_customers:
                self.stdout.write(f'- {customer.nome_razao_social} <{customer.email}> ({customer.get_tipo_pessoa_display()})')
            return

        sent_count = sum(1 for log in logs if log.status == MessageStatus.SENT)
        error_count = sum(1 for log in logs if log.status == MessageStatus.ERROR)
        self.stdout.write(self.style.SUCCESS(
            f'Processamento concluido para {target_date:%Y-%m-%d}: {sent_count} enviado(s), {error_count} erro(s).'
        ))
