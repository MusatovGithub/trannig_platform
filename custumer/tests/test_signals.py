"""Тесты для проверки работы сигналов синхронизации между CustomUser и Custumer."""  # noqa: E501

from django.contrib.auth import get_user_model
from django.test import TestCase

from authen.models import Company, Gender
from custumer.models import (
    Cashier,
    Custumer,
    CustumerSubscription,
    CustumerSubscriptonPayment,
)

CustomUser = get_user_model()


class SignalSyncTest(TestCase):
    """Тест синхронизации данных через сигналы"""

    def setUp(self):
        """Подготовка тестовых данных"""
        # Создаем компанию
        self.company = Company.objects.create(name="Test Company")

        # Создаем пол
        self.gender = Gender.objects.create(name="Мужской")

        # Создаем пользователя
        self.user = CustomUser.objects.create(
            username="test@example.com",
            email="test@example.com",
            first_name="Test User",
            phone="+9989999999",
            company=self.company,
        )

        # Создаем профиль клиента
        self.custumer = Custumer.objects.create(
            user=self.user,
            full_name="Test User",
            phone="+9989999999",
            email="test@example.com",
            company=self.company,
        )

    def test_sync_customuser_to_custumer(self):
        """Тест синхронизации из CustomUser в Custumer"""
        # Изменяем данные пользователя
        self.user.first_name = "Updated Name"
        self.user.email = "updated@example.com"
        self.user.phone = "+9988888888"
        self.user.save()

        # Обновляем объект из базы
        self.custumer.refresh_from_db()

        # Проверяем, что данные синхронизировались
        self.assertEqual(self.custumer.full_name, "Updated Name")
        self.assertEqual(self.custumer.email, "updated@example.com")
        self.assertEqual(self.custumer.phone, "+9988888888")

    def test_sync_custumer_to_customuser(self):
        """Тест синхронизации из Custumer в CustomUser"""
        # Изменяем данные профиля клиента
        self.custumer.full_name = "Updated Custumer Name"
        self.custumer.email = "updated_custumer@example.com"
        self.custumer.phone = "+9987777777"
        self.custumer.save()

        # Обновляем объект из базы
        self.user.refresh_from_db()

        # Проверяем, что данные синхронизировались
        self.assertEqual(self.user.first_name, "Updated Custumer Name")
        self.assertEqual(self.user.email, "updated_custumer@example.com")
        self.assertEqual(self.user.phone, "+9987777777")
        self.assertEqual(self.user.username, "updated_custumer@example.com")


class SubscriptionStatusTest(TestCase):
    """Тест обновления статуса абонемента при изменении платежей"""

    def setUp(self):
        """Подготовка тестовых данных"""
        # Создаем компанию
        self.company = Company.objects.create(name="Test Company")

        # Создаем пользователя
        self.user = CustomUser.objects.create(
            username="test@example.com",
            email="test@example.com",
            first_name="Test User",
            phone="+9989999999",
            company=self.company,
        )

        # Создаем профиль клиента
        self.custumer = Custumer.objects.create(
            user=self.user,
            full_name="Test User",
            phone="+9989999999",
            email="test@example.com",
            company=self.company,
        )

        # Создаем кассу
        self.cashier = Cashier.objects.create(
            name="Test Cashier",
            company=self.company,
            owner=self.user,
        )

        # Создаем абонемент
        self.subscription = CustumerSubscription.objects.create(
            custumer=self.custumer,
            total_cost=1000,  # Стоимость абонемента 1000
            attendance_status="unpaid",  # Изначально неоплачен
            company=self.company,
            owner=self.user,
        )

    def test_subscription_status_update_on_payment_create(self):
        """Тест обновления статуса абонемента при создании платежа"""
        # Создаем платеж на полную сумму
        CustumerSubscriptonPayment.objects.create(
            custumer=self.custumer,
            subscription=self.subscription,
            summ=1000,  # Полная сумма абонемента
            cashier=self.cashier,
            company=self.company,
            owner=self.user,
        )

        # Обновляем объект из базы
        self.subscription.refresh_from_db()

        # Проверяем, что статус изменился на "оплачен"
        self.assertEqual(self.subscription.attendance_status, "paid")

    def test_subscription_status_update_on_partial_payment(self):
        """Тест обновления статуса абонемента при частичной оплате"""
        # Создаем платеж на частичную сумму
        CustumerSubscriptonPayment.objects.create(
            custumer=self.custumer,
            subscription=self.subscription,
            summ=500,  # Частичная сумма
            cashier=self.cashier,
            company=self.company,
            owner=self.user,
        )

        # Обновляем объект из базы
        self.subscription.refresh_from_db()

        # Проверяем, что статус остался "неоплачен"
        self.assertEqual(self.subscription.attendance_status, "unpaid")

    def test_subscription_status_update_on_payment_update(self):
        """Тест обновления статуса абонемента при изменении платежа"""
        # Создаем платеж на частичную сумму
        payment = CustumerSubscriptonPayment.objects.create(
            custumer=self.custumer,
            subscription=self.subscription,
            summ=500,  # Частичная сумма
            cashier=self.cashier,
            company=self.company,
            owner=self.user,
        )

        # Обновляем объект из базы
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.attendance_status, "unpaid")

        # Обновляем платеж на полную сумму
        payment.summ = 1000
        payment.save()

        # Обновляем объект из базы
        self.subscription.refresh_from_db()

        # Проверяем, что статус изменился на "оплачен"
        self.assertEqual(self.subscription.attendance_status, "paid")

    def test_subscription_status_update_on_payment_delete(self):
        """Тест обновления статуса абонемента при удалении платежа"""
        # Создаем платеж на полную сумму
        payment = CustumerSubscriptonPayment.objects.create(
            custumer=self.custumer,
            subscription=self.subscription,
            summ=1000,  # Полная сумма
            cashier=self.cashier,
            company=self.company,
            owner=self.user,
        )

        # Обновляем объект из базы
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.attendance_status, "paid")

        # Удаляем платеж
        payment.delete()

        # Обновляем объект из базы
        self.subscription.refresh_from_db()

        # Проверяем, что статус изменился на "неоплачен"
        self.assertEqual(self.subscription.attendance_status, "unpaid")
