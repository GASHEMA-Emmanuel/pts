from django.urls import path
from . import views

app_name = 'alerts'

urlpatterns = [
    # User alert dashboard
    path('', views.alert_dashboard_view, name='dashboard'),
    path('history/', views.alert_history_view, name='history'),

    # Alert actions
    path('<uuid:alert_id>/acknowledge/', views.acknowledge_alert_view, name='acknowledge'),
    path('<uuid:alert_id>/resolve/', views.resolve_alert_view, name='resolve'),

    # Attention modal dismiss
    path('attention/dismiss/', views.attention_dismiss_view, name='attention_dismiss'),

    # Admin views
    path('admin/config/', views.alert_configuration_view, name='admin_config'),
    path('admin/config/<uuid:config_id>/edit/', views.alert_configuration_edit_view, name='admin_config_edit'),
    path('admin/statistics/', views.alert_statistics_view, name='admin_statistics'),
]
