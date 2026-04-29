"""
Тесты логики работы с абонементами
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from authen.models import Gender
from custumer.models import (
    Company,
    Custumer,
    CustumerSubscription,
)
from custumer.payment.services import process_subscription_payment
from employe.models import Employe
from groups_custumer.models import (
    GroupClasses,
    GroupClassessCustumer,
    GroupsClass,
)

User = get_user_model()


class SubscriptionDateValidationTests(TestCase):
    """Тесты проверки дат абонемента"""

    def setUp(self):
        self.user = User.objects.create_user(username="test", password="test")
        self.company = Company.objects.create(name="Test Company")
        self.customer = Custumer.objects.create(
            full_name="Test Customer", company=self.company, owner=self.user
        )
        self.group = GroupsClass.objects.create(
            name="Test Group", company=self.company, owner_id=self.user
        )
        self.gender = Gender.objects.create(name="Male")
        self.employe = Employe.objects.create(
            full_name="Test Employe",
            gender=self.gender,
            company=self.company,
            owner=self.user,
        )

    def test_cannot_use_subscription_before_start_date(self):
        """Нельзя списать посещение до начала абонемента"""
        # Абонемент с 10 января
        subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=10,
            start_date=date(2024, 1, 10),
            end_date=date(2024, 1, 31),
            unlimited=False,
            total_cost=1000,
            attendance_status="paid",
            company=self.company,
            owner=self.user,
        )
        subscription.groups.add(self.group)

        # Создаем занятие 5 января (до начала абонемента)
        gr_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2024, 1, 5),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )
        attendance = GroupClassessCustumer.objects.create(
            custumer=self.customer,
            gr_class=gr_class,
            date=date(2024, 1, 5),
            attendance_status="attended_5",
            company=self.company,
            owner=self.user,
        )

        # Попытка списать с абонемента
        with self.assertRaises(ValueError) as context:
            process_subscription_payment(
                customer=self.customer,
                group=self.group,
                attendance_ids=[attendance.id],
                subscription_id=subscription.id,
            )

        self.assertIn("не входят в период", str(context.exception))

    def test_cannot_use_subscription_after_end_date(self):
        """Нельзя списать посещение после окончания абонемента"""
        # Абонемент до 31 января
        subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=10,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            unlimited=False,
            total_cost=1000,
            attendance_status="paid",
            company=self.company,
            owner=self.user,
        )
        subscription.groups.add(self.group)

        # Создаем занятие 5 февраля (после окончания)
        gr_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2024, 2, 5),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )
        attendance = GroupClassessCustumer.objects.create(
            custumer=self.customer,
            gr_class=gr_class,
            date=date(2024, 2, 5),
            attendance_status="attended_5",
            company=self.company,
            owner=self.user,
        )

        # Попытка списать с абонемента
        with self.assertRaises(ValueError) as context:
            process_subscription_payment(
                customer=self.customer,
                group=self.group,
                attendance_ids=[attendance.id],
                subscription_id=subscription.id,
            )

        self.assertIn("не входят в период", str(context.exception))

    def test_can_use_subscription_within_dates(self):
        """Можно списать посещение в период действия абонемента"""
        subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=10,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            unlimited=False,
            total_cost=1000,
            attendance_status="paid",
            company=self.company,
            owner=self.user,
        )
        subscription.groups.add(self.group)

        # Создаем занятие внутри периода
        gr_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2024, 1, 15),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )
        attendance = GroupClassessCustumer.objects.create(
            custumer=self.customer,
            gr_class=gr_class,
            date=date(2024, 1, 15),
            attendance_status="attended_5",
            company=self.company,
            owner=self.user,
        )

        # Списываем с абонемента
        result = process_subscription_payment(
            customer=self.customer,
            group=self.group,
            attendance_ids=[attendance.id],
            subscription_id=subscription.id,
        )

        self.assertTrue(result["success"])
        attendance.refresh_from_db()
        self.assertEqual(attendance.used_subscription, subscription)
        self.assertTrue(attendance.is_block)


class SubscriptionRemainedTests(TestCase):
    """Тесты обновления remained с NULL значениями"""

    def setUp(self):
        self.user = User.objects.create_user(username="test", password="test")
        self.company = Company.objects.create(name="Test Company")
        self.customer = Custumer.objects.create(
            full_name="Test Customer", company=self.company, owner=self.user
        )
        self.group = GroupsClass.objects.create(
            name="Test Group", company=self.company, owner_id=self.user
        )
        self.gender = Gender.objects.create(name="Male")
        self.employe = Employe.objects.create(
            full_name="Test Employe",
            gender=self.gender,
            company=self.company,
            owner=self.user,
        )

    def test_remained_null_becomes_zero(self):
        """remained=NULL при инкременте становится 0+N"""
        subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=10,
            remained=None,  # NULL
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            unlimited=False,
            total_cost=1000,
            attendance_status="paid",
            company=self.company,
            owner=self.user,
        )
        subscription.groups.add(self.group)

        gr_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2024, 1, 15),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )
        attendance = GroupClassessCustumer.objects.create(
            custumer=self.customer,
            gr_class=gr_class,
            date=date(2024, 1, 15),
            attendance_status="attended_5",
            company=self.company,
            owner=self.user,
        )

        # Списываем 1 посещение
        process_subscription_payment(
            customer=self.customer,
            group=self.group,
            attendance_ids=[attendance.id],
            subscription_id=subscription.id,
        )

        subscription.refresh_from_db()
        # remained должно стать 1 (0 + 1), а не NULL
        self.assertEqual(subscription.remained, 1)


class SubscriptionPaymentProcessingTests(TestCase):
    """Тесты процесса оплаты абонементом"""

    def setUp(self):
        self.user = User.objects.create_user(username="test", password="test")
        self.company = Company.objects.create(
            name="Test Company",
        )
        self.customer = Custumer.objects.create(
            full_name="Test Customer", company=self.company, owner=self.user
        )
        self.group = GroupsClass.objects.create(
            name="Test Group", company=self.company, owner_id=self.user
        )
        self.gender = Gender.objects.create(name="Male")
        self.employe = Employe.objects.create(
            full_name="Test Employe",
            gender=self.gender,
            company=self.company,
            owner=self.user,
        )

    def test_process_subscription_payment_success(self):
        """Успешное списание с абонемента"""
        subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=10,
            remained=0,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            unlimited=False,
            total_cost=1000,
            attendance_status="paid",
            company=self.company,
            owner=self.user,
        )
        subscription.groups.add(self.group)

        gr_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2024, 1, 15),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )
        attendance = GroupClassessCustumer.objects.create(
            custumer=self.customer,
            gr_class=gr_class,
            date=date(2024, 1, 15),
            attendance_status="attended_5",
            company=self.company,
            owner=self.user,
        )

        result = process_subscription_payment(
            customer=self.customer,
            group=self.group,
            attendance_ids=[attendance.id],
            subscription_id=subscription.id,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["attendances_count"], 1)

        subscription.refresh_from_db()
        self.assertEqual(subscription.remained, 1)

    def test_process_subscription_payment_insufficient(self):
        """Недостаточно занятий в абонементе"""
        subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=2,
            remained=1,  # Осталось только 1 занятие
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            unlimited=False,
            total_cost=1000,
            attendance_status="paid",
            company=self.company,
            owner=self.user,
        )
        subscription.groups.add(self.group)

        # Создаем 2 посещения
        attendances = []
        for day in [15, 16]:
            gr_class = GroupClasses.objects.create(
                groups_id=self.group,
                date=date(2024, 1, day),
                strat="10:00:00",
                end="11:00:00",
                employe=self.employe,
                company=self.company,
                owner=self.user,
            )
            att = GroupClassessCustumer.objects.create(
                custumer=self.customer,
                gr_class=gr_class,
                date=date(2024, 1, day),
                attendance_status="attended_5",
                company=self.company,
                owner=self.user,
            )
            attendances.append(att)

        # Пытаемся списать 2, хотя осталось только 1
        with self.assertRaises(ValueError) as context:
            process_subscription_payment(
                customer=self.customer,
                group=self.group,
                attendance_ids=[a.id for a in attendances],
                subscription_id=subscription.id,
            )

        self.assertIn("Недостаточно занятий", str(context.exception))

    def test_process_subscription_payment_blocks_attendance(self):
        """Посещение блокируется после списания"""
        subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=10,
            remained=0,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            unlimited=False,
            total_cost=1000,
            attendance_status="paid",
            company=self.company,
            owner=self.user,
        )
        subscription.groups.add(self.group)

        gr_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2024, 1, 15),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )
        attendance = GroupClassessCustumer.objects.create(
            custumer=self.customer,
            gr_class=gr_class,
            date=date(2024, 1, 15),
            attendance_status="attended_5",
            is_block=False,
            company=self.company,
            owner=self.user,
        )

        process_subscription_payment(
            customer=self.customer,
            group=self.group,
            attendance_ids=[attendance.id],
            subscription_id=subscription.id,
        )

        attendance.refresh_from_db()
        self.assertTrue(attendance.is_block)
        self.assertEqual(attendance.used_subscription, subscription)


class SubscriptionAutoBindTests(TestCase):
    """Тесты автоматической привязки посещений при создании абонемента"""

    def setUp(self):
        self.user = User.objects.create_user(username="test", password="test")
        self.company = Company.objects.create(name="Test Company")
        self.customer = Custumer.objects.create(
            full_name="Test Customer", company=self.company, owner=self.user
        )
        self.group = GroupsClass.objects.create(
            name="Test Group", company=self.company, owner_id=self.user
        )
        self.gender = Gender.objects.create(name="Male")
        self.employe = Employe.objects.create(
            full_name="Test Employe",
            gender=self.gender,
            company=self.company,
            owner=self.user,
        )

    def test_auto_bind_flag_in_form_data(self):
        """Проверка, что флаг auto_bind_attendances корректно обрабатывается"""
        from django.test import RequestFactory

        from custumer.subscription.services import (
            prepare_subscription_form_context,
        )

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user

        # Создаем контекст формы с флагом
        context = prepare_subscription_form_context(
            request=request,
            custumer=self.customer,
            groups_qs=GroupsClass.objects.filter(company=self.company),
            allow_group_selection=True,
            cancel_url="/cancel",
            form_data={"auto_bind_attendances": True},
        )

        # Проверяем, что флаг присутствует в контексте
        self.assertIn("form_data", context)
        self.assertTrue(context["form_data"]["auto_bind_attendances"])


class SubscriptionDeletionTests(TestCase):
    """Тесты удаления абонемента и корректной обработки связанных посещений"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="test_del", password="test"
        )
        self.user.groups.create(name="admin")
        self.company = Company.objects.create(name="Test Company")
        self.customer = Custumer.objects.create(
            full_name="Test Customer", company=self.company, owner=self.user
        )
        self.group = GroupsClass.objects.create(
            name="Test Group", company=self.company, owner_id=self.user
        )
        self.gender = Gender.objects.create(name="Male")
        self.employe = Employe.objects.create(
            full_name="Test Employe",
            gender=self.gender,
            company=self.company,
            owner=self.user,
        )

    def test_delete_subscription_resets_attendances_correctly(self):
        """
        При удалении абонемента посещения должны стать неоплаченными,
        а НЕ оплаченными наличными
        """
        # Создаем оплаченный абонемент
        subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=10,
            remained=0,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            unlimited=False,
            total_cost=1000,
            attendance_status="paid",
            company=self.company,
            owner=self.user,
        )
        subscription.groups.add(self.group)

        # Создаем посещение, списанное с абонемента
        gr_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2024, 1, 15),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )
        attendance = GroupClassessCustumer.objects.create(
            custumer=self.customer,
            gr_class=gr_class,
            date=date(2024, 1, 15),
            attendance_status="attended_5",
            used_subscription=subscription,
            is_block=True,  # Списано с абонемента
            company=self.company,
            owner=self.user,
        )

        # Проверяем начальное состояние
        self.assertTrue(attendance.is_block)
        self.assertEqual(attendance.used_subscription, subscription)
        self.assertEqual(
            attendance.payment_status_display, "Оплачено (абонемент)"
        )

        # Удаляем абонемент
        subscription.delete()

        # Обновляем данные посещения из БД
        attendance.refresh_from_db()

        # КРИТИЧНО: После удаления абонемента посещение должно быть:
        # 1. НЕ заблокировано (is_block=False)
        self.assertFalse(
            attendance.is_block,
            "Посещение должно быть разблокировано после удаления абонемента",
        )

        # 2. Без привязки к абонементу (used_subscription=None)
        self.assertIsNone(
            attendance.used_subscription,
            "Посещение не должно быть привязано к абонементу",
        )

        # 3. Статус должен быть "Не оплачено", а НЕ "Оплачено наличными"
        self.assertEqual(
            attendance.payment_status_display,
            "Не оплачено",
            "Посещение должно быть неоплаченным, а не оплаченным наличными",
        )

        # 4. Проверяем, что посещение можно теперь оплатить
        # (не заблокировано для оплаты)
        self.assertFalse(
            attendance.is_payment_blocked,
            "Посещение должно быть доступно для оплаты",
        )


class PaymentStatusFourStatesTests(TestCase):
    """Тесты 4 состояний оплаты посещений"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="test_states", password="test"
        )
        self.user.groups.create(name="admin")
        self.company = Company.objects.create(name="Test Company")
        self.customer = Custumer.objects.create(
            full_name="Test Customer", company=self.company, owner=self.user
        )
        self.group = GroupsClass.objects.create(
            name="Test Group", company=self.company, owner_id=self.user
        )
        self.gender = Gender.objects.create(name="Male")
        self.employe = Employe.objects.create(
            full_name="Test Employe",
            gender=self.gender,
            company=self.company,
            owner=self.user,
        )

    def test_state_1_unpaid(self):
        """Состояние 1: Не оплачено"""
        gr_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2024, 1, 15),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )
        attendance = GroupClassessCustumer.objects.create(
            custumer=self.customer,
            gr_class=gr_class,
            date=date(2024, 1, 15),
            attendance_status="attended_5",
            is_block=False,
            used_subscription=None,
            company=self.company,
            owner=self.user,
        )

        self.assertEqual(attendance.payment_status_display, "Не оплачено")
        self.assertFalse(attendance.is_payment_blocked)
        self.assertFalse(attendance.is_block)

    def test_state_2_paid_cash(self):
        """Состояние 2: Оплачено наличными"""
        from custumer.models import CustumerSubscriptonPayment

        gr_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2024, 1, 15),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )
        attendance = GroupClassessCustumer.objects.create(
            custumer=self.customer,
            gr_class=gr_class,
            date=date(2024, 1, 15),
            attendance_status="attended_5",
            is_block=True,
            used_subscription=None,
            company=self.company,
            owner=self.user,
        )

        # Создаем запись об оплате наличными
        CustumerSubscriptonPayment.objects.create(
            custumer=self.customer,
            groups=self.group,
            sub_date=date(2024, 1, 15),
            subscription=None,
            summ=100,
            is_pay=True,
            company=self.company,
            owner=self.user,
        )

        self.assertEqual(
            attendance.payment_status_display, "Оплачено наличными"
        )
        self.assertFalse(attendance.is_payment_blocked)
        self.assertTrue(attendance.is_block)

    def test_state_3_forgiven(self):
        """Состояние 3: Прощено"""
        from custumer.models import CustumerSubscriptonPayment

        gr_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2024, 1, 15),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )
        attendance = GroupClassessCustumer.objects.create(
            custumer=self.customer,
            gr_class=gr_class,
            date=date(2024, 1, 15),
            attendance_status="attended_5",
            is_block=True,
            used_subscription=None,
            company=self.company,
            owner=self.user,
        )

        # Создаем запись о прощении (summ=0) с привязкой к посещению
        CustumerSubscriptonPayment.objects.create(
            custumer=self.customer,
            groups=self.group,
            attendance_record=attendance,  # ✅ Привязка к посещению
            sub_date=date(2024, 1, 15),
            subscription=None,
            summ=0,
            is_pay=True,
            company=self.company,
            owner=self.user,
        )

        # Перезагружаем объект с правильным запросом для получения связи
        attendance = GroupClassessCustumer.objects.select_related(
            "payment_record"
        ).get(id=attendance.id)
        self.assertEqual(attendance.payment_status_display, "Прощено")
        self.assertFalse(attendance.is_payment_blocked)
        self.assertTrue(attendance.is_block)

    def test_state_4_subscription_paid(self):
        """Состояние 4a: Оплачено абонементом"""
        subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=10,
            remained=1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            unlimited=False,
            total_cost=1000,
            attendance_status="paid",
            company=self.company,
            owner=self.user,
        )
        subscription.groups.add(self.group)

        gr_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2024, 1, 15),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )
        attendance = GroupClassessCustumer.objects.create(
            custumer=self.customer,
            gr_class=gr_class,
            date=date(2024, 1, 15),
            attendance_status="attended_5",
            is_block=True,
            used_subscription=subscription,
            company=self.company,
            owner=self.user,
        )

        self.assertEqual(
            attendance.payment_status_display, "Оплачено (абонемент)"
        )
        self.assertTrue(attendance.is_payment_blocked)
        self.assertTrue(attendance.is_block)

    def test_state_4_subscription_unpaid(self):
        """Состояние 4b: Списано с неоплаченного абонемента"""
        subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=10,
            remained=1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            unlimited=False,
            total_cost=1000,
            attendance_status="unpaid",
            company=self.company,
            owner=self.user,
        )
        subscription.groups.add(self.group)

        gr_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2024, 1, 15),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )
        attendance = GroupClassessCustumer.objects.create(
            custumer=self.customer,
            gr_class=gr_class,
            date=date(2024, 1, 15),
            attendance_status="attended_5",
            is_block=True,
            used_subscription=subscription,
            company=self.company,
            owner=self.user,
        )

        self.assertEqual(
            attendance.payment_status_display,
            "Списано с неоплаченного абонемента",
        )
        self.assertTrue(attendance.is_payment_blocked)
        self.assertTrue(attendance.is_block)

    def test_forgive_attendances_function(self):
        """Тест функции прощения посещений"""
        from custumer.payment.services import forgive_attendances

        gr_class = GroupClasses.objects.create(
            groups_id=self.group,
            date=date(2024, 1, 15),
            strat="10:00:00",
            end="11:00:00",
            employe=self.employe,
            company=self.company,
            owner=self.user,
        )
        attendance = GroupClassessCustumer.objects.create(
            custumer=self.customer,
            gr_class=gr_class,
            date=date(2024, 1, 15),
            attendance_status="attended_5",
            is_block=False,
            company=self.company,
            owner=self.user,
        )

        # Прощаем посещение
        result = forgive_attendances(
            customer=self.customer,
            group=self.group,
            attendance_ids=[attendance.id],
            company=self.company,
            owner=self.user,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["attendances_count"], 1)

        attendance.refresh_from_db()
        self.assertTrue(attendance.is_block)
        self.assertIsNone(attendance.used_subscription)
        self.assertEqual(attendance.payment_status_display, "Прощено")
