from django.apps import AppConfig


class MaintenanceConfig(AppConfig):
    name = 'maintenance'

    def ready(self):
        from . import signals  # noqa: F401
