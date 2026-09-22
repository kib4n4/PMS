# backend/config/urls.py

"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


def healthz(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('healthz/', healthz),
    path('accounts/', include('accounts.urls')),
    path('api/auth/', include('accounts.urls')),
    path('api/', include('leasing.urls')),
    path('api/', include('billing.urls')),
    path('api/', include('partners.urls')),
    path('api/', include('taxes.urls')),
    path('api/', include('api_auth.urls')),
    path('api/', include('properties.urls')),
    path('api/', include('maintenance.urls')),
    path('api/', include('caretakers.urls')),
    path('api/', include('landlords.urls')),
    # API documentation — auto-generated from DRF views/serializers.
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    # Public webhook routes — kept on a distinct path group so host Nginx
    # can apply a stricter/separate rate limit, per the design doc.
    path('webhooks/', include('billing.webhook_urls')),
    path('webhooks/', include('messaging.webhook_urls')),
]