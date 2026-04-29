from datetime import time, timedelta

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from authen.models import Company, CustomUser, Gender
from competitions.models import Competitions, CustumerCompetitionResult
from competitions.schemas import StatusTextChoices as CompetitionStatus
from custumer.models import Custumer, CustumerSubscription
from custumer.services.home import (
    get_active_subscriptions_data,
    get_customer_with_relations,
    get_distance_summary,
    get_group_ratings_data,
    get_news_data,
    get_team_members_data,
    get_trainings_today_data,
)
from employe.models import Employe
from groups_custumer.models import (
    GroupClasses,
    GroupClassessCustumer,
    GroupsClass,
)
from news.models import News
from news.schemas import StatusTextChoices


class CustomerHomeServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Test Company")
        self.owner = CustomUser.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="owner-pass",
            company=self.company,
        )
        self.client_group, _ = Group.objects.get_or_create(name="client")

        self.customer_user = CustomUser.objects.create_user(
            username="client",
            email="client@example.com",
            password="client-pass",
            company=self.company,
        )
        self.customer_user.groups.add(self.client_group)

        self.customer = Custumer.objects.create(
            user=self.customer_user,
            full_name="Client One",
            company=self.company,
            owner=self.owner,
        )

        self.second_user = CustomUser.objects.create_user(
            username="teammate",
            email="teammate@example.com",
            password="mate-pass",
            company=self.company,
        )
        self.second_user.groups.add(self.client_group)
        self.second_customer = Custumer.objects.create(
            user=self.second_user,
            full_name="Client Two",
            company=self.company,
            owner=self.owner,
        )

        gender = Gender.objects.create(name="Мужской")
        self.coach = Employe.objects.create(
            full_name="Coach One",
            gender=gender,
            company=self.company,
            owner=self.owner,
        )

        self.group = GroupsClass.objects.create(
            name="Group A", company=self.company, owner_id=self.owner
        )
        self.customer.groups.add(self.group)
        self.second_customer.groups.add(self.group)

        today = timezone.now().date()
        self.today = today
        self.training = GroupClasses.objects.create(
            groups_id=self.group,
            name="Morning Swim",
            date=today,
            strat=time(10, 0),
            end=time(11, 0),
            employe=self.coach,
            company=self.company,
            owner=self.owner,
        )

        GroupClassessCustumer.objects.create(
            gr_class=self.training,
            custumer=self.customer,
            date=today,
            attendance_status="attended_5",
            company=self.company,
            owner=self.owner,
        )
        GroupClassessCustumer.objects.create(
            gr_class=self.training,
            custumer=self.second_customer,
            date=today,
            attendance_status="attended_3",
            company=self.company,
            owner=self.owner,
        )

        self.subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=10,
            remained=5,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=5),
            company=self.company,
            owner=self.owner,
        )
        self.subscription.groups.add(self.group)

        self.news = News.objects.create(
            owner=self.owner,
            title="Новость дня",
            descriptions="Описание новости",
            status=StatusTextChoices.PUBLISHED,
        )

        competition = Competitions.objects.create(
            name="Indoor Cup",
            location="Pool",
            date=today,
            owner=self.owner,
            status=CompetitionStatus.OPEN,
        )
        CustumerCompetitionResult.objects.create(
            competition=competition,
            customer=self.customer,
            distance=1000,
            result_time_ms=60000,
        )

        self.client.force_login(self.customer_user)

    def test_get_customer_with_relations(self):
        customer = get_customer_with_relations(self.customer_user)
        self.assertIsNotNone(customer)
        self.assertEqual(customer.id, self.customer.id)

    def test_get_trainings_today_data(self):
        data = get_trainings_today_data(self.customer, date=self.today)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Morning Swim")

    def test_get_active_subscriptions_data(self):
        data = get_active_subscriptions_data(self.customer, date=self.today)
        self.assertEqual(len(data), 1)
        payload = data[0]
        self.assertEqual(payload["id"], self.subscription.id)
        self.assertAlmostEqual(payload["percent_used"], 50.0)

    def test_get_group_ratings_data(self):
        result = get_group_ratings_data(self.customer)
        self.assertTrue(result["groups"])
        self.assertEqual(result["best_group"]["id"], self.group.id)
        self.assertEqual(result["groups"][0]["total"], 2)

    def test_get_team_members_data(self):
        result = get_team_members_data(self.customer)
        self.assertEqual(result["team_total"], 2)
        self.assertEqual(len(result["members"]), 2)
        self.assertGreater(result["team_avg"], 0)

    def test_get_news_data(self):
        news = get_news_data(self.customer)
        self.assertEqual(len(news), 1)
        self.assertEqual(news[0]["title"], "Новость дня")

    def test_get_distance_summary(self):
        summary = get_distance_summary(self.customer, date=self.today)
        self.assertGreater(summary.week, 0)
        self.assertGreater(summary.year, 0)

    def test_home_trainings_endpoint(self):
        response = self.client.get(reverse("customer:home_trainings"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["trainings"]), 1)

    def test_home_subscriptions_endpoint(self):
        response = self.client.get(reverse("customer:home_subscriptions"))
        self.assertEqual(response.status_code, 200)
        data = response.json()["subscriptions"][0]
        self.assertEqual(data["id"], self.subscription.id)

    def test_home_group_ratings_endpoint(self):
        response = self.client.get(reverse("customer:home_group_ratings"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["groups"])
        self.assertEqual(body["best_group"]["id"], self.group.id)

    def test_home_team_members_endpoint(self):
        response = self.client.get(reverse("customer:home_team_members"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["team_total"], 2)
        self.assertEqual(len(data["members"]), 2)

    def test_home_distances_endpoint(self):
        response = self.client.get(reverse("customer:home_distances"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["week"], 0)
        self.assertGreater(data["year"], 0)
