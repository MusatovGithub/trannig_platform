from django.db import models

from authen.models import Company, CustomUser, TypeSportsCompany
from employe.models import Employe


class TypeSports(models.Model):
    name = models.CharField(max_length=250, verbose_name="Вид спорта")

    def __str__(self):
        return self.name

    class Meta:
        db_table = "type_sport"
        verbose_name = "Вид спорта"
        verbose_name_plural = "Вид спорта"


class Week(models.Model):
    name = models.CharField(max_length=250, verbose_name="Неделя")
    short_name = models.CharField(max_length=250, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "week"
        verbose_name = "День недели"
        verbose_name_plural = "Дни недели"


class GroupsClass(models.Model):
    name = models.CharField(max_length=250, verbose_name="Название")
    type_sport = models.ForeignKey(
        TypeSportsCompany,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Вид спорта",
    )
    employe_id = models.ManyToManyField(
        Employe, blank=True, verbose_name="Тренеры"
    )
    strat_training = models.DateField(
        null=True, blank=True, verbose_name="Начало обучения"
    )
    end_training = models.DateField(
        null=True, blank=True, verbose_name="Конец обучения"
    )
    position = models.BigIntegerField(
        null=True, blank=True, verbose_name="Позиция"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Компания",
    )
    owner_id = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="owner",
        verbose_name="Владелец",
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "groups_class"
        verbose_name = "Группа класса"
        verbose_name_plural = "Группа класса"


class Schedule(models.Model):
    groups_id = models.ForeignKey(
        GroupsClass,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="groups",
        verbose_name="Группа класса",
    )
    name = models.CharField(
        max_length=250, null=True, blank=True, verbose_name="Имя занятиям"
    )
    week = models.ForeignKey(
        Week,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="День недели",
    )
    strat_time = models.TimeField(
        null=True, blank=True, verbose_name="Время начала"
    )
    end_time = models.TimeField(
        null=True, blank=True, verbose_name="Время окончания"
    )

    class Meta:
        db_table = "schedule"
        verbose_name = "Расписание"
        verbose_name_plural = "Расписание"


class GroupClasses(models.Model):
    groups_id = models.ForeignKey(
        GroupsClass,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="group_class",
        verbose_name="Группа класса",
    )
    name = models.CharField(
        max_length=250, null=True, blank=True, verbose_name="Имя занятиям"
    )
    date = models.DateField(verbose_name="Дата")
    strat = models.TimeField(verbose_name="Начало")
    end = models.TimeField(verbose_name="Конец")
    employe = models.ForeignKey(
        Employe, on_delete=models.CASCADE, verbose_name="Тренеры"
    )
    comment = models.TextField(
        null=True, blank=True, verbose_name="Комментарий"
    )
    attendance_status = models.CharField(
        max_length=50,
        choices=[
            ("attended", "Был"),
            ("not_attended", "Не Был"),
            ("none", "None"),
        ],
        default="none",
        verbose_name="Статус посещения",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Компания",
    )
    owner = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, null=True, blank=True
    )
    is_manual = models.BooleanField(
        default=False,
        verbose_name="Ручное добавление",
    )

    def __str__(self):
        return f"{self.groups_id}"

    class Meta:
        db_table = "group_classes"
        verbose_name = "Занятие"
        verbose_name_plural = "Занятие"
        indexes = [
            models.Index(
                fields=["groups_id", "date"], name="idx_gc_groups_date"
            ),
            models.Index(fields=["date"], name="idx_gc_date"),
        ]


class ClasessProgramm(models.Model):
    classes = models.ForeignKey(
        GroupClasses,
        on_delete=models.CASCADE,
        related_name="classes",
        null=True,
        blank=True,
    )
    stages = models.CharField(max_length=250, verbose_name="Этапы")
    distance = models.CharField(max_length=250, verbose_name="Дистанция")
    style = models.CharField(max_length=250, verbose_name="Стиль")
    comments = models.TextField(
        null=True, blank=True, verbose_name="Комментарии"
    )
    rest = models.CharField(max_length=250, verbose_name="Отдых")

    class Meta:
        db_table = "classes_programm"
        verbose_name = "Занятие программа "
        verbose_name_plural = "Занятие программа"


class GroupClassessCustumer(models.Model):
    gr_class = models.ForeignKey(
        GroupClasses,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Занятие",
    )
    custumer = models.ForeignKey(
        "custumer.Custumer",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="custumer_id",
        verbose_name="Клиенты",
    )
    date = models.DateField(null=True, blank=True, verbose_name="Дата")
    class_time = models.TimeField(null=True, blank=True)
    attendance_status = models.CharField(
        max_length=20,
        choices=[
            ("not_attended", "Не Был"),
            ("attended_2", "Был (2)"),
            ("attended_3", "Был (3)"),
            ("attended_4", "Был (4)"),
            ("attended_5", "Был (5)"),
            ("attended_10", "Был (10)"),
            ("none", "None"),
        ],
        default="none",
        verbose_name="Статус посещения",
    )
    comment = models.TextField(
        null=True,
        blank=True,
        verbose_name="Комментарий",
    )
    used_subscription = models.ForeignKey(
        "custumer.CustumerSubscription",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="used_attendances",
        verbose_name="Использованная подписка",
    )
    is_block = models.BooleanField(default=False)
    is_none = models.BooleanField(default=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Компания",
    )
    owner = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, null=True, blank=True
    )
    create_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    update_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    @property
    def payment_status_display(self) -> str:
        """
        Отображаемый статус оплаты посещения.

        4 возможных состояния:
        1. Не оплачено: is_block=False, used_subscription=None
        2. Оплачено наличными: is_block=True, used_subscription=None, summ>0
        3. Прощено: is_block=True, used_subscription=None, summ=0
        4. С абонемента: used_subscription != None

        ВАЖНО: Для оптимизации используйте prefetch_related("payment_record")
        при загрузке QuerySet, чтобы избежать N+1 запросов.
        """
        # Состояние 4: Списано с абонемента
        if self.used_subscription:
            if self.used_subscription.attendance_status == "paid":
                return "Оплачено (абонемент)"
            elif self.used_subscription.attendance_status == "unpaid":
                return "Списано с неоплаченного абонемента"
            elif self.used_subscription.attendance_status == "none":
                return "Прощено (бесплатный абонемент)"

        # Состояния 1, 2, 3: Без абонемента
        if self.is_block:
            # Используем связь payment_record вместо запроса к БД
            # (оптимизация: prefetch_related загружает данные заранее)
            try:
                # Проверяем наличие payment_record через связь OneToOneField
                # Если prefetch_related использован,
                # это не вызовет дополнительный запрос
                # Используем getattr для безопасной проверки
                payment = getattr(self, "payment_record", None)

                if (
                    payment is not None
                    and payment.subscription is None
                    and payment.is_pay
                ):
                    if payment.summ == 0:
                        return "Прощено"  # Состояние 3
                    else:
                        return "Оплачено наличными"  # Состояние 2
            except (AttributeError, Exception):
                # Если payment_record не существует или произошла ошибка
                pass

            # Fallback если записи нет
            return "Оплачено наличными"

        # Состояние 1: Не оплачено
        return "Не оплачено"

    @property
    def is_payment_blocked(self) -> bool:
        """
        Заблокировано ли посещение для повторной оплаты.

        Заблокировано только если привязано к абонементу.
        Оплаченное наличными или прощенное можно переоплатить/изменить.
        """
        return bool(self.used_subscription)

    def __str__(self):
        return f"{self.custumer} - {self.gr_class} - {self.date}"

    class Meta:
        db_table = "group_classes_custumer"
        verbose_name = "Посещаемость"
        verbose_name_plural = "Посещаемость"
        unique_together = ("custumer", "gr_class", "date")
        indexes = [
            models.Index(
                fields=["gr_class", "date"], name="idx_gcc_class_date"
            ),
            models.Index(fields=["date"], name="idx_gcc_date"),
            models.Index(fields=["custumer"], name="idx_gcc_custumer"),
            models.Index(fields=["attendance_status"], name="idx_gcc_status"),
            models.Index(fields=["is_block"], name="idx_gcc_is_block"),
        ]
