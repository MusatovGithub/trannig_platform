from django.core.validators import RegexValidator
from django.db import models
from django.utils.timezone import localdate

from authen.models import Company, CustomUser, Gender
from custumer.schemas import ReasonTextChoices
from groups_custumer.models import GroupsClass

ATTENDANCE_SCORE = {
    "attended_2": 2,
    "attended_3": 3,
    "attended_4": 4,
    "attended_5": 5,
    "attended_10": 10,
}


class SubscriptionTemplate(models.Model):
    name = models.CharField(max_length=250, verbose_name="Название")
    price = models.IntegerField(verbose_name="Стоимость")
    expired = models.IntegerField(verbose_name="Срок действия")
    number_classes = models.IntegerField(
        verbose_name="Количество занятий", null=True, blank=True
    )
    unlimited = models.BooleanField(default=False, verbose_name="Безлимитный")
    is_free = models.BooleanField(default=False, verbose_name="Бесплатно")
    is_day = models.BooleanField(default=False, verbose_name="Дни")
    is_week = models.BooleanField(default=False, verbose_name="Недели")
    is_month = models.BooleanField(default=False, verbose_name="Месяцы")
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Компания",
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "subscription_template"
        verbose_name = "Шаблоны абонементов"
        verbose_name_plural = "Шаблоны абонементов"


class Cashier(models.Model):
    name = models.CharField(max_length=250, verbose_name="Касса")
    description = models.TextField(
        null=True, blank=True, verbose_name="Комментарий"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Компания",
    )
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Владелец",
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "cashier"
        verbose_name = "Касса"
        verbose_name_plural = "Касса"


class TypeRepresentatives(models.Model):
    name = models.CharField(max_length=250, verbose_name="Представители")

    def __str__(self):
        return self.name

    class Meta:
        db_table = "type_representatives"
        verbose_name = "Тип родства"
        verbose_name_plural = "Тип родства"


class SportCategory(models.Model):
    name = models.CharField(max_length=250, verbose_name="Спортивный разряд")
    level = models.PositiveIntegerField(
        verbose_name="Уровень разряда",
        help_text=(
            "Чем выше число, тем выше разряд "
            "(например: 1-новичок, 10-мастер спорта)"
        ),
        default=1,
    )
    description = models.TextField(
        verbose_name="Описание разряда", blank=True, null=True
    )

    def __str__(self):
        return self.name

    def get_short_name(self):
        """Возвращает сокращенное название разряда для отображения в UI."""
        short_names = {
            "Кандидат в мастера спорта": "КМС",
            "Мастер спорта": "МС",
            "Мастер спорта международного класса": "МСМК",
            "Заслуженный мастер спорта": "ЗМС",
        }
        return short_names.get(self.name, self.name)

    class Meta:
        db_table = "sport_category"
        verbose_name = "Спортивный разряд"
        verbose_name_plural = "Спортивные разряды"
        ordering = ["level"]


class Custumer(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="client_profile",
        verbose_name="Пользователь клиента (личный кабинет)",
    )
    full_name = models.CharField(max_length=250, verbose_name="Ф.И.О")
    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message="Phone number must be entered in the format: '+9989999999'. Up to 15 digits allowed.",  # noqa: E501
    )
    phone = models.CharField(
        validators=[phone_regex],
        max_length=250,
        null=True,
        blank=True,
        verbose_name="Телефон",
    )
    gender = models.ForeignKey(
        Gender,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Пол",
    )
    birth_date = models.DateField(
        verbose_name="День рождения", null=True, blank=True
    )
    address = models.CharField(
        max_length=250, verbose_name="Адрес", null=True, blank=True
    )
    email = models.EmailField(verbose_name="E-mail", null=True, blank=True)
    contract_number = models.CharField(
        max_length=250, verbose_name="Номер договора", null=True, blank=True
    )
    contract_type = models.CharField(
        max_length=250, verbose_name="Тип договора", null=True, blank=True
    )
    strat_date = models.DateField(
        verbose_name="Дата начала обучения", null=True, blank=True
    )
    groups = models.ManyToManyField(
        "groups_custumer.GroupsClass", blank=True, verbose_name="Группы"
    )
    sport_category = models.ForeignKey(
        SportCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Спортивный разряд",
    )
    photo = models.ImageField(
        upload_to="custumer/", null=True, blank=True, verbose_name="Фото"
    )
    is_none = models.BooleanField(default=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Компания",
    )
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Владелец",
    )
    achievements = models.ManyToManyField(
        "achievements.Achievement",
        blank=True,
        related_name="customers",
        verbose_name="Достижения",
    )
    competitions = models.ManyToManyField(
        "competitions.Competitions",
        blank=True,
        related_name="customers",
        verbose_name="Соревнования",
    )
    is_send = models.BooleanField(
        default=False, verbose_name="Приглашение отправлено"
    )
    balance = models.PositiveIntegerField(
        default=0, verbose_name="Баланс (баллы)"
    )

    def __str__(self):
        return self.full_name

    class Meta:
        db_table = "custumer"
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"


class CustumerSubscription(models.Model):
    custumer = models.ForeignKey(
        Custumer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Клиент",
    )
    groups = models.ManyToManyField(
        GroupsClass, blank=True, verbose_name="Группы"
    )
    number_classes = models.BigIntegerField(
        verbose_name="Количество занятий", null=True, blank=True
    )
    remained = models.BigIntegerField(
        verbose_name="Количество посещений", null=True, blank=True
    )
    start_date = models.DateField(
        verbose_name="Дата начала", null=True, blank=True
    )
    end_date = models.DateField(
        verbose_name="Дата окончания", null=True, blank=True
    )
    unlimited = models.BooleanField(default=False, verbose_name="Безлимитный")
    total_cost = models.BigIntegerField(
        null=True, blank=True, verbose_name="Итоговая стоимость"
    )
    is_free = models.BooleanField(default=False, verbose_name="Бесплатно")
    is_blok = models.BooleanField(default=False, verbose_name="Закрыть")
    closing_date = models.DateField(null=True, blank=True)
    attendance_status = models.CharField(
        max_length=50,
        choices=[
            ("paid", "Оплачено"),
            ("unpaid", "Не оплачено"),
            ("none", "Бесплатно"),
        ],
        default="none",
        verbose_name="Статус посещения",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Время создания"
    )
    updated_at = models.DateField(
        auto_now=True, verbose_name="Время обновления"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Компания",
    )
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Владелец",
    )

    class Meta:
        db_table = "custumer_subscription"
        verbose_name = "Абонемент"
        verbose_name_plural = "Абонементы"
        indexes = [
            # Для поиска активных абонементов по клиенту и датам
            models.Index(
                fields=["custumer", "start_date", "end_date"],
                name="idx_sub_cust_dates",
            ),
            # Для фильтрации по статусу и блокировке
            models.Index(
                fields=["attendance_status", "is_blok"],
                name="idx_sub_status",
            ),
            # Для проверки истекших абонементов
            models.Index(fields=["end_date"], name="idx_sub_end_date"),
            # Для подсчета оставшихся занятий и безлимитных
            models.Index(
                fields=["unlimited", "number_classes", "remained"],
                name="idx_sub_classes",
            ),
            # Для компании (часто фильтруем по компании)
            models.Index(fields=["company"], name="idx_sub_company"),
        ]

    def __str__(self):
        return f"{self.custumer} - {self.count_of_trainnig_left}"

    @property
    def count_of_trainnig_left(self):
        """Возращает количество оставшихся тренировок."""
        if self.unlimited:
            return "Безлимит"
        if self.number_classes == 0:
            return 0
        if self.remained:
            return self.number_classes - self.remained or 0
        return self.number_classes

    @property
    def days_left(self):
        if self.end_date and self.end_date > localdate():
            return (self.end_date - localdate()).days
        return 0

    @property
    def remaining_amount(self):
        """Возвращает сумму к доплате для неоплаченного абонемента."""
        if self.attendance_status != "unpaid" or self.is_free:
            return 0

        # Получаем общую сумму всех платежей по этому абонементу
        total_paid = sum(
            payment.summ
            for payment in self.payments.all()
            if payment.summ is not None
        )

        # Вычисляем сумму к доплате
        if self.total_cost and total_paid:
            remaining = self.total_cost - total_paid
            return max(0, remaining)  # Не возвращаем отрицательные значения

        return self.total_cost or 0


class CustumerSubscriptonPayment(models.Model):
    custumer = models.ForeignKey(
        Custumer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Клиент",
    )
    groups = models.ForeignKey(
        GroupsClass,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Группы",
    )
    subscription = models.ForeignKey(
        CustumerSubscription,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name="Абонемент",
    )
    attendance_record = models.OneToOneField(
        "groups_custumer.GroupClassessCustumer",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Запись посещения",
        related_name="payment_record",
    )
    summ = models.BigIntegerField(
        null=True, blank=True, verbose_name="Сумма платежа"
    )
    summ_date = models.DateField(
        null=True, blank=True, verbose_name="Дата платежа"
    )
    sub_date = models.DateField(
        null=True, blank=True, verbose_name="Дата посещения"
    )
    cashier = models.ForeignKey(
        Cashier,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Касса",
    )
    count = models.IntegerField(
        null=True, blank=True, verbose_name="Не оплачено"
    )
    is_pay = models.BooleanField(default=False, verbose_name="Оплачено")
    is_blok = models.BooleanField(default=False, verbose_name="Закрыто")
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Компания",
    )
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Владелец",
    )
    create_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    update_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"Клиент: {self.custumer}"

    class Meta:
        db_table = "custumer_payment"
        verbose_name = "Платеж"
        verbose_name_plural = "Платежи"
        indexes = [
            # Для поиска по посещению
            models.Index(
                fields=["attendance_record"],
                name="idx_payment_attendance",
            ),
            # Для поиска по клиенту и дате
            models.Index(
                fields=["custumer", "sub_date"],
                name="idx_payment_cust_date",
            ),
            # Для поиска по абонементу
            models.Index(
                fields=["subscription"],
                name="idx_payment_sub",
            ),
        ]


class CustumerDocs(models.Model):
    custumer = models.ForeignKey(
        Custumer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Клиент",
    )
    name = models.CharField(
        max_length=250,
        verbose_name="Название",
        null=True,
        blank=True,
    )
    files = models.FileField(
        upload_to="custumer_files/",
        verbose_name="Файл",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "custumer_docs"
        verbose_name = "Документ"
        verbose_name_plural = "Документы"


class CustumerRepresentatives(models.Model):
    custumer = models.ForeignKey(
        Custumer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Клиент",
    )
    type = models.ForeignKey(
        TypeRepresentatives,
        on_delete=models.CASCADE,
        verbose_name="Тип родства",
        null=True,
        blank=True,
    )
    full_name = models.CharField(
        max_length=250, verbose_name="Ф.И.О", null=True, blank=True
    )
    phone = models.CharField(
        max_length=250, verbose_name="Телефон", null=True, blank=True
    )
    work = models.CharField(
        max_length=250, null=True, blank=True, verbose_name="Место работы"
    )

    class Meta:
        db_table = "custumer_representatives"
        verbose_name = "Представители"
        verbose_name_plural = "Представители"


class PointsHistory(models.Model):
    """История начисления баллов."""

    custumer = models.ForeignKey(
        Custumer,
        on_delete=models.CASCADE,
        verbose_name="Клиент",
    )
    points = models.IntegerField(
        verbose_name="Баллы",
    )
    reason = models.CharField(
        max_length=50,
        verbose_name="Причина",
        choices=ReasonTextChoices.choices,
    )
    description = models.TextField(
        verbose_name="Описание",
        null=True,
        blank=True,
    )
    # Связи с другими моделями (опционально)
    attendance_record = models.ForeignKey(
        "groups_custumer.GroupClassessCustumer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Запись посещения",
    )
    achievement = models.ForeignKey(
        "achievements.Achievement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Достижение",
    )
    competition_result = models.ForeignKey(
        "competitions.CustumerCompetitionResult",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Результат соревнования",
    )
    purchase = models.ForeignKey(
        "market.Purchase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Покупка",
    )
    # Кто начислил баллы
    awarded_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Начислил",
    )
    created_at = models.DateTimeField(
        verbose_name="Время создания", auto_now_add=True
    )

    class Meta:
        db_table = "points_history"
        verbose_name = "История начисления баллов"
        verbose_name_plural = "История начисления баллов"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.custumer} - {self.points} - {self.reason}"
