from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0004_sitesettings_email_oficina'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sitesettings',
            name='google_maps_embed',
            field=models.URLField(
                blank=True,
                help_text='Cole aqui o endereco src do iframe de incorporacao do Google Maps.',
                max_length=2000,
                verbose_name='URL de incorporacao do Google Maps',
            ),
        ),
    ]
