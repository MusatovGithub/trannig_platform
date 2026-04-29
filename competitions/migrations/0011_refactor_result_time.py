# Generated manually

import random

from django.db import migrations, models


def populate_test_data(apps, schema_editor):
    """
    Удаляет все существующие результаты и создает тестовые данные.
    """
    CustumerCompetitionResult = apps.get_model(
        "competitions", "CustumerCompetitionResult"
    )
    Competitions = apps.get_model("competitions", "Competitions")
    CustomUser = apps.get_model("authen", "CustomUser")

    # Удаляем все существующие результаты
    CustumerCompetitionResult.objects.all().delete()

    # Получаем существующие соревнования и пользователей
    competitions = list(
        Competitions.objects.all()[:5]
    )  # Берем до 5 соревнований
    users = list(CustomUser.objects.all()[:20])  # Берем до 20 пользователей

    if not competitions or not users:
        # Если нет данных, просто выходим
        return

    # Создаем 10-15 тестовых результатов
    num_results = random.randint(10, 15)
    distances = [50.0, 100.0, 200.0, 400.0, 800.0, 1500.0]
    styles = ["25m", "50m", "open_water"]

    for i in range(num_results):
        competition = random.choice(competitions)
        user = random.choice(users)
        distance = random.choice(distances)
        style = random.choice(styles)

        # Генерируем рандомное время от 00:30:000 до 15:00:000
        # В миллисекундах: от 30000 до 900000
        time_ms = random.randint(30000, 900000)

        # Место от 1 до 10
        place = random.randint(1, 10)

        # Создаем результат
        CustumerCompetitionResult.objects.create(
            competition=competition,
            custumer=user,
            distance=distance,
            style=style,
            result_time_ms=time_ms,
            place=place,
            is_disqualified=False,  # noqa: E501
        )


def reverse_populate(apps, schema_editor):
    """
    Откат: удаляем тестовые данные.
    """
    CustumerCompetitionResult = apps.get_model(
        "competitions", "CustumerCompetitionResult"
    )
    CustumerCompetitionResult.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        (
            "competitions",
            "0010_alter_custumercompetitionresult_discipline_and_more",
        ),
    ]

    operations = [
        # Добавляем новое поле
        migrations.AddField(
            model_name="custumercompetitionresult",
            name="result_time_ms",
            field=models.BigIntegerField(
                blank=True,
                help_text=(
                    "Не заполняется при дисквалификации. Формат: мм:сс:ммм"
                ),
                null=True,
                verbose_name="Показанное время в миллисекундах",
            ),
        ),
        # Удаляем старые поля
        migrations.RemoveField(
            model_name="custumercompetitionresult",
            name="result_time",
        ),
        migrations.RemoveField(
            model_name="custumercompetitionresult",
            name="result_ms",
        ),
        # Заполняем тестовыми данными
        migrations.RunPython(populate_test_data, reverse_populate),
    ]
