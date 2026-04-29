from django.core.validators import MinValueValidator
from django.db import models

from authen.models import CustomUser
from competitions.schemas import StatusTextChoices, StyleTextChoices
from custumer.models import Custumer


class Competitions(models.Model):
    """Соревнования."""

    name = models.CharField(
        max_length=255,
        verbose_name="Название",
    )
    location = models.CharField(
        max_length=255,
        verbose_name="Место проведения",
    )
    date = models.DateField(
        verbose_name="Дата начала",
    )
    end_date = models.DateField(
        verbose_name="Дата окончания",
        null=True,
        blank=True,
    )
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="competitions",
        verbose_name="Владелец",
    )
    status = models.CharField(
        max_length=50,
        verbose_name="Статус",
        choices=StatusTextChoices,
        default=StatusTextChoices.OPEN,
    )

    class Meta:
        verbose_name = "Соревнование"
        verbose_name_plural = "Соревнования"
        unique_together = ("name", "location", "date", "end_date")

    def __str__(self):
        return self.name


class CustumerCompetitionResult(models.Model):
    """Результаты соревнований."""

    competition = models.ForeignKey(
        Competitions,
        on_delete=models.CASCADE,
        related_name="results",
        verbose_name="Соревнование",
    )
    customer = models.ForeignKey(
        Custumer,
        on_delete=models.CASCADE,
        related_name="results",
        verbose_name="Клиент",
    )
    distance = models.FloatField(max_length=100, verbose_name="Дистанция")
    discipline = models.CharField(
        max_length=255,
        verbose_name="Дисциплина",
        blank=True,
        null=True,
        help_text=("Название дисциплины (например: 'Плавание вольный стиль')"),
    )
    style = models.CharField(
        max_length=100,
        verbose_name="Стиль",
        choices=StyleTextChoices,
        blank=True,
        null=True,
    )
    result_time_ms = models.BigIntegerField(
        verbose_name="Показанное время в миллисекундах",
        help_text="Не заполняется при дисквалификации. Формат: мм:сс:ммм",
        validators=[MinValueValidator(0)],
        blank=True,
        null=True,
    )
    place = models.PositiveIntegerField(
        verbose_name="Занятое место",
        null=True,
        blank=True,
        help_text="Не заполняется при дисквалификации",
    )
    is_disqualified = models.BooleanField(
        default=False,
        verbose_name="Дисквалифицирован",
        help_text="Отметить, если участник дисквалифицирован",
    )
    disqualification_comment = models.TextField(
        max_length=500,
        verbose_name="Причина дисквалификации",
        blank=True,
        null=True,
        help_text="Укажите причину дисквалификации",
    )
    sport_category = models.ForeignKey(
        "custumer.SportCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Полученный разряд",
        help_text="Разряд, полученный на этом соревновании",
    )

    class Meta:
        verbose_name = "Результат соревнования"
        verbose_name_plural = "Результаты соревнований"

    def format_time(self):
        """
        Преобразует миллисекунды в строку формата мм:сс:ммм.

        Returns:
            str: Время в формате мм:сс:ммм или None если время не установлено
        """
        if self.result_time_ms is None:
            return None

        minutes = self.result_time_ms // 60000
        seconds = (self.result_time_ms % 60000) // 1000
        milliseconds = self.result_time_ms % 1000
        return f"{minutes:02d}:{seconds:02d}:{milliseconds:03d}"

    def set_time_from_string(self, time_str):
        """
        Парсит строку формата мм:сс:ммм и устанавливает result_time_ms.

        Args:
            time_str: Строка времени в формате мм:сс:ммм

        Raises:
            ValueError: Если формат строки некорректен
        """
        if not time_str:
            self.result_time_ms = None
            return

        try:
            parts = time_str.split(":")
            if len(parts) != 3:
                raise ValueError("Время должно быть в формате мм:сс:ммм")

            minutes = int(parts[0])
            seconds = int(parts[1])
            milliseconds = int(parts[2])

            # Валидация
            if not (0 <= minutes <= 99):
                raise ValueError("Минуты должны быть от 0 до 99")
            if not (0 <= seconds <= 59):
                raise ValueError("Секунды должны быть от 0 до 59")
            if not (0 <= milliseconds <= 999):
                raise ValueError("Миллисекунды должны быть от 0 до 999")

            # Преобразование в миллисекунды
            self.result_time_ms = (
                minutes * 60 + seconds
            ) * 1000 + milliseconds

        except (ValueError, IndexError) as e:
            raise ValueError(f"Некорректный формат времени: {e}")

    @property
    def formatted_time(self):
        """
        Свойство для удобного доступа к форматированному времени.

        Returns:
            str: Время в формате мм:сс:ммм или None
        """
        return self.format_time()

    @property
    def get_style_display(self):
        """
        Возвращает читаемое название стиля бассейна.

        Returns:
            str: Читаемое название или пустую строку
        """
        if not self.style:
            return ""
        return dict(StyleTextChoices.choices).get(self.style, self.style)

    def __str__(self):
        return f"{self.customer} - {self.competition}"
