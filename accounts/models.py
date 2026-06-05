from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import PessoaTipo, only_digits
from .managers import UserManager


class EmployeeRole(models.TextChoices):
    ADM = 'adm', 'Administrativo'
    ATENDENTE = 'atendente', 'Atendente'
    TECNICO = 'tecnico', 'Técnico'
    FINANCEIRO = 'financeiro', 'Financeiro'
    ESTOQUE = 'estoque', 'Estoque'


class User(AbstractUser):
    username = None
    email = models.EmailField('Email', unique=True)

    role = models.CharField('Função', max_length=20, choices=EmployeeRole.choices, default=EmployeeRole.ATENDENTE)
    tipo_pessoa = models.CharField('Tipo de pessoa', max_length=10, choices=PessoaTipo.choices, default=PessoaTipo.FISICA)
    nome_razao_social = models.CharField('Nome / Razão social', max_length=180)
    documento = models.CharField('CPF / CNPJ', max_length=18, unique=True, blank=True, null=True)
    data_nascimento_fundacao = models.DateField('Nascimento / Fundação', blank=True, null=True)
    whatsapp = models.CharField('WhatsApp', max_length=20, blank=True)
    cep = models.CharField('CEP', max_length=9, blank=True)
    logradouro = models.CharField('Logradouro', max_length=180, blank=True)
    numero = models.CharField('Número', max_length=20, blank=True)
    complemento = models.CharField('Complemento', max_length=120, blank=True)
    bairro = models.CharField('Bairro', max_length=120, blank=True)
    cidade = models.CharField('Cidade', max_length=120, blank=True)
    uf = models.CharField('UF', max_length=2, blank=True)
    aceita_marketing = models.BooleanField('Aceita marketing?', default=False)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nome_razao_social']

    objects = UserManager()

    class Meta:
        verbose_name = 'Funcionário'
        verbose_name_plural = 'Funcionários'
        ordering = ['nome_razao_social', 'email']

    def clean(self):
        super().clean()

        if self.documento:
            digits = only_digits(self.documento)

            if self.tipo_pessoa == PessoaTipo.FISICA and len(digits) != 11:
                raise ValidationError({'documento': 'CPF deve conter 11 dígitos.'})

            if self.tipo_pessoa == PessoaTipo.JURIDICA and len(digits) != 14:
                raise ValidationError({'documento': 'CNPJ deve conter 14 dígitos.'})

    @property
    def is_employee(self):
        return not self.is_superuser

    def __str__(self):
        return self.email


class LoginAttempt(models.Model):
    email = models.EmailField('Email informado', db_index=True)
    ip_address = models.GenericIPAddressField('IP', blank=True, null=True, db_index=True)
    failure_count = models.PositiveIntegerField('Falhas consecutivas', default=0)
    first_failure_at = models.DateTimeField('Primeira falha da janela', blank=True, null=True)
    last_failure_at = models.DateTimeField('Última falha', blank=True, null=True)
    locked_until = models.DateTimeField('Bloqueado até', blank=True, null=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Tentativa de login'
        verbose_name_plural = 'Tentativas de login'
        ordering = ['-last_failure_at', 'email']
        constraints = [
            models.UniqueConstraint(fields=['email', 'ip_address'], name='unique_login_attempt_email_ip'),
        ]

    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > timezone.now())

    def __str__(self):
        return f'{self.email} - {self.ip_address or "sem IP"}'
