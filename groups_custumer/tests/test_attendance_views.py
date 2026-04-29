"""
Интеграционные тесты для представлений работы с оценками посещаемости.
"""

import json
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group as AuthGroup
from django.test import Client, TestCase
from django.urls import reverse

from authen.models import Company, CustomUser, Gender
from custumer.models import Custumer, CustumerSubscription
from employe.models import Employe
from groups_custumer.models import (
    GroupClasses,
    GroupClassessCustumer,
    GroupsClass,
)


class MarkAttendanceViewTests(TestCase):
    """Тесты представления mark_attendance."""

    def setUp(self):
        """Подготовка тестовых данных."""
        # Создание компании
        self.company = Company.objects.create(name="Test Company")

        # Создание базовых справочников
        self.gender = Gender.objects.create(name="Мужской")

        # Создание админа
        self.admin_user = CustomUser.objects.create_user(
            username="admin",
            password="admin123",
            company=self.company,
        )
        self.admin_group = AuthGroup.objects.create(name="admin")
        self.admin_user.groups.add(self.admin_group)

        # Создание клиента
        self.client = Client()
        self.client.login(username="admin", password="admin123")

        # Создание клиента (customer)
        self.custumer = Custumer.objects.create(
            full_name="Test Customer",
            balance=Decimal("100.00"),
            company=self.company,
            owner=self.admin_user,
        )

        # Создание группы
        self.group = GroupsClass.objects.create(
            name="Test Group",
            company=self.company,
            owner_id=self.admin_user,
        )

        # Создание тренера
        self.employe = Employe.objects.create(
            full_name="Test Coach",
            gender=self.gender,
            company=self.company,
            owner=self.admin_user,
        )

        # Создание занятия
        self.group_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date.today(),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.admin_user,
        )

        # Создание записи посещаемости
        self.attendance = GroupClassessCustumer.objects.create(
            gr_class=self.group_class,
            custumer=self.custumer,
            date=date.today(),
            attendance_status="none",
            company=self.company,
            owner=self.admin_user,
        )

    def test_mark_attendance_post_request(self):
        """Тест POST запроса для выставления оценки."""
        url = reverse(
            "groups_custumer:mark_attendance",
            kwargs={
                "group_id": self.group.id,
                "custumer_id": self.custumer.id,
                "day_date": date.today().strftime("%Y-%m-%d"),
                "pk": self.attendance.id,
            },
        )

        response = self.client.post(
            url,
            {
                "status": "attended_5",
                "comment": "Good work",
            },
        )

        # Проверяем редирект
        self.assertEqual(response.status_code, 302)

        # Проверяем, что оценка выставлена
        self.attendance.refresh_from_db()
        self.assertEqual(self.attendance.attendance_status, "attended_5")
        self.assertEqual(self.attendance.comment, "Good work")

    def test_mark_attendance_blocked_record(self):
        """Тест изменения заблокированной записи (теперь разрешено)."""
        self.attendance.is_block = True
        self.attendance.save()

        url = reverse(
            "groups_custumer:mark_attendance",
            kwargs={
                "group_id": self.group.id,
                "custumer_id": self.custumer.id,
                "day_date": date.today().strftime("%Y-%m-%d"),
                "pk": self.attendance.id,
            },
        )

        response = self.client.post(
            url,
            {
                "status": "attended_5",
                "comment": "Test",
            },
        )

        # Должен быть успешный редирект
        self.assertEqual(response.status_code, 302)

        # Проверяем, что оценка ИЗМЕНИЛАСЬ (теперь можно изменять заблокированные)
        self.attendance.refresh_from_db()
        self.assertEqual(self.attendance.attendance_status, "attended_5")

    def test_mark_attendance_invalid_status(self):
        """Тест невалидного статуса."""
        url = reverse(
            "groups_custumer:mark_attendance",
            kwargs={
                "group_id": self.group.id,
                "custumer_id": self.custumer.id,
                "day_date": date.today().strftime("%Y-%m-%d"),
                "pk": self.attendance.id,
            },
        )

        response = self.client.post(
            url,
            {
                "status": "invalid_status",
                "comment": "Test",
            },
        )

        # Должен быть редирект с ошибкой
        self.assertEqual(response.status_code, 302)

    def test_mark_attendance_requires_login(self):
        """Тест требования авторизации."""
        # Выходим из системы
        self.client.logout()

        url = reverse(
            "groups_custumer:mark_attendance",
            kwargs={
                "group_id": self.group.id,
                "custumer_id": self.custumer.id,
                "day_date": date.today().strftime("%Y-%m-%d"),
                "pk": self.attendance.id,
            },
        )

        response = self.client.post(
            url,
            {
                "status": "attended_5",
            },
        )

        # Должен быть редирект на логин
        self.assertEqual(response.status_code, 302)
        self.assertIn("?next=", response.url)
        self.assertTrue(response.url.startswith(f"{settings.LOGIN_URL}"))


class MarkAttendanceAjaxViewTests(TestCase):
    """Тесты AJAX представления mark_attendance_ajax."""

    def setUp(self):
        """Подготовка тестовых данных."""
        # Создание компании
        self.company = Company.objects.create(name="Test Company")

        # Создание базовых справочников
        self.gender = Gender.objects.create(name="Мужской")

        # Создание админа
        self.admin_user = CustomUser.objects.create_user(
            username="admin",
            password="admin123",
            company=self.company,
        )
        self.admin_group = AuthGroup.objects.create(name="admin")
        self.admin_user.groups.add(self.admin_group)

        # Создание клиента
        self.client = Client()
        self.client.login(username="admin", password="admin123")

        # Создание клиента (customer)
        self.custumer = Custumer.objects.create(
            full_name="Test Customer",
            balance=Decimal("100.00"),
            company=self.company,
            owner=self.admin_user,
        )

        # Создание группы
        self.group = GroupsClass.objects.create(
            name="Test Group",
            company=self.company,
            owner_id=self.admin_user,
        )

        # Создание тренера
        self.employe = Employe.objects.create(
            full_name="Test Coach",
            gender=self.gender,
            company=self.company,
            owner=self.admin_user,
        )

        # Создание занятия
        self.group_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date.today(),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.admin_user,
        )

        # Создание записи посещаемости
        self.attendance = GroupClassessCustumer.objects.create(
            gr_class=self.group_class,
            custumer=self.custumer,
            date=date.today(),
            attendance_status="none",
            company=self.company,
            owner=self.admin_user,
        )

    def test_ajax_mark_attendance_success(self):
        """Тест успешного AJAX запроса."""
        url = reverse(
            "groups_custumer:mark_attendance_ajax",
            kwargs={"attendance_id": self.attendance.id},
        )

        response = self.client.post(
            url,
            {
                "status": "attended_5",
                "comment": "Excellent",
            },
        )

        # Проверяем успешный ответ
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["new_status"], "attended_5")
        self.assertEqual(data["display_text"], "5")
        self.assertEqual(data["css_class"], "grade-5")

        # Проверяем, что запись обновлена
        self.attendance.refresh_from_db()
        self.assertEqual(self.attendance.attendance_status, "attended_5")
        self.assertEqual(self.attendance.comment, "Excellent")

    def test_ajax_mark_attendance_invalid_status(self):
        """Тест AJAX запроса с невалидным статусом."""
        url = reverse(
            "groups_custumer:mark_attendance_ajax",
            kwargs={"attendance_id": self.attendance.id},
        )

        response = self.client.post(
            url,
            {
                "status": "invalid",
            },
        )

        # Должен вернуть ошибку
        self.assertEqual(response.status_code, 400)

        data = json.loads(response.content)
        self.assertFalse(data["success"])
        self.assertIn("error", data)

    def test_ajax_mark_attendance_blocked(self):
        """Тест AJAX запроса для заблокированной записи (теперь разрешено)."""
        self.attendance.is_block = True
        self.attendance.save()

        url = reverse(
            "groups_custumer:mark_attendance_ajax",
            kwargs={"attendance_id": self.attendance.id},
        )

        response = self.client.post(
            url,
            {
                "status": "attended_5",
            },
        )

        # Должен вернуть успех (теперь можно изменять заблокированные)
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertTrue(data["success"])

    def test_ajax_mark_attendance_missing_status(self):
        """Тест AJAX запроса без статуса."""
        url = reverse(
            "groups_custumer:mark_attendance_ajax",
            kwargs={"attendance_id": self.attendance.id},
        )

        response = self.client.post(url, {})

        # Должен вернуть ошибку 400
        self.assertEqual(response.status_code, 400)

        data = json.loads(response.content)
        self.assertFalse(data["success"])

    def test_ajax_mark_attendance_requires_post(self):
        """Тест что AJAX endpoint требует POST."""
        url = reverse(
            "groups_custumer:mark_attendance_ajax",
            kwargs={"attendance_id": self.attendance.id},
        )

        response = self.client.get(url)

        # Должен вернуть ошибку 405
        self.assertEqual(response.status_code, 405)

    def test_ajax_mark_attendance_requires_login(self):
        """Тест требования авторизации для AJAX."""
        self.client.logout()

        url = reverse(
            "groups_custumer:mark_attendance_ajax",
            kwargs={"attendance_id": self.attendance.id},
        )

        response = self.client.post(
            url,
            {
                "status": "attended_5",
            },
        )

        # Должен быть редирект на логин
        self.assertEqual(response.status_code, 302)

    def test_ajax_mark_attendance_with_subscription(self):
        """Тест AJAX запроса с использованием подписки."""
        # Создаем подписку
        subscription = CustumerSubscription.objects.create(
            custumer=self.custumer,
            number_classes=10,
            remained=5,
            start_date=date.today(),
            end_date=date.today(),
            company=self.company,
            owner=self.admin_user,
        )
        subscription.groups.set([self.group])

        url = reverse(
            "groups_custumer:mark_attendance_ajax",
            kwargs={"attendance_id": self.attendance.id},
        )

        response = self.client.post(
            url,
            {
                "status": "attended_5",
            },
        )

        self.assertEqual(response.status_code, 200)

        # Проверяем, что подписка использована
        subscription.refresh_from_db()
        self.assertEqual(subscription.remained, 6)

        # Проверяем, что attendance связан с подпиской
        self.attendance.refresh_from_db()
        self.assertEqual(self.attendance.used_subscription.id, subscription.id)


class MarkAttendanceDateViewTests(TestCase):
    """Тесты представления mark_attendance_date."""

    def setUp(self):
        """Подготовка тестовых данных."""
        # Создание компании
        self.company = Company.objects.create(name="Test Company")

        # Создание базовых справочников
        self.gender = Gender.objects.create(name="Мужской")

        # Создание админа
        self.admin_user = CustomUser.objects.create_user(
            username="admin",
            password="admin123",
            company=self.company,
        )
        self.admin_group = AuthGroup.objects.create(name="admin")
        self.admin_user.groups.add(self.admin_group)

        # Создание клиента
        self.client = Client()
        self.client.login(username="admin", password="admin123")

        # Создание клиента (customer)
        self.custumer = Custumer.objects.create(
            full_name="Test Customer",
            balance=Decimal("100.00"),
            company=self.company,
            owner=self.admin_user,
        )

        # Создание группы
        self.group = GroupsClass.objects.create(
            name="Test Group",
            company=self.company,
            owner_id=self.admin_user,
        )

        # Создание тренера
        self.employe = Employe.objects.create(
            full_name="Test Coach",
            gender=self.gender,
            company=self.company,
            owner=self.admin_user,
        )

        # Создание занятия
        self.group_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date.today(),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.admin_user,
        )

        # Создание записи посещаемости
        self.attendance = GroupClassessCustumer.objects.create(
            gr_class=self.group_class,
            custumer=self.custumer,
            date=date.today(),
            attendance_status="none",
            company=self.company,
            owner=self.admin_user,
        )

    def test_mark_attendance_date_post_request(self):
        """Тест POST запроса для выставления оценки по конкретной дате."""
        url = reverse(
            "groups_custumer:mark_attendance_date",
            kwargs={
                "group_id": self.group.id,
                "custumer_id": self.custumer.id,
                "day_date": date.today().strftime("%Y-%m-%d"),
                "pk": self.attendance.id,
            },
        )

        response = self.client.post(
            url,
            {
                "status": "attended_4",
                "comment": "Good",
            },
        )

        # Проверяем редирект на страницу с датой
        self.assertEqual(response.status_code, 302)
        self.assertIn("date", response.url)

        # Проверяем, что оценка выставлена
        self.attendance.refresh_from_db()
        self.assertEqual(self.attendance.attendance_status, "attended_4")
        self.assertEqual(self.attendance.comment, "Good")
