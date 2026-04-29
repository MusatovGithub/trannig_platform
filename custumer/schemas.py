from django.db import models


class ReasonTextChoices(models.TextChoices):
    """Причина получения баллов."""

    ATTENDANCE = ("attendance", "Посещение занятия")
    ACHIEVEMENT = ("achievement", "Достижение")
    COMPETITION = ("competition", "Соревнование")
    MANUAL = ("manual", "Ручное начисление")
    PURCHASE = ("purchase", "Покупка товара")
