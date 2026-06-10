from django import forms

from core.forms import BASE_CHECKBOX_CLASS, BASE_INPUT_CLASS, BASE_SELECT_CLASS, format_phone
from core.models import only_digits
from .models import BlogPost, Lead, LeadStatus, PublicService, SiteSettings

BASE_TEXTAREA_CLASS = 'textarea textarea-bordered min-h-32 w-full'
BASE_FILE_CLASS = 'file-input file-input-bordered w-full'


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['nome', 'telefone', 'email', 'veiculo', 'placa', 'servico', 'mensagem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'Seu nome'}),
            'telefone': forms.TextInput(attrs={
                'class': BASE_INPUT_CLASS,
                'placeholder': '(11) 90000-0000',
                'autocomplete': 'tel',
                'inputmode': 'tel',
            }),
            'email': forms.EmailInput(attrs={
                'class': BASE_INPUT_CLASS,
                'placeholder': 'seu@email.com',
                'autocomplete': 'email',
                'inputmode': 'email',
            }),
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
        self.fields['email'].required = True
        self.fields['veiculo'].required = False
        self.fields['placa'].required = False
        self.fields['servico'].required = False
        self.fields['mensagem'].required = False

    def clean_telefone(self):
        telefone = (self.cleaned_data.get('telefone') or '').strip()
        digits = only_digits(telefone)

        # Aceita entrada com codigo do Brasil (+55/55) e armazena no padrao local.
        if len(digits) in (12, 13) and digits.startswith('55'):
            digits = digits[2:]

        if len(digits) not in (10, 11):
            raise forms.ValidationError('Informe um telefone/WhatsApp valido com DDD.')

        ddd = int(digits[:2])
        subscriber = digits[2:]
        if ddd < 11 or subscriber.startswith('0') or len(set(digits)) == 1:
            raise forms.ValidationError('Informe um telefone/WhatsApp valido.')

        return format_phone(digits)

    def clean_placa(self):
        return (self.cleaned_data.get('placa') or '').strip().upper()


class LeadStatusForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': BASE_SELECT_CLASS}),
        }


class LeadFilterForm(forms.Form):
    q = forms.CharField(
        label='Busca',
        required=False,
        widget=forms.TextInput(attrs={
            'class': BASE_INPUT_CLASS,
            'placeholder': 'Nome, telefone, e-mail, veículo, placa ou mensagem',
        }),
    )
    status = forms.ChoiceField(
        label='Status',
        required=False,
        choices=[('', 'Todos os status')] + list(LeadStatus.choices),
        widget=forms.Select(attrs={'class': BASE_SELECT_CLASS}),
    )
    servico = forms.ModelChoiceField(
        label='Serviço',
        required=False,
        queryset=PublicService.objects.none(),
        empty_label='Todos os serviços',
        widget=forms.Select(attrs={'class': BASE_SELECT_CLASS}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['servico'].queryset = PublicService.objects.order_by('ordem', 'titulo')


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


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            'nome_fantasia', 'slogan', 'sobre', 'logo',
            'hero_titulo', 'hero_subtitulo',
            'telefone_principal', 'telefone_secundario', 'whatsapp', 'email_contato', 'email_oficina',
            'endereco', 'bairro', 'cidade', 'uf', 'cep', 'google_maps_embed',
            'horario_semana', 'horario_sabado', 'horario_domingo',
            'instagram_url', 'facebook_url',
        ]
        widgets = {
            'nome_fantasia': forms.TextInput(attrs={'class': BASE_INPUT_CLASS}),
            'slogan': forms.TextInput(attrs={'class': BASE_INPUT_CLASS}),
            'sobre': forms.Textarea(attrs={'class': BASE_TEXTAREA_CLASS}),
            'logo': forms.ClearableFileInput(attrs={'class': BASE_FILE_CLASS, 'accept': 'image/*'}),
            'hero_titulo': forms.TextInput(attrs={'class': BASE_INPUT_CLASS}),
            'hero_subtitulo': forms.TextInput(attrs={'class': BASE_INPUT_CLASS}),
            'telefone_principal': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': '(11) 90000-0000'}),
            'telefone_secundario': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': '(11) 90000-0000'}),
            'whatsapp': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': '5511900000000'}),
            'email_contato': forms.EmailInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'contato@oficina.com'}),
            'email_oficina': forms.EmailInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'orcamentos@oficina.com'}),
            'endereco': forms.TextInput(attrs={'class': BASE_INPUT_CLASS}),
            'bairro': forms.TextInput(attrs={'class': BASE_INPUT_CLASS}),
            'cidade': forms.TextInput(attrs={'class': BASE_INPUT_CLASS}),
            'uf': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'maxlength': 2}),
            'cep': forms.TextInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': '00000-000'}),
            'google_maps_embed': forms.URLInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'https://www.google.com/maps/embed?...'}),
            'horario_semana': forms.TextInput(attrs={'class': BASE_INPUT_CLASS}),
            'horario_sabado': forms.TextInput(attrs={'class': BASE_INPUT_CLASS}),
            'horario_domingo': forms.TextInput(attrs={'class': BASE_INPUT_CLASS}),
            'instagram_url': forms.URLInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'https://instagram.com/...'}),
            'facebook_url': forms.URLInput(attrs={'class': BASE_INPUT_CLASS, 'placeholder': 'https://facebook.com/...'}),
        }
