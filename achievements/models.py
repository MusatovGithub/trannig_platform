from django.db import models

from achievements.schemas import TagsTextChoices
from authen.models import CustomUser


class Achievement(models.Model):
    """Модель достижения"""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="achievements/", null=True, blank=True)
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="achievements",
        verbose_name="Владелец",
    )
    tag = models.CharField(
        "Тэг",
        max_length=255,
        help_text="Выберите теги для достижения",
        choices=TagsTextChoices.choices,
        default=TagsTextChoices.WATER_ELEMENT,
    )
    points = models.IntegerField(
        "Баллы",
        default=0,
        help_text="Баллы за достижение",
    )

    class Meta:
        verbose_name = "Достижение"
        verbose_name_plural = "Достижения"

    def __str__(self):
        return self.name
