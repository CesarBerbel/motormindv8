from django import forms

from core.forms import BASE_CHECKBOX_CLASS, BASE_INPUT_CLASS, BASE_SELECT_CLASS, format_phone
from .models import BlogPost, Lead, PublicService

BASE_TEXTAREA_CLASS = 'textarea textarea-bordered min-h-32 w-full'
BASE_FILE_CLASS = 'file-input file-input-bordered w-full'


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['nome', 'telefone', 'email', 'veiculo', 'placa', 'servico', 'mensagem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'Seu nome'}),
            'telefone': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': '(11) 90000-0000'}),
            'email': forms.EmailInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'seu@email.com (opcional)'}),
            'veiculo': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'Ex.: Fiat Uno 2015'}),
            'placa': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'ABC1D23 (opcional)'}),
            'servico': forms.Select(attrs={'class': BASE_SELECT_CLASS}),
            'mensagem': forms.Textarea(attrs={
                'class': BASE_TEXTAREA_CLASS,
                'placeholder': 'Descreva o problema ou o serviço que precisa.',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['servico'].queryset = PublicService.objects.filter(ativo=True).order_by('ordem', 'titulo')
        self.fields['servico'].empty_label = 'Não sei / outro'
        self.fields['email'].required = False
        self.fields['veiculo'].required = False
        self.fields['placa'].required = False
        self.fields['servico'].required = False
        self.fields['mensagem'].required = False

    def clean_telefone(self):
        telefone = (self.cleaned_data.get('telefone') or '').strip()
        return format_phone(telefone) or telefone

    def clean_placa(self):
        return (self.cleaned_data.get('placa') or '').strip().upper()


class BlogPostForm(forms.ModelForm):
    class Meta:
        model = BlogPost
        fields = ['titulo', 'slug', 'resumo', 'imagem', 'conteudo', 'publicado']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'Título do artigo'}),
            'slug': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'gerado-automaticamente (opcional)'}),
            'resumo': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered min-h-20 w-full',
                'placeholder': 'Resumo curto exibido na lista do blog.',
            }),
            'imagem': forms.ClearableFileInput(attrs={'class': BASE_FILE_CLASS, 'accept': 'image/*'}),
            'conteudo': forms.Textarea(attrs={
                'class': 'textarea textarea-bordered min-h-96 w-full',
                'placeholder': 'Conteúdo do artigo. Aceita HTML simples (<p>, <h2>, <ul>, <strong>...).',
            }),
            'publicado': forms.CheckboxInput(attrs={'class': BASE_CHECKBOX_CLASS}),
        }
        help_texts = {
            'slug': 'Endereço do artigo. Se ficar vazio, é gerado a partir do título.',
            'conteudo': 'Aceita HTML simples. Use <h2> para subtítulos e <p> para parágrafos.',
            'publicado': 'Enquanto desmarcado, o artigo fica como rascunho e não aparece no site.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['resumo'].required = False
        self.fields['imagem'].required = False
