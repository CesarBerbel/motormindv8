# Generated manually for MotorMind v37 AI assistant field-specific instructions.

from django.db import migrations, models


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


class Migration(migrations.Migration):

    dependencies = [
        ('ai_assistant', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='aisettings',
            name='instrucao_problema_relatado',
            field=models.TextField(
                blank=True,
                default=DEFAULT_INSTRUCAO_PROBLEMA_RELATADO,
                help_text='Regra usada pelo botão IA melhorar no campo Problema relatado.',
                verbose_name='Instrução específica: problema relatado',
            ),
        ),
        migrations.AddField(
            model_name='aisettings',
            name='instrucao_diagnostico',
            field=models.TextField(
                blank=True,
                default=DEFAULT_INSTRUCAO_DIAGNOSTICO,
                help_text='Regra usada pelo botão IA detalhar no campo Diagnóstico.',
                verbose_name='Instrução específica: diagnóstico',
            ),
        ),
        migrations.AddField(
            model_name='aisettings',
            name='instrucao_observacao',
            field=models.TextField(
                blank=True,
                default=DEFAULT_INSTRUCAO_OBSERVACAO,
                help_text='Regra usada pelo botão Sugerir obs., considerando os dados da OS enviados no contexto.',
                verbose_name='Instrução específica: observação da OS',
            ),
        ),
        migrations.AddField(
            model_name='aisettings',
            name='instrucao_template_mensagem',
            field=models.TextField(
                blank=True,
                default=DEFAULT_INSTRUCAO_TEMPLATE,
                help_text='Regra usada para melhorar/gerar templates de email, WhatsApp e mensagens manuais.',
                verbose_name='Instrução específica: templates e mensagens',
            ),
        ),
    ]
