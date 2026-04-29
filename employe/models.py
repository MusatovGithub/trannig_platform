from django.contrib.auth.models import Permission
from django.core.validators import RegexValidator
from django.db import models

from authen.models import Company, CustomUser, Gender


class EmployePermissionsGroups(models.Model):
    name = models.CharField(max_length=250, verbose_name="Название")

    def __str__(self):
        return self.name

    class Meta:
        db_table = "employe_permissions_group"
        verbose_name = "Доступные права Группы"
        verbose_name_plural = "Доступные права Группы"


class EmployePermissions(models.Model):
    name = models.CharField(max_length=250, verbose_name="Название")
    group = models.ForeignKey(
        EmployePermissionsGroups,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="perm_group",
        verbose_name="Группы",
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "employe_permissions"
        verbose_name = "Доступные права"
        verbose_name_plural = "Доступные права"


class EmployeRoll(models.Model):
    name = models.CharField(max_length=250, verbose_name="Название")
    permissons = models.ManyToManyField(Permission, verbose_name="Права")
    perm = models.ManyToManyField(EmployePermissions, blank=True)
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
        db_table = "employe_roll"
        verbose_name = "Роль сотрудника"
        verbose_name_plural = "Роли сотрудников"


class Employe(models.Model):
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
        unique=True,
        verbose_name="Телефон",
    )
    gender = models.ForeignKey(
        Gender, on_delete=models.CASCADE, verbose_name="Пол"
    )
    roll = models.ForeignKey(
        EmployeRoll,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Роль",
    )
    decription = models.TextField(
        null=True, blank=True, verbose_name="Комментарий"
    )
    is_send = models.BooleanField(
        default=False, verbose_name="Отправить приглашение"
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_id",
        verbose_name="Пользователь",
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
        related_name="owner_id",
        verbose_name="Владелец",
    )

    def __str__(self):
        return self.full_name

    class Meta:
        db_table = "employe"
        verbose_name = "Сотрудники"
        verbose_name_plural = "Сотрудники"
