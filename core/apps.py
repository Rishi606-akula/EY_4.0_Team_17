from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        """Import signals when the app is ready."""
        import core.signals  # noqa
