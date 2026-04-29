"""
Тесты для сервисов работы с группами.
"""

from datetime import date, timedelta

from django.contrib.auth.models import Group as AuthGroup
from django.test import TestCase

from authen.models import Company, CustomUser, Gender, TypeSportsCompany
from employe.models import Employe, EmployeRoll
from groups_custumer.services import (
    GroupValidationError,
    assign_coaches,
    create_group,
    update_group,
    validate_group_data,
)


class GroupServiceTestCase(TestCase):
    """Тесты для group_service."""

    def setUp(self):
        """Подготовка тестовых данных."""
        # Создание компании
        self.company = Company.objects.create(name="Test Company")

        # Создание пользователя
        self.user = CustomUser.objects.create_user(
            username="testuser",
            password="testpass123",
            company=self.company,
        )

        # Создание группы admin
        self.admin_group = AuthGroup.objects.create(name="admin")
        self.user.groups.add(self.admin_group)

        # Создание типа спорта
        self.sport_type = TypeSportsCompany.objects.create(
            name="Футбол", company=self.company
        )

        # Создание пола
        self.gender = Gender.objects.create(name="Мужской")

        # Создание роли сотрудника
        self.role = EmployeRoll.objects.create(
            name="Тренер", company=self.company
        )

        # Создание пользователей для тренеров
        self.coach1_user = CustomUser.objects.create_user(
            username="coach1",
            password="coach123",
            company=self.company,
        )
        self.coach2_user = CustomUser.objects.create_user(
            username="coach2",
            password="coach123",
            company=self.company,
        )

        # Создание тренеров с отдельными пользователями
        self.coach1 = Employe.objects.create(
            full_name="Тренер 1",
            company=self.company,
            user=self.coach1_user,
            roll=self.role,
            gender=self.gender,
        )
        self.coach2 = Employe.objects.create(
            full_name="Тренер 2",
            company=self.company,
            user=self.coach2_user,
            roll=self.role,
            gender=self.gender,
        )

    def test_validate_group_data_success(self):
        """Тест успешной валидации данных группы."""
        name = "Тестовая группа"
        sport_type_id = str(self.sport_type.id)
        coaches_ids = [str(self.coach1.id)]
        start_date_str = "01.12.2025"

        result = validate_group_data(
            name, sport_type_id, coaches_ids, start_date_str, self.company
        )

        self.assertEqual(result[0], name)
        self.assertEqual(result[1], self.sport_type)
        self.assertEqual(len(result[2]), 1)
        self.assertIsInstance(result[3], date)

    def test_validate_group_data_empty_name(self):
        """Тест валидации с пустым названием."""
        with self.assertRaises(GroupValidationError) as context:
            validate_group_data(
                "",
                str(self.sport_type.id),
                [str(self.coach1.id)],
                "01.12.2025",
                self.company,
            )
        self.assertIn("Название группы", str(context.exception))

    def test_validate_group_data_no_coaches(self):
        """Тест валидации без тренеров."""
        with self.assertRaises(GroupValidationError) as context:
            validate_group_data(
                "Группа",
                str(self.sport_type.id),
                [],
                "01.12.2025",
                self.company,
            )
        self.assertIn("тренера", str(context.exception))

    def test_validate_group_data_invalid_date(self):
        """Тест валидации с невалидной датой."""
        with self.assertRaises(GroupValidationError):
            validate_group_data(
                "Группа",
                str(self.sport_type.id),
                [str(self.coach1.id)],
                "invalid-date",
                self.company,
            )

    def test_validate_group_data_nonexistent_sport_type(self):
        """Тест валидации с несуществующим типом спорта."""
        with self.assertRaises(GroupValidationError) as context:
            validate_group_data(
                "Группа",
                "99999",
                [str(self.coach1.id)],
                "01.12.2025",
                self.company,
            )
        self.assertIn("вид спорта", str(context.exception))

    def test_create_group_success(self):
        """Тест успешного создания группы."""
        name = "Новая группа"
        start_date = date(2025, 12, 1)
        end_date = date(2025, 12, 31)

        group = create_group(
            name,
            self.sport_type,
            start_date,
            end_date,
            self.company,
            self.user,
        )

        self.assertIsNotNone(group.id)
        self.assertEqual(group.name, name)
        self.assertEqual(group.type_sport, self.sport_type)
        self.assertEqual(group.strat_training, start_date)
        self.assertEqual(group.company, self.company)

    def test_update_group_success(self):
        """Тест успешного обновления группы."""
        # Создание группы
        group = create_group(
            "Старое название",
            self.sport_type,
            date(2025, 11, 1),
            date(2025, 11, 30),
            self.company,
            self.user,
        )

        # Обновление
        new_name = "Новое название"
        new_date = date(2025, 12, 1)
        new_end_date = date(2025, 12, 31)
        updated_group = update_group(
            group, new_name, self.sport_type, new_date, new_end_date
        )

        self.assertEqual(updated_group.name, new_name)
        self.assertEqual(updated_group.strat_training, new_date)
        self.assertEqual(updated_group.end_training, new_end_date)

    def test_assign_coaches_new_group(self):
        """Тест назначения тренеров новой группе."""
        group = create_group(
            "Группа",
            self.sport_type,
            date(2025, 12, 1),
            date(2025, 12, 31),
            self.company,
            self.user,
        )

        coaches = [self.coach1, self.coach2]
        assign_coaches(group, coaches)

        self.assertEqual(group.employe_id.count(), 2)
        self.assertIn(self.coach1, group.employe_id.all())
        self.assertIn(self.coach2, group.employe_id.all())

    def test_assign_coaches_update_group(self):
        """Тест обновления списка тренеров."""
        group = create_group(
            "Группа",
            self.sport_type,
            date(2025, 12, 1),
            date(2025, 12, 31),
            self.company,
            self.user,
        )
        assign_coaches(group, [self.coach1])

        # Обновление списка тренеров
        assign_coaches(group, [self.coach2])

        self.assertEqual(group.employe_id.count(), 1)
        self.assertNotIn(self.coach1, group.employe_id.all())
        self.assertIn(self.coach2, group.employe_id.all())

    def test_validate_group_data_multiple_coaches(self):
        """Тест валидации с несколькими тренерами."""
        name = "Группа"
        coaches_ids = [str(self.coach1.id), str(self.coach2.id)]

        result = validate_group_data(
            name,
            str(self.sport_type.id),
            coaches_ids,
            "01.12.2025",
            self.company,
        )

        self.assertEqual(len(result[2]), 2)

    def test_validate_group_data_whitespace_name(self):
        """Тест валидации с пробелами в названии."""
        with self.assertRaises(GroupValidationError):
            validate_group_data(
                "   ",
                str(self.sport_type.id),
                [str(self.coach1.id)],
                "01.12.2025",
                self.company,
            )

    def test_create_group_with_future_date(self):
        """Тест создания группы с будущей датой."""
        future_date = date.today() + timedelta(days=30)
        end_date = future_date + timedelta(days=30)
        group = create_group(
            "Будущая группа",
            self.sport_type,
            future_date,
            end_date,
            self.company,
            self.user,
        )

        self.assertEqual(group.strat_training, future_date)

    def test_validate_group_data_different_date_formats(self):
        """Тест валидации с разными форматами дат."""
        # Формат DD.MM.YYYY
        result1 = validate_group_data(
            "Группа1",
            str(self.sport_type.id),
            [str(self.coach1.id)],
            "01.12.2025",
            self.company,
        )
        self.assertEqual(result1[3], date(2025, 12, 1))

        # Формат YYYY-MM-DD
        result2 = validate_group_data(
            "Группа2",
            str(self.sport_type.id),
            [str(self.coach1.id)],
            "2025-12-01",
            self.company,
        )
        self.assertEqual(result2[3], date(2025, 12, 1))
