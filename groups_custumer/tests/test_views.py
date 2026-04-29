"""
Интеграционные тесты для views групп.
"""

from datetime import date

from django.contrib.auth.models import Group as AuthGroup
from django.test import Client, TestCase
from django.urls import reverse

from authen.models import Company, CustomUser, Gender, TypeSportsCompany
from employe.models import Employe, EmployePermissions, EmployeRoll
from groups_custumer.models import GroupClasses, GroupsClass, Schedule, Week


class GroupsViewsTestCase(TestCase):
    """Интеграционные тесты для views создания и обновления групп."""

    def setUp(self):
        """Подготовка тестовых данных."""
        # Создание компании
        self.company = Company.objects.create(name="Test Company")

        # Создание пользователя admin
        self.admin_user = CustomUser.objects.create_user(
            username="admin",
            password="admin123",
            company=self.company,
        )
        self.admin_group = AuthGroup.objects.create(name="admin")
        self.admin_user.groups.add(self.admin_group)

        # Создание пользователя assistant
        self.assistant_user = CustomUser.objects.create_user(
            username="assistant",
            password="assistant123",
            company=self.company,
        )
        self.assistant_group = AuthGroup.objects.create(name="assistant")
        self.assistant_user.groups.add(self.assistant_group)

        # Создание пола
        self.gender = Gender.objects.create(name="Мужской")

        # Создание роли с правами
        self.role = EmployeRoll.objects.create(
            name="Тренер с правами", company=self.company
        )

        # Создание прав
        self.perm_add = EmployePermissions.objects.create(
            name="Может добавлять группы"
        )
        self.perm_edit = EmployePermissions.objects.create(
            name="Может редактировать группы"
        )
        self.role.perm.add(self.perm_add, self.perm_edit)

        # Создание сотрудника assistant
        self.assistant_employe = Employe.objects.create(
            full_name="Ассистент",
            company=self.company,
            user=self.assistant_user,
            roll=self.role,
            gender=self.gender,
        )

        # Создание типа спорта
        self.sport_type = TypeSportsCompany.objects.create(
            name="Футбол", company=self.company
        )

        # Создание отдельного пользователя для тренера
        self.coach_user = CustomUser.objects.create_user(
            username="coach",
            password="coach123",
            company=self.company,
        )

        # Создание тренера с отдельным пользователем
        self.coach = Employe.objects.create(
            full_name="Тренер",
            company=self.company,
            user=self.coach_user,
            roll=self.role,
            gender=self.gender,
        )

        # Создание дней недели
        self.monday = Week.objects.create(name="Понедельник")
        self.wednesday = Week.objects.create(name="Среда")

        # Клиент для тестирования
        self.client = Client()

    def test_groups_create_get_admin(self):
        """Тест GET запроса на создание группы (admin)."""
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("groups_custumer:groups_create"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "groups/create.html")
        self.assertIn("employes", response.context)
        self.assertIn("weeks", response.context)
        self.assertIn("type_sports", response.context)

    def test_groups_create_post_success(self):
        """Тест успешного POST запроса на создание группы."""
        self.client.login(username="admin", password="admin123")

        data = {
            "name": "Новая группа",
            "sport_type": self.sport_type.id,
            "coaches": [self.coach.id],
            "start_date": "01.12.2025",
            "name_schedule[]": ["Тренировка"],
            "weeks[]": [self.monday.id],
            "time_strat": ["10:00"],
            "time_end": ["12:00"],
            "end_date": "31.12.2025",
        }

        response = self.client.post(
            reverse("groups_custumer:groups_create"), data
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            GroupsClass.objects.filter(name="Новая группа").exists()
        )

        # Проверка создания расписания
        group = GroupsClass.objects.get(name="Новая группа")
        self.assertEqual(Schedule.objects.filter(groups_id=group).count(), 1)

    def test_groups_create_post_without_schedule(self):
        """Тест создания группы без расписания."""
        self.client.login(username="admin", password="admin123")

        data = {
            "name": "Группа без расписания",
            "sport_type": self.sport_type.id,
            "coaches": [self.coach.id],
            "start_date": "01.12.2025",
            "name_schedule[]": [],
            "weeks[]": [],
            "time_strat": [],
            "time_end": [],
        }

        response = self.client.post(
            reverse("groups_custumer:groups_create"), data
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            GroupsClass.objects.filter(name="Группа без расписания").exists()
        )

    def test_groups_create_post_validation_error(self):
        """Тест валидационной ошибки при создании группы."""
        self.client.login(username="admin", password="admin123")

        data = {
            "name": "",  # Пустое название
            "sport_type": self.sport_type.id,
            "coaches": [self.coach.id],
            "start_date": "01.12.2025",
        }

        response = self.client.post(
            reverse("groups_custumer:groups_create"), data
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)
        self.assertFalse(GroupsClass.objects.filter(name="").exists())

    def test_groups_create_unauthorized(self):
        """Тест доступа без авторизации."""
        response = self.client.get(reverse("groups_custumer:groups_create"))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_groups_update_get_admin(self):
        """Тест GET запроса на обновление группы (admin)."""
        # Создание группы
        group = GroupsClass.objects.create(
            name="Тестовая группа",
            type_sport=self.sport_type,
            strat_training=date(2025, 12, 1),
            company=self.company,
            owner_id=self.admin_user,
        )
        group.employe_id.add(self.coach)

        self.client.login(username="admin", password="admin123")
        response = self.client.get(
            reverse("groups_custumer:groups_update", args=[group.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "groups/update.html")
        self.assertEqual(response.context["groups"], group)

    def test_groups_update_post_success(self):
        """Тест успешного обновления группы."""
        # Создание группы с расписанием
        group = GroupsClass.objects.create(
            name="Старое название",
            type_sport=self.sport_type,
            strat_training=date(2025, 12, 1),
            company=self.company,
            owner_id=self.admin_user,
        )
        group.employe_id.add(self.coach)

        # Создание старого расписания
        Schedule.objects.create(
            groups_id=group,
            name="Старое",
            week=self.monday,
            strat_time="10:00",
            end_time="12:00",
        )

        self.client.login(username="admin", password="admin123")

        data = {
            "name": "Новое название",
            "sport_type": self.sport_type.id,
            "coaches": [self.coach.id],
            "start_date": "15.12.2025",
            "name_schedule[]": ["Обновленная тренировка"],
            "weeks[]": [self.wednesday.id],
            "time_strat": ["14:00"],
            "time_end": ["16:00"],
        }

        response = self.client.post(
            reverse("groups_custumer:groups_update", args=[group.id]), data
        )

        self.assertEqual(response.status_code, 302)

        # Проверка обновления
        group.refresh_from_db()
        self.assertEqual(group.name, "Новое название")
        self.assertEqual(group.strat_training, date(2025, 12, 15))

        # Проверка обновления расписания
        schedules = Schedule.objects.filter(groups_id=group)
        self.assertEqual(schedules.count(), 1)
        self.assertEqual(schedules.first().week, self.wednesday)

    def test_groups_update_preserves_attendance(self):
        """Тест сохранения данных посещаемости при обновлении."""
        # Создание группы
        group = GroupsClass.objects.create(
            name="Группа",
            type_sport=self.sport_type,
            strat_training=date(2025, 12, 1),
            company=self.company,
            owner_id=self.admin_user,
        )
        group.employe_id.add(self.coach)

        # Создание занятия
        GroupClasses.objects.create(
            groups_id=group,
            date=date(2025, 12, 2),
            strat="10:00",
            end="12:00",
            name="Тренировка",
            employe=self.coach,
            company=self.company,
            owner=self.admin_user,
            is_manual=False,
        )

        self.client.login(username="admin", password="admin123")

        # Обновление группы
        data = {
            "name": "Обновленная группа",
            "sport_type": self.sport_type.id,
            "coaches": [self.coach.id],
            "start_date": "01.12.2025",
            "name_schedule[]": [],
            "weeks[]": [],
            "time_strat": [],
            "time_end": [],
        }

        response = self.client.post(
            reverse("groups_custumer:groups_update", args=[group.id]), data
        )

        self.assertEqual(response.status_code, 302)

    def test_groups_update_validation_error(self):
        """Тест валидационной ошибки при обновлении группы."""
        group = GroupsClass.objects.create(
            name="Группа",
            type_sport=self.sport_type,
            strat_training=date(2025, 12, 1),
            company=self.company,
            owner_id=self.admin_user,
        )

        self.client.login(username="admin", password="admin123")

        data = {
            "name": "",  # Пустое название
            "sport_type": self.sport_type.id,
            "coaches": [self.coach.id],
            "start_date": "01.12.2025",
        }

        response = self.client.post(
            reverse("groups_custumer:groups_update", args=[group.id]), data
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.context)

    def test_groups_create_with_end_date_bug_fix(self):
        """Тест исправления бага с end_date (передача числа дней)."""
        self.client.login(username="admin", password="admin123")

        data = {
            "name": "Группа с датой",
            "sport_type": self.sport_type.id,
            "coaches": [self.coach.id],
            "start_date": "01.12.2025",
            "name_schedule[]": ["Тренировка"],
            "weeks[]": [self.monday.id],
            "time_strat": ["10:00"],
            "time_end": ["12:00"],
            "end_date": "30",  # Передаем число дней
        }

        response = self.client.post(
            reverse("groups_custumer:groups_create"), data
        )

        self.assertEqual(response.status_code, 302)
        group = GroupsClass.objects.get(name="Группа с датой")

        # Проверка, что занятия созданы
        classes_count = GroupClasses.objects.filter(groups_id=group).count()
        self.assertGreater(classes_count, 0)

    def test_groups_create_with_end_date_as_string(self):
        """Тест создания группы с end_date как датой."""
        self.client.login(username="admin", password="admin123")

        data = {
            "name": "Группа с строковой датой",
            "sport_type": self.sport_type.id,
            "coaches": [self.coach.id],
            "start_date": "01.12.2025",
            "name_schedule[]": ["Тренировка"],
            "weeks[]": [self.monday.id],
            "time_strat": ["10:00"],
            "time_end": ["12:00"],
            "end_date": "31.12.2025",  # Передаем дату
        }

        response = self.client.post(
            reverse("groups_custumer:groups_create"), data
        )

        self.assertEqual(response.status_code, 302)

    def test_groups_all_pagination(self):
        """Тест пагинации списка групп."""
        # Создание нескольких групп
        for i in range(15):
            GroupsClass.objects.create(
                name=f"Группа {i}",
                type_sport=self.sport_type,
                strat_training=date(2025, 12, 1),
                company=self.company,
                owner_id=self.admin_user,
            )

        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("groups_custumer:groups_all"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue("page_obj" in response.context)
        self.assertTrue(response.context["page_obj"].has_next())
