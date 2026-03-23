"""
URL configuration for Procurement Tracking System (PTS).
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView
)

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Home redirect to login (unauthenticated) or dashboard (authenticated)
    path('', RedirectView.as_view(url='/accounts/login/', permanent=False), name='home'),
    
    # Dashboard (template-based views)
    path('dashboard/', include('apps.dashboard.urls')),

    # Contract Management
    path('dashboard/contracts/', include('apps.contracts.urls')),

    # Alerts and Notifications
    path('alerts/', include('apps.alerts.urls')),
    
    # Authentication (template-based + API)
    path('accounts/', include(('apps.accounts.urls', 'accounts'))),
    
    # Allauth URLs (for email verification, etc.)
    path('accounts/allauth/', include('allauth.urls')),
    
    # API v1 endpoints
    path('api/v1/', include([
        # Core modules
        path('divisions/', include('apps.divisions.urls')),
        path('procurement/', include('apps.procurement.urls')),
        path('workflows/', include('apps.workflows.urls')),
        path('notifications/', include('apps.notifications.urls')),
        path('reports/', include('apps.reports.urls')),
    ])),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site customization
admin.site.site_header = 'PTS Administration'
admin.site.site_title = 'Procurement Tracking System'
admin.site.index_title = 'Welcome to PTS Admin Portal'
