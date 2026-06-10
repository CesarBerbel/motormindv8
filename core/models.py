import re

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


def only_digits(value):
    return ''.join(char for char in (value or '') if char.isdigit())


def only_alnum_upper(value):
    return re.sub(r'[^A-Z0-9]', '', (value or '').upper())


def format_plate(value):
    raw = only_alnum_upper(value)[:7]
    old_pattern = r'^[A-Z]{3}[0-9]{4}$'
    mercosul_pattern = r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$'

    if re.match(old_pattern, raw):
        return f'{raw[:3]}-{raw[3:]}'

    if re.match(mercosul_pattern, raw):
        return raw

    return raw


class ActivePessoaManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(ativo=True, excluido_em__isnull=True)


class PessoaTipo(models.TextChoices):
    FISICA = 'fisica', 'Pessoa física'
    JURIDICA = 'juridica', 'Pessoa jurídica'


class PessoaBase(models.Model):
    tipo_pessoa = models.CharField('Tipo de pessoa', max_length=10, choices=PessoaTipo.choices)
    nome_razao_social = models.CharField('Nome / Razão social', max_length=180)
    documento = models.CharField('CPF / CNPJ', max_length=18, blank=True, null=True, db_index=True)
    data_nascimento_fundacao = models.DateField('Nascimento / Fundação', blank=True, null=True)
    email = models.EmailField('Email')
    whatsapp = models.CharField('WhatsApp', max_length=20)
    cep = models.CharField('CEP', max_length=9, blank=True)
    logradouro = models.CharField('Logradouro', max_length=180, blank=True)
    numero = models.CharField('Número', max_length=20, blank=True)
    complemento = models.CharField('Complemento', max_length=120, blank=True)
    bairro = models.CharField('Bairro', max_length=120, blank=True)
    cidade = models.CharField('Cidade', max_length=120, blank=True)
    uf = models.CharField('UF', max_length=2, blank=True)
    aceita_marketing = models.BooleanField('Aceita marketing?', default=False)
    ativo = models.BooleanField('Ativo?', default=True, db_index=True)
    excluido_em = models.DateTimeField('Excluído em', blank=True, null=True, db_index=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    objects = ActivePessoaManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def clean(self):
        super().clean()

        if not self.documento:
            return

        digits = only_digits(self.documento)

        if self.tipo_pessoa == PessoaTipo.FISICA and len(digits) != 11:
            raise ValidationError({'documento': 'CPF deve conter 11 dígitos.'})

        if self.tipo_pessoa == PessoaTipo.JURIDICA and len(digits) != 14:
            raise ValidationError({'documento': 'CNPJ deve conter 14 dígitos.'})

    @property
    def documento_label(self):
        return 'CPF' if self.tipo_pessoa == PessoaTipo.FISICA else 'CNPJ'

    @property
    def nome_label(self):
        return 'Nome' if self.tipo_pessoa == PessoaTipo.FISICA else 'Razão social'

    @property
    def data_label(self):
        return 'Data de nascimento' if self.tipo_pessoa == PessoaTipo.FISICA else 'Data de fundação'

    @property
    def endereco_completo(self):
        partes = [
            self.logradouro,
            self.numero,
            self.complemento,
            self.bairro,
            self.cidade,
            self.uf,
            self.cep,
        ]
        return ', '.join(parte for parte in partes if parte)

    def soft_delete(self):
        self.ativo = False
        self.excluido_em = timezone.now()
        self.save(update_fields=['ativo', 'excluido_em', 'atualizado_em'])

    def restore(self):
        self.ativo = True
        self.excluido_em = None
        self.save(update_fields=['ativo', 'excluido_em', 'atualizado_em'])

    def __str__(self):
        return self.nome_razao_social


class CategoryAudience(models.TextChoices):
    CLIENTE = 'cliente', 'Cliente'
    FORNECEDOR = 'fornecedor', 'Fornecedor'


class Category(models.Model):
    nome = models.CharField('Nome', max_length=120)
    aplicacao = models.CharField('Aplicação', max_length=20, choices=CategoryAudience.choices)
    ativa = models.BooleanField('Ativa?', default=True)
    excluido_em = models.DateTimeField('Excluída em', blank=True, null=True, db_index=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['aplicacao', 'nome']
        constraints = [
            models.UniqueConstraint(
                fields=['nome', 'aplicacao'],
                condition=Q(excluido_em__isnull=True),
                name='unique_active_category_by_audience',
            )
        ]

    def soft_delete(self):
        self.ativa = False
        self.excluido_em = timezone.now()
        self.save(update_fields=['ativa', 'excluido_em', 'atualizado_em'])

    def restore(self):
        self.ativa = True
        self.excluido_em = None
        self.save(update_fields=['ativa', 'excluido_em', 'atualizado_em'])

    def __str__(self):
        return f'{self.nome} ({self.get_aplicacao_display()})'

    def get_absolute_url(self):
        return reverse('category_list')


class Customer(PessoaBase):
    categorias = models.ManyToManyField(
        Category,
        verbose_name='Categorias',
        blank=True,
        related_name='clientes',
        limit_choices_to={'aplicacao': CategoryAudience.CLIENTE, 'ativa': True, 'excluido_em__isnull': True},
    )

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['nome_razao_social']
        constraints = [
            models.UniqueConstraint(
                fields=['documento'],
                condition=Q(ativo=True) & Q(excluido_em__isnull=True) & Q(documento__isnull=False) & ~Q(documento=''),
                name='unique_active_customer_documento_not_blank',
            )
        ]

    def get_absolute_url(self):
        return reverse('customer_detail', kwargs={'pk': self.pk})


class Supplier(PessoaBase):
    categorias = models.ManyToManyField(
        Category,
        verbose_name='Categorias',
        blank=True,
        related_name='fornecedores',
        limit_choices_to={'aplicacao': CategoryAudience.FORNECEDOR, 'ativa': True, 'excluido_em__isnull': True},
    )

    class Meta:
        verbose_name = 'Fornecedor'
        verbose_name_plural = 'Fornecedores'
        ordering = ['nome_razao_social']
        constraints = [
            models.UniqueConstraint(
                fields=['documento'],
                condition=Q(ativo=True) & Q(excluido_em__isnull=True) & Q(documento__isnull=False) & ~Q(documento=''),
                name='unique_active_supplier_documento_not_blank',
            )
        ]

    def get_absolute_url(self):
        return reverse('supplier_detail', kwargs={'pk': self.pk})


class VehicleFipeType(models.TextChoices):
    CARRO = 'cars', 'Carro'
    MOTO = 'motorcycles', 'Moto'
    CAMINHAO = 'trucks', 'Caminhão'


class VehicleFuelType(models.TextChoices):
    GASOLINA = 'gasolina', 'Gasolina'
    ETANOL = 'etanol', 'Etanol'
    FLEX = 'flex', 'Flex'
    DIESEL = 'diesel', 'Diesel'
    GNV = 'gnv', 'GNV'
    ELETRICO = 'eletrico', 'Elétrico'
    HIBRIDO = 'hibrido', 'Híbrido'
    OUTRO = 'outro', 'Outro'


class VehicleDirectionType(models.TextChoices):
    MECANICA = 'mecanica', 'Mecânica'
    HIDRAULICA = 'hidraulica', 'Hidráulica'
    ELETRICA = 'eletrica', 'Elétrica'
    ELETRO_HIDRAULICA = 'eletro_hidraulica', 'Eletro-hidráulica'
    ASSISTIDA = 'assistida', 'Assistida'
    OUTRA = 'outra', 'Outra'


class ActiveVehicleManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(ativo=True, excluido_em__isnull=True)


class Vehicle(models.Model):
    cliente = models.ForeignKey(
        Customer,
        verbose_name='Cliente',
        on_delete=models.PROTECT,
        related_name='veiculos',
    )
    placa = models.CharField('Placa', max_length=8, db_index=True)
    fipe_tipo = models.CharField('Tipo FIPE', max_length=20, choices=VehicleFipeType.choices, default=VehicleFipeType.CARRO)
    fipe_marca_codigo = models.CharField('Código da marca FIPE', max_length=20, blank=True)
    fipe_modelo_codigo = models.CharField('Código do modelo FIPE', max_length=20, blank=True)
    fipe_ano_codigo = models.CharField('Código do ano/versão FIPE', max_length=20, blank=True)
    codigo_fipe = models.CharField('Código FIPE', max_length=20, blank=True)
    mes_referencia_fipe = models.CharField('Mês de referência FIPE', max_length=80, blank=True)
    marca = models.CharField('Marca', max_length=120)
    modelo = models.CharField('Modelo', max_length=180)
    versao = models.CharField('Versão', max_length=180, blank=True)
    qtd_portas = models.PositiveSmallIntegerField(
        'Quantidade de portas',
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(9)],
    )
    combustivel = models.CharField('Combustível', max_length=30, choices=VehicleFuelType.choices, blank=True)
    km = models.PositiveIntegerField('KM', default=0, validators=[MinValueValidator(0)])
    chassi = models.CharField('Chassi', max_length=17, blank=True)
    tipo_direcao = models.CharField('Tipo de direção', max_length=30, choices=VehicleDirectionType.choices, blank=True)
    ar_condicionado = models.BooleanField('Tem ar condicionado?', default=False)
    modificado = models.BooleanField('É modificado?', default=False)
    observacao = models.TextField('Observação', blank=True)
    ativo = models.BooleanField('Ativo?', default=True, db_index=True)
    excluido_em = models.DateTimeField('Excluído em', blank=True, null=True, db_index=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    objects = ActiveVehicleManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'Veículo'
        verbose_name_plural = 'Veículos'
        ordering = ['placa']
        constraints = [
            models.UniqueConstraint(
                fields=['placa'],
                condition=Q(ativo=True) & Q(excluido_em__isnull=True),
                name='unique_active_vehicle_placa',
            )
        ]

    def clean(self):
        super().clean()
        placa = format_plate(self.placa)
        raw = only_alnum_upper(placa)

        if len(raw) != 7:
            raise ValidationError({'placa': 'Informe uma placa válida com 7 caracteres.'})

        if not (re.match(r'^[A-Z]{3}[0-9]{4}$', raw) or re.match(r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$', raw)):
            raise ValidationError({'placa': 'Informe uma placa válida no padrão ABC-1234 ou ABC1D23.'})

        self.placa = placa
        self.chassi = only_alnum_upper(self.chassi)[:17]

    def save(self, *args, **kwargs):
        self.placa = format_plate(self.placa)
        self.chassi = only_alnum_upper(self.chassi)[:17]
        super().save(*args, **kwargs)

    def soft_delete(self):
        self.ativo = False
        self.excluido_em = timezone.now()
        self.save(update_fields=['ativo', 'excluido_em', 'atualizado_em'])

    def restore(self):
        self.ativo = True
        self.excluido_em = None
        self.save(update_fields=['ativo', 'excluido_em', 'atualizado_em'])

    def __str__(self):
        return f'{self.placa} - {self.marca} {self.modelo}'

    def get_absolute_url(self):
        return reverse('vehicle_detail', kwargs={'pk': self.pk})


class AppNotificationLevel(models.TextChoices):
    INFO = 'info', 'Informação'
    SUCCESS = 'success', 'Sucesso'
    WARNING = 'warning', 'Atenção'
    ERROR = 'error', 'Erro'


class AppNotification(models.Model):
    """Notificação interna exibida na interface autenticada do sistema."""

    usuario = models.ForeignKey(
        'accounts.User',
        verbose_name='Usuário',
        on_delete=models.CASCADE,
        related_name='notificacoes_app',
    )
    titulo = models.CharField('Título', max_length=160)
    mensagem = models.TextField('Mensagem', blank=True)
    url = models.CharField('URL de destino', max_length=300, blank=True)
    nivel = models.CharField('Nível', max_length=20, choices=AppNotificationLevel.choices, default=AppNotificationLevel.INFO)
    categoria = models.CharField('Categoria', max_length=60, blank=True, db_index=True)
    lida_em = models.DateTimeField('Lida em', blank=True, null=True, db_index=True)
    exibida_em = models.DateTimeField('Exibida em', blank=True, null=True, db_index=True)
    criado_em = models.DateTimeField('Criada em', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Notificação interna'
        verbose_name_plural = 'Notificações internas'
        ordering = ['-criado_em', '-pk']
        indexes = [
            models.Index(fields=['usuario', 'lida_em', '-criado_em']),
            models.Index(fields=['usuario', 'exibida_em', '-criado_em']),
        ]

    @property
    def is_read(self):
        return self.lida_em is not None

    def mark_displayed(self):
        if self.exibida_em is None:
            self.exibida_em = timezone.now()
            self.save(update_fields=['exibida_em'])

    def mark_read(self):
        if self.lida_em is None:
            self.lida_em = timezone.now()
            self.save(update_fields=['lida_em'])

    def __str__(self):
        return f'{self.titulo} - {self.usuario}'
