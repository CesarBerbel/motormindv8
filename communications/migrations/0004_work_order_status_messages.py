from django.db import migrations, models
import django.db.models.deletion


WORK_ORDER_STATUS_CHOICES = [
    ('aberta', 'Aberta'),
    ('diagnostico', 'Diagnóstico'),
    ('orcamento', 'Orçamento'),
    ('aguardando_aprovacao', 'Aguardando aprovação'),
    ('aprovada', 'Aprovada'),
    ('em_execucao', 'Em execução'),
    ('aguardando_peca', 'Aguardando peça'),
    ('em_teste', 'Em teste'),
    ('pronta', 'Pronta'),
    ('pronto_para_retirar', 'Pronto para retirar'),
    ('entregue', 'Entregue'),
    ('cancelada', 'Cancelada'),
    ('arquivada', 'Arquivada'),
]


DEFAULT_STATUS_SUBJECT = 'Atualização da OS {{ ordem_servico.codigo }}: {{ status_novo_label }}'
DEFAULT_STATUS_BODY = (
    '<p>Olá, {{ nome }}!</p>'
    '<p>A OS <strong>{{ ordem_servico.codigo }}</strong> do veículo '
    '<strong>{{ veiculo }}</strong> mudou para <strong>{{ status_novo_label }}</strong>.</p>'
    '<p>{{ mensagem_status }}</p>'
)


def seed_status_templates_and_rules(apps, schema_editor):
    MessageTemplate = apps.get_model('communications', 'MessageTemplate')
    WorkOrderStatusMessageRule = apps.get_model('communications', 'WorkOrderStatusMessageRule')

    template = MessageTemplate.objects.filter(
        tipo='work_order_status',
        padrao=True,
        ativo=True,
        excluido_em__isnull=True,
    ).first()
    if template is None:
        template = MessageTemplate.objects.create(
            nome='Mudança de status da OS - Padrão',
            tipo='work_order_status',
            assunto=DEFAULT_STATUS_SUBJECT,
            corpo=DEFAULT_STATUS_BODY,
            ativo=True,
            padrao=True,
        )

    recommended = {'aguardando_aprovacao', 'aguardando_peca', 'pronto_para_retirar', 'entregue'}
    for index, (status, _label) in enumerate(WORK_ORDER_STATUS_CHOICES, start=1):
        WorkOrderStatusMessageRule.objects.get_or_create(
            status=status,
            defaults={
                'ordem': index,
                'enviar_email': status in recommended,
                'template': template,
            },
        )


def unseed_status_templates_and_rules(apps, schema_editor):
    WorkOrderStatusMessageRule = apps.get_model('communications', 'WorkOrderStatusMessageRule')
    WorkOrderStatusMessageRule.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('communications', '0003_messagesettings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messagetemplate',
            name='tipo',
            field=models.CharField(choices=[('customer_birthday_physical', 'Aniversário - Cliente pessoa física'), ('customer_foundation_legal', 'Fundação - Cliente pessoa jurídica'), ('work_order_status', 'Mudança de status da OS'), ('manual', 'Manual / Outro')], db_index=True, max_length=40, verbose_name='Tipo'),
        ),
        migrations.AlterField(
            model_name='messagelog',
            name='tipo',
            field=models.CharField(choices=[('manual', 'Manual'), ('birthday', 'Aniversário'), ('foundation', 'Fundação'), ('work_order_status', 'Status da OS')], max_length=20, verbose_name='Tipo da mensagem'),
        ),
        migrations.AddField(
            model_name='messagesettings',
            name='enviar_status_os',
            field=models.BooleanField(default=False, help_text='Quando habilitado, o sistema verifica as regras por status abaixo a cada mudança de status da OS.', verbose_name='Enviar email quando a OS mudar de status?'),
        ),
        migrations.AddField(
            model_name='messagelog',
            name='ordem_servico_codigo',
            field=models.CharField(blank=True, max_length=20, verbose_name='Código da OS'),
        ),
        migrations.AddField(
            model_name='messagelog',
            name='ordem_servico_id',
            field=models.PositiveBigIntegerField(blank=True, db_index=True, null=True, verbose_name='ID da OS'),
        ),
        migrations.AddField(
            model_name='messagelog',
            name='ordem_servico_status',
            field=models.CharField(blank=True, choices=WORK_ORDER_STATUS_CHOICES, max_length=30, verbose_name='Status da OS'),
        ),
        migrations.CreateModel(
            name='WorkOrderStatusMessageRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=WORK_ORDER_STATUS_CHOICES, db_index=True, max_length=30, unique=True, verbose_name='Status da OS')),
                ('ordem', models.PositiveSmallIntegerField(db_index=True, default=999, verbose_name='Ordem')),
                ('enviar_email', models.BooleanField(db_index=True, default=False, verbose_name='Enviar email?')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                ('template', models.ForeignKey(blank=True, help_text='Template usado quando a OS entrar neste status. Se ficar vazio, será usado o template padrão de mudança de status da OS.', limit_choices_to={'tipo': 'work_order_status'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='regras_status_os', to='communications.messagetemplate', verbose_name='Template')),
            ],
            options={
                'verbose_name': 'Regra de mensagem por status da OS',
                'verbose_name_plural': 'Regras de mensagem por status da OS',
                'ordering': ['ordem', 'status'],
            },
        ),
        migrations.AddIndex(
            model_name='messagelog',
            index=models.Index(fields=['ordem_servico_id', 'ordem_servico_status'], name='communicatio_ordem_s_3d8b0f_idx'),
        ),
        migrations.RunPython(seed_status_templates_and_rules, unseed_status_templates_and_rules),
    ]
