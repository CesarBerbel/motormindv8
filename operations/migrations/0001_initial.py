# Generated manually for MotorMind v17.

import decimal
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

import core.money


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('stock', '0002_stockmovement_fornecedor'),
    ]

    operations = [
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ativo', models.BooleanField(db_index=True, default=True, verbose_name='Ativo?')),
                ('excluido_em', models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Excluído em')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                ('codigo', models.CharField(blank=True, db_index=True, editable=False, max_length=20, null=True, unique=True, verbose_name='Código')),
                ('nome', models.CharField(max_length=180, verbose_name='Nome')),
                ('descricao', models.TextField(blank=True, verbose_name='Descrição')),
                ('duracao_minutos', models.PositiveIntegerField(default=60, validators=[django.core.validators.MinValueValidator(1)], verbose_name='Duração em minutos')),
                ('valor', core.money.MoneyField(decimal_places=2, default=decimal.Decimal('0.00'), max_digits=12, validators=[django.core.validators.MinValueValidator(decimal.Decimal('0'))], verbose_name='Valor')),
            ],
            options={
                'verbose_name': 'Serviço',
                'verbose_name_plural': 'Serviços',
                'ordering': ['nome'],
            },
        ),
        migrations.CreateModel(
            name='ServiceDefaultPart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantidade', models.DecimalField(decimal_places=3, default=decimal.Decimal('1.000'), max_digits=12, validators=[django.core.validators.MinValueValidator(decimal.Decimal('0.001'))], verbose_name='Quantidade padrão')),
                ('observacao', models.CharField(blank=True, max_length=180, verbose_name='Observação')),
                ('criado_em', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='servicos_associados', to='stock.inventoryitem', verbose_name='Peça/Insumo')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pecas_associadas', to='operations.service', verbose_name='Serviço')),
            ],
            options={
                'verbose_name': 'Peça padrão do serviço',
                'verbose_name_plural': 'Peças padrão do serviço',
                'ordering': ['item__nome'],
            },
        ),
        migrations.AddField(
            model_name='service',
            name='pecas_padrao',
            field=models.ManyToManyField(blank=True, related_name='servicos_padrao', through='operations.ServiceDefaultPart', to='stock.inventoryitem', verbose_name='Peças padrão'),
        ),
        migrations.AddConstraint(
            model_name='service',
            constraint=models.UniqueConstraint(condition=models.Q(('ativo', True), ('excluido_em__isnull', True)), fields=('nome',), name='unique_active_service_name'),
        ),
        migrations.AddConstraint(
            model_name='servicedefaultpart',
            constraint=models.UniqueConstraint(fields=('service', 'item'), name='unique_service_default_part_item'),
        ),
    ]
