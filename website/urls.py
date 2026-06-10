from django.urls import path

from . import views

urlpatterns = [
    path('', views.PublicHomeView.as_view(), name='public_home'),
    path('servicos/', views.PublicServiceListView.as_view(), name='public_service_list'),
    path('servicos/<slug:slug>/', views.PublicServiceDetailView.as_view(), name='public_service_detail'),
    path('blog/', views.PublicBlogListView.as_view(), name='public_blog_list'),
    path('blog/<slug:slug>/', views.PublicBlogDetailView.as_view(), name='public_blog_detail'),
    path('sobre/', views.PublicAboutView.as_view(), name='public_about'),
    path('contato/', views.PublicContactView.as_view(), name='public_contact'),

    # Área restrita: gestão do conteúdo do site.
    path('painel/oficina/', views.SiteSettingsView.as_view(), name='site_settings'),
    path('painel/orcamentos/', views.LeadManageListView.as_view(), name='site_lead_list'),
    path('painel/orcamentos/<int:pk>/', views.LeadManageDetailView.as_view(), name='site_lead_detail'),
    path('painel/artigos/', views.BlogPostManageListView.as_view(), name='blog_manage_list'),
    path('painel/artigos/gerar-ia/', views.BlogArticleGenerateView.as_view(), name='blog_generate_ai'),
    path('painel/artigos/novo/', views.BlogPostCreateView.as_view(), name='blog_manage_create'),
    path('painel/artigos/<int:pk>/editar/', views.BlogPostUpdateView.as_view(), name='blog_manage_update'),
    path('painel/artigos/<int:pk>/excluir/', views.BlogPostDeleteView.as_view(), name='blog_manage_delete'),
]
