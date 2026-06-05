from decimal import Decimal
from itertools import cycle

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Category, CategoryAudience
from operations.models import Service, ServiceCategory, ServiceCombo, ServiceComboItem, ServiceDefaultPart
from stock.models import Brand, InventoryItem, InventoryItemType, StockCategory, UnitOfMeasure


BRANDS = [
    'Bosch', 'NGK', 'Denso', 'Delphi', 'Magneti Marelli', 'Valeo', 'ACDelco', 'Mahle', 'Mann-Filter', 'Tecfil',
    'Wega', 'Fram', 'Donaldson', 'Gates', 'Dayco', 'Continental', 'SKF', 'Schaeffler LuK', 'Sachs', 'ZF',
    'Monroe', 'Nakata', 'Cofap', 'TRW/Varga', 'Cobreq', 'Jurid', 'Fras-le', 'Brembo', 'Fremax', 'Bosch Freios',
    'Moura', 'Heliar', 'Philips', 'Osram', 'Mobil', 'Shell', 'Castrol', 'Motul', 'Lubrax', 'TotalEnergies',
    'Petronas', 'Bardahl', 'Wurth', 'Loctite', '3M', 'Elring', 'Sabo', 'Febi Bilstein', 'Goodyear', 'Pirelli',
]

UNITS = [
    ('Unidade', 'UN', False),
    ('Litro', 'L', True),
    ('Jogo', 'JG', False),
    ('Kit', 'KIT', False),
    ('Par', 'PAR', False),
    ('Metro', 'M', True),
    ('Frasco', 'FR', False),
    ('Galao', 'GL', True),
]

STOCK_CATEGORIES = [
    ('Filtros', 'Filtros de oleo, ar, combustivel, cabine e separadores para manutencao preventiva.'),
    ('Lubrificantes e fluidos', 'Oleos, fluidos hidraulicos, aditivos e graxas aplicados em motor, cambio, freios e direcao.'),
    ('Freios', 'Pastilhas, discos, sapatas, lonas, cilindros, sensores e insumos do sistema de freio.'),
    ('Suspensao', 'Amortecedores, buchas, bieletas, coxins, bandejas, pivots e componentes de estabilidade.'),
    ('Direcao', 'Terminais, barras, coifas, bombas, caixas e componentes do sistema de direcao.'),
    ('Ignicao e injecao', 'Velas, cabos, bobinas, bicos, sensores e atuadores de gerenciamento do motor.'),
    ('Correias e transmissao', 'Correias, tensores, rolamentos, kits de embreagem, juntas homocineticas e semieixos.'),
    ('Eletrica e iluminacao', 'Baterias, lampadas, fusis, relays, sensores eletricos e componentes de partida e carga.'),
    ('Arrefecimento', 'Radiadores, mangueiras, valvulas, bomba dagua, reservatorios e eletroventiladores.'),
    ('Motor e vedacao', 'Juntas, retentores, coxins, suportes, velas de aquecimento e componentes internos auxiliares.'),
    ('Rodas, pneus e alinhamento', 'Bicos, pesos, rolamentos de roda, parafusos, porcas e insumos de geometria.'),
    ('Higienizacao, acabamento e consumiveis', 'Produtos de limpeza, acabamento, fixacao, vedacao, panos e consumiveis de oficina.'),
]

SERVICE_CATEGORIES = [
    ('Manutencao preventiva', 'Servicos de revisao periodica, troca de filtros, fluidos e verificacoes programadas.'),
    ('Lubrificacao e fluidos', 'Servicos de troca, sangria, limpeza e completamento de oleos e fluidos automotivos.'),
    ('Freios', 'Servicos de manutencao, substituicao e diagnostico do sistema de freio.'),
    ('Suspensao e estabilidade', 'Servicos em amortecedores, buchas, bandejas, bieletas, molas e estabilidade.'),
    ('Direcao e geometria', 'Servicos de direcao, alinhamento, balanceamento e correcao de geometria.'),
    ('Motor', 'Servicos mecanicos no motor, vedacoes, suporte, correias e componentes associados.'),
    ('Ignicao e injecao', 'Servicos em velas, cabos, bobinas, bicos, sensores e alimentacao do motor.'),
    ('Arrefecimento', 'Servicos no sistema de temperatura, radiador, valvula, bomba dagua e ventoinha.'),
    ('Eletrica e bateria', 'Servicos eletricos, partida, carga, iluminacao, bateria e sensores.'),
    ('Transmissao e embreagem', 'Servicos em embreagem, cambio, homocinetica, semieixo e transmissoes.'),
    ('Ar-condicionado e cabine', 'Servicos de higienizacao, filtro de cabine, carga de gas e conforto interno.'),
    ('Diagnostico e inspecao', 'Servicos de avaliacao tecnica, scanner, testes, laudos e checklist operacional.'),
]

CUSTOMER_CATEGORIES = [
    'Particular', 'Frota empresarial', 'Aplicativo e taxi', 'Veiculo premium', 'Cliente recorrente',
    'Manutencao preventiva', 'Atendimento emergencial', 'Cliente convenio', 'Revenda de veiculos', 'Veiculo utilitario',
]

SUPPLIER_CATEGORIES = [
    'Autopecas geral', 'Distribuidor de lubrificantes', 'Fornecedor de pneus', 'Retifica e usinagem',
    'Eletrica automotiva', 'Ar-condicionado automotivo', 'Freios e embreagens', 'Suspensao e direcao',
    'Baterias', 'Ferramentas e consumiveis', 'Funilaria e pintura', 'Servicos terceirizados',
]

GROUPS = {
    'Filtros': {
        'unit': 'UN', 'type': InventoryItemType.PECA, 'min': 8, 'price': Decimal('32.00'),
        'brands': ['Tecfil', 'Mann-Filter', 'Wega', 'Fram', 'Mahle', 'Donaldson'],
        'description': 'Componente filtrante indicado para reter contaminantes e proteger o sistema informado na aplicacao.',
        'items': [
            'Filtro de oleo blindado 3/4 UNF para motores flex', 'Filtro de oleo refil papel para motores 1.0 e 1.4 flex',
            'Filtro de oleo blindado M20 para motores 1.6 flex', 'Filtro de oleo blindado para motores diesel leves',
            'Filtro de ar do motor retangular para hatch compacto', 'Filtro de ar do motor painel para sedan medio',
            'Filtro de ar do motor cilindrico para utilitario diesel', 'Filtro de ar esportivo inbox lavavel',
            'Filtro de combustivel linha flex externo', 'Filtro de combustivel diesel com dreno de agua',
            'Filtro de combustivel diesel blindado para pickup', 'Filtro de cabine antipolen convencional',
            'Filtro de cabine carvao ativado', 'Filtro de cabine para SUV com ar digital', 'Filtro secador do ar-condicionado',
            'Filtro separador de agua para diesel leve', 'Elemento filtrante de oleo para motor turbo',
            'Filtro de oleo para cambio automatico 6 marchas', 'Filtro de respiro do motor', 'Filtro de retorno hidraulico direcao',
            'Filtro de ar do motor para SUV flex', 'Filtro de ar do motor para pickup diesel', 'Filtro de combustivel interno tanque flex',
            'Filtro de oleo para motor 1.0 turbo', 'Filtro de oleo para motor 2.0 flex', 'Filtro de ar para van diesel',
            'Filtro de cabine premium antiviral', 'Filtro de combustivel flex alta vazao', 'Filtro de oleo para motor diesel pesado',
            'Filtro de ar secundario para diesel',
        ],
    },
    'Lubrificantes e fluidos': {
        'unit': 'L', 'type': InventoryItemType.INSUMO, 'min': 12, 'price': Decimal('42.00'),
        'brands': ['Mobil', 'Shell', 'Castrol', 'Motul', 'Lubrax', 'TotalEnergies', 'Petronas', 'Bardahl'],
        'description': 'Fluido especificado para reduzir atrito, proteger componentes e manter a viscosidade adequada no sistema.',
        'items': [
            'Oleo motor 5W30 sintetico API SP 1L', 'Oleo motor 5W40 sintetico API SN 1L', 'Oleo motor 0W20 sintetico API SP 1L',
            'Oleo motor 10W40 semissintetico 1L', 'Oleo motor 15W40 mineral 1L', 'Oleo motor diesel 15W40 API CI-4 1L',
            'Oleo motor diesel 5W30 low SAPS 1L', 'Oleo cambio manual 75W80 GL-4 1L', 'Oleo cambio manual 75W90 GL-5 1L',
            'Fluido ATF Dexron VI 1L', 'Fluido CVT premium 1L', 'Fluido dupla embreagem DCT 1L', 'Fluido de freio DOT 3 500 ml',
            'Fluido de freio DOT 4 500 ml', 'Fluido de freio DOT 5.1 500 ml', 'Fluido direcao hidraulica ATF 1L',
            'Aditivo radiador organico rosa pronto uso 1L', 'Aditivo radiador concentrado organico vermelho 1L',
            'Aditivo radiador hibrido verde pronto uso 1L', 'Agua desmineralizada para radiador 1L', 'Limpa radiador 500 ml',
            'Aditivo limpador de para-brisa 100 ml', 'Graxa azul para rolamentos 500 g', 'Desengripante multiuso 300 ml',
            'Limpa contato eletrico 300 ml', 'Limpa freio spray 500 ml', 'Descarbonizante de admissao 300 ml',
            'Aditivo limpeza bicos injetores gasolina 200 ml', 'Aditivo limpeza bicos injetores diesel 200 ml', 'Fluido de arrefecimento longa vida 5L',
        ],
    },
    'Freios': {
        'unit': 'UN', 'type': InventoryItemType.PECA, 'min': 6, 'price': Decimal('95.00'),
        'brands': ['Cobreq', 'Jurid', 'Fras-le', 'Brembo', 'Fremax', 'TRW/Varga', 'Bosch Freios'],
        'description': 'Componente do sistema de freio destinado a recuperar eficiencia, estabilidade e seguranca de frenagem.',
        'items': [
            'Jogo pastilha freio dianteira hatch compacto', 'Jogo pastilha freio dianteira sedan medio',
            'Jogo pastilha freio dianteira SUV compacto', 'Jogo pastilha freio traseira disco', 'Disco de freio dianteiro ventilado hatch compacto',
            'Disco de freio dianteiro ventilado sedan medio', 'Disco de freio traseiro solido', 'Tambor de freio traseiro hatch compacto',
            'Jogo sapata freio traseiro hatch compacto', 'Jogo lona freio utilitario leve', 'Cilindro mestre de freio',
            'Cilindro de roda traseiro', 'Flexivel de freio dianteiro', 'Flexivel de freio traseiro', 'Sensor ABS roda dianteira',
            'Sensor ABS roda traseira', 'Cabo freio de mao esquerdo', 'Cabo freio de mao direito', 'Servo freio hidrovacuo',
            'Reparo pinca freio dianteira', 'Pinca freio dianteira esquerda', 'Pinca freio dianteira direita',
            'Fluido de freio DOT 4 oficina 500 ml', 'Jogo pastilha freio ceramica premium', 'Disco de freio high carbon dianteiro',
            'Mola retorno sapata freio traseiro', 'Kit regulagem freio traseiro', 'Sensor desgaste pastilha dianteira',
            'Cubo disco freio dianteiro integrado', 'Jogo parafuso fixacao disco freio',
        ],
    },
    'Suspensao': {
        'unit': 'UN', 'type': InventoryItemType.PECA, 'min': 4, 'price': Decimal('120.00'),
        'brands': ['Monroe', 'Nakata', 'Cofap', 'Sachs', 'SKF', 'Febi Bilstein'],
        'description': 'Componente de suspensao aplicado para controle de impactos, estabilidade direcional e conforto do veiculo.',
        'items': [
            'Amortecedor dianteiro esquerdo hatch compacto', 'Amortecedor dianteiro direito hatch compacto',
            'Amortecedor traseiro hatch compacto', 'Amortecedor dianteiro SUV compacto', 'Amortecedor traseiro SUV compacto',
            'Kit batente e coifa amortecedor dianteiro', 'Kit batente e coifa amortecedor traseiro', 'Coxim amortecedor dianteiro com rolamento',
            'Coxim amortecedor traseiro', 'Bieleta dianteira esquerda', 'Bieleta dianteira direita', 'Bucha barra estabilizadora 19 mm',
            'Bucha barra estabilizadora 21 mm', 'Pivo suspensao dianteiro', 'Terminal axial direcao', 'Bandeja suspensao dianteira esquerda',
            'Bandeja suspensao dianteira direita', 'Bucha bandeja dianteira pequena', 'Bucha bandeja dianteira grande',
            'Mola helicoidal dianteira', 'Mola helicoidal traseira', 'Rolamento coxim amortecedor', 'Kit suspensao dianteira completa',
            'Kit suspensao traseira completa', 'Barra estabilizadora dianteira', 'Parafuso excentrico cambagem', 'Coxim agregado dianteiro',
            'Batente elastico suspensao traseira', 'Bucha eixo traseiro', 'Suporte superior amortecedor traseiro',
        ],
    },
    'Direcao': {
        'unit': 'UN', 'type': InventoryItemType.PECA, 'min': 4, 'price': Decimal('88.00'),
        'brands': ['Nakata', 'SKF', 'ZF', 'TRW/Varga', 'Febi Bilstein'],
        'description': 'Componente de direcao utilizado para eliminar folgas, manter alinhamento e garantir resposta segura do volante.',
        'items': [
            'Terminal de direcao esquerdo', 'Terminal de direcao direito', 'Barra axial esquerda', 'Barra axial direita',
            'Coifa caixa direcao lado esquerdo', 'Coifa caixa direcao lado direito', 'Bomba direcao hidraulica remanufaturada',
            'Reservatorio fluido direcao hidraulica', 'Mangueira alta pressao direcao hidraulica', 'Mangueira retorno direcao hidraulica',
            'Caixa direcao mecanica', 'Caixa direcao hidraulica', 'Junta coluna direcao', 'Cruzeta coluna direcao',
            'Bucha caixa direcao', 'Sensor angulo direcao', 'Terminal pitman utilitario', 'Braco auxiliar direcao',
            'Reparo caixa direcao hidraulica', 'Fluido direcao hidraulica premium 1L',
        ],
    },
    'Ignicao e injecao': {
        'unit': 'UN', 'type': InventoryItemType.PECA, 'min': 6, 'price': Decimal('78.00'),
        'brands': ['Bosch', 'NGK', 'Denso', 'Delphi', 'Magneti Marelli', 'ACDelco'],
        'description': 'Componente de gerenciamento do motor destinado a melhorar partida, queima, consumo e resposta da aceleracao.',
        'items': [
            'Jogo vela ignicao nickel motor 1.0 flex', 'Jogo vela ignicao iridium motor 1.0 turbo',
            'Jogo vela ignicao platinum motor 1.6 flex', 'Cabo vela ignicao motor 1.0 flex', 'Cabo vela ignicao motor 1.6 flex',
            'Bobina ignicao dupla', 'Bobina ignicao caneta motor 3 cilindros', 'Bobina ignicao individual motor 4 cilindros',
            'Bico injetor flex multiponto', 'Bico injetor flex alta vazao', 'Bico injetor diesel common rail', 'Sensor MAP',
            'Sensor MAF fluxo de ar', 'Sensor TPS posicao borboleta', 'Sensor rotacao virabrequim', 'Sensor fase comando',
            'Sonda lambda pre catalisador', 'Sonda lambda pos catalisador', 'Atuador marcha lenta', 'Corpo borboleta eletronico',
            'Valvula canister', 'Valvula EGR diesel', 'Regulador pressao combustivel', 'Bomba combustivel flex refil',
            'Pre-filtro bomba combustivel', 'Filtro tela bico injetor', 'Kit reparo bico injetor', 'Sensor temperatura ar admissao',
            'Sensor temperatura motor injecao', 'Modulo rele bomba combustivel',
        ],
    },
    'Correias e transmissao': {
        'unit': 'UN', 'type': InventoryItemType.PECA, 'min': 4, 'price': Decimal('135.00'),
        'brands': ['Gates', 'Dayco', 'Continental', 'Schaeffler LuK', 'SKF', 'Sachs', 'ZF'],
        'description': 'Componente de transmissao de torque ou sincronismo aplicado para operacao correta do motor e da tracao.',
        'items': [
            'Correia dentada motor 1.0 flex', 'Correia dentada motor 1.6 flex', 'Correia dentada motor diesel leve',
            'Tensor correia dentada automatico', 'Rolamento guia correia dentada', 'Kit correia dentada com tensor',
            'Correia alternador 5PK', 'Correia alternador 6PK', 'Correia ar-condicionado 4PK', 'Tensor correia auxiliar',
            'Polia alternador roda livre', 'Kit embreagem completo motor 1.0', 'Kit embreagem completo motor 1.6',
            'Cilindro mestre embreagem', 'Cilindro auxiliar embreagem', 'Atuador hidraulico embreagem', 'Cabo embreagem regulagem automatica',
            'Junta homocinetica lado roda', 'Junta homocinetica lado cambio', 'Coifa homocinetica lado roda', 'Coifa homocinetica lado cambio',
            'Semieixo completo esquerdo', 'Semieixo completo direito', 'Rolamento cambio manual', 'Coxim cambio inferior',
        ],
    },
    'Eletrica e iluminacao': {
        'unit': 'UN', 'type': InventoryItemType.PECA, 'min': 6, 'price': Decimal('58.00'),
        'brands': ['Moura', 'Heliar', 'Bosch', 'Philips', 'Osram', 'Magneti Marelli', 'ACDelco'],
        'description': 'Componente eletrico empregado em partida, carga, sinalizacao, iluminacao ou protecao do circuito automotivo.',
        'items': [
            'Bateria 45Ah caixa baixa', 'Bateria 60Ah caixa alta', 'Bateria 70Ah start-stop AGM', 'Bateria 90Ah diesel',
            'Lampada H4 12V 60/55W', 'Lampada H7 12V 55W', 'Lampada H11 farol milha', 'Lampada T10 pingo LED',
            'Lampada PY21W seta ambar', 'Lampada P21/5W lanterna e freio', 'Fusivel lamina mini 10A', 'Fusivel lamina mini 15A',
            'Fusivel lamina mini 20A', 'Rele auxiliar 4 pinos 40A', 'Rele auxiliar 5 pinos 40A', 'Sensor nivel combustivel',
            'Interruptor oleo motor', 'Interruptor luz freio', 'Motor limpador para-brisa', 'Palheta limpador 16 polegadas',
            'Palheta limpador 18 polegadas', 'Palheta limpador 22 polegadas', 'Regulador voltagem alternador', 'Escova alternador',
            'Bendix motor partida',
        ],
    },
    'Arrefecimento': {
        'unit': 'UN', 'type': InventoryItemType.PECA, 'min': 4, 'price': Decimal('92.00'),
        'brands': ['Valeo', 'Magneti Marelli', 'Denso', 'Gates', 'Dayco', 'Mahle'],
        'description': 'Componente do arrefecimento responsavel por controlar temperatura, vedacao e circulacao do fluido do motor.',
        'items': [
            'Radiador motor hatch compacto flex', 'Radiador motor sedan medio flex', 'Radiador motor pickup diesel', 'Bomba dagua motor 1.0 flex',
            'Bomba dagua motor 1.6 flex', 'Bomba dagua motor diesel leve', 'Valvula termostatica 87 graus', 'Valvula termostatica 92 graus',
            'Reservatorio expansao radiador', 'Tampa reservatorio radiador 1.4 bar', 'Mangueira superior radiador', 'Mangueira inferior radiador',
            'Mangueira ar quente entrada', 'Mangueira ar quente saida', 'Sensor temperatura radiador', 'Interruptor termico ventoinha',
            'Eletroventilador radiador', 'Resistencia ventoinha radiador', 'Aditivo radiador organico pronto uso 5L', 'Abraçadeira mangueira radiador 32 mm',
            'Junta bomba dagua', 'Tubo distribuicao agua motor', 'Carcaca valvula termostatica', 'Conexao rapida mangueira arrefecimento',
            'Liquido arrefecimento concentrado premium 1L',
        ],
    },
    'Motor e vedacao': {
        'unit': 'UN', 'type': InventoryItemType.PECA, 'min': 4, 'price': Decimal('68.00'),
        'brands': ['Elring', 'Sabo', 'Mahle', 'Schaeffler LuK', 'Cofap', 'Nakata'],
        'description': 'Componente usado para vedar, fixar ou suportar o conjunto motriz, evitando vazamentos, vibracoes e folgas.',
        'items': [
            'Junta tampa valvulas motor 1.0 flex', 'Junta tampa valvulas motor 1.6 flex', 'Junta carter motor flex',
            'Junta coletor admissao', 'Junta coletor escapamento', 'Retentor virabrequim dianteiro', 'Retentor virabrequim traseiro',
            'Retentor comando valvulas', 'Coxim motor lado direito', 'Coxim motor lado esquerdo', 'Coxim motor traseiro',
            'Suporte coxim motor aluminio', 'Parafuso bujao carter magnetico', 'Arruela bujao carter cobre', 'Kit junta cabecote motor 1.0',
            'Kit junta cabecote motor 1.6', 'Tucho hidraulico motor flex', 'Bronzina biela STD', 'Bronzina mancal STD',
            'Anel segmento motor 1.0 STD', 'Anel segmento motor 1.6 STD', 'Valvula PCV respiro motor', 'Mangueira respiro oleo',
            'Sensor pressao oleo motor', 'Capa correia dentada superior',
        ],
    },
    'Rodas, pneus e alinhamento': {
        'unit': 'UN', 'type': InventoryItemType.PECA, 'min': 10, 'price': Decimal('22.00'),
        'brands': ['SKF', 'Goodyear', 'Pirelli', 'Nakata', 'Febi Bilstein'],
        'description': 'Item aplicado em roda, pneu ou geometria para garantir fixacao, vedacao, balanceamento e rodagem segura.',
        'items': [
            'Bico pneu sem camara TR413', 'Bico pneu metalico para roda liga', 'Peso balanceamento adesivo 5 g', 'Peso balanceamento adesivo 10 g',
            'Peso balanceamento garra 15 g', 'Parafuso roda cone 17 mm', 'Porca roda cone 19 mm', 'Rolamento roda dianteira',
            'Rolamento roda traseira', 'Cubo roda dianteiro com rolamento', 'Cubo roda traseiro com rolamento', 'Sensor TPMS universal',
            'Kit reparo pneu macarrao', 'Valvula TPMS borracha', 'Prisioneiro roda utilitario',
        ],
    },
    'Higienizacao, acabamento e consumiveis': {
        'unit': 'UN', 'type': InventoryItemType.INSUMO, 'min': 12, 'price': Decimal('18.00'),
        'brands': ['3M', 'Wurth', 'Loctite', 'Bardahl', 'Bosch'],
        'description': 'Consumivel de oficina usado em limpeza, protecao, acabamento, fixacao ou apoio ao reparo automotivo.',
        'items': [
            'Higienizador ar-condicionado granada 250 ml', 'Limpa ar-condicionado spray 300 ml', 'Pano microfibra automotivo',
            'Fita isolante automotiva antichama', 'Fita dupla face automotiva alta fixacao', 'Abraçadeira nylon 200 mm pacote',
            'Abraçadeira metalica 16 a 27 mm', 'Silicone alta temperatura vermelho', 'Trava rosca medio torque azul', 'Veda junta anaerobico',
            'Desengraxante biodegradavel 1L', 'Shampoo automotivo neutro 1L', 'Cera liquida protecao 500 ml',
            'Luva nitrilica caixa 100 unidades', 'Protetor banco volante e tapete descartavel',
        ],
    },
}


def money(value):
    return Decimal(value).quantize(Decimal('0.01'))


def revive(obj, active_field='ativo'):
    changed = []
    if hasattr(obj, active_field) and not getattr(obj, active_field):
        setattr(obj, active_field, True)
        changed.append(active_field)
    if hasattr(obj, 'excluido_em') and obj.excluido_em is not None:
        obj.excluido_em = None
        changed.append('excluido_em')
    if changed:
        obj.save(update_fields=changed)
    return obj


class Command(BaseCommand):
    help = 'Popula o banco com catalogo realista: marcas, categorias, pecas, servicos, pecas padrao e combos.'

    def add_arguments(self, parser):
        parser.add_argument('--quiet', action='store_true', help='Mostra apenas o resumo final.')

    def handle(self, *args, **options):
        self.quiet = options.get('quiet', False)
        with transaction.atomic():
            units = self.seed_units()
            brands = self.seed_brands()
            stock_categories = self.seed_stock_categories()
            service_categories = self.seed_service_categories()
            self.seed_person_categories()
            items = self.seed_inventory_items(units, brands, stock_categories)
            services = self.seed_services(service_categories, items)
            combos = self.seed_combos(services)

        self.stdout.write(self.style.SUCCESS('Feed realista aplicado com sucesso.'))
        self.stdout.write(f'- Marcas: {len(BRANDS)}')
        self.stdout.write(f'- Categorias de pecas: {len(STOCK_CATEGORIES)}')
        self.stdout.write(f'- Categorias de servicos: {len(SERVICE_CATEGORIES)}')
        self.stdout.write(f'- Categorias de clientes: {len(CUSTOMER_CATEGORIES)}')
        self.stdout.write(f'- Categorias de fornecedores: {len(SUPPLIER_CATEGORIES)}')
        self.stdout.write(f'- Pecas/insumos cadastrados: {len(items)}')
        self.stdout.write(f'- Servicos cadastrados: {len(services)}')
        self.stdout.write(f'- Combos cadastrados: {len(combos)}')

    def log(self, message):
        if not self.quiet:
            self.stdout.write(message)

    def seed_units(self):
        result = {}
        for nome, sigla, permite in UNITS:
            obj, _ = UnitOfMeasure.objects.update_or_create(
                sigla=sigla,
                defaults={'nome': nome, 'permite_fracionado': permite, 'ativo': True},
            )
            result[sigla] = obj
        self.log(f'Unidades configuradas: {len(result)}')
        return result

    def seed_brands(self):
        result = {}
        for nome in BRANDS:
            obj, _ = Brand.all_objects.get_or_create(nome=nome)
            revive(obj)
            result[nome] = obj
        self.log(f'Marcas configuradas: {len(result)}')
        return result

    def seed_stock_categories(self):
        result = {}
        for nome, descricao in STOCK_CATEGORIES:
            obj, _ = StockCategory.all_objects.get_or_create(nome=nome, defaults={'descricao': descricao})
            obj.descricao = descricao
            revive(obj)
            obj.save(update_fields=['descricao', 'ativo', 'excluido_em', 'atualizado_em'])
            result[nome] = obj
        self.log(f'Categorias de pecas configuradas: {len(result)}')
        return result

    def seed_service_categories(self):
        result = {}
        for nome, descricao in SERVICE_CATEGORIES:
            obj, _ = ServiceCategory.all_objects.get_or_create(nome=nome, defaults={'descricao': descricao})
            obj.descricao = descricao
            revive(obj)
            obj.save(update_fields=['descricao', 'ativo', 'excluido_em', 'atualizado_em'])
            result[nome] = obj
        self.log(f'Categorias de servicos configuradas: {len(result)}')
        return result

    def seed_person_categories(self):
        for nome in CUSTOMER_CATEGORIES:
            Category.objects.update_or_create(
                nome=nome,
                aplicacao=CategoryAudience.CLIENTE,
                defaults={'ativa': True, 'excluido_em': None},
            )
        for nome in SUPPLIER_CATEGORIES:
            Category.objects.update_or_create(
                nome=nome,
                aplicacao=CategoryAudience.FORNECEDOR,
                defaults={'ativa': True, 'excluido_em': None},
            )
        self.log(f'Categorias de clientes/fornecedores configuradas: {len(CUSTOMER_CATEGORIES) + len(SUPPLIER_CATEGORIES)}')

    def build_part_catalog(self):
        catalog = []
        for category_name, spec in GROUPS.items():
            brand_cycle = cycle(spec['brands'])
            for index, item_name in enumerate(spec['items'], start=1):
                unit = 'JG' if item_name.lower().startswith('jogo') else spec['unit']
                if item_name.lower().startswith('kit'):
                    unit = 'KIT'
                if item_name.lower().startswith('par'):
                    unit = 'PAR'
                if 'oleo motor' in item_name.lower() or 'fluido' in item_name.lower() or 'aditivo' in item_name.lower() or 'agua desmineralizada' in item_name.lower():
                    unit = 'L' if '500 ml' not in item_name.lower() and '300 ml' not in item_name.lower() and '200 ml' not in item_name.lower() and '100 ml' not in item_name.lower() else 'FR'
                price = spec['price'] + Decimal(index % 11) * Decimal('7.30')
                catalog.append({
                    'nome': item_name,
                    'descricao': self.part_description(item_name, category_name, spec['description']),
                    'categoria': category_name,
                    'marca': next(brand_cycle),
                    'unidade': unit,
                    'tipo': spec['type'],
                    'estoque_minimo': spec['min'] + (index % 5),
                    'preco_custo': price.quantize(Decimal('0.01')),
                })
        names = [item['nome'] for item in catalog]
        if len(catalog) != 300:
            raise RuntimeError(f'Catalogo de pecas precisa ter 300 itens; gerado {len(catalog)}.')
        if len(set(names)) != len(names):
            duplicates = sorted({name for name in names if names.count(name) > 1})
            raise RuntimeError(f'Catalogo de pecas contem nomes duplicados: {duplicates[:10]}')
        return catalog

    def part_description(self, name, category_name, base):
        lower = name.lower()
        if 'filtro de oleo' in lower:
            return 'Filtro para reter particulas do lubrificante; deve ser trocado junto com o oleo do motor para evitar desgaste interno.'
        if 'filtro de ar' in lower:
            return 'Filtro da admissao que impede entrada de poeira no motor e ajuda a manter consumo, desempenho e marcha lenta estaveis.'
        if 'filtro de cabine' in lower:
            return 'Filtro do sistema de ventilacao da cabine, indicado para reduzir poeira, odores e particulas no ar interno.'
        if 'pastilha' in lower:
            return 'Jogo de pastilhas para recuperar atrito e eficiencia de frenagem, recomendado com inspecao de discos e fluido.'
        if 'amortecedor' in lower:
            return 'Amortecedor para controle de oscilacao da carroceria, estabilidade em curvas e contato adequado do pneu com o solo.'
        if 'vela ignicao' in lower:
            return 'Velas de ignicao para centelha correta, melhor partida, queima regular e reducao de falhas de combustao.'
        if 'correia dentada' in lower:
            return 'Componente de sincronismo do motor; a substituicao preventiva evita perda de ponto e danos graves ao conjunto.'
        if 'bateria' in lower:
            return 'Bateria automotiva para partida e estabilizacao eletrica do veiculo, dimensionada conforme capacidade informada.'
        if 'radiador' in lower or 'bomba dagua' in lower:
            return 'Componente do arrefecimento para manter temperatura de trabalho correta e prevenir superaquecimento do motor.'
        return f'{base} Aplicacao cadastrada: {name}.'

    def seed_inventory_items(self, units, brands, categories):
        result = {}
        for data in self.build_part_catalog():
            category = categories[data['categoria']]
            brand = brands[data['marca']]
            obj, _ = InventoryItem.all_objects.get_or_create(
                nome=data['nome'],
                categoria=category,
                marca=brand,
                defaults={
                    'tipo': data['tipo'],
                    'descricao': data['descricao'],
                    'estoque_minimo': data['estoque_minimo'],
                    'unidade': units[data['unidade']],
                    'preco_custo': data['preco_custo'],
                },
            )
            obj.tipo = data['tipo']
            obj.descricao = data['descricao']
            obj.estoque_minimo = data['estoque_minimo']
            obj.unidade = units[data['unidade']]
            obj.preco_custo = data['preco_custo']
            revive(obj)
            obj.save()
            result[data['nome']] = obj
        self.log(f'Pecas/insumos configurados: {len(result)}')
        return result

    def service_specs(self):
        return [
            ('Troca de oleo do motor e filtro', 'Lubrificacao e fluidos', 45, '129.90'),
            ('Troca de oleo com revisao de niveis', 'Manutencao preventiva', 60, '159.90'),
            ('Revisao preventiva 10.000 km', 'Manutencao preventiva', 120, '349.90'),
            ('Revisao preventiva 20.000 km', 'Manutencao preventiva', 150, '449.90'),
            ('Revisao preventiva 40.000 km', 'Manutencao preventiva', 210, '699.90'),
            ('Revisao preventiva 60.000 km', 'Manutencao preventiva', 240, '899.90'),
            ('Troca do filtro de ar do motor', 'Manutencao preventiva', 20, '49.90'),
            ('Troca do filtro de cabine', 'Ar-condicionado e cabine', 25, '59.90'),
            ('Troca do filtro de combustivel flex', 'Manutencao preventiva', 35, '89.90'),
            ('Troca do filtro diesel separador de agua', 'Manutencao preventiva', 50, '139.90'),
            ('Limpeza de bicos injetores flex', 'Ignicao e injecao', 90, '249.90'),
            ('Teste de vazao dos bicos injetores', 'Ignicao e injecao', 80, '219.90'),
            ('Troca de velas de ignicao', 'Ignicao e injecao', 60, '149.90'),
            ('Troca de cabos de vela', 'Ignicao e injecao', 50, '119.90'),
            ('Troca de bobina de ignicao', 'Ignicao e injecao', 45, '129.90'),
            ('Diagnostico de falha de injecao com scanner', 'Diagnostico e inspecao', 70, '189.90'),
            ('Limpeza do corpo de borboleta eletronico', 'Ignicao e injecao', 80, '199.90'),
            ('Troca da sonda lambda pre catalisador', 'Ignicao e injecao', 60, '169.90'),
            ('Troca da bomba de combustivel flex', 'Ignicao e injecao', 120, '299.90'),
            ('Troca do sensor de rotacao', 'Ignicao e injecao', 70, '189.90'),
            ('Troca de pastilhas de freio dianteiras', 'Freios', 80, '179.90'),
            ('Troca de pastilhas de freio traseiras', 'Freios', 80, '179.90'),
            ('Troca de discos de freio dianteiros', 'Freios', 100, '249.90'),
            ('Troca de discos e pastilhas dianteiras', 'Freios', 130, '329.90'),
            ('Troca de sapatas de freio traseiras', 'Freios', 100, '239.90'),
            ('Regulagem e limpeza do freio traseiro', 'Freios', 70, '149.90'),
            ('Sangria e troca do fluido de freio', 'Freios', 70, '169.90'),
            ('Troca de flexivel de freio dianteiro', 'Freios', 75, '159.90'),
            ('Troca de cilindro mestre de freio', 'Freios', 120, '289.90'),
            ('Diagnostico de luz ABS', 'Freios', 80, '199.90'),
            ('Troca do sensor ABS dianteiro', 'Freios', 70, '169.90'),
            ('Substituicao de cabo do freio de mao', 'Freios', 100, '229.90'),
            ('Troca de amortecedores dianteiros', 'Suspensao e estabilidade', 150, '389.90'),
            ('Troca de amortecedores traseiros', 'Suspensao e estabilidade', 110, '289.90'),
            ('Troca de kit batente e coifa dianteiro', 'Suspensao e estabilidade', 120, '249.90'),
            ('Troca de coxim do amortecedor dianteiro', 'Suspensao e estabilidade', 140, '329.90'),
            ('Troca de bieletas dianteiras', 'Suspensao e estabilidade', 80, '169.90'),
            ('Troca de buchas da barra estabilizadora', 'Suspensao e estabilidade', 70, '149.90'),
            ('Troca de pivo de suspensao dianteiro', 'Suspensao e estabilidade', 90, '199.90'),
            ('Troca de bandeja de suspensao esquerda', 'Suspensao e estabilidade', 110, '269.90'),
            ('Troca de bandeja de suspensao direita', 'Suspensao e estabilidade', 110, '269.90'),
            ('Troca de buchas de bandeja dianteira', 'Suspensao e estabilidade', 160, '349.90'),
            ('Troca de molas dianteiras', 'Suspensao e estabilidade', 140, '309.90'),
            ('Troca de bucha do eixo traseiro', 'Suspensao e estabilidade', 180, '449.90'),
            ('Alinhamento dianteiro', 'Direcao e geometria', 45, '99.90'),
            ('Alinhamento 3D completo', 'Direcao e geometria', 70, '169.90'),
            ('Balanceamento de rodas', 'Direcao e geometria', 60, '119.90'),
            ('Rodizio de pneus com calibragem', 'Direcao e geometria', 35, '69.90'),
            ('Troca de terminal de direcao', 'Direcao e geometria', 80, '179.90'),
            ('Troca de barra axial', 'Direcao e geometria', 90, '199.90'),
            ('Troca de coifa da caixa de direcao', 'Direcao e geometria', 80, '169.90'),
            ('Troca de fluido da direcao hidraulica', 'Direcao e geometria', 70, '149.90'),
            ('Diagnostico de folga na direcao', 'Direcao e geometria', 70, '169.90'),
            ('Troca da correia dentada', 'Motor', 180, '449.90'),
            ('Troca do kit correia dentada com tensor', 'Motor', 240, '649.90'),
            ('Troca da correia do alternador', 'Motor', 60, '139.90'),
            ('Troca do tensor da correia auxiliar', 'Motor', 90, '209.90'),
            ('Troca da junta da tampa de valvulas', 'Motor', 120, '289.90'),
            ('Troca da junta do carter', 'Motor', 150, '369.90'),
            ('Troca do coxim do motor', 'Motor', 120, '299.90'),
            ('Troca do retentor dianteiro do virabrequim', 'Motor', 180, '449.90'),
            ('Troca da valvula PCV', 'Motor', 60, '149.90'),
            ('Diagnostico de vazamento de oleo', 'Motor', 90, '219.90'),
            ('Descarbonizacao da admissao', 'Motor', 120, '299.90'),
            ('Troca do sensor de pressao do oleo', 'Motor', 60, '149.90'),
            ('Troca do radiador', 'Arrefecimento', 160, '399.90'),
            ('Troca da bomba dagua', 'Arrefecimento', 180, '449.90'),
            ('Troca da valvula termostatica', 'Arrefecimento', 120, '279.90'),
            ('Limpeza e troca do fluido de arrefecimento', 'Arrefecimento', 90, '219.90'),
            ('Troca da mangueira superior do radiador', 'Arrefecimento', 70, '159.90'),
            ('Troca da mangueira inferior do radiador', 'Arrefecimento', 70, '159.90'),
            ('Troca do reservatorio de expansao', 'Arrefecimento', 60, '139.90'),
            ('Diagnostico de superaquecimento', 'Arrefecimento', 100, '249.90'),
            ('Teste de bateria e sistema de carga', 'Eletrica e bateria', 35, '79.90'),
            ('Troca de bateria', 'Eletrica e bateria', 30, '59.90'),
            ('Troca de lampadas do farol', 'Eletrica e bateria', 30, '69.90'),
            ('Troca de palhetas do limpador', 'Eletrica e bateria', 20, '39.90'),
            ('Diagnostico do alternador', 'Eletrica e bateria', 70, '179.90'),
            ('Troca do regulador de voltagem', 'Eletrica e bateria', 100, '249.90'),
            ('Reparo do motor de partida', 'Eletrica e bateria', 140, '349.90'),
            ('Troca de fusivel e revisao de circuito', 'Eletrica e bateria', 45, '99.90'),
            ('Instalacao de rele auxiliar', 'Eletrica e bateria', 60, '139.90'),
            ('Diagnostico de pane eletrica intermitente', 'Eletrica e bateria', 120, '299.90'),
            ('Troca do kit de embreagem', 'Transmissao e embreagem', 300, '899.90'),
            ('Troca do cilindro mestre da embreagem', 'Transmissao e embreagem', 120, '299.90'),
            ('Troca do atuador hidraulico da embreagem', 'Transmissao e embreagem', 160, '389.90'),
            ('Troca de oleo do cambio manual', 'Transmissao e embreagem', 60, '149.90'),
            ('Troca de fluido CVT', 'Transmissao e embreagem', 100, '299.90'),
            ('Troca da junta homocinetica lado roda', 'Transmissao e embreagem', 120, '289.90'),
            ('Troca da coifa da homocinetica', 'Transmissao e embreagem', 100, '229.90'),
            ('Troca do coxim do cambio', 'Transmissao e embreagem', 100, '249.90'),
            ('Higienizacao do ar-condicionado', 'Ar-condicionado e cabine', 50, '129.90'),
            ('Troca do filtro de cabine com higienizacao', 'Ar-condicionado e cabine', 70, '179.90'),
            ('Carga de gas do ar-condicionado', 'Ar-condicionado e cabine', 90, '249.90'),
            ('Diagnostico de vazamento do ar-condicionado', 'Ar-condicionado e cabine', 90, '229.90'),
            ('Troca do filtro secador do ar-condicionado', 'Ar-condicionado e cabine', 130, '329.90'),
            ('Limpeza do sistema de ventilacao interna', 'Ar-condicionado e cabine', 80, '189.90'),
            ('Troca de rolamento de roda dianteiro', 'Direcao e geometria', 120, '289.90'),
            ('Substituicao de valvulas dos pneus', 'Direcao e geometria', 45, '89.90'),
            ('Inspecao pre-viagem completa', 'Diagnostico e inspecao', 90, '199.90'),
        ]

    def service_description(self, name, category):
        lower = name.lower()
        if 'diagnostico' in lower:
            return f'Avaliacao tecnica de {name.replace("Diagnostico de ", "").lower()} com testes direcionados, leitura de sintomas, verificacao visual e orientacao do reparo recomendado.'
        if 'troca' in lower or 'substituicao' in lower:
            return f'Servico de {name.lower()} com remocao do componente antigo, conferencia da aplicacao, montagem correta e verificacao final de funcionamento.'
        if 'revisao' in lower:
            return f'Revisao com checklist preventivo, substituicao dos itens de desgaste programado e orientacao sobre proximas manutencoes.'
        if 'limpeza' in lower or 'higienizacao' in lower:
            return f'Procedimento de limpeza tecnica para remover residuos, melhorar funcionamento do sistema e entregar o veiculo em condicao adequada de uso.'
        return f'Servico de {category.lower()} executado com avaliacao inicial, aplicacao correta de pecas/insumos e teste de conclusao.'

    def seed_services(self, categories, items):
        result = {}
        for name, category_name, duration, value in self.service_specs():
            obj, _ = Service.all_objects.get_or_create(nome=name, defaults={
                'categoria': categories[category_name],
                'descricao': self.service_description(name, category_name),
                'duracao_minutos': duration,
                'valor': money(value),
            })
            obj.categoria = categories[category_name]
            obj.descricao = self.service_description(name, category_name)
            obj.duracao_minutos = duration
            obj.valor = money(value)
            revive(obj)
            obj.save()
            result[name] = obj
            self.apply_default_parts(obj, items)
        self.log(f'Servicos configurados: {len(result)}')
        return result

    def find_item(self, items, *keywords):
        normalized = [keyword.lower() for keyword in keywords]
        for name, item in items.items():
            lower = name.lower()
            if all(keyword in lower for keyword in normalized):
                return item
        return None

    def default_part_rules(self, service_name, items):
        name = service_name.lower()
        rules = []
        def add(quantity, *keywords, obs='Peca ou insumo padrao do servico.'):
            item = self.find_item(items, *keywords)
            if item:
                rules.append((item, quantity, obs))

        add(1, 'protetor banco', obs='Protecao do interior durante o atendimento.')
        if 'oleo' in name and 'cambio' not in name:
            add(4, 'oleo motor 5w30', obs='Quantidade base para motores flex compactos; ajustar na OS quando necessario.')
            add(1, 'filtro de oleo blindado', obs='Troca recomendada junto com o lubrificante.')
            add(1, 'arruela bujao carter', obs='Vedacao nova do bujao do carter.')
        if 'revisao preventiva' in name:
            add(4, 'oleo motor 5w30')
            add(1, 'filtro de oleo blindado')
            add(1, 'filtro de ar do motor retangular')
            add(1, 'filtro de cabine antipolen')
            add(1, 'filtro de combustivel linha flex')
            add(1, 'aditivo limpador de para-brisa')
        if '60.000' in name or '40.000' in name:
            add(1, 'kit correia dentada com tensor')
            add(1, 'correia alternador 5pk')
            add(1, 'fluido de freio dot 4')
        if 'filtro de ar do motor' in name:
            add(1, 'filtro de ar do motor retangular')
        if 'filtro de cabine' in name:
            add(1, 'filtro de cabine carvao')
            add(1, 'higienizador ar-condicionado')
        if 'filtro de combustivel flex' in name:
            add(1, 'filtro de combustivel linha flex')
        if 'diesel separador' in name:
            add(1, 'filtro separador de agua')
        if 'bicos' in name or 'injecao' in name:
            add(1, 'aditivo limpeza bicos injetores gasolina')
            add(1, 'descarbonizante de admissao')
        if 'velas' in name:
            add(1, 'jogo vela ignicao nickel')
        if 'cabos de vela' in name:
            add(1, 'cabo vela ignicao motor 1.0')
        if 'bobina' in name:
            add(1, 'bobina ignicao dupla')
        if 'corpo de borboleta' in name or 'descarbonizacao' in name:
            add(1, 'descarbonizante de admissao')
            add(1, 'limpa contato eletrico')
        if 'sonda lambda' in name:
            add(1, 'sonda lambda pre catalisador')
        if 'bomba de combustivel' in name:
            add(1, 'bomba combustivel flex refil')
            add(1, 'pre-filtro bomba combustivel')
        if 'sensor de rotacao' in name:
            add(1, 'sensor rotacao virabrequim')
        if 'pastilhas de freio dianteiras' in name:
            add(1, 'jogo pastilha freio dianteira hatch compacto')
            add(1, 'limpa freio spray')
        if 'pastilhas de freio traseiras' in name:
            add(1, 'jogo pastilha freio traseira disco')
            add(1, 'limpa freio spray')
        if 'discos de freio dianteiros' in name or 'discos e pastilhas' in name:
            add(2, 'disco de freio dianteiro ventilado hatch')
            add(1, 'jogo pastilha freio dianteira hatch')
            add(1, 'limpa freio spray')
        if 'sapatas' in name:
            add(1, 'jogo sapata freio traseiro')
            add(1, 'kit regulagem freio traseiro')
        if 'fluido de freio' in name or 'sangria' in name:
            add(1, 'fluido de freio dot 4')
        if 'flexivel de freio' in name:
            add(1, 'flexivel de freio dianteiro')
            add(1, 'fluido de freio dot 4')
        if 'cilindro mestre de freio' in name:
            add(1, 'cilindro mestre de freio')
            add(1, 'fluido de freio dot 4')
        if 'sensor abs' in name or 'luz abs' in name:
            add(1, 'sensor abs roda dianteira')
            add(1, 'limpa contato eletrico')
        if 'cabo do freio de mao' in name:
            add(1, 'cabo freio de mao esquerdo')
            add(1, 'cabo freio de mao direito')
        if 'amortecedores dianteiros' in name:
            add(1, 'amortecedor dianteiro esquerdo')
            add(1, 'amortecedor dianteiro direito')
            add(1, 'kit batente e coifa amortecedor dianteiro')
        if 'amortecedores traseiros' in name:
            add(2, 'amortecedor traseiro hatch')
            add(1, 'kit batente e coifa amortecedor traseiro')
        if 'batente e coifa dianteiro' in name:
            add(1, 'kit batente e coifa amortecedor dianteiro')
        if 'coxim do amortecedor' in name:
            add(2, 'coxim amortecedor dianteiro com rolamento')
        if 'bieletas' in name:
            add(1, 'bieleta dianteira esquerda')
            add(1, 'bieleta dianteira direita')
        if 'buchas da barra' in name:
            add(2, 'bucha barra estabilizadora 19 mm')
        if 'pivo' in name:
            add(1, 'pivo suspensao dianteiro')
        if 'bandeja de suspensao esquerda' in name:
            add(1, 'bandeja suspensao dianteira esquerda')
        if 'bandeja de suspensao direita' in name:
            add(1, 'bandeja suspensao dianteira direita')
        if 'buchas de bandeja' in name:
            add(2, 'bucha bandeja dianteira pequena')
            add(2, 'bucha bandeja dianteira grande')
        if 'molas dianteiras' in name:
            add(2, 'mola helicoidal dianteira')
        if 'eixo traseiro' in name:
            add(2, 'bucha eixo traseiro')
        if 'alinhamento' in name:
            add(2, 'parafuso excentrico cambagem')
        if 'balanceamento' in name:
            add(4, 'peso balanceamento adesivo 10 g')
            add(4, 'bico pneu sem camara')
        if 'rodizio' in name:
            add(4, 'bico pneu sem camara')
        if 'rolamento de roda' in name:
            add(1, 'rolamento roda dianteira')
        if 'valvulas dos pneus' in name:
            add(4, 'bico pneu sem camara')
        if 'pre-viagem' in name:
            add(1, 'aditivo limpador de para-brisa')
            add(1, 'limpa contato eletrico')
            add(1, 'pano microfibra')
        if 'terminal de direcao' in name:
            add(1, 'terminal de direcao esquerdo')
            add(1, 'terminal de direcao direito')
        if 'barra axial' in name:
            add(1, 'barra axial esquerda')
            add(1, 'barra axial direita')
        if 'coifa da caixa' in name:
            add(1, 'coifa caixa direcao lado esquerdo')
            add(1, 'coifa caixa direcao lado direito')
        if 'fluido da direcao' in name:
            add(1, 'fluido direcao hidraulica premium')
        if 'folga na direcao' in name:
            add(1, 'limpa contato eletrico')
        if 'correia dentada' in name:
            add(1, 'kit correia dentada com tensor')
            add(1, 'bomba dagua motor 1.0')
            add(1, 'liquido arrefecimento concentrado')
        if 'correia do alternador' in name:
            add(1, 'correia alternador 5pk')
        if 'tensor da correia auxiliar' in name:
            add(1, 'tensor correia auxiliar')
            add(1, 'correia alternador 5pk')
        if 'tampa de valvulas' in name:
            add(1, 'junta tampa valvulas motor 1.0')
            add(1, 'veda junta anaerobico')
        if 'junta do carter' in name:
            add(1, 'junta carter motor flex')
            add(1, 'arruela bujao carter')
        if 'coxim do motor' in name:
            add(1, 'coxim motor lado direito')
        if 'retentor dianteiro' in name:
            add(1, 'retentor virabrequim dianteiro')
        if 'valvula pcv' in name:
            add(1, 'valvula pcv respiro motor')
            add(1, 'mangueira respiro oleo')
        if 'vazamento de oleo' in name:
            add(1, 'desengraxante biodegradavel')
        if 'sensor de pressao do oleo' in name:
            add(1, 'sensor pressao oleo motor')
        if 'radiador' in name and 'mangueira' not in name:
            add(1, 'radiador motor hatch compacto flex')
            add(1, 'aditivo radiador organico pronto uso 5l')
        if 'bomba dagua' in name:
            add(1, 'bomba dagua motor 1.0')
            add(1, 'junta bomba dagua')
            add(1, 'aditivo radiador organico pronto uso 5l')
        if 'valvula termostatica' in name:
            add(1, 'valvula termostatica 87 graus')
            add(1, 'carcaca valvula termostatica')
        if 'arrefecimento' in name or 'superaquecimento' in name:
            add(1, 'limpa radiador')
            add(1, 'aditivo radiador organico pronto uso 5l')
        if 'mangueira superior' in name:
            add(1, 'mangueira superior radiador')
            add(2, 'abraçadeira mangueira radiador')
        if 'mangueira inferior' in name:
            add(1, 'mangueira inferior radiador')
            add(2, 'abraçadeira mangueira radiador')
        if 'reservatorio de expansao' in name:
            add(1, 'reservatorio expansao radiador')
            add(1, 'tampa reservatorio radiador')
        if 'bateria' in name:
            add(1, 'bateria 60ah')
            add(1, 'limpa contato eletrico')
        if 'lampadas' in name:
            add(2, 'lampada h4')
        if 'palhetas' in name:
            add(1, 'palheta limpador 18')
            add(1, 'aditivo limpador de para-brisa')
        if 'alternador' in name:
            add(1, 'regulador voltagem alternador')
            add(1, 'escova alternador')
        if 'motor de partida' in name:
            add(1, 'bendix motor partida')
        if 'fusivel' in name:
            add(2, 'fusivel lamina mini 10a')
            add(2, 'fusivel lamina mini 15a')
        if 'rele auxiliar' in name:
            add(1, 'rele auxiliar 4 pinos')
        if 'pane eletrica' in name:
            add(1, 'limpa contato eletrico')
            add(1, 'fusivel lamina mini 15a')
        if 'kit de embreagem' in name:
            add(1, 'kit embreagem completo motor 1.0')
        if 'cilindro mestre da embreagem' in name:
            add(1, 'cilindro mestre embreagem')
        if 'atuador hidraulico da embreagem' in name:
            add(1, 'atuador hidraulico embreagem')
        if 'oleo do cambio manual' in name:
            add(2, 'oleo cambio manual 75w80')
        if 'fluido cvt' in name:
            add(4, 'fluido cvt premium')
        if 'homocinetica lado roda' in name:
            add(1, 'junta homocinetica lado roda')
            add(1, 'coifa homocinetica lado roda')
        if 'coifa da homocinetica' in name:
            add(1, 'coifa homocinetica lado roda')
        if 'coxim do cambio' in name:
            add(1, 'coxim cambio inferior')
        if 'higienizacao do ar-condicionado' in name:
            add(1, 'higienizador ar-condicionado')
            add(1, 'filtro de cabine carvao')
        if 'carga de gas' in name:
            add(1, 'limpa ar-condicionado spray')
        if 'vazamento do ar-condicionado' in name:
            add(1, 'limpa contato eletrico')
        if 'filtro secador' in name:
            add(1, 'filtro secador do ar-condicionado')
        if 'ventilacao interna' in name:
            add(1, 'limpa ar-condicionado spray')
            add(1, 'pano microfibra')
        if not rules:
            add(1, 'pano microfibra', obs='Consumivel padrao de apoio ao atendimento.')
        return rules

    def apply_default_parts(self, service, items):
        seen = set()
        for item, quantity, observation in self.default_part_rules(service.nome, items):
            if item.pk in seen:
                continue
            seen.add(item.pk)
            obj, _ = ServiceDefaultPart.objects.get_or_create(
                service=service,
                item=item,
                defaults={'quantidade': quantity, 'observacao': observation[:180]},
            )
            obj.quantidade = quantity
            obj.observacao = observation[:180]
            obj.save(update_fields=['quantidade', 'observacao', 'atualizado_em'])

    def combo_specs(self):
        return [
            ('Combo revisao rapida urbana', ['Troca de oleo do motor e filtro', 'Troca do filtro de ar do motor', 'Troca do filtro de cabine']),
            ('Combo revisao 10.000 km flex', ['Revisao preventiva 10.000 km', 'Alinhamento dianteiro', 'Balanceamento de rodas']),
            ('Combo revisao 20.000 km completa', ['Revisao preventiva 20.000 km', 'Sangria e troca do fluido de freio', 'Rodizio de pneus com calibragem']),
            ('Combo revisao 40.000 km com correia', ['Revisao preventiva 40.000 km', 'Troca do kit correia dentada com tensor', 'Limpeza e troca do fluido de arrefecimento']),
            ('Combo revisao 60.000 km premium', ['Revisao preventiva 60.000 km', 'Troca de oleo do cambio manual', 'Sangria e troca do fluido de freio']),
            ('Combo freio dianteiro completo', ['Troca de discos e pastilhas dianteiras', 'Sangria e troca do fluido de freio']),
            ('Combo freio traseiro tambor', ['Troca de sapatas de freio traseiras', 'Regulagem e limpeza do freio traseiro', 'Sangria e troca do fluido de freio']),
            ('Combo seguranca ABS', ['Diagnostico de luz ABS', 'Troca do sensor ABS dianteiro', 'Sangria e troca do fluido de freio']),
            ('Combo suspensao dianteira leve', ['Troca de amortecedores dianteiros', 'Troca de kit batente e coifa dianteiro', 'Alinhamento dianteiro']),
            ('Combo suspensao dianteira completa', ['Troca de amortecedores dianteiros', 'Troca de coxim do amortecedor dianteiro', 'Troca de bieletas dianteiras', 'Alinhamento 3D completo']),
            ('Combo suspensao traseira', ['Troca de amortecedores traseiros', 'Troca de bucha do eixo traseiro', 'Alinhamento 3D completo']),
            ('Combo estabilidade SUV', ['Troca de bieletas dianteiras', 'Troca de buchas da barra estabilizadora', 'Troca de pivo de suspensao dianteiro', 'Alinhamento 3D completo']),
            ('Combo direcao sem folga', ['Diagnostico de folga na direcao', 'Troca de terminal de direcao', 'Troca de barra axial', 'Alinhamento dianteiro']),
            ('Combo geometria e pneus', ['Alinhamento 3D completo', 'Balanceamento de rodas', 'Rodizio de pneus com calibragem']),
            ('Combo motor partida dificil', ['Diagnostico de falha de injecao com scanner', 'Troca de velas de ignicao', 'Troca de cabos de vela']),
            ('Combo ignicao turbo', ['Diagnostico de falha de injecao com scanner', 'Troca de velas de ignicao', 'Troca de bobina de ignicao']),
            ('Combo injecao limpa', ['Limpeza de bicos injetores flex', 'Limpeza do corpo de borboleta eletronico', 'Descarbonizacao da admissao']),
            ('Combo combustivel flex', ['Troca do filtro de combustivel flex', 'Limpeza de bicos injetores flex', 'Troca da bomba de combustivel flex']),
            ('Combo correia preventiva', ['Troca do kit correia dentada com tensor', 'Troca da correia do alternador', 'Troca da bomba dagua']),
            ('Combo correias auxiliares', ['Troca da correia do alternador', 'Troca do tensor da correia auxiliar']),
            ('Combo vedacao superior motor', ['Troca da junta da tampa de valvulas', 'Troca da valvula PCV', 'Diagnostico de vazamento de oleo']),
            ('Combo vazamento inferior motor', ['Diagnostico de vazamento de oleo', 'Troca da junta do carter', 'Troca do retentor dianteiro do virabrequim']),
            ('Combo arrefecimento preventivo', ['Limpeza e troca do fluido de arrefecimento', 'Troca da valvula termostatica', 'Troca do reservatorio de expansao']),
            ('Combo superaquecimento', ['Diagnostico de superaquecimento', 'Troca da valvula termostatica', 'Troca da bomba dagua']),
            ('Combo radiador completo', ['Troca do radiador', 'Troca da mangueira superior do radiador', 'Troca da mangueira inferior do radiador']),
            ('Combo bateria e carga', ['Teste de bateria e sistema de carga', 'Troca de bateria', 'Diagnostico do alternador']),
            ('Combo iluminacao basica', ['Troca de lampadas do farol', 'Troca de fusivel e revisao de circuito']),
            ('Combo chuva segura', ['Troca de palhetas do limpador', 'Troca de lampadas do farol', 'Rodizio de pneus com calibragem']),
            ('Combo eletrica pesada', ['Diagnostico de pane eletrica intermitente', 'Diagnostico do alternador', 'Reparo do motor de partida']),
            ('Combo embreagem completa', ['Troca do kit de embreagem', 'Troca do atuador hidraulico da embreagem', 'Troca do coxim do cambio']),
            ('Combo cambio manual', ['Troca de oleo do cambio manual', 'Troca do coxim do cambio', 'Troca da coifa da homocinetica']),
            ('Combo transmissao dianteira', ['Troca da junta homocinetica lado roda', 'Troca da coifa da homocinetica', 'Alinhamento dianteiro']),
            ('Combo CVT preventivo', ['Troca de fluido CVT', 'Diagnostico de falha de injecao com scanner']),
            ('Combo cabine saudavel', ['Troca do filtro de cabine com higienizacao', 'Higienizacao do ar-condicionado', 'Limpeza do sistema de ventilacao interna']),
            ('Combo ar-condicionado frio', ['Diagnostico de vazamento do ar-condicionado', 'Carga de gas do ar-condicionado', 'Troca do filtro secador do ar-condicionado']),
            ('Combo diesel preventivo', ['Troca do filtro diesel separador de agua', 'Revisao preventiva 20.000 km', 'Limpeza e troca do fluido de arrefecimento']),
            ('Combo pickup trabalho', ['Revisao preventiva 40.000 km', 'Troca de amortecedores traseiros', 'Troca de sapatas de freio traseiras']),
            ('Combo aplicativo alto uso', ['Troca de oleo com revisao de niveis', 'Troca de pastilhas de freio dianteiras', 'Alinhamento 3D completo']),
            ('Combo viagem curta', ['Troca de oleo com revisao de niveis', 'Teste de bateria e sistema de carga', 'Alinhamento dianteiro', 'Balanceamento de rodas']),
            ('Combo viagem longa', ['Revisao preventiva 20.000 km', 'Sangria e troca do fluido de freio', 'Teste de bateria e sistema de carga', 'Higienizacao do ar-condicionado']),
            ('Combo compra de usado', ['Diagnostico de falha de injecao com scanner', 'Diagnostico de vazamento de oleo', 'Diagnostico de folga na direcao', 'Diagnostico de superaquecimento']),
            ('Combo pos enchente leve', ['Troca de oleo do motor e filtro', 'Troca do filtro de ar do motor', 'Troca do filtro de cabine', 'Diagnostico de pane eletrica intermitente']),
            ('Combo economia de combustivel', ['Troca de velas de ignicao', 'Limpeza de bicos injetores flex', 'Troca do filtro de ar do motor', 'Troca do filtro de combustivel flex']),
            ('Combo conforto urbano', ['Higienizacao do ar-condicionado', 'Troca de palhetas do limpador', 'Troca de coxim do motor']),
            ('Combo luzes painel', ['Diagnostico de falha de injecao com scanner', 'Diagnostico de luz ABS', 'Teste de bateria e sistema de carga']),
            ('Combo freio e suspensao dianteira', ['Troca de discos e pastilhas dianteiras', 'Troca de amortecedores dianteiros', 'Alinhamento 3D completo']),
            ('Combo manutencao premium sedan', ['Revisao preventiva 40.000 km', 'Troca de fluido CVT', 'Higienizacao do ar-condicionado', 'Alinhamento 3D completo']),
            ('Combo utilitario leve', ['Revisao preventiva 20.000 km', 'Troca de sapatas de freio traseiras', 'Troca de amortecedores traseiros', 'Balanceamento de rodas']),
            ('Combo arrefecimento mangueiras', ['Troca da mangueira superior do radiador', 'Troca da mangueira inferior do radiador', 'Limpeza e troca do fluido de arrefecimento']),
            ('Combo vedacao e limpeza motor', ['Diagnostico de vazamento de oleo', 'Troca da junta da tampa de valvulas', 'Descarbonizacao da admissao']),
        ]

    def seed_combos(self, services):
        result = {}
        for index, (name, service_names) in enumerate(self.combo_specs(), start=1):
            selected = [services[service_name] for service_name in service_names if service_name in services]
            if len(selected) < 2:
                continue
            combo, _ = ServiceCombo.all_objects.get_or_create(nome=name, defaults={
                'descricao': self.combo_description(name, selected),
                'desconto_percentual': Decimal('8.00') if index % 3 else Decimal('10.00'),
            })
            combo.descricao = self.combo_description(name, selected)
            combo.desconto_percentual = Decimal('8.00') if index % 3 else Decimal('10.00')
            revive(combo)
            combo.save()
            existing_ids = set(combo.servicos_associados.values_list('service_id', flat=True))
            for service in selected:
                if service.pk not in existing_ids:
                    ServiceComboItem.objects.get_or_create(combo=combo, service=service)
            result[name] = combo
        self.log(f'Combos configurados: {len(result)}')
        return result

    def combo_description(self, name, services):
        service_list = ', '.join(service.nome for service in services)
        return f'{name}: pacote realista com {service_list}. Agrupa servicos complementares para reduzir retrabalho, melhorar previsibilidade do orcamento e facilitar a aprovacao do cliente.'
