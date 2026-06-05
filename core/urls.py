from django.urls import path

from . import views

urlpatterns = [
    path('healthz/', views.HealthCheckView.as_view(), name='health_check'),
    path('', views.HomeView.as_view(), name='home'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),

    path('clientes/', views.CustomerListView.as_view(), name='customer_list'),
    path('clientes/autocomplete/', views.CustomerAutocompleteView.as_view(), name='customer_autocomplete'),
    path('clientes/novo/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('clientes/<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    path('clientes/<int:pk>/editar/', views.CustomerUpdateView.as_view(), name='customer_update'),
    path('clientes/<int:pk>/excluir/', views.CustomerDeleteView.as_view(), name='customer_delete'),


    path('veiculos/', views.VehicleListView.as_view(), name='vehicle_list'),
    path('veiculos/autocomplete/', views.VehicleAutocompleteView.as_view(), name='vehicle_autocomplete'),
    path('veiculos/novo/', views.VehicleCreateView.as_view(), name='vehicle_create'),
    path('veiculos/fipe/marcas/', views.FipeBrandsView.as_view(), name='vehicle_fipe_brands'),
    path('veiculos/fipe/modelos/', views.FipeModelsView.as_view(), name='vehicle_fipe_models'),
    path('veiculos/fipe/anos/', views.FipeYearsView.as_view(), name='vehicle_fipe_years'),
    path('veiculos/fipe/valor/', views.FipeValueView.as_view(), name='vehicle_fipe_value'),
    path('veiculos/<int:pk>/', views.VehicleDetailView.as_view(), name='vehicle_detail'),
    path('veiculos/<int:pk>/editar/', views.VehicleUpdateView.as_view(), name='vehicle_update'),
    path('veiculos/<int:pk>/excluir/', views.VehicleDeleteView.as_view(), name='vehicle_delete'),

    path('fornecedores/', views.SupplierListView.as_view(), name='supplier_list'),
    path('fornecedores/autocomplete/', views.SupplierAutocompleteView.as_view(), name='supplier_autocomplete'),
    path('fornecedores/novo/', views.SupplierCreateView.as_view(), name='supplier_create'),
    path('fornecedores/<int:pk>/', views.SupplierDetailView.as_view(), name='supplier_detail'),
    path('fornecedores/<int:pk>/editar/', views.SupplierUpdateView.as_view(), name='supplier_update'),
    path('fornecedores/<int:pk>/excluir/', views.SupplierDeleteView.as_view(), name='supplier_delete'),

    path('categorias/', views.CategoryListView.as_view(), name='category_list'),
    path('categorias/autocomplete/', views.CategoryAutocompleteView.as_view(), name='category_autocomplete'),
    path('categorias/nova/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categorias/<int:pk>/editar/', views.CategoryUpdateView.as_view(), name='category_update'),
    path('categorias/<int:pk>/excluir/', views.CategoryDeleteView.as_view(), name='category_delete'),
]
