from django.apps import AppConfig


class RealEstateConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.real_estate'
    verbose_name = 'Real Estate Intelligence'

    def ready(self):
        from . import signals  # noqa: F401
