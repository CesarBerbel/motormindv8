from django.db import migrations
from django.utils.text import slugify


DEFAULT_SERVICES = [
    ('Mecânica geral', '🔧', 'Manutenção preventiva e corretiva para o seu veículo.',
     'Revisões completas, troca de óleo e filtros, correias, embreagem e muito mais. Mantemos seu carro rodando com segurança.'),
    ('Diagnóstico eletrônico', '💻', 'Leitura de falhas com scanner automotivo.',
     'Identificamos com precisão a causa dos problemas usando equipamento de diagnóstico, evitando trocas desnecessárias.'),
    ('Suspensão e direção', '🛞', 'Amortecedores, molas, pivôs, terminais e alinhamento.',
     'Cuidamos da estabilidade e do conforto do seu carro, com peças de qualidade e geometria correta.'),
    ('Freios', '🛑', 'Pastilhas, discos, tambores e fluido de freio.',
     'Segurança em primeiro lugar: revisão completa do sistema de freios com peças de procedência.'),
    ('Ar-condicionado', '❄️', 'Higienização, recarga de gás e reparos.',
     'Mantenha o conforto da cabine com a manutenção completa do sistema de climatização.'),
    ('Injeção eletrônica', '⚙️', 'Limpeza de bicos, sondas e sistema de injeção.',
     'Mais economia e desempenho com a manutenção do sistema de alimentação e injeção do motor.'),
]

DEFAULT_TESTIMONIALS = [
    ('Marcelo A.', 'Atendimento honesto e serviço de qualidade. Explicaram tudo antes de fazer. Recomendo!', 5, 1),
    ('Patrícia S.', 'Resolveram um problema que outras oficinas não conseguiram. Carro voltou novo.', 5, 2),
    ('Rodrigo T.', 'Preço justo e prazo cumprido. Virei cliente fiel.', 5, 3),
]


def seed(apps, schema_editor):
    SiteSettings = apps.get_model('website', 'SiteSettings')
    PublicService = apps.get_model('website', 'PublicService')
    Testimonial = apps.get_model('website', 'Testimonial')

    # Cria a linha única de configurações com os defaults dos campos.
    SiteSettings.objects.get_or_create(pk=1)

    for index, (titulo, icone, resumo, descricao) in enumerate(DEFAULT_SERVICES, start=1):
        PublicService.objects.get_or_create(
            slug=slugify(titulo),
            defaults={
                'titulo': titulo,
                'icone': icone,
                'resumo': resumo,
                'descricao': descricao,
                'ordem': index,
                'destaque': True,
                'ativo': True,
            },
        )

    for nome, texto, nota, ordem in DEFAULT_TESTIMONIALS:
        Testimonial.objects.get_or_create(
            nome_cliente=nome,
            defaults={'texto': texto, 'nota': nota, 'ordem': ordem, 'ativo': True},
        )


def unseed(apps, schema_editor):
    PublicService = apps.get_model('website', 'PublicService')
    Testimonial = apps.get_model('website', 'Testimonial')
    PublicService.objects.filter(slug__in=[slugify(t) for t, *_ in DEFAULT_SERVICES]).delete()
    Testimonial.objects.filter(nome_cliente__in=[n for n, *_ in DEFAULT_TESTIMONIALS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
