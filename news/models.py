from django.db import models

from authen.models import CustomUser
from news.schemas import StatusTextChoices


class News(models.Model):
    """Модель новости."""

    title = models.CharField(max_length=255, verbose_name="Заголовок")
    descriptions = models.TextField(verbose_name="Описание")
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Дата создания"
    )
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="news",
        verbose_name="Владелец",
    )
    image = models.ImageField(upload_to="news/", null=True, blank=True)
    status = models.CharField(
        max_length=50,
        verbose_name="Статус",
        choices=StatusTextChoices,
        default=StatusTextChoices.DRAFT,
    )

    class Meta:
        verbose_name = "Новость"
        verbose_name_plural = "Новости"

    def __str__(self):
        return self.title
