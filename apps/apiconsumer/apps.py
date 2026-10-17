from django.apps import AppConfig


class ApiconsumerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.apiconsumer'

    def ready(self):
        from . import signals  # noqa: F401
