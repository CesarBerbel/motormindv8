"""Modelos do site público (vitrine) da oficina.

Conteúdo gerível pelo admin: configurações do site (singleton), serviços
apresentados, artigos do blog, depoimentos e os pedidos de orçamento/contato
recebidos pelo formulário público.
"""

import re

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


def _only_digits(value):
    return re.sub(r'\D', '', value or '')


class SiteSettings(models.Model):
    """Configurações globais do site público. Linha única (pk=1)."""

    nome_fantasia = models.CharField('Nome', max_length=120, default='Automecânica Bandeirantes Multimarcas')
    slogan = models.CharField('Slogan', max_length=180, blank=True, default='Multimarcas com confiança e qualidade')
    sobre = models.TextField(
        'Sobre a oficina',
        blank=True,
        help_text='Texto institucional exibido na página Sobre e na home.',
    )

    logo = models.ImageField('Logo', upload_to='site/', blank=True, null=True)

    telefone_principal = models.CharField('Telefone principal', max_length=20, blank=True, default='(11) 98821-2625')
    telefone_secundario = models.CharField('Telefone secundário', max_length=20, blank=True, default='(11) 98829-2505')
    whatsapp = models.CharField(
        'WhatsApp (somente dígitos com DDD)',
        max_length=20,
        blank=True,
        default='5511988212625',
        help_text='Número usado nos botões de WhatsApp. Ex.: 5511988212625.',
    )
    email_contato = models.EmailField('E-mail público de contato', blank=True)
    email_oficina = models.EmailField(
        'E-mail da oficina',
        blank=True,
        help_text='E-mail interno que receberá pedidos de orçamento enviados pelo site.',
    )

    endereco = models.CharField('Endereço', max_length=200, blank=True)
    bairro = models.CharField('Bairro', max_length=120, blank=True)
    cidade = models.CharField('Cidade', max_length=120, blank=True, default='São Paulo')
    uf = models.CharField('UF', max_length=2, blank=True, default='SP')
    cep = models.CharField('CEP', max_length=9, blank=True)

    horario_semana = models.CharField('Horário (seg-sex)', max_length=120, blank=True, default='08h às 18h')
    horario_sabado = models.CharField('Horário (sábado)', max_length=120, blank=True, default='08h às 12h')
    horario_domingo = models.CharField('Horário (domingo)', max_length=120, blank=True, default='Fechado')

    instagram_url = models.URLField('Instagram', blank=True)
    facebook_url = models.URLField('Facebook', blank=True)
    google_maps_embed = models.URLField(
        'URL de incorporação do Google Maps',
        blank=True,
        help_text='Cole aqui o endereço "src" do iframe de incorporação do Google Maps.',
    )

    hero_titulo = models.CharField(
        'Título do hero',
        max_length=180,
        blank=True,
        default='Cuidamos do seu carro como se fosse nosso',
    )
    hero_subtitulo = models.CharField(
        'Subtítulo do hero',
        max_length=240,
        blank=True,
        default='Mecânica geral multimarcas com diagnóstico preciso, peças de qualidade e atendimento honesto.',
    )

    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Configuração do site'
        verbose_name_plural = 'Configurações do site'

    def __str__(self):
        return self.nome_fantasia

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        if self.whatsapp:
            self.whatsapp = _only_digits(self.whatsapp)
        return super().save(*args, **kwargs)

    @property
    def whatsapp_link(self):
        if not self.whatsapp:
            return ''
        return f'https://wa.me/{self.whatsapp}'

    @property
    def cidade_uf(self):
        partes = [parte for parte in (self.cidade, self.uf) if parte]
        return ' / '.join(partes)

    @property
    def endereco_completo(self):
        partes = [self.endereco, self.bairro, self.cidade_uf, self.cep]
        return ', '.join(parte for parte in partes if parte)


class PublicService(models.Model):
    """Serviço apresentado na vitrine pública (independente da tabela de preços interna)."""

    titulo = models.CharField('Título', max_length=120)
    slug = models.SlugField('Slug', max_length=140, unique=True, blank=True)
    resumo = models.CharField('Resumo', max_length=200, blank=True)
    descricao = models.TextField('Descrição', blank=True)
    icone = models.CharField(
        'Ícone (emoji)',
        max_length=8,
        blank=True,
        help_text='Emoji opcional exibido no cartão. Ex.: 🔧',
    )
    imagem = models.ImageField('Imagem', upload_to='site/servicos/', blank=True, null=True)
    ordem = models.PositiveSmallIntegerField('Ordem', default=0, db_index=True)
    destaque = models.BooleanField('Destacar na home?', default=False, db_index=True)
    ativo = models.BooleanField('Ativo?', default=True, db_index=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Serviço (site)'
        verbose_name_plural = 'Serviços (site)'
        ordering = ['ordem', 'titulo']

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        return super().save(*args, **kwargs)

    def _unique_slug(self):
        base = slugify(self.titulo) or 'servico'
        slug = base
        counter = 2
        while PublicService.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f'{base}-{counter}'
            counter += 1
        return slug

    def get_absolute_url(self):
        return reverse('public_service_detail', kwargs={'slug': self.slug})


class PublishedPostManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(publicado=True, publicado_em__isnull=False)


class BlogPost(models.Model):
    """Artigo do blog/dicas da oficina."""

    titulo = models.CharField('Título', max_length=180)
    slug = models.SlugField('Slug', max_length=200, unique=True, blank=True)
    resumo = models.CharField('Resumo', max_length=300, blank=True)
    conteudo = models.TextField('Conteúdo', help_text='Aceita HTML simples.')
    imagem = models.ImageField('Imagem de destaque', upload_to='site/blog/', blank=True, null=True)
    autor = models.ForeignKey(
        'accounts.User',
        verbose_name='Autor',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='posts_blog',
    )
    publicado = models.BooleanField('Publicado?', default=False, db_index=True)
    publicado_em = models.DateTimeField('Publicado em', blank=True, null=True, db_index=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    objects = models.Manager()
    publicados = PublishedPostManager()

    class Meta:
        verbose_name = 'Artigo do blog'
        verbose_name_plural = 'Artigos do blog'
        ordering = ['-publicado_em', '-criado_em']

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        if self.publicado and self.publicado_em is None:
            self.publicado_em = timezone.now()
        return super().save(*args, **kwargs)

    def _unique_slug(self):
        base = slugify(self.titulo) or 'artigo'
        slug = base
        counter = 2
        while BlogPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f'{base}-{counter}'
            counter += 1
        return slug

    def get_absolute_url(self):
        return reverse('public_blog_detail', kwargs={'slug': self.slug})


class Testimonial(models.Model):
    """Depoimento de cliente exibido na home."""

    nome_cliente = models.CharField('Cliente', max_length=120)
    texto = models.TextField('Depoimento')
    nota = models.PositiveSmallIntegerField('Nota (1 a 5)', default=5)
    ativo = models.BooleanField('Ativo?', default=True, db_index=True)
    ordem = models.PositiveSmallIntegerField('Ordem', default=0, db_index=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Depoimento'
        verbose_name_plural = 'Depoimentos'
        ordering = ['ordem', '-criado_em']

    def __str__(self):
        return self.nome_cliente

    @property
    def estrelas(self):
        nota = max(0, min(5, self.nota or 0))
        return '★' * nota + '☆' * (5 - nota)


class LeadStatus(models.TextChoices):
    NOVO = 'novo', 'Novo'
    EM_CONTATO = 'em_contato', 'Em contato'
    CONCLUIDO = 'concluido', 'Concluído'
    DESCARTADO = 'descartado', 'Descartado'


class Lead(models.Model):
    """Pedido de orçamento/contato recebido pelo formulário público."""

    nome = models.CharField('Nome', max_length=180)
    telefone = models.CharField('Telefone / WhatsApp', max_length=20)
    email = models.EmailField('E-mail', blank=True)
    veiculo = models.CharField('Veículo', max_length=180, blank=True, help_text='Marca, modelo e ano.')
    placa = models.CharField('Placa', max_length=10, blank=True)
    servico = models.ForeignKey(
        PublicService,
        verbose_name='Serviço de interesse',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='leads',
    )
    mensagem = models.TextField('Mensagem', blank=True)
    status = models.CharField('Status', max_length=20, choices=LeadStatus.choices, default=LeadStatus.NOVO, db_index=True)
    origem = models.CharField('Origem', max_length=40, default='site', blank=True)
    criado_em = models.DateTimeField('Recebido em', auto_now_add=True, db_index=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Pedido de orçamento'
        verbose_name_plural = 'Pedidos de orçamento'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.nome} ({self.telefone})'
