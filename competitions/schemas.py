from django.db import models


class StatusTextChoices(models.TextChoices):
    """Статус для соревнований."""

    OPEN = "open", "Активно"
    CLOSED = "closed", "Завершено"


class StyleTextChoices(models.TextChoices):
    """Стиль для соревнований."""

    POOL_25M = "25m", "25 метров"
    POOL_50M = "50m", "50 метров"
    OPEN_WATER = "open_water", "Открытая вода"
