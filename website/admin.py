from django.contrib import admin

from .models import BlogPost, Lead, PublicService, SiteSettings, Testimonial


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('nome_fantasia', 'telefone_principal', 'whatsapp', 'cidade', 'atualizado_em')
    readonly_fields = ('atualizado_em',)
    fieldsets = (
        ('Identidade', {'fields': ('nome_fantasia', 'slogan', 'logo', 'sobre')}),
        ('Hero (topo da home)', {'fields': ('hero_titulo', 'hero_subtitulo')}),
        ('Contato', {'fields': ('telefone_principal', 'telefone_secundario', 'whatsapp', 'email_contato')}),
        ('Endereço', {'fields': ('endereco', 'bairro', 'cidade', 'uf', 'cep', 'google_maps_embed')}),
        ('Horário', {'fields': ('horario_semana', 'horario_sabado', 'horario_domingo')}),
        ('Redes sociais', {'fields': ('instagram_url', 'facebook_url')}),
        ('Sistema', {'fields': ('atualizado_em',)}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PublicService)
class PublicServiceAdmin(admin.ModelAdmin):
    list_display = ('ordem', 'titulo', 'destaque', 'ativo', 'atualizado_em')
    list_display_links = ('titulo',)
    list_editable = ('ordem', 'destaque', 'ativo')
    list_filter = ('ativo', 'destaque')
    search_fields = ('titulo', 'resumo', 'descricao')
    prepopulated_fields = {'slug': ('titulo',)}
    readonly_fields = ('criado_em', 'atualizado_em')


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'publicado', 'publicado_em', 'autor', 'atualizado_em')
    list_filter = ('publicado', 'publicado_em')
    search_fields = ('titulo', 'resumo', 'conteudo')
    prepopulated_fields = {'slug': ('titulo',)}
    readonly_fields = ('criado_em', 'atualizado_em')
    autocomplete_fields = ()

    def save_model(self, request, obj, form, change):
        if obj.autor_id is None:
            obj.autor = request.user
        super().save_model(request, obj, form, change)


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('ordem', 'nome_cliente', 'nota', 'ativo', 'criado_em')
    list_display_links = ('nome_cliente',)
    list_editable = ('ordem', 'ativo')
    list_filter = ('ativo', 'nota')
    search_fields = ('nome_cliente', 'texto')


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('criado_em', 'nome', 'telefone', 'veiculo', 'servico', 'status')
    list_filter = ('status', 'criado_em', 'servico')
    search_fields = ('nome', 'telefone', 'email', 'veiculo', 'placa', 'mensagem')
    list_editable = ('status',)
    readonly_fields = ('nome', 'telefone', 'email', 'veiculo', 'placa', 'servico', 'mensagem', 'origem', 'criado_em', 'atualizado_em')
    fields = ('status', 'nome', 'telefone', 'email', 'veiculo', 'placa', 'servico', 'mensagem', 'origem', 'criado_em', 'atualizado_em')

    def has_add_permission(self, request):
        return False
