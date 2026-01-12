from django.apps import AppConfig
import os
import sys


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"

    def ready(self):
        """
        Called when the billing app is ready.
        Starts the real-time access expiry watcher in production.
        """
        # Only start watcher in the main process (not in manage.py commands or migrations)
        # Check if we're running the main server process
        is_main_server = (
            "runserver" in sys.argv or "gunicorn" in sys.argv[0]
            if sys.argv
            else False
            or os.environ.get("RUN_MAIN") == "true"  # Django dev server reloader
            or os.environ.get("GUNICORN_WORKERS", None)  # Gunicorn production
        )

        # Skip watcher for management commands (migrations, shell, etc.)
        is_management_command = any(
            cmd in sys.argv
            for cmd in [
                "migrate",
                "makemigrations",
                "shell",
                "dbshell",
                "collectstatic",
                "createsuperuser",
                "crontab",
                "run_expiry_watcher",  # Don't auto-start if running the dedicated command
            ]
        )

        # Check if expiry watcher is explicitly enabled
        watcher_enabled = (
            os.environ.get("EXPIRY_WATCHER_ENABLED", "false").lower() == "true"
        )

        if watcher_enabled and is_main_server and not is_management_command:
            try:
                from .expiry_watcher import start_expiry_watcher

                start_expiry_watcher()
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Could not start expiry watcher: {e}")

        # Register custom admin dashboard URL
        self._register_admin_urls()

    def _register_admin_urls(self):
        """Register custom admin URLs for dashboard/statistics"""
        try:
            from django.contrib import admin
            from django.urls import path
            from .views import dashboard_stats

            # Get the original get_urls method
            original_get_urls = admin.site.get_urls

            def custom_get_urls():
                custom_urls = [
                    path(
                        "dashboard/",
                        admin.site.admin_view(dashboard_stats),
                        name="billing_statistics",
                    ),
                ]
                return custom_urls + original_get_urls()

            # Replace the get_urls method
            admin.site.get_urls = custom_get_urls
        except ImportError:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning("Could not register admin URLs: import error")
