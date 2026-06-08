from django.db import migrations
from django.utils import timezone
from django.utils.text import slugify


POSTS = [
    {
        'titulo': 'Os 5 problemas mais comuns nos veículos (e como evitá-los)',
        'resumo': 'Conheça as falhas que mais levam carros à oficina e descubra hábitos simples que evitam dores de cabeça e gastos inesperados.',
        'conteudo': """
<p>Todo motorista, mais cedo ou mais tarde, acaba enfrentando algum problema com o carro. A boa notícia é que a maioria das falhas mais comuns tem origem na falta de manutenção e pode ser evitada com cuidados simples. Conheça os cinco problemas que mais aparecem na nossa oficina e como preveni-los.</p>

<h2>1. Bateria descarregada</h2>
<p>A bateria é uma das principais causas de "carro que não pega", especialmente em veículos que ficam parados por muitos dias ou que rodam apenas trajetos curtos. A vida útil média é de 2 a 4 anos. Fique atento a sinais como o motor de arranque lento e as luzes do painel mais fracas — eles costumam antecipar a pane.</p>
<p><strong>Como evitar:</strong> teste a bateria nas revisões, mantenha os terminais limpos e, se o carro fica muito tempo parado, dê uma volta de pelo menos 20 minutos por semana.</p>

<h2>2. Pastilhas e discos de freio gastos</h2>
<p>O sistema de freios é um item de segurança e sofre desgaste natural. Ruídos agudos ao frear, vibração no pedal ou aumento da distância de frenagem são sinais de alerta que não devem ser ignorados.</p>
<p><strong>Como evitar:</strong> faça a inspeção dos freios a cada 10.000 km ou conforme o manual, e troque pastilhas e discos sempre em conjunto quando necessário.</p>

<h2>3. Pneus carecas ou calibragem incorreta</h2>
<p>Pneus em mau estado comprometem a aderência, aumentam o consumo de combustível e elevam o risco de acidentes. A calibragem errada acelera o desgaste e prejudica a dirigibilidade.</p>
<p><strong>Como evitar:</strong> calibre os pneus a cada 15 dias (com eles frios), faça o rodízio a cada 10.000 km e verifique o alinhamento e o balanceamento periodicamente.</p>

<h2>4. Óleo do motor vencido</h2>
<p>O óleo lubrifica e protege o motor. Quando ele perde as propriedades, o desgaste das peças internas dispara — e um motor fundido é um dos reparos mais caros que existem.</p>
<p><strong>Como evitar:</strong> respeite o intervalo de troca indicado pelo fabricante (em geral entre 5.000 e 10.000 km) e troque também o filtro de óleo.</p>

<h2>5. Superaquecimento do motor</h2>
<p>Vazamentos no sistema de arrefecimento, nível baixo de líquido de arrefecimento ou problemas na válvula termostática podem fazer o motor superaquecer. O ponteiro de temperatura subindo é um aviso para parar imediatamente.</p>
<p><strong>Como evitar:</strong> verifique o nível do líquido de arrefecimento regularmente e fique atento a manchas no chão da garagem, que indicam vazamento.</p>

<h2>Conclusão</h2>
<p>A maioria desses problemas dá sinais antes de virar uma pane. Ouvir o carro e manter a manutenção em dia é mais barato do que consertar. Na dúvida, agende uma avaliação com a nossa equipe — fazemos um diagnóstico completo e honesto do seu veículo.</p>
""",
    },
    {
        'titulo': 'Revisão periódica: por que ela é tão importante',
        'resumo': 'Mais do que cumprir o manual, a revisão em dia garante segurança, economia e tranquilidade. Entenda o que é avaliado e a frequência ideal.',
        'conteudo': """
<p>Muita gente só lembra da oficina quando algo dá errado. Mas a revisão periódica existe justamente para evitar que o "errado" aconteça. Ela é uma checagem programada dos principais sistemas do veículo, feita em intervalos definidos pelo fabricante — normalmente a cada 10.000 km ou uma vez por ano, o que vier primeiro.</p>

<h2>O que é verificado em uma revisão</h2>
<ul>
  <li><strong>Óleo e filtros:</strong> troca do óleo do motor e dos filtros de óleo, ar e combustível.</li>
  <li><strong>Freios:</strong> pastilhas, discos, fluido de freio e mangueiras.</li>
  <li><strong>Suspensão e direção:</strong> amortecedores, buchas, pivôs, terminais e alinhamento.</li>
  <li><strong>Pneus:</strong> desgaste, calibragem, rodízio e balanceamento.</li>
  <li><strong>Sistema elétrico:</strong> bateria, alternador, luzes e sensores.</li>
  <li><strong>Arrefecimento:</strong> nível e estado do líquido de arrefecimento, correias e mangueiras.</li>
</ul>

<h2>Por que não vale a pena adiar</h2>
<p>Adiar a revisão para "economizar" quase sempre sai mais caro. Uma correia desgastada que se rompe pode danificar o motor inteiro; uma pastilha no fim pode comprometer o disco. Pequenos reparos feitos na hora certa evitam consertos grandes e imprevistos.</p>

<h2>Segurança em primeiro lugar</h2>
<p>Freios, pneus, suspensão e direção são itens diretamente ligados à sua segurança e à de quem anda com você. A revisão garante que esses sistemas estão respondendo como deveriam, principalmente antes de viagens longas.</p>

<h2>Economia que aparece no fim do mês</h2>
<p>Um carro revisado consome menos combustível, desgasta menos as peças e mantém um valor de revenda mais alto. O histórico de manutenção em dia é um dos primeiros itens que um comprador atento verifica.</p>

<h2>Com que frequência revisar</h2>
<p>Siga sempre o manual do seu veículo. Como regra geral, considere uma revisão a cada 10.000 km ou 12 meses. Carros mais antigos ou que rodam em condições severas (muito trânsito, estradas de terra, cargas pesadas) podem precisar de intervalos menores.</p>

<p>Quer saber em que ponto está o seu carro? Agende uma revisão com a gente. Avaliamos tudo e explicamos, com transparência, o que é urgente e o que pode esperar.</p>
""",
    },
    {
        'titulo': 'Manutenção preventiva: economia e segurança o ano todo',
        'resumo': 'Cuidar antes de quebrar é o segredo para gastar menos e rodar tranquilo. Veja como a manutenção preventiva protege o seu bolso e o seu veículo.',
        'conteudo': """
<p>Existe uma diferença simples, mas decisiva, entre dois tipos de manutenção: a <strong>corretiva</strong>, feita depois que a peça quebra, e a <strong>preventiva</strong>, feita antes que isso aconteça. A preventiva custa menos, evita imprevistos e mantém o carro sempre confiável.</p>

<h2>O que é manutenção preventiva</h2>
<p>É o conjunto de cuidados e trocas programadas que antecipam o desgaste natural dos componentes. Em vez de esperar a falha, você substitui ou ajusta a peça no momento certo, seguindo a quilometragem e o tempo de uso recomendados.</p>

<h2>Por que ela compensa</h2>
<ul>
  <li><strong>Custa menos:</strong> trocar uma correia desgastada é muito mais barato do que reparar um motor danificado pela ruptura dela.</li>
  <li><strong>Evita imprevistos:</strong> menos chance de ficar parado na estrada ou de perder compromissos por causa de uma pane.</li>
  <li><strong>Mais segurança:</strong> freios, pneus e suspensão sempre em condições de uso.</li>
  <li><strong>Valoriza o carro:</strong> um veículo com manutenção em dia vale mais na hora da revenda.</li>
</ul>

<h2>Itens que pedem atenção preventiva</h2>
<ul>
  <li>Óleo do motor e filtros — conforme o intervalo do fabricante.</li>
  <li>Correia dentada ou corrente de comando — item crítico, com prazo definido de troca.</li>
  <li>Velas de ignição — influenciam consumo e desempenho.</li>
  <li>Fluido de freio e líquido de arrefecimento — perdem propriedades com o tempo.</li>
  <li>Pneus, alinhamento e balanceamento — segurança e economia de combustível.</li>
  <li>Bateria — vida útil média de 2 a 4 anos.</li>
</ul>

<h2>Crie uma rotina simples</h2>
<p>Você não precisa ser mecânico para cuidar bem do carro. Verifique semanalmente o nível de óleo, a água do radiador e a calibragem dos pneus. Fique atento a ruídos, vibrações e luzes no painel. E, principalmente, mantenha as revisões programadas em dia.</p>

<h2>Conte com a gente</h2>
<p>Na nossa oficina, montamos um plano de manutenção preventiva sob medida para o seu veículo e o seu uso. Assim, você sabe exatamente o que fazer e quando — sem surpresas. Fale com a nossa equipe e rode tranquilo o ano todo.</p>
""",
    },
]


def seed(apps, schema_editor):
    BlogPost = apps.get_model('website', 'BlogPost')
    now = timezone.now()
    for post in POSTS:
        slug = slugify(post['titulo'])
        BlogPost.objects.get_or_create(
            slug=slug,
            defaults={
                'titulo': post['titulo'],
                'resumo': post['resumo'],
                'conteudo': post['conteudo'].strip(),
                'publicado': True,
                'publicado_em': now,
            },
        )


def unseed(apps, schema_editor):
    BlogPost = apps.get_model('website', 'BlogPost')
    BlogPost.objects.filter(slug__in=[slugify(p['titulo']) for p in POSTS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0002_seed_content'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
