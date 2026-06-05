# Generated for MotorMind v37 PDF settings.

from django.db import migrations, models


def seed_pdf_templates(apps, schema_editor):
    PdfTemplateSettings = apps.get_model('operations', 'PdfTemplateSettings')
    PdfTemplateSettings.objects.get_or_create(
        tipo='checkin',
        defaults={
            'titulo': 'Check-in de recepção do veículo',
            'notas_rodape': 'Documento gerado no check-in do veículo. Confira as informações antes da assinatura.',
            'mostrar_assinatura_cliente': True,
            'mostrar_assinatura_oficina': True,
        },
    )
    PdfTemplateSettings.objects.get_or_create(
        tipo='orcamento',
        defaults={
            'titulo': 'Orçamento / aprovação da OS',
            'notas_rodape': 'A aprovação do orçamento autoriza a execução somente dos itens aprovados.',
            'mostrar_assinatura_cliente': False,
            'mostrar_assinatura_oficina': False,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('operations', '0012_work_order_approval_signature'),
    ]

    operations = [
        migrations.CreateModel(
            name='PdfSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('logo', models.ImageField(blank=True, null=True, upload_to='pdf/logos/', verbose_name='Logo global')),
                ('cabecalho_global', models.TextField(blank=True, verbose_name='Cabeçalho global')),
                ('rodape_global', models.TextField(blank=True, verbose_name='Rodapé global')),
                ('mostrar_assinatura_cliente_padrao', models.BooleanField(default=True, verbose_name='Mostrar assinatura do cliente por padrão?')),
                ('mostrar_assinatura_oficina_padrao', models.BooleanField(default=True, verbose_name='Mostrar assinatura da oficina por padrão?')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
            ],
            options={
                'verbose_name': 'Configuração de PDF',
                'verbose_name_plural': 'Configurações de PDF',
            },
        ),
        migrations.CreateModel(
            name='PdfTemplateSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('checkin', 'Check-in do veículo'), ('orcamento', 'Orçamento / aprovação da OS')], db_index=True, max_length=30, unique=True, verbose_name='Template')),
                ('titulo', models.CharField(blank=True, max_length=180, verbose_name='Título do PDF')),
                ('cabecalho', models.TextField(blank=True, verbose_name='Cabeçalho específico')),
                ('notas_rodape', models.TextField(blank=True, verbose_name='Notas de rodapé')),
                ('mostrar_assinatura_cliente', models.BooleanField(default=True, verbose_name='Mostrar assinatura do cliente?')),
                ('mostrar_assinatura_oficina', models.BooleanField(default=True, verbose_name='Mostrar assinatura da oficina?')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
            ],
            options={
                'verbose_name': 'Template de PDF',
                'verbose_name_plural': 'Templates de PDF',
                'ordering': ['tipo'],
            },
        ),
        migrations.RunPython(seed_pdf_templates, migrations.RunPython.noop),
    ]
