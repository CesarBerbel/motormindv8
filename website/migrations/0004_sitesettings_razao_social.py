from django.db import migrations, models


def copy_nome_fantasia_to_razao_social(apps, schema_editor):
    SiteSettings = apps.get_model('website', 'SiteSettings')
    for site in SiteSettings.objects.filter(razao_social=''):
        site.razao_social = site.nome_fantasia
        site.save(update_fields=['razao_social'])


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0003_seed_blog_posts'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='razao_social',
            field=models.CharField('Razão social', blank=True, max_length=180),
        ),
        migrations.RunPython(copy_nome_fantasia_to_razao_social, migrations.RunPython.noop),
    ]
