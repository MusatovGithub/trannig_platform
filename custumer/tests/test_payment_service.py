"""
Тесты для сервисного слоя оплаты посещений.
"""

from datetime import date, datetime

from django.test import TestCase

from authen.models import Company, CustomUser, Gender
from custumer.models import Cashier, Custumer, CustumerSubscription
from custumer.payment import services
from employe.models import Employe
from groups_custumer.models import (
    GroupClasses,
    GroupClassessCustumer,
    GroupsClass,
)


class PaymentServiceTests(TestCase):
    def setUp(self):
        """Настройка тестовых данных."""
        self.company = Company.objects.create(name="Test Company")
        self.owner = CustomUser.objects.create_user(
            username="owner", password="pass", company=self.company
        )
        self.gender = Gender.objects.create(name="Мужской")
        self.employe = Employe.objects.create(
            full_name="Test Coach",
            gender=self.gender,
            company=self.company,
            owner=self.owner,
        )
        self.customer = Custumer.objects.create(
            full_name="Test Customer",
            company=self.company,
            owner=self.owner,
        )
        self.group = GroupsClass.objects.create(
            name="Test Group",
            company=self.company,
            owner_id=self.owner,
        )
        self.cashier = Cashier.objects.create(
            name="Test Cashier",
            company=self.company,
            owner=self.owner,
        )

    def test_get_customer_groups_with_unpaid_attendances(self):
        """Тест получения групп с неоплаченными посещениями."""
        # Создаем занятие
        group_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date.today(),
            strat=datetime.now().time(),
            end=datetime.now().time(),
            employe=self.employe,
            company=self.company,
            owner=self.owner,
        )

        # Создаем неоплаченное посещение
        GroupClassessCustumer.objects.create(
            gr_class=group_class,
            custumer=self.customer,
            date=date.today(),
            attendance_status="attended_2",
            is_block=False,
            company=self.company,
            owner=self.owner,
        )

        # Получаем группы
        groups = services.get_customer_groups_with_unpaid_attendances(
            self.customer.id
        )

        self.assertEqual(groups.count(), 1)
        self.assertEqual(groups.first().id, self.group.id)

    def test_get_unpaid_attendances_by_group(self):
        """Тест получения неоплаченных посещений по группе."""
        # Создаем занятие
        group_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date.today(),
            strat=datetime.now().time(),
            end=datetime.now().time(),
            employe=self.employe,
            company=self.company,
            owner=self.owner,
        )

        # Создаем неоплаченное посещение
        attendance = GroupClassessCustumer.objects.create(
            gr_class=group_class,
            custumer=self.customer,
            date=date.today(),
            attendance_status="attended_2",
            is_block=False,
            company=self.company,
            owner=self.owner,
        )

        # Получаем посещения
        attendances = services.get_unpaid_attendances_by_group(
            self.customer.id, self.group.id
        )

        self.assertEqual(attendances.count(), 1)
        self.assertEqual(attendances.first().id, attendance.id)

    def test_process_payment_for_attendances(self):
        """Тест обработки оплаты посещений наличными."""
        # Создаем занятие
        group_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date.today(),
            strat=datetime.now().time(),
            end=datetime.now().time(),
            employe=self.employe,
            company=self.company,
            owner=self.owner,
        )

        # Создаем неоплаченное посещение
        attendance = GroupClassessCustumer.objects.create(
            gr_class=group_class,
            custumer=self.customer,
            date=date.today(),
            attendance_status="attended_2",
            is_block=False,
            company=self.company,
            owner=self.owner,
        )

        # Обрабатываем оплату
        created, updated = services.process_payment_for_attendances(
            customer=self.customer,
            group=self.group,
            attendance_ids=[attendance.id],
            summ=1000,
            cashier_id=self.cashier.id,
            summ_date=date.today(),
            company=self.company,
            owner=self.owner,
        )

        # Проверяем, что посещение заблокировано
        attendance.refresh_from_db()
        self.assertTrue(attendance.is_block)

        # Проверяем, что создан платеж
        self.assertGreater(len(created), 0)

    def test_process_subscription_payment(self):
        """Тест обработки списания с абонемента."""
        # Создаем абонемент
        subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=10,
            remained=0,
            start_date=date.today(),
            end_date=date.today(),
            is_blok=False,
            company=self.company,
            owner=self.owner,
        )
        subscription.groups.add(self.group)

        # Создаем занятие
        group_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date.today(),
            strat=datetime.now().time(),
            end=datetime.now().time(),
            employe=self.employe,
            company=self.company,
            owner=self.owner,
        )

        # Создаем неоплаченное посещение
        attendance = GroupClassessCustumer.objects.create(
            gr_class=group_class,
            custumer=self.customer,
            date=date.today(),
            attendance_status="attended_2",
            is_block=False,
            company=self.company,
            owner=self.owner,
        )

        # Обрабатываем списание с абонемента
        result = services.process_subscription_payment(
            customer=self.customer,
            group=self.group,
            attendance_ids=[attendance.id],
            subscription_id=subscription.id,
        )

        # Проверяем результат
        self.assertTrue(result["success"])
        self.assertEqual(result["attendances_count"], 1)

        # Проверяем, что посещение связано с абонементом
        attendance.refresh_from_db()
        self.assertEqual(attendance.used_subscription.id, subscription.id)

        # Проверяем, что абонемент обновлен
        subscription.refresh_from_db()
        self.assertEqual(subscription.remained, 1)

    def test_process_subscription_payment_insufficient_classes(self):
        """Тест обработки списания с абонемента при недостатке занятий."""
        # Создаем абонемент с 0 оставшихся занятий
        subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=10,
            remained=10,  # Все занятия использованы
            start_date=date.today(),
            end_date=date.today(),
            is_blok=False,
            company=self.company,
            owner=self.owner,
        )
        subscription.groups.add(self.group)

        # Создаем занятие
        group_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date.today(),
            strat=datetime.now().time(),
            end=datetime.now().time(),
            employe=self.employe,
            company=self.company,
            owner=self.owner,
        )

        # Создаем неоплаченное посещение
        attendance = GroupClassessCustumer.objects.create(
            gr_class=group_class,
            custumer=self.customer,
            date=date.today(),
            attendance_status="attended_2",
            is_block=False,
            company=self.company,
            owner=self.owner,
        )

        # Пытаемся обработать списание - должно вызвать ошибку
        with self.assertRaises(ValueError) as context:
            services.process_subscription_payment(
                customer=self.customer,
                group=self.group,
                attendance_ids=[attendance.id],
                subscription_id=subscription.id,
            )

        self.assertIn("Недостаточно занятий", str(context.exception))

    def test_process_free_attendances(self):
        """Тест обработки прощения посещений."""
        # Создаем занятие
        group_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date.today(),
            strat=datetime.now().time(),
            end=datetime.now().time(),
            employe=self.employe,
            company=self.company,
            owner=self.owner,
        )

        # Создаем неоплаченное посещение
        attendance = GroupClassessCustumer.objects.create(
            gr_class=group_class,
            custumer=self.customer,
            date=date.today(),
            attendance_status="attended_2",
            is_block=False,
            company=self.company,
            owner=self.owner,
        )

        # Обрабатываем прощение
        result = services.process_free_attendances(
            customer=self.customer,
            group=self.group,
            attendance_ids=[attendance.id],
        )

        # Проверяем результат
        self.assertTrue(result["success"])
        self.assertEqual(result["attendances_count"], 1)

    def test_get_available_subscriptions_for_group(self):
        """Тест получения доступных абонементов для группы."""
        # Создаем абонемент
        subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=10,
            remained=0,
            start_date=date.today(),
            end_date=date.today(),
            is_blok=False,
            company=self.company,
            owner=self.owner,
        )
        subscription.groups.add(self.group)

        # Получаем абонементы
        subscriptions = services.get_available_subscriptions_for_group(
            self.customer.id, self.group.id
        )

        self.assertEqual(subscriptions.count(), 1)
        self.assertEqual(subscriptions.first().id, subscription.id)

    def test_get_cashiers_for_company(self):
        """Тест получения кассиров для компании."""
        # Получаем кассиров (теперь возвращается список из кеша)
        cashiers = services.get_cashiers_for_company(self.company)

        self.assertEqual(len(cashiers), 1)
        self.assertEqual(cashiers[0].id, self.cashier.id)
