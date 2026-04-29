from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


class Gender(models.Model):
    name = models.CharField(max_length=250, verbose_name="Пол")

    def __str__(self):
        return self.name

    class Meta:
        db_table = "gender"
        verbose_name = "Пол"
        verbose_name_plural = "Пол"


class CustomUser(AbstractUser):
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
    avatar = models.ImageField(
        upload_to="avatars/", null=True, blank=True, verbose_name="Аватар"
    )
    company = models.ForeignKey(
        "Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Компания",
        related_name="company",
    )
    must_change_password = models.BooleanField(
        default=False,
        verbose_name="Требуется смена пароля",
    )
    temporary_password_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Срок действия временного пароля",
    )


class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    reset_token = models.CharField(max_length=32, null=True, blank=True)


class Company(models.Model):
    name = models.CharField(max_length=250, verbose_name="Название")

    class Meta:
        db_table = "company"
        verbose_name = "Компания"
        verbose_name_plural = "Компания"

    def __str__(self):
        return self.name


class TypeSportsCompany(models.Model):
    name = models.CharField(max_length=250, verbose_name="Название")
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Компания",
    )

    def __str__(self):
        return f"Спорт: {self.name}"

    class Meta:
        db_table = "type_sport_company"
        verbose_name = "Тип Спорт Компания"
        verbose_name_plural = "Тип Спорт Компания"
