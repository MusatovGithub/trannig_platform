from datetime import date

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from authen.models import Company, CustomUser
from custumer.models import (
    Cashier,
    Custumer,
    CustumerSubscription,
    CustumerSubscriptonPayment,
)
from groups_custumer.models import GroupsClass


class SubscriptionCreationViewTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Test Company")
        self.admin_group = Group.objects.create(name="admin")
        self.assistant_group = Group.objects.create(name="assistant")

        self.admin_user = CustomUser.objects.create_user(
            username="admin",
            password="admin-pass",
            email="admin@example.com",
            company=self.company,
        )
        self.admin_user.groups.add(self.admin_group)

        self.customer = Custumer.objects.create(
            full_name="Test Customer",
            company=self.company,
            owner=self.admin_user,
        )
        self.group = GroupsClass.objects.create(
            name="Group A", company=self.company, owner_id=self.admin_user
        )
        self.cashier = Cashier.objects.create(
            name="Main cashier", company=self.company, owner=self.admin_user
        )

        self.client.force_login(self.admin_user)

    def _post_customer_subscription(self, customer, payload):
        url = reverse(
            "customer:custumer_subscriptions_add",
            args=[customer.id],
        )
        return url, self.client.post(url, payload)

    def test_customer_subscription_create_success(self):
        payload = {
            "group": [str(self.group.id)],
            "number": "10",
            "start_date": "01.01.2025",
            "end_date": "31.01.2025",
            "price": "1000",
            "summ": "1000",
            "cashier": str(self.cashier.id),
            "date_summ": "01.01.2025",
        }

        _, response = self._post_customer_subscription(self.customer, payload)

        self.assertRedirects(
            response,
            reverse(
                "customer:custumer_subscriptions", args=[self.customer.id]
            ),
        )

        subscription = CustumerSubscription.objects.get(custumer=self.customer)
        self.assertEqual(subscription.total_cost, 1000)
        self.assertEqual(subscription.attendance_status, "paid")
        self.assertEqual(subscription.groups.count(), 1)
        self.assertEqual(subscription.groups.first(), self.group)

        payments = CustumerSubscriptonPayment.objects.filter(
            subscription=subscription
        )
        self.assertEqual(payments.count(), 1)
        self.assertEqual(payments.first().summ, 1000)

    def test_customer_subscription_overlap_is_rejected(self):
        existing = CustumerSubscription.objects.create(
            custumer=self.customer,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            company=self.company,
            owner=self.admin_user,
            total_cost=1000,
        )
        existing.groups.add(self.group)

        payload = {
            "group": [str(self.group.id)],
            "start_date": "15.01.2025",
            "end_date": "15.02.2025",
            "price": "1000",
            "summ": "500",
            "cashier": str(self.cashier.id),
        }

        _, response = self._post_customer_subscription(self.customer, payload)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "B этом диапазоне уже есть абонемент!",
            response.content.decode("utf-8"),
        )
        self.assertEqual(CustumerSubscription.objects.count(), 1)

    def test_customer_subscription_free_creates_no_payment(self):
        payload = {
            "group": [str(self.group.id)],
            "start_date": "01.03.2025",
            "end_date": "31.03.2025",
            "is_free": "on",
        }

        _, response = self._post_customer_subscription(self.customer, payload)

        self.assertRedirects(
            response,
            reverse(
                "customer:custumer_subscriptions", args=[self.customer.id]
            ),
        )

        subscription = CustumerSubscription.objects.get(custumer=self.customer)
        self.assertTrue(subscription.is_free)
        self.assertEqual(subscription.attendance_status, "none")
        self.assertEqual(subscription.payments.count(), 0)

    def test_group_subscription_create_success(self):
        another_customer = Custumer.objects.create(
            full_name="Another Customer",
            company=self.company,
            owner=self.admin_user,
        )

        url = reverse(
            "groups_custumer:group_subscription_create",
            args=[self.group.id, another_customer.id],
        )
        response = self.client.post(
            url,
            {
                "start_date": "01.04.2025",
                "end_date": "30.04.2025",
                "price": "500",
                "summ": "500",
                "cashier": str(self.cashier.id),
                "date_summ": "01.04.2025",
            },
        )

        self.assertRedirects(
            response,
            reverse("groups_custumer:groups_detail", args=[self.group.id]),
        )

        subscription = CustumerSubscription.objects.get(
            custumer=another_customer
        )
        self.assertEqual(subscription.groups.count(), 1)
        self.assertEqual(subscription.groups.first(), self.group)

    def test_subscription_creation_requires_permissions(self):
        self.client.logout()
        regular_user = CustomUser.objects.create_user(
            username="regular",
            password="regular-pass",
            email="regular@example.com",
            company=self.company,
        )
        self.client.force_login(regular_user)

        url = reverse(
            "customer:custumer_subscriptions_add",
            args=[self.customer.id],
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "page_404.html")
        self.assertEqual(CustumerSubscription.objects.count(), 0)
