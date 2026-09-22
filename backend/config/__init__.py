from .celery import app as celery_app

default_app_config = "config.apps.ConfigConfig"

__all__ = ("celery_app",)
