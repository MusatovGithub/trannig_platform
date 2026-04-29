from django.core.exceptions import ValidationError
from django.test import TestCase

from authen.models import Company, CustomUser, Gender
from custumer.models import Custumer, SportCategory
from custumer.services.customer import create_customer, update_customer
from groups_custumer.models import GroupsClass


class CustomerServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Test Company")
        self.owner = CustomUser.objects.create_user(
            username="owner", password="pass", company=self.company
        )
        self.gender = Gender.objects.create(name="Мужской")
        self.sport_category = SportCategory.objects.create(name="МС")
        self.group = GroupsClass.objects.create(
            name="Group A", company=self.company, owner_id=self.owner
        )

    def test_create_customer_assigns_groups(self):
        payload = {
            "full_name": "John Doe",
            "phone": "+1234567890",
            "gender": str(self.gender.id),
            "birth_date": "2024-01-01",
            "address": "Street 1",
            "contract_number": "CN-1",
            "contract_type": "paid",
            "start_date": "2024-01-05",
            "group_ids": [str(self.group.id)],
            "sport_rank": str(self.sport_category.id),
        }

        result = create_customer(owner=self.owner, data=payload, photo=None)

        self.assertIsInstance(result.customer, Custumer)
        self.assertEqual(result.customer.full_name, "John Doe")
        self.assertListEqual(result.group_ids, [self.group.id])

    def test_update_customer_refreshes_fields(self):
        customer = Custumer.objects.create(
            full_name="Old Name", company=self.company, owner=self.owner
        )
        payload = {
            "full_name": "Jane Smith",
            "phone": "+1987654321",
            "gender": str(self.gender.id),
            "birth_date": "2024-02-01",
            "address": "Updated Street",
            "contract_number": "CN-2",
            "contract_type": "free",
            "start_date": "2024-02-10",
            "group_ids": [str(self.group.id)],
            "sport_rank": str(self.sport_category.id),
        }

        result = update_customer(
            customer=customer, owner=self.owner, data=payload, photo=None
        )

        customer.refresh_from_db()
        self.assertEqual(result.customer.id, customer.id)
        self.assertEqual(customer.full_name, "Jane Smith")
        self.assertListEqual(result.group_ids, [self.group.id])

    def test_invalid_date_raises_validation_error(self):
        payload = {
            "full_name": "Broken Date",
            "birth_date": "invalid-date",
            "group_ids": [],
        }

        with self.assertRaises(ValidationError):
            create_customer(owner=self.owner, data=payload, photo=None)
