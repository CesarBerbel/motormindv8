from django.urls import path

from . import views

urlpatterns = [
    path('estoque/itens/', views.InventoryItemListView.as_view(), name='inventory_item_list'),
    path('estoque/itens/novo/', views.InventoryItemCreateView.as_view(), name='inventory_item_create'),
    path('estoque/itens/importar-xml/', views.InventoryItemXmlImportView.as_view(), name='inventory_item_import_xml'),
    path('estoque/itens/autocomplete/', views.InventoryItemAutocompleteView.as_view(), name='inventory_item_autocomplete'),
    path('estoque/itens/<int:pk>/', views.InventoryItemDetailView.as_view(), name='inventory_item_detail'),
    path('estoque/itens/<int:pk>/editar/', views.InventoryItemUpdateView.as_view(), name='inventory_item_update'),
    path('estoque/itens/<int:pk>/excluir/', views.InventoryItemDeleteView.as_view(), name='inventory_item_delete'),


    path('estoque/pedidos-compra/', views.PurchaseOrderListView.as_view(), name='purchase_order_list'),
    path('estoque/pedidos-compra/novo/', views.PurchaseOrderCreateView.as_view(), name='purchase_order_create'),
    path('estoque/pedidos-compra/autocomplete/', views.PurchaseOrderAutocompleteView.as_view(), name='purchase_order_autocomplete'),
    path('estoque/pedidos-compra/<int:pk>/', views.PurchaseOrderDetailView.as_view(), name='purchase_order_detail'),
    path('estoque/pedidos-compra/<int:pk>/editar/', views.PurchaseOrderUpdateView.as_view(), name='purchase_order_update'),
    path('estoque/pedidos-compra/<int:pk>/excluir/', views.PurchaseOrderDeleteView.as_view(), name='purchase_order_delete'),
    path('estoque/pedidos-compra/<int:pk>/receber/', views.PurchaseOrderReceiveView.as_view(), name='purchase_order_receive'),

    path('estoque/movimentacoes/', views.StockMovementListView.as_view(), name='stock_movement_list'),
    path('estoque/movimentacoes/nova/', views.StockMovementCreateView.as_view(), name='stock_movement_create'),
    path('estoque/movimentacoes/autocomplete/', views.StockMovementAutocompleteView.as_view(), name='stock_movement_autocomplete'),
    path('estoque/movimentacoes/<int:pk>/', views.StockMovementDetailView.as_view(), name='stock_movement_detail'),

    path('configuracoes/estoque/categorias/', views.StockCategoryListView.as_view(), name='stock_category_list'),
    path('configuracoes/estoque/categorias/nova/', views.StockCategoryCreateView.as_view(), name='stock_category_create'),
    path('configuracoes/estoque/categorias/<int:pk>/editar/', views.StockCategoryUpdateView.as_view(), name='stock_category_update'),
    path('configuracoes/estoque/categorias/<int:pk>/excluir/', views.StockCategoryDeleteView.as_view(), name='stock_category_delete'),

    path('configuracoes/marcas/', views.BrandListView.as_view(), name='brand_list'),
    path('configuracoes/marcas/nova/', views.BrandCreateView.as_view(), name='brand_create'),
    path('configuracoes/marcas/<int:pk>/editar/', views.BrandUpdateView.as_view(), name='brand_update'),
    path('configuracoes/marcas/<int:pk>/excluir/', views.BrandDeleteView.as_view(), name='brand_delete'),
]
