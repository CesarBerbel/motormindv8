from django.urls import path

from . import views

urlpatterns = [


    path('cliente/veiculo/', views.CustomerVehicleAccessRequestView.as_view(), name='customer_vehicle_access_request'),
    path('cliente/veiculo/codigo/<uuid:token>/', views.CustomerVehicleAccessVerifyView.as_view(), name='customer_vehicle_access_verify'),
    path('cliente/veiculo/historico/<uuid:token>/', views.CustomerVehicleHistoryView.as_view(), name='customer_vehicle_history'),
    path('cliente/veiculo/sair/<uuid:token>/', views.CustomerVehicleAccessLogoutView.as_view(), name='customer_vehicle_access_logout'),

    path('mecanica/os/', views.MechanicWorkOrderListView.as_view(), name='mechanic_work_order_list'),
    path('mecanica/kanban/', views.MechanicKanbanView.as_view(), name='mechanic_kanban'),
    path('mecanica/os/<int:pk>/', views.MechanicWorkOrderDetailView.as_view(), name='mechanic_work_order_detail'),
    path('mecanica/os/<int:pk>/itens/', views.MechanicWorkOrderItemsView.as_view(), name='mechanic_work_order_items'),
    path('mecanica/os/<int:pk>/kanban/adicionar-item/', views.MechanicKanbanAddItemView.as_view(), name='mechanic_kanban_add_item'),
    path('mecanica/os/<int:pk>/kanban/reabrir-itens/', views.MechanicKanbanReopenItemsView.as_view(), name='mechanic_kanban_reopen_items'),
    path('mecanica/os/<int:pk>/iniciar/', views.MechanicWorkOrderStartView.as_view(), name='mechanic_work_order_start'),
    path('mecanica/os/<int:pk>/diagnostico/', views.MechanicWorkOrderDiagnosisView.as_view(), name='mechanic_work_order_diagnosis'),
    path('mecanica/os/<int:pk>/mover-kanban/', views.MechanicKanbanMoveView.as_view(), name='mechanic_kanban_move'),

    path('atendimento/checkins/', views.VehicleCheckInListView.as_view(), name='vehicle_checkin_list'),
    path('atendimento/checkins/novo/', views.VehicleCheckInCreateView.as_view(), name='vehicle_checkin_create'),
    path('atendimento/checkins/autocomplete/', views.VehicleCheckInAutocompleteView.as_view(), name='vehicle_checkin_autocomplete'),
    path('atendimento/checkins/<int:pk>/', views.VehicleCheckInDetailView.as_view(), name='vehicle_checkin_detail'),
    path('atendimento/checkins/<int:pk>/editar/', views.VehicleCheckInUpdateView.as_view(), name='vehicle_checkin_update'),
    path('atendimento/checkins/<int:pk>/excluir/', views.VehicleCheckInDeleteView.as_view(), name='vehicle_checkin_delete'),
    path('atendimento/checkins/<int:pk>/pdf/', views.VehicleCheckInPdfView.as_view(), name='vehicle_checkin_pdf'),
    path('atendimento/checkins/fotos/<int:pk>/', views.VehicleCheckInPhotoFileView.as_view(), name='vehicle_checkin_photo'),
    path('atendimento/checkins/<int:pk>/enviar-email/', views.VehicleCheckInSendEmailView.as_view(), name='vehicle_checkin_send_email'),

    path('configuracoes/os/', views.WorkOrderSettingsView.as_view(), name='work_order_settings'),
    path('configuracoes/pdfs/', views.PdfSettingsView.as_view(), name='pdf_settings'),

    path('operacional/os/', views.WorkOrderListView.as_view(), name='work_order_list'),
    path('operacional/os/nova/', views.WorkOrderCreateView.as_view(), name='work_order_create'),
    path('operacional/os/autocomplete/', views.WorkOrderAutocompleteView.as_view(), name='work_order_autocomplete'),
    path('operacional/os/cliente-veiculos/', views.WorkOrderCustomerVehiclesView.as_view(), name='work_order_customer_vehicles'),
    path('operacional/os/<int:pk>/', views.WorkOrderDetailView.as_view(), name='work_order_detail'),
    path('operacional/os/<int:pk>/pdf/', views.WorkOrderPdfView.as_view(), name='work_order_pdf'),
    path('operacional/os/<int:pk>/editar/', views.WorkOrderUpdateView.as_view(), name='work_order_update'),
    path('operacional/os/<int:pk>/excluir/', views.WorkOrderDeleteView.as_view(), name='work_order_delete'),
    path('operacional/os/<int:pk>/baixar-estoque/', views.WorkOrderStockOutView.as_view(), name='work_order_stock_out'),
    path('operacional/os/<int:pk>/ajustar-pecas-previstas/', views.WorkOrderStockRequirementUpdateView.as_view(), name='work_order_stock_requirement_update'),
    path('operacional/os/<int:pk>/alterar-status/', views.WorkOrderStatusTransitionView.as_view(), name='work_order_transition'),
    path('operacional/os/<int:pk>/enviar-orcamento/', views.WorkOrderSendApprovalBudgetView.as_view(), name='work_order_send_approval_budget'),
    path('operacional/os/<int:pk>/registrar-aprovacao/', views.WorkOrderRegisterApprovalView.as_view(), name='work_order_register_approval'),
    path('operacional/os/<int:pk>/novo-orcamento/', views.WorkOrderNewApprovalBudgetView.as_view(), name='work_order_new_approval_budget'),
    path('operacional/aprovacoes/<int:pk>/', views.WorkOrderApprovalDetailView.as_view(), name='work_order_approval_detail'),
    path('aprovacao-os/<uuid:token>/', views.PublicWorkOrderApprovalView.as_view(), name='work_order_public_approval'),

    path('operacional/servicos/categorias/', views.ServiceCategoryListView.as_view(), name='service_category_list'),
    path('operacional/servicos/categorias/nova/', views.ServiceCategoryCreateView.as_view(), name='service_category_create'),
    path('operacional/servicos/categorias/<int:pk>/editar/', views.ServiceCategoryUpdateView.as_view(), name='service_category_update'),
    path('operacional/servicos/categorias/<int:pk>/excluir/', views.ServiceCategoryDeleteView.as_view(), name='service_category_delete'),

    path('operacional/servicos/', views.ServiceListView.as_view(), name='service_list'),
    path('operacional/servicos/novo/', views.ServiceCreateView.as_view(), name='service_create'),
    path('operacional/servicos/autocomplete/', views.ServiceAutocompleteView.as_view(), name='service_autocomplete'),
    path('operacional/servicos/<int:pk>/', views.ServiceDetailView.as_view(), name='service_detail'),
    path('operacional/servicos/<int:pk>/editar/', views.ServiceUpdateView.as_view(), name='service_update'),
    path('operacional/servicos/<int:pk>/excluir/', views.ServiceDeleteView.as_view(), name='service_delete'),

    path('operacional/combos/', views.ServiceComboListView.as_view(), name='service_combo_list'),
    path('operacional/combos/novo/', views.ServiceComboCreateView.as_view(), name='service_combo_create'),
    path('operacional/combos/autocomplete/', views.ServiceComboAutocompleteView.as_view(), name='service_combo_autocomplete'),
    path('operacional/combos/<int:pk>/', views.ServiceComboDetailView.as_view(), name='service_combo_detail'),
    path('operacional/combos/<int:pk>/editar/', views.ServiceComboUpdateView.as_view(), name='service_combo_update'),
    path('operacional/combos/<int:pk>/excluir/', views.ServiceComboDeleteView.as_view(), name='service_combo_delete'),
]
