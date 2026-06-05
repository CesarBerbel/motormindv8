# Generated manually for MotorMind v37 AI assistant.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AISettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ativo', models.BooleanField(default=True, verbose_name='IA ativa?')),
                ('provedor', models.CharField(choices=[('local', 'Local / simulado'), ('openai', 'OpenAI'), ('anthropic', 'Anthropic'), ('gemini', 'Google Gemini'), ('ollama', 'Ollama'), ('custom', 'Endpoint customizado')], default='local', max_length=30, verbose_name='Provedor')),
                ('modelo', models.CharField(blank=True, default='gpt-4o-mini', max_length=120, verbose_name='Modelo')),
                ('api_key', models.CharField(blank=True, max_length=500, verbose_name='Chave de API')),
                ('endpoint_base', models.URLField(blank=True, verbose_name='Endpoint/base URL')),
                ('temperatura', models.DecimalField(decimal_places=2, default=0.3, max_digits=3, verbose_name='Temperatura')),
                ('timeout_segundos', models.PositiveIntegerField(default=20, verbose_name='Timeout em segundos')),
                ('tom_resposta', models.CharField(blank=True, default='profissional, claro, objetivo e cordial', max_length=120, verbose_name='Tom das respostas')),
                ('caracteristicas_oficina', models.TextField(blank=True, help_text='Ex.: oficina premium, atendimento consultivo, linguagem simples, foco em transparência.', verbose_name='Características da oficina')),
                ('instrucoes_gerais', models.TextField(blank=True, default='Escreva em português do Brasil. Não invente medições, peças, laudos, falhas ou serviços. Quando faltar informação técnica, indique que a informação deve ser confirmada pela oficina.', verbose_name='Instruções gerais para a IA')),
                ('limite_caracteres_resposta', models.PositiveIntegerField(default=1200, verbose_name='Limite aproximado de caracteres')),
                ('habilitar_os', models.BooleanField(default=True, verbose_name='Exibir IA em campos da OS?')),
                ('habilitar_mensagens', models.BooleanField(default=True, verbose_name='Exibir IA em templates/mensagens?')),
                ('atualizado_em', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
            ],
            options={
                'verbose_name': 'Configuração de IA',
                'verbose_name_plural': 'Configurações de IA',
                'permissions': [('use_ai_assistant', 'Pode usar o assistente de IA')],
            },
        ),
        migrations.CreateModel(
            name='AIInteractionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('acao', models.CharField(choices=[('improve_problem', 'Melhorar problema relatado'), ('improve_diagnosis', 'Melhorar diagnóstico'), ('suggest_observation', 'Sugerir observação pertinente'), ('improve_message', 'Melhorar mensagem/template'), ('email_template', 'Gerar template de email'), ('whatsapp_template', 'Gerar template de WhatsApp'), ('general', 'Ajuda geral')], max_length=40, verbose_name='Ação')),
                ('provedor', models.CharField(choices=[('local', 'Local / simulado'), ('openai', 'OpenAI'), ('anthropic', 'Anthropic'), ('gemini', 'Google Gemini'), ('ollama', 'Ollama'), ('custom', 'Endpoint customizado')], max_length=30, verbose_name='Provedor')),
                ('modelo', models.CharField(blank=True, max_length=120, verbose_name='Modelo')),
                ('entrada', models.TextField(blank=True, verbose_name='Entrada')),
                ('contexto', models.JSONField(blank=True, default=dict, verbose_name='Contexto')),
                ('resposta', models.TextField(blank=True, verbose_name='Resposta')),
                ('sucesso', models.BooleanField(default=False, verbose_name='Sucesso?')),
                ('erro', models.TextField(blank=True, verbose_name='Erro')),
                ('criado_em', models.DateTimeField(db_index=True, default=timezone.now, verbose_name='Criado em')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
            ],
            options={
                'verbose_name': 'Registro de uso de IA',
                'verbose_name_plural': 'Registros de uso de IA',
                'ordering': ['-criado_em'],
            },
        ),
    ]
