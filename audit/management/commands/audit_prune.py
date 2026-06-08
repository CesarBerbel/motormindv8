from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from audit.models import AuditLog


class Command(BaseCommand):
    help = 'Remove registros de auditoria mais antigos que o número de dias informado.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=365,
            help='Retém registros dos últimos N dias (padrão: 365).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra quantos registros seriam removidos sem apagar.',
        )

    def handle(self, *args, **options):
        dias = max(1, options['dias'])
        limite = timezone.now() - timedelta(days=dias)
        qs = AuditLog.objects.filter(criado_em__lt=limite)
        total = qs.count()

        if options['dry_run']:
            self.stdout.write(f'{total} registro(s) anteriores a {limite:%Y-%m-%d} seriam removidos.')
            return

        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f'{deleted} registro(s) de auditoria removidos (anteriores a {limite:%Y-%m-%d}).'
        ))
