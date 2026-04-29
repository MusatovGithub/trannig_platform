from django.apps import AppConfig


class CustumerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "custumer"
    verbose_name = "Клиент"

    def ready(self):
        """Импортируем сигналы при запуске приложения"""
        import custumer.signals  # noqa: F401
