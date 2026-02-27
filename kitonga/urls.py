"""
URL configuration for Kitonga project
"""

from django.contrib import admin
from django.contrib.auth import logout as auth_logout
from django.urls import path, include
from django.http import HttpResponse
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static


def empty_favicon(_request):
    # Return an empty response to avoid 404 noise until a real favicon is provided
    return HttpResponse(status=204)


def admin_logout_view(request):
    """
    Custom admin logout that accepts both GET and POST.
    Django 5.x restricted /admin/logout/ to POST only, causing HTTP 405
    when users click "Log out" in the admin panel.
    """
    auth_logout(request)
    return redirect("/admin/login/")


urlpatterns = [
    # Override admin logout BEFORE admin/ to intercept GET requests
    path("admin/logout/", admin_logout_view, name="admin_logout_override"),
    path("admin/", admin.site.urls),
    path("api/", include("billing.urls")),
    path("dashboard/", include("billing.urls")),
    # Handle browser requests to /favicon.ico to prevent 404 logs
    path("favicon.ico", empty_favicon),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
