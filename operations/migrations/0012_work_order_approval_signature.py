# Generated for MotorMind v37 manual approval signature
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('operations', '0011_work_order_approvals'),
    ]

    operations = [
        migrations.AddField(
            model_name='workorderapprovalaudit',
            name='assinatura_base64',
            field=models.TextField(blank=True, verbose_name='Assinatura digital'),
        ),
        migrations.AddField(
            model_name='workorderapprovalaudit',
            name='assinatura_nome',
            field=models.CharField(blank=True, max_length=180, verbose_name='Nome da assinatura'),
        ),
    ]
