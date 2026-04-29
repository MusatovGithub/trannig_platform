from unittest import mock

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from authen.models import Company, CustomUser, Gender
from custumer.models import Custumer, SportCategory
from groups_custumer.models import GroupsClass


class CustomerViewsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Company")
        self.user = CustomUser.objects.create_user(
            username="admin", password="pass", company=self.company
        )
        admin_group, _ = Group.objects.get_or_create(name="admin")
        self.user.groups.add(admin_group)

        self.gender = Gender.objects.create(name="Мужской")
        self.sport_category = SportCategory.objects.create(name="МС")
        self.group = GroupsClass.objects.create(
            name="Group X", company=self.company, owner_id=self.user
        )

        self.client.force_login(self.user)

    def test_customer_create_registers_on_commit_callback(self):
        callbacks = []

        def capture_callback(func):
            callbacks.append(func)

        with (
            mock.patch(
                "custumer.views.transaction.on_commit",
                side_effect=capture_callback,
            ) as on_commit_mock,
            mock.patch(
                "custumer.views.sync_customer_attendances.delay"
            ) as delay_mock,
        ):
            response = self.client.post(
                reverse("customer:customer_create"),
                {
                    "full_name": "New Client",
                    "phone": "+10000000000",
                    "gender": str(self.gender.id),
                    "birth_date": "2024-01-01",
                    "address": "Street",
                    "contract_number": "C-1",
                    "contract_type": "paid",
                    "start_date": "2024-01-10",
                    "group": [str(self.group.id)],
                    "sport_rank": str(self.sport_category.id),
                },
            )

            self.assertEqual(response.status_code, 302)
            self.assertTrue(on_commit_mock.called)
            self.assertEqual(len(callbacks), 1)

            created_customer = Custumer.objects.get(full_name="New Client")
            callbacks[0]()
            delay_mock.assert_called_once_with(created_customer.id)

    def test_customer_update_registers_on_commit_callback(self):
        customer = Custumer.objects.create(
            full_name="Existing",
            company=self.company,
            owner=self.user,
        )

        callbacks = []

        def capture_callback(func):
            callbacks.append(func)

        with (
            mock.patch(
                "custumer.views.transaction.on_commit",
                side_effect=capture_callback,
            ),
            mock.patch(
                "custumer.views.sync_customer_attendances.delay"
            ) as delay_mock,
        ):
            response = self.client.post(
                reverse("customer:custumer_update", args=[customer.id]),
                {
                    "full_name": "Updated Name",
                    "phone": "+19999999999",
                    "gender": str(self.gender.id),
                    "birth_date": "2024-03-01",
                    "address": "New Street",
                    "contract_number": "C-2",
                    "contract_type": "free",
                    "start_date": "2024-03-05",
                    "group": [str(self.group.id)],
                    "sport_rank": str(self.sport_category.id),
                },
            )

            self.assertEqual(response.status_code, 302)
            self.assertEqual(len(callbacks), 1)

            callbacks[0]()
            delay_mock.assert_called_once_with(customer.id)
            customer.refresh_from_db()
            self.assertEqual(customer.full_name, "Updated Name")
