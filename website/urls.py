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
]
