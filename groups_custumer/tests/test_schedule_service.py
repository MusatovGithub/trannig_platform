"""
Тесты для сервисов работы с расписаниями.
"""

from datetime import date

from django.contrib.auth.models import Group as AuthGroup
from django.test import TestCase

from authen.models import Company, CustomUser, Gender, TypeSportsCompany
from custumer.models import Custumer
from employe.models import Employe, EmployeRoll
from groups_custumer.models import (
    GroupClasses,
    GroupClassessCustumer,
    Schedule,
    Week,
)
from groups_custumer.services import (
    ScheduleValidationError,
    create_attendance_records_bulk,
    create_group,
    create_group_classes_bulk,
    create_schedules_bulk,
    delete_old_schedule_and_classes,
    generate_group_classes,
    preserve_attendance_data,
    restore_attendance_data,
    validate_end_date,
    validate_schedule_data,
)


class ScheduleServiceTestCase(TestCase):
    """Тесты для schedule_service."""

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

        # Создание роли и тренера
        self.role = EmployeRoll.objects.create(
            name="Тренер", company=self.company
        )
        self.coach = Employe.objects.create(
            full_name="Тренер",
            company=self.company,
            user=self.user,
            roll=self.role,
            gender=self.gender,
        )

        # Создание группы
        self.group = create_group(
            "Тестовая группа",
            self.sport_type,
            date(2025, 12, 1),
            date(2025, 12, 31),
            self.company,
            self.user,
        )
        self.group.employe_id.add(self.coach)

        # Создание дней недели
        self.monday = Week.objects.create(name="Понедельник")
        self.wednesday = Week.objects.create(name="Среда")
        self.friday = Week.objects.create(name="Пятница")

    def test_validate_schedule_data_success(self):
        """Тест успешной валидации расписания."""
        name_schedule = ["Тренировка"]
        weeks_data = [str(self.monday.id)]
        time_start = ["10:00"]
        time_end = ["12:00"]

        result = validate_schedule_data(
            name_schedule, weeks_data, time_start, time_end
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Тренировка")
        self.assertEqual(result[0]["week_id"], self.monday.id)

    def test_validate_schedule_data_empty(self):
        """Тест валидации пустого расписания."""
        result = validate_schedule_data([], [], [], [])
        self.assertEqual(len(result), 0)

    def test_validate_schedule_data_invalid_time(self):
        """Тест валидации с невалидным временем."""
        with self.assertRaises(ScheduleValidationError):
            validate_schedule_data(
                ["Тренировка"],
                [str(self.monday.id)],
                ["25:00"],  # Невалидное время
                ["12:00"],
            )

    def test_validate_schedule_data_end_before_start(self):
        """Тест валидации когда время окончания раньше начала."""
        with self.assertRaises(ScheduleValidationError) as context:
            validate_schedule_data(
                ["Тренировка"],
                [str(self.monday.id)],
                ["14:00"],
                ["12:00"],
            )
        self.assertIn("раньше", str(context.exception))

    def test_validate_schedule_data_multiple_entries(self):
        """Тест валидации нескольких записей расписания."""
        result = validate_schedule_data(
            ["Тренировка 1", "Тренировка 2"],
            [str(self.monday.id), str(self.wednesday.id)],
            ["10:00", "14:00"],
            ["12:00", "16:00"],
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["week_id"], self.monday.id)
        self.assertEqual(result[1]["week_id"], self.wednesday.id)

    def test_validate_end_date_none(self):
        """Тест валидации конечной даты как None."""
        start_date = date(2025, 12, 1)
        result = validate_end_date(None, start_date)
        self.assertIsNone(result)

    def test_validate_end_date_as_date_string(self):
        """Тест валидации конечной даты как строки с датой."""
        start_date = date(2025, 12, 1)
        result = validate_end_date("31.12.2025", start_date)
        self.assertEqual(result, date(2025, 12, 31))

    def test_validate_end_date_as_days(self):
        """Тест валидации конечной даты как количества дней."""
        start_date = date(2025, 12, 1)
        result = validate_end_date("30", start_date)
        self.assertEqual(result, date(2025, 12, 31))

    def test_validate_end_date_negative_days(self):
        """Тест валидации отрицательного количества дней."""
        start_date = date(2025, 12, 1)
        with self.assertRaises(ScheduleValidationError):
            validate_end_date("-10", start_date)

    def test_create_schedules_bulk(self):
        """Тест массового создания расписаний."""
        validated_schedules = [
            {
                "name": "Тренировка 1",
                "week_id": self.monday.id,
                "start_time": "10:00",
                "end_time": "12:00",
            },
            {
                "name": "Тренировка 2",
                "week_id": self.wednesday.id,
                "start_time": "14:00",
                "end_time": "16:00",
            },
        ]

        schedules = create_schedules_bulk(self.group, validated_schedules)

        self.assertEqual(len(schedules), 2)
        self.assertEqual(
            Schedule.objects.filter(groups_id=self.group).count(), 2
        )

    def test_create_schedules_bulk_empty(self):
        """Тест массового создания с пустым списком."""
        result = create_schedules_bulk(self.group, [])
        self.assertEqual(len(result), 0)

    def test_generate_group_classes(self):
        """Тест генерации занятий на основе расписания."""
        validated_schedules = [
            {
                "name": "Тренировка",
                "week_id": self.monday.id,
                "start_time": "10:00",
                "end_time": "12:00",
            }
        ]

        start_date = date(2025, 12, 1)  # Понедельник
        end_date = date(2025, 12, 31)

        classes = generate_group_classes(
            self.group,
            validated_schedules,
            start_date,
            end_date,
            self.company,
            self.user,
        )

        # В декабре 2025 должно быть 5 понедельников
        monday_count = sum(
            1 for c in classes if c.date.strftime("%A") == "Monday"
        )
        self.assertGreater(monday_count, 0)

    def test_generate_group_classes_no_end_date(self):
        """Тест генерации занятий без конечной даты (по умолчанию 2 года)."""
        validated_schedules = [
            {
                "name": "Тренировка",
                "week_id": self.monday.id,
                "start_time": "10:00",
                "end_time": "12:00",
            }
        ]

        start_date = date(2025, 12, 1)

        classes = generate_group_classes(
            self.group,
            validated_schedules,
            start_date,
            None,  # Без конечной даты
            self.company,
            self.user,
        )

        # Должно быть создано много занятий
        # (примерно 104 понедельника за 2 года)
        self.assertGreater(len(classes), 50)

    def test_create_group_classes_bulk(self):
        """Тест массового создания занятий."""
        classes_objects = [
            GroupClasses(
                groups_id=self.group,
                date=date(2025, 12, 1),
                strat="10:00",
                end="12:00",
                name="Тренировка 1",
                employe=self.coach,
                company=self.company,
                owner=self.user,
            ),
            GroupClasses(
                groups_id=self.group,
                date=date(2025, 12, 3),
                strat="14:00",
                end="16:00",
                name="Тренировка 2",
                employe=self.coach,
                company=self.company,
                owner=self.user,
            ),
        ]

        created = create_group_classes_bulk(classes_objects)

        self.assertEqual(len(created), 2)
        self.assertEqual(
            GroupClasses.objects.filter(groups_id=self.group).count(), 2
        )

    def test_create_attendance_records_bulk(self):
        """Тест массового создания записей посещаемости."""
        # Создание занятия
        group_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2025, 12, 1),
            strat="10:00",
            end="12:00",
            name="Тренировка",
            employe=self.coach,
            company=self.company,
            owner=self.user,
        )

        # Создание клиентов
        customer1 = Custumer.objects.create(
            full_name="Клиент 1",
            company=self.company,
            owner=self.user,
        )
        customer2 = Custumer.objects.create(
            full_name="Клиент 2",
            company=self.company,
            owner=self.user,
        )

        customers = [customer1, customer2]

        create_attendance_records_bulk(
            [group_class], customers, self.company, self.user
        )

        self.assertEqual(
            GroupClassessCustumer.objects.filter(gr_class=group_class).count(),
            2,
        )

    def test_preserve_attendance_data(self):
        """Тест сохранения данных посещаемости."""
        # Создание занятия
        group_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2025, 12, 1),
            strat="10:00",
            end="12:00",
            name="Тренировка",
            employe=self.coach,
            company=self.company,
            owner=self.user,
        )

        # Создание клиента
        customer = Custumer.objects.create(
            full_name="Клиент",
            company=self.company,
            owner=self.user,
        )

        # Создание записи посещаемости
        GroupClassessCustumer.objects.create(
            gr_class=group_class,
            custumer=customer,
            date=date(2025, 12, 1),
            attendance_status="attended_2",
            is_block=True,
            company=self.company,
            owner=self.user,
        )

        # Сохранение данных
        attendance_map = preserve_attendance_data(self.group)

        key = (customer.id, date(2025, 12, 1))
        self.assertIn(key, attendance_map)
        self.assertEqual(
            attendance_map[key]["attendance_status"], "attended_2"
        )
        self.assertTrue(attendance_map[key]["is_block"])

    def test_restore_attendance_data(self):
        """Тест восстановления данных посещаемости."""
        # Создание клиента
        customer = Custumer.objects.create(
            full_name="Клиент",
            company=self.company,
            owner=self.user,
        )

        # Подготовка данных посещаемости
        attendance_map = {
            (customer.id, date(2025, 12, 1)): {
                "attendance_status": "attended_2",
                "used_subscription": None,
                "is_block": True,
                "is_none": False,
                "comment": "Тест",
            }
        }

        # Создание нового занятия
        new_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2025, 12, 1),
            strat="10:00",
            end="12:00",
            name="Тренировка",
            employe=self.coach,
            company=self.company,
            owner=self.user,
        )

        # Восстановление данных
        restore_attendance_data(
            [new_class], attendance_map, [customer], self.company, self.user
        )

        # Проверка восстановленных данных
        restored = GroupClassessCustumer.objects.get(
            gr_class=new_class, custumer=customer
        )
        self.assertEqual(restored.attendance_status, "attended_2")
        self.assertTrue(restored.is_block)
        self.assertEqual(restored.comment, "Тест")

    def test_delete_old_schedule_and_classes(self):
        """Тест удаления старого расписания и занятий."""
        # Создание расписания
        Schedule.objects.create(
            groups_id=self.group,
            name="Старое расписание",
            week=self.monday,
            strat_time="10:00",
            end_time="12:00",
        )

        # Создание автоматического и ручного занятия
        GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2025, 12, 1),
            strat="10:00",
            end="12:00",
            name="Авто",
            employe=self.coach,
            company=self.company,
            owner=self.user,
            is_manual=False,
        )
        manual_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2025, 12, 2),
            strat="14:00",
            end="16:00",
            name="Ручное",
            employe=self.coach,
            company=self.company,
            owner=self.user,
            is_manual=True,
        )

        # Удаление
        delete_old_schedule_and_classes(self.group)

        # Проверка
        self.assertEqual(
            Schedule.objects.filter(groups_id=self.group).count(), 0
        )
        self.assertEqual(
            GroupClasses.objects.filter(
                groups_id=self.group, is_manual=False
            ).count(),
            0,
        )
        self.assertTrue(
            GroupClasses.objects.filter(id=manual_class.id).exists()
        )

    def test_validate_schedule_data_skip_empty_entries(self):
        """Тест пропуска пустых записей в расписании."""
        result = validate_schedule_data(
            ["Тренировка 1", ""],
            [str(self.monday.id), ""],
            ["10:00", ""],
            ["12:00", ""],
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Тренировка 1")
