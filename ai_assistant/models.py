from django.conf import settings
from django.db import models
from django.utils import timezone

from core.encryption import EncryptedTextField


class AIProvider(models.TextChoices):
    LOCAL = 'local', 'Local / simulado'
    OPENAI = 'openai', 'OpenAI'
    ANTHROPIC = 'anthropic', 'Anthropic'
    GEMINI = 'gemini', 'Google Gemini'
    OLLAMA = 'ollama', 'Ollama'
    CUSTOM = 'custom', 'Endpoint customizado'


class AIAssistantAction(models.TextChoices):
    IMPROVE_PROBLEM = 'improve_problem', 'Melhorar problema relatado'
    IMPROVE_DIAGNOSIS = 'improve_diagnosis', 'Melhorar diagnóstico'
    SUGGEST_OBSERVATION = 'suggest_observation', 'Sugerir observação pertinente'
    IMPROVE_MESSAGE = 'improve_message', 'Melhorar mensagem/template'
    EMAIL_TEMPLATE = 'email_template', 'Gerar template de email'
    WHATSAPP_TEMPLATE = 'whatsapp_template', 'Gerar template de WhatsApp'
    GENERAL = 'general', 'Ajuda geral'




DEFAULT_INSTRUCAO_PROBLEMA_RELATADO = (
    'Melhore apenas o relato do cliente, mantendo o sentido original, sem transformar em diagnóstico. '
    'Deixe a descrição curta, clara e objetiva para abertura da OS.'
)
DEFAULT_INSTRUCAO_DIAGNOSTICO = (
    'Elabore melhor o diagnóstico técnico, detalhando o serviço que deverá ser feito, desmontagens necessárias, '
    'testes/verificações realizados, esforço aplicado e próximos passos. Não invente medições, códigos de falha, peças ou conclusões.'
)
DEFAULT_INSTRUCAO_OBSERVACAO = (
    'Sugira observações pertinentes levando em consideração todos os dados disponíveis da OS, como cliente, veículo, problema relatado, '
    'diagnóstico, itens, status e contexto operacional. Seja útil, objetivo e não repita informações desnecessárias.'
)
DEFAULT_INSTRUCAO_TEMPLATE = (
    'Ao gerar ou melhorar templates de email/WhatsApp, leve em consideração o contexto informado, o tipo de template, o público de destino '
    'e o momento da OS. Preserve variáveis do sistema, como {{ cliente.nome_razao_social }}, {{ ordem_servico.codigo }}, {{ veiculo }} '
    'e {{ link_aprovacao }}, quando existirem.'
)

class AISettings(models.Model):
    ativo = models.BooleanField('IA ativa?', default=True)
    provedor = models.CharField('Provedor', max_length=30, choices=AIProvider.choices, default=AIProvider.LOCAL)
    modelo = models.CharField('Modelo', max_length=120, blank=True, default='gpt-4o-mini')
    api_key = EncryptedTextField('Chave de API', blank=True, default='')
    endpoint_base = models.URLField('Endpoint/base URL', blank=True)
    temperatura = models.DecimalField('Temperatura', max_digits=3, decimal_places=2, default=0.30)
    timeout_segundos = models.PositiveIntegerField('Timeout em segundos', default=20)

    tom_resposta = models.CharField(
        'Tom das respostas',
        max_length=120,
        blank=True,
        default='profissional, claro, objetivo e cordial',
    )
    caracteristicas_oficina = models.TextField(
        'Características da oficina',
        blank=True,
        help_text='Ex.: oficina premium, atendimento consultivo, linguagem simples, foco em transparência.',
    )
    instrucoes_gerais = models.TextField(
        'Instruções gerais para a IA',
        blank=True,
        default=(
            'Escreva em português do Brasil. Não invente medições, peças, laudos, falhas ou serviços. '
            'Quando faltar informação técnica, indique que a informação deve ser confirmada pela oficina.'
        ),
    )

    instrucao_problema_relatado = models.TextField(
        'Instrução específica: problema relatado',
        blank=True,
        default=DEFAULT_INSTRUCAO_PROBLEMA_RELATADO,
        help_text='Regra usada pelo botão IA melhorar no campo Problema relatado.',
    )
    instrucao_diagnostico = models.TextField(
        'Instrução específica: diagnóstico',
        blank=True,
        default=DEFAULT_INSTRUCAO_DIAGNOSTICO,
        help_text='Regra usada pelo botão IA detalhar no campo Diagnóstico.',
    )
    instrucao_observacao = models.TextField(
        'Instrução específica: observação da OS',
        blank=True,
        default=DEFAULT_INSTRUCAO_OBSERVACAO,
        help_text='Regra usada pelo botão Sugerir obs., considerando os dados da OS enviados no contexto.',
    )
    instrucao_template_mensagem = models.TextField(
        'Instrução específica: templates e mensagens',
        blank=True,
        default=DEFAULT_INSTRUCAO_TEMPLATE,
        help_text='Regra usada para melhorar/gerar templates de email, WhatsApp e mensagens manuais.',
    )
    limite_caracteres_resposta = models.PositiveIntegerField('Limite aproximado de caracteres', default=1200)

    habilitar_os = models.BooleanField('Exibir IA em campos da OS?', default=True)
    habilitar_mensagens = models.BooleanField('Exibir IA em templates/mensagens?', default=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Configuração de IA'
        verbose_name_plural = 'Configurações de IA'
        permissions = [
            ('use_ai_assistant', 'Pode usar o assistente de IA'),
        ]

    def __str__(self):
        return f'IA: {self.get_provedor_display()} ({"ativa" if self.ativo else "inativa"})'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.ativo = False
        self.api_key = ''
        self.endpoint_base = ''
        self.save(update_fields=['ativo', 'api_key', 'endpoint_base', 'atualizado_em'])

    @property
    def masked_api_key(self):
        if not self.api_key:
            return 'Não configurada'
        if len(self.api_key) <= 8:
            return '••••'
        return f'{self.api_key[:4]}••••{self.api_key[-4:]}'


class AIInteractionLog(models.Model):
    acao = models.CharField('Ação', max_length=40, choices=AIAssistantAction.choices)
    provedor = models.CharField('Provedor', max_length=30, choices=AIProvider.choices)
    modelo = models.CharField('Modelo', max_length=120, blank=True)
    entrada = models.TextField('Entrada', blank=True)
    contexto = models.JSONField('Contexto', default=dict, blank=True)
    resposta = models.TextField('Resposta', blank=True)
    sucesso = models.BooleanField('Sucesso?', default=False)
    erro = models.TextField('Erro', blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='Usuário', on_delete=models.SET_NULL, blank=True, null=True)
    criado_em = models.DateTimeField('Criado em', default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'Registro de uso de IA'
        verbose_name_plural = 'Registros de uso de IA'
        ordering = ['-criado_em']

    def __str__(self):
        status = 'ok' if self.sucesso else 'erro'
        return f'{self.get_acao_display()} - {status} - {self.criado_em:%d/%m/%Y %H:%M}'
