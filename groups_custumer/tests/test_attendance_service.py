"""
Тесты для сервисного слоя работы с посещаемостью.
"""

from datetime import date, time, timedelta
from decimal import Decimal

from django.test import TestCase

from authen.models import Company, CustomUser, Gender
from custumer.models import (
    Custumer,
    CustumerSubscription,
    CustumerSubscriptonPayment,
)
from employe.models import Employe
from groups_custumer.models import (
    GroupClasses,
    GroupClassessCustumer,
    GroupsClass,
)
from groups_custumer.services import (
    AttendanceValidationError,
    create_payment_record,
    delete_payment_record,
    find_and_use_subscription,
    get_attendance_css_class,
    get_attendance_display_text,
    process_attendance_mark,
    return_subscription_usage,
    update_customer_balance,
    validate_attendance_status,
)


class AttendanceValidationTests(TestCase):
    """Тесты валидации статусов посещаемости."""

    def test_validate_valid_statuses(self):
        """Тест валидации корректных статусов."""
        valid_statuses = [
            "attended_2",
            "attended_3",
            "attended_4",
            "attended_5",
            "attended_10",
            "none",
            "not_attended",
        ]
        for status in valid_statuses:
            try:
                validate_attendance_status(status)
            except AttendanceValidationError:
                self.fail(
                    f"validate_attendance_status raised AttendanceValidationError "  # noqa: E501
                    f"for valid status: {status}"
                )

    def test_validate_invalid_status(self):
        """Тест валидации некорректного статуса."""
        with self.assertRaises(AttendanceValidationError):
            validate_attendance_status("invalid_status")

    # УДАЛЕН: test_check_attendance_blocked - функция больше не используется
    # Теперь можно изменять посещения независимо от статуса оплаты


class AttendanceDisplayTests(TestCase):
    """Тесты функций отображения."""

    def test_get_attendance_display_text(self):
        """Тест получения текста для отображения."""
        test_cases = {
            "attended_2": "2",
            "attended_3": "3",
            "attended_4": "4",
            "attended_5": "5",
            "attended_10": "10",
            "not_attended": "Н",
            "none": "+",
        }
        for status, expected_text in test_cases.items():
            self.assertEqual(
                get_attendance_display_text(status), expected_text
            )

    def test_get_attendance_css_class(self):
        """Тест получения CSS класса."""
        test_cases = {
            "attended_2": "grade-2",
            "attended_3": "grade-3",
            "attended_4": "grade-4",
            "attended_5": "grade-5",
            "attended_10": "grade-10",
            "not_attended": "status-absent",
            "none": "status-empty",
        }
        for status, expected_class in test_cases.items():
            self.assertEqual(get_attendance_css_class(status), expected_class)


class CustomerBalanceTests(TestCase):
    """Тесты обновления баланса клиента."""

    def setUp(self):
        """Подготовка тестовых данных."""
        self.company = Company.objects.create(name="Test Company")
        self.user = CustomUser.objects.create_user(
            username="testuser", password="test123", company=self.company
        )
        self.custumer = Custumer.objects.create(
            full_name="Test Customer",
            balance=Decimal("50.00"),
            company=self.company,
            owner=self.user,
        )

    def test_update_balance_increase(self):
        """Тест увеличения баланса."""
        initial_balance = self.custumer.balance
        update_customer_balance(self.custumer, "none", "attended_5")

        self.custumer.refresh_from_db()
        # Проверяем, что баланс увеличился
        self.assertGreater(self.custumer.balance, initial_balance)

    def test_update_balance_decrease(self):
        """Тест уменьшения баланса."""
        initial_balance = self.custumer.balance
        update_customer_balance(self.custumer, "attended_5", "none")

        self.custumer.refresh_from_db()
        # Проверяем, что баланс уменьшился
        self.assertLess(self.custumer.balance, initial_balance)

    def test_update_balance_insufficient_funds(self):
        """Тест недостатка средств при списании."""
        # Устанавливаем малый баланс
        self.custumer.balance = Decimal("1.00")
        self.custumer.save()

        # Попытка списать больше, чем есть
        with self.assertRaises(ValueError) as context:
            update_customer_balance(self.custumer, "attended_5", "none")

        self.assertIn("Недостаточно баллов", str(context.exception))


class SubscriptionTests(TestCase):
    """Тесты работы с подписками."""

    def setUp(self):
        """Подготовка тестовых данных."""
        self.company = Company.objects.create(name="Test Company")
        self.user = CustomUser.objects.create_user(
            username="testuser", password="test123", company=self.company
        )
        self.custumer = Custumer.objects.create(
            full_name="Test Customer",
            balance=Decimal("100.00"),
            company=self.company,
            owner=self.user,
        )
        self.group = GroupsClass.objects.create(
            name="Test Group", company=self.company, owner_id=self.user
        )

    def test_find_and_use_subscription(self):
        """Тест поиска и использования подписки."""
        # Создаем подписку
        subscription = CustumerSubscription.objects.create(
            custumer=self.custumer,
            number_classes=10,
            remained=5,
            start_date=date.today() - timedelta(days=10),
            end_date=date.today() + timedelta(days=10),
            company=self.company,
            owner=self.user,
        )
        subscription.groups.set([self.group])

        # Используем подписку
        result = find_and_use_subscription(
            self.custumer, self.group, date.today()
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.id, subscription.id)

        # Проверяем, что remained увеличился
        subscription.refresh_from_db()
        self.assertEqual(subscription.remained, 6)

    def test_return_subscription_usage(self):
        """Тест возврата использования подписки."""
        subscription = CustumerSubscription.objects.create(
            custumer=self.custumer,
            number_classes=10,
            remained=6,
            start_date=date.today() - timedelta(days=10),
            end_date=date.today() + timedelta(days=10),
            company=self.company,
            owner=self.user,
        )
        subscription.groups.set([self.group])

        return_subscription_usage(subscription)

        subscription.refresh_from_db()
        self.assertEqual(subscription.remained, 5)


class PaymentRecordTests(TestCase):
    """Тесты работы с записями оплаты."""

    def setUp(self):
        """Подготовка тестовых данных."""
        self.company = Company.objects.create(name="Test Company")
        self.user = CustomUser.objects.create_user(
            username="testuser", password="test123", company=self.company
        )
        self.gender = Gender.objects.create(name="Мужской")
        self.custumer = Custumer.objects.create(
            full_name="Test Customer",
            balance=Decimal("100.00"),
            company=self.company,
            owner=self.user,
        )
        self.group = GroupsClass.objects.create(
            name="Test Group", company=self.company, owner_id=self.user
        )
        self.employe = Employe.objects.create(
            full_name="Test Coach",
            gender=self.gender,
            company=self.company,
            owner=self.user,
        )

    def test_create_payment_record(self):
        """Тест создания записи оплаты."""
        # Создаем занятие
        group_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date.today(),
            strat=time(10, 0),
            end=time(11, 0),
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )

        # Создаем запись посещаемости
        attendance = GroupClassessCustumer.objects.create(
            gr_class=group_class,
            custumer=self.custumer,
            date=date.today(),
            attendance_status="none",
            company=self.company,
            owner=self.user,
        )

        # Создаем запись оплаты
        create_payment_record(
            custumer=self.custumer,
            group=self.group,
            day_date=date.today(),
            attendance=attendance,
            company=self.company,
            owner=self.user,
        )

        # Проверяем, что запись создана
        payment = CustumerSubscriptonPayment.objects.filter(
            custumer=self.custumer,
            groups=self.group,
            sub_date=date.today(),
            subscription=None,
            attendance_record=attendance,
        ).first()

        self.assertIsNotNone(payment)
        self.assertEqual(payment.count, 1)

    def test_delete_payment_record(self):
        """Тест удаления записи оплаты."""
        # Создаем запись
        CustumerSubscriptonPayment.objects.create(
            custumer=self.custumer,
            groups=self.group,
            subscription=None,
            summ=0,
            sub_date=date.today(),
            count=1,
            is_blok=True,
            company=self.company,
            owner=self.user,
        )

        delete_payment_record(self.custumer, self.group, date.today())

        # Проверяем, что запись удалена
        payment_exists = CustumerSubscriptonPayment.objects.filter(
            custumer=self.custumer,
            groups=self.group,
            sub_date=date.today(),
            subscription=None,
        ).exists()

        self.assertFalse(payment_exists)


class ProcessAttendanceMarkTests(TestCase):
    """Тесты основной функции выставления оценок."""

    def setUp(self):
        """Подготовка тестовых данных."""
        self.company = Company.objects.create(name="Test Company")
        self.user = CustomUser.objects.create_user(
            username="testuser", password="test123", company=self.company
        )
        self.gender = Gender.objects.create(name="Мужской")
        self.custumer = Custumer.objects.create(
            full_name="Test Customer",
            balance=Decimal("100.00"),
            company=self.company,
            owner=self.user,
        )
        self.group = GroupsClass.objects.create(
            name="Test Group", company=self.company, owner_id=self.user
        )
        self.employe = Employe.objects.create(
            full_name="Test Coach",
            gender=self.gender,
            company=self.company,
            owner=self.user,
        )
        self.group_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date.today(),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )
        self.attendance = GroupClassessCustumer.objects.create(
            gr_class=self.group_class,
            custumer=self.custumer,
            date=date.today(),
            attendance_status="none",
            company=self.company,
            owner=self.user,
        )

    def test_process_attendance_mark_with_grade(self):
        """Тест выставления числовой оценки."""
        result = process_attendance_mark(
            attendance=self.attendance,
            new_status="attended_5",
            comment="Good performance",
            company=self.company,
            owner=self.user,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["new_status"], "attended_5")

        self.attendance.refresh_from_db()
        self.assertEqual(self.attendance.attendance_status, "attended_5")
        self.assertEqual(self.attendance.comment, "Good performance")

    def test_process_attendance_mark_not_attended(self):
        """Тест отметки 'не был'."""
        result = process_attendance_mark(
            attendance=self.attendance,
            new_status="not_attended",
            comment="Absent",
            company=self.company,
            owner=self.user,
        )

        self.assertTrue(result["success"])
        self.attendance.refresh_from_db()
        self.assertEqual(self.attendance.attendance_status, "not_attended")

    def test_process_attendance_mark_paid_can_be_modified(self):
        """Тест изменения оплаченной записи - теперь это разрешено."""
        # Помечаем как оплаченное наличными
        self.attendance.is_block = True
        self.attendance.used_subscription = None
        self.attendance.attendance_status = "attended_5"
        self.attendance.save()

        # Теперь МОЖНО изменить оценку оплаченного посещения
        result = process_attendance_mark(
            attendance=self.attendance,
            new_status="attended_10",
            comment="Изменили оценку",
            company=self.company,
            owner=self.user,
        )

        # Проверяем, что изменение прошло успешно
        self.assertTrue(result["success"])
        self.attendance.refresh_from_db()
        self.assertEqual(self.attendance.attendance_status, "attended_10")
        self.assertEqual(self.attendance.comment, "Изменили оценку")
        # Важно: статус оплаты сохраняется
        self.assertTrue(self.attendance.is_block)

    def test_process_attendance_mark_invalid_status(self):
        """Тест невалидного статуса."""
        with self.assertRaises(AttendanceValidationError):
            process_attendance_mark(
                attendance=self.attendance,
                new_status="invalid",
                comment=None,
                company=self.company,
                owner=self.user,
            )

    def test_process_attendance_mark_change_grade(self):
        """Тест изменения оценки."""
        # Сначала ставим оценку 3
        self.attendance.attendance_status = "attended_3"
        self.attendance.save()

        # Меняем на 5
        result = process_attendance_mark(
            attendance=self.attendance,
            new_status="attended_5",
            comment="Improved",
            company=self.company,
            owner=self.user,
        )

        self.assertTrue(result["success"])
        self.attendance.refresh_from_db()
        self.assertEqual(self.attendance.attendance_status, "attended_5")
