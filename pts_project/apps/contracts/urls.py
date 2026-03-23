from django.urls import path
from .views import (
    contracts_list_view,
    contract_check_number_view,
    contract_create_view,
    contract_detail_view,
    contract_update_view,
    contract_issue_po_view,
    po_complete_view,
    po_extend_view,
    po_set_pg_view,
    contract_add_comment_view,
    contract_set_milestone_alert_view,
    # New views
    contract_add_pg_view,
    po_add_pg_view,
    contract_receive_view,
    contract_evaluate_view,
    po_receive_view,
    po_evaluate_view,
    contract_add_communication_view,
)

urlpatterns = [
    path('',                                        contracts_list_view,              name='contracts_list'),
    path('check-number/',                           contract_check_number_view,       name='contract_check_number'),
    path('create/',                                 contract_create_view,             name='contract_create'),
    path('<int:pk>/',                               contract_detail_view,             name='contract_detail'),
    path('<int:pk>/update/',                        contract_update_view,             name='contract_update'),
    path('<int:pk>/comment/',                       contract_add_comment_view,        name='contract_add_comment'),
    path('<int:pk>/alert/',                         contract_set_milestone_alert_view, name='contract_set_alert'),
    # Performance Guarantees
    path('<int:pk>/pg/add/',                        contract_add_pg_view,             name='contract_add_pg'),
    # Delivery receipt & evaluation
    path('<int:pk>/receive/',                       contract_receive_view,            name='contract_receive'),
    path('<int:pk>/evaluate/',                      contract_evaluate_view,           name='contract_evaluate'),
    # Communication
    path('<int:pk>/communication/',                 contract_add_communication_view,  name='contract_add_communication'),
    # Purchase Orders
    path('<int:pk>/po/',                            contract_issue_po_view,           name='contract_issue_po'),
    path('<int:pk>/po/<int:po_pk>/complete/',       po_complete_view,                 name='po_complete'),
    path('<int:pk>/po/<int:po_pk>/extend/',         po_extend_view,                   name='po_extend'),
    path('<int:pk>/po/<int:po_pk>/set-pg/',         po_set_pg_view,                   name='po_set_pg'),
    path('<int:pk>/po/<int:po_pk>/pg/add/',         po_add_pg_view,                   name='po_add_pg'),
    path('<int:pk>/po/<int:po_pk>/receive/',        po_receive_view,                  name='po_receive'),
    path('<int:pk>/po/<int:po_pk>/evaluate/',       po_evaluate_view,                 name='po_evaluate'),
]
