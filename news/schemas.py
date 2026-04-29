from django.db import models


class StatusTextChoices(models.TextChoices):
    """Status choices for news."""

    DRAFT = "Черновик", "Draft"
    PUBLISHED = "Опубликовано", "Published"
