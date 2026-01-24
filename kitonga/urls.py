"""
URL configuration for Kitonga project
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls.static import static


def empty_favicon(_request):
    # Return an empty response to avoid 404 noise until a real favicon is provided
    return HttpResponse(status=204)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('billing.urls')),
    path('dashboard/', include('billing.urls')),
    # Handle browser requests to /favicon.ico to prevent 404 logs
    path('favicon.ico', empty_favicon),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
