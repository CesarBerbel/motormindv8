from django import forms

from core.forms import BASE_CHECKBOX_CLASS, BASE_INPUT_CLASS, BASE_SELECT_CLASS
from .models import AIProvider, AISettings


BASE_TEXTAREA_CLASS = 'textarea textarea-bordered min-h-28 w-full'


class AISettingsForm(forms.ModelForm):
    class Meta:
        model = AISettings
        fields = [
            'ativo',
            'provedor',
            'modelo',
            'api_key',
            'endpoint_base',
            'temperatura',
            'timeout_segundos',
            'tom_resposta',
            'caracteristicas_oficina',
            'instrucoes_gerais',
            'instrucao_problema_relatado',
            'instrucao_diagnostico',
            'instrucao_observacao',
            'instrucao_template_mensagem',
            'limite_caracteres_resposta',
            'habilitar_os',
            'habilitar_mensagens',
        ]
        widgets = {
            'ativo': forms.CheckboxInput(attrs={'class': BASE_CHECKBOX_CLASS}),
            'provedor': forms.Select(attrs={'class': BASE_SELECT_CLASS}),
            'modelo': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'Ex.: gpt-4o-mini, claude-3-5-sonnet-latest, gemini-1.5-flash, llama3'}),
            'api_key': forms.PasswordInput(render_value=True, attrs={'class': BASE_INPUT_CLASS, 'autocomplete': 'new-password', 'placeholder': 'Cole a chave do provedor, quando aplicável'}),
            'endpoint_base': forms.URLInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'Opcional. Ex.: http://localhost:11434 ou https://api.openai.com'}),
            'temperatura': forms.NumberInput(attrs={'class': BASE_INPUT_CLASS, 'min': '0', 'max': '2', 'step': '0.1'}),
            'timeout_segundos': forms.NumberInput(attrs={'class': BASE_INPUT_CLASS, 'min': '3', 'max': '120', 'step': '1'}),
            'tom_resposta': forms.TextInput(attrs={'class': BASE_INPUT_CLASS}),
            'caracteristicas_oficina': forms.Textarea(attrs={'class': BASE_TEXTAREA_CLASS, 'rows': 3}),
            'instrucoes_gerais': forms.Textarea(attrs={'class': BASE_TEXTAREA_CLASS, 'rows': 4}),
            'instrucao_problema_relatado': forms.Textarea(attrs={'class': BASE_TEXTAREA_CLASS, 'rows': 3}),
            'instrucao_diagnostico': forms.Textarea(attrs={'class': BASE_TEXTAREA_CLASS, 'rows': 4}),
            'instrucao_observacao': forms.Textarea(attrs={'class': BASE_TEXTAREA_CLASS, 'rows': 4}),
            'instrucao_template_mensagem': forms.Textarea(attrs={'class': BASE_TEXTAREA_CLASS, 'rows': 4}),
            'limite_caracteres_resposta': forms.NumberInput(attrs={'class': BASE_INPUT_CLASS, 'min': '200', 'max': '5000', 'step': '50'}),
            'habilitar_os': forms.CheckboxInput(attrs={'class': BASE_CHECKBOX_CLASS}),
            'habilitar_mensagens': forms.CheckboxInput(attrs={'class': BASE_CHECKBOX_CLASS}),
        }
        help_texts = {
            'provedor': 'Use Local / simulado para desenvolvimento sem internet/chave. Para produção, selecione o provedor real.',
            'modelo': 'Nome do modelo no provedor selecionado.',
            'endpoint_base': 'Obrigatório para Ollama/customizado quando o serviço estiver fora do padrão. Opcional para OpenAI/Anthropic/Gemini.',
            'temperatura': 'Valores menores deixam a resposta mais objetiva e consistente.',
            'limite_caracteres_resposta': 'Ajuda a controlar respostas curtas nos botões pequenos do sistema.',
            'instrucao_problema_relatado': 'Ex.: deixar curto, melhorar gramática e não diagnosticar.',
            'instrucao_diagnostico': 'Ex.: detalhar desmontagem, testes, esforço técnico e próximos passos sem inventar medições.',
            'instrucao_observacao': 'Ex.: considerar cliente, veículo, problema, diagnóstico e itens da OS.',
            'instrucao_template_mensagem': 'Ex.: considerar contexto, canal, tipo do template e preservar variáveis do sistema.',
        }

    def clean(self):
        cleaned_data = super().clean()
        provider = cleaned_data.get('provedor')
        api_key = (cleaned_data.get('api_key') or '').strip()
        endpoint_base = (cleaned_data.get('endpoint_base') or '').strip()

        if provider in {AIProvider.OPENAI, AIProvider.ANTHROPIC, AIProvider.GEMINI} and not api_key:
            self.add_error('api_key', 'Informe a chave de API para usar este provedor.')
        if provider in {AIProvider.OLLAMA, AIProvider.CUSTOM} and not endpoint_base:
            self.add_error('endpoint_base', 'Informe o endpoint/base URL para este provedor.')
        return cleaned_data
