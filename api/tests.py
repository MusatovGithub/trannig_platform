import json
from datetime import date, time, timedelta

from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from achievements.models import Achievement
from api.models import ApiToken
from authen.models import Company, CustomUser, Gender
from competitions.models import Competitions, CustumerCompetitionResult
from custumer.models import (
    Cashier,
    Custumer,
    CustumerDocs,
    CustumerRepresentatives,
    CustumerSubscription,
    CustumerSubscriptonPayment,
    SportCategory,
    TypeRepresentatives,
)
from employe.models import Employe
from groups_custumer.models import (
    GroupClasses,
    GroupClassessCustumer,
    GroupsClass,
)
from market.models import Order


class ApiCompetitionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Цунамис")
        self.user = CustomUser.objects.create_user(
            username="admin",
            password="pass",
            company=self.company,
        )
        admin_group, _ = Group.objects.get_or_create(name="admin")
        self.user.groups.add(admin_group)
        self.client_user = CustomUser.objects.create_user(
            username="client",
            password="pass",
            company=self.company,
        )

        self.customer = Custumer.objects.create(
            user=self.client_user,
            full_name="Фирсов Семён Антонович",
            phone="+79172120783",
            company=self.company,
            owner=self.user,
        )
        self.other_customer = Custumer.objects.create(
            full_name="Лохматов Михаил Кириллович",
            phone="+79271288142",
            company=self.company,
            owner=self.user,
        )
        self.rank = SportCategory.objects.create(name="3 разряд", level=4)
        self.gender = Gender.objects.create(name="Мужской")
        self.employee = Employe.objects.create(
            full_name="Тренер",
            gender=self.gender,
            company=self.company,
            owner=self.user,
        )
        self.group = GroupsClass.objects.create(
            name="Кракен",
            company=self.company,
            owner_id=self.user,
        )
        self.group.custumer_set.add(self.customer)
        self.group_class = GroupClasses.objects.create(
            groups_id=self.group,
            name="Техника",
            date=date(2026, 4, 28),
            strat=time(18, 30),
            end=time(19, 30),
            employe=self.employee,
            company=self.company,
            owner=self.user,
        )
        self.attendance = GroupClassessCustumer.objects.create(
            gr_class=self.group_class,
            custumer=self.customer,
            date=self.group_class.date,
            class_time=self.group_class.strat,
            attendance_status="none",
            company=self.company,
            owner=self.user,
        )
        self.subscription = CustumerSubscription.objects.create(
            custumer=self.customer,
            number_classes=12,
            remained=2,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 5, 1),
            attendance_status="paid",
            company=self.company,
            owner=self.user,
        )
        self.subscription.groups.add(self.group)
        self.achievement = Achievement.objects.create(
            name="Отличный старт",
            description="Первое место на соревнованиях",
            points=10,
            owner=self.user,
        )
        self.customer.achievements.add(self.achievement)
        self.document = CustumerDocs.objects.create(
            custumer=self.customer,
            name="Договор",
        )
        self.representative_type = TypeRepresentatives.objects.create(
            name="Родитель",
        )
        self.representative = CustumerRepresentatives.objects.create(
            custumer=self.customer,
            type=self.representative_type,
            full_name="Иванов Иван",
            phone="+79000000000",
        )
        self.payment = CustumerSubscriptonPayment.objects.create(
            custumer=self.customer,
            groups=self.group,
            subscription=self.subscription,
            summ=1000,
            summ_date=date(2026, 4, 2),
            is_pay=True,
            company=self.company,
            owner=self.user,
        )
        self.cashier = Cashier.objects.create(
            name="Основная касса",
            company=self.company,
            owner=self.user,
        )
        today = timezone.localdate()
        self.today_class = GroupClasses.objects.create(
            groups_id=self.group,
            name="Сегодняшняя тренировка",
            date=today,
            strat=time(17, 0),
            end=time(18, 0),
            employe=self.employee,
            company=self.company,
            owner=self.user,
        )
        self.expired_subscription = CustumerSubscription.objects.create(
            custumer=self.other_customer,
            number_classes=8,
            remained=8,
            start_date=today - timedelta(days=40),
            end_date=today - timedelta(days=1),
            attendance_status="paid",
            company=self.company,
            owner=self.user,
        )
        self.unpaid_attendance = GroupClassessCustumer.objects.create(
            gr_class=self.today_class,
            custumer=self.other_customer,
            date=today,
            class_time=self.today_class.strat,
            attendance_status="attended_5",
            company=self.company,
            owner=self.user,
        )
        self.order = Order.objects.create(
            customer=self.client_user,
            status="PENDING",
            total_amount=150,
        )
        self.competition = Competitions.objects.create(
            name="Весенние старты",
            location="Бассейн 25м",
            date="2026-04-26",
            owner=self.user,
        )
        self.competition.customers.add(self.customer)
        _, self.token = ApiToken.create_token(self.user, name="tests")
        self.client.force_login(self.user)
        self.token_client = Client(enforce_csrf_checks=True)

    def post_json(self, url, payload):
        return self.token_client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def put_json(self, url, payload):
        return self.token_client.put(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def test_login_returns_api_token(self):
        response = self.client.post(
            reverse("api:login_user"),
            data=json.dumps(
                {
                    "username": "admin",
                    "password": "pass",
                    "device_name": "iPhone",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        token = response.json()["token"]
        self.assertTrue(token)
        self.assertTrue(
            ApiToken.objects.filter(
                key_hash=ApiToken.hash_token(token),
                user=self.user,
                name="iPhone",
            ).exists()
        )

    def test_me_returns_current_user(self):
        response = self.client.get(reverse("api:me"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()["user"]
        self.assertEqual(payload["username"], "admin")
        self.assertEqual(payload["account_type"], "school")
        self.assertIn("Клиенты", payload["mobile_sections"])
        self.assertIn("Испытания", payload["mobile_sections"])
        self.assertIn("Мой профиль", payload["mobile_sections"])

    def test_me_returns_client_sections_for_client_account(self):
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("api:me"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()["user"]
        self.assertEqual(payload["account_type"], "client")
        self.assertEqual(
            payload["mobile_sections"],
            [
                "Главная",
                "Мои достижения",
                "Дневник",
                "Мои соревнования",
                "Испытания",
                "Магазин",
                "Мои покупки",
                "Мой профиль",
            ],
        )

    def test_customers_are_limited_to_user_company(self):
        other_company = Company.objects.create(name="Other")
        Custumer.objects.create(
            full_name="Hidden Customer",
            company=other_company,
        )

        response = self.client.get(reverse("api:customers"))

        self.assertEqual(response.status_code, 200)
        names = [item["full_name"] for item in response.json()["customers"]]
        self.assertIn("Фирсов Семён Антонович", names)
        self.assertNotIn("Hidden Customer", names)

    def test_add_competition_participant(self):
        url = reverse(
            "api:competition_participants",
            args=[self.competition.id],
        )

        response = self.post_json(url, {"customer_ids": [self.other_customer.id]})

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            self.competition.customers.filter(
                id=self.other_customer.id,
            ).exists()
        )

    def test_create_competition_result(self):
        url = reverse("api:create_result", args=[self.competition.id])

        response = self.post_json(
            url,
            {
                "customer_id": self.customer.id,
                "discipline": "Комплекс",
                "distance": 100,
                "style": "25m",
                "result_time": "01:15:380",
                "place": 1,
                "assign_rank": self.rank.id,
                "is_disqualified": False,
                "disqualification_comment": "",
            },
        )

        self.assertEqual(response.status_code, 201)
        result = CustumerCompetitionResult.objects.get()
        self.assertEqual(result.result_time_ms, 75380)
        self.assertEqual(result.sport_category, self.rank)

    def test_create_result_requires_participant(self):
        url = reverse("api:create_result", args=[self.competition.id])

        response = self.post_json(
            url,
            {
                "customer_id": self.other_customer.id,
                "discipline": "Комплекс",
                "distance": 100,
                "style": "25m",
                "result_time": "01:27:130",
                "place": 1,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(CustumerCompetitionResult.objects.count(), 0)

    def test_update_competition_result(self):
        result = CustumerCompetitionResult.objects.create(
            competition=self.competition,
            customer=self.customer,
            distance=50,
            discipline="Кроль",
            style="25m",
            result_time_ms=36030,
            place=1,
        )
        url = reverse("api:result_detail", args=[result.id])

        response = self.put_json(
            url,
            {
                "discipline": "Брасс",
                "distance": 50,
                "style": "25m",
                "result_time": "00:42:600",
                "place": 2,
                "assign_rank": 0,
                "is_disqualified": False,
                "disqualification_comment": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        result.refresh_from_db()
        self.assertEqual(result.discipline, "Брасс")
        self.assertEqual(result.result_time_ms, 42600)
        self.assertEqual(result.place, 2)

    def test_delete_competition_result(self):
        result = CustumerCompetitionResult.objects.create(
            competition=self.competition,
            customer=self.customer,
            distance=50,
            discipline="Кроль",
            style="25m",
            result_time_ms=36030,
            place=1,
        )
        url = reverse("api:result_detail", args=[result.id])

        response = self.token_client.delete(
            url,
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(CustumerCompetitionResult.objects.count(), 0)

    def test_coach_classes_returns_grade_cells(self):
        response = self.client.get(
            reverse("api:coach_classes"),
            {"date": "2026-04-28"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["date"], "2026-04-28")
        self.assertEqual(payload["classes"][0]["group"]["name"], "Кракен")
        self.assertEqual(
            payload["classes"][0]["attendances"][0]["display_text"],
            "+",
        )

    def test_coach_dashboard_returns_school_home_work_items(self):
        self.other_customer.birth_date = timezone.localdate()
        self.other_customer.save(update_fields=["birth_date"])

        response = self.client.get(reverse("api:coach_dashboard"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(
            payload["summary"]["today_classes_count"],
            1,
        )
        self.assertEqual(
            payload["expired_subscriptions"][0]["customer"]["full_name"],
            self.other_customer.full_name,
        )
        self.assertEqual(
            payload["unpaid_lessons"][0]["customer_name"],
            self.other_customer.full_name,
        )
        self.assertEqual(payload["pending_orders"][0]["id"], self.order.id)
        self.assertEqual(payload["summary"]["active_challenges_count"], 0)
        self.assertEqual(
            payload["birthdays_today"][0]["full_name"],
            self.other_customer.full_name,
        )
        self.assertEqual(
            payload["today_training_tasks"][0]["group"]["name"],
            self.group.name,
        )

    def test_coach_customer_detail_keeps_site_relations(self):
        response = self.client.get(
            reverse("api:coach_customer_detail", args=[self.customer.id]),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["links"]["subscriptions"],
            f"/customer/{self.customer.id}/subscriptions/",
        )
        self.assertEqual(payload["groups"][0]["name"], "Кракен")
        self.assertEqual(payload["subscriptions"][0]["id"], self.subscription.id)
        self.assertEqual(payload["payments"][0]["amount"], 1000)
        self.assertEqual(payload["documents"][0]["name"], "Договор")
        self.assertEqual(
            payload["representatives"][0]["full_name"],
            "Иванов Иван",
        )
        self.assertEqual(payload["diary"][0]["class_name"], "Техника")
        self.assertEqual(payload["achievements"][0]["name"], "Отличный старт")

    def test_coach_can_issue_customer_subscription(self):
        response = self.post_json(
            reverse(
                "api:coach_customer_issue_subscription",
                args=[self.other_customer.id],
            ),
            {
                "group_ids": [self.group.id],
                "number_classes": 8,
                "start_date": "2026-06-01",
                "end_date": "2026-06-30",
                "unlimited": False,
                "is_free": False,
                "total_cost": 1000,
                "payment_amount": 1000,
                "cashier_id": self.cashier.id,
                "payment_date": "2026-06-01",
            },
        )

        self.assertEqual(response.status_code, 201)
        subscription = CustumerSubscription.objects.get(
            custumer=self.other_customer,
            start_date=date(2026, 6, 1),
        )
        self.assertEqual(subscription.attendance_status, "paid")
        self.assertEqual(subscription.groups.first(), self.group)
        self.assertEqual(subscription.payments.first().summ, 1000)

    def test_coach_group_detail_keeps_group_journal_relations(self):
        response = self.client.get(
            reverse("api:coach_group_detail", args=[self.group.id]),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["links"]["detail"], f"/groups/detail/{self.group.id}/")
        self.assertEqual(payload["customers"][0]["full_name"], self.customer.full_name)
        class_items = payload["classes"]
        self.assertTrue(
            any(class_item["group"]["name"] == "Кракен" for class_item in class_items)
        )
        attendance_ids = [
            attendance["id"]
            for class_item in class_items
            for attendance in class_item["attendances"]
        ]
        self.assertIn(self.attendance.id, attendance_ids)

    def test_client_diary_returns_lesson_journal(self):
        self.client.force_login(self.client_user)

        response = self.client.get(
            reverse("api:client_diary"),
            {"date_from": "2026-04-01", "date_to": "2026-04-30"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["entries"][0]["class_name"], "Техника")
        self.assertEqual(payload["entries"][0]["display_text"], "+")

    def test_client_dashboard_returns_achievement_count(self):
        self.client.force_login(self.client_user)
        self.attendance.attendance_status = "attended_5"
        self.attendance.save(update_fields=["attendance_status"])

        response = self.client.get(reverse("api:client_dashboard"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["achievements_count"], 1)
        self.assertIsNone(payload["active_challenge"])
        self.assertEqual(
            payload["training_tasks_today"][0]["group"]["name"],
            self.group.name,
        )
        self.assertEqual(
            payload["company_group_ratings"]["groups"][0]["name"],
            self.group.name,
        )
        self.assertEqual(
            payload["company_group_ratings"]["week_group"]["name"],
            self.group.name,
        )

    def test_client_subscriptions_return_customer_passes(self):
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("api:client_subscriptions"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["subscriptions"][0]["classes_left"], 10)
        self.assertEqual(
            payload["subscriptions"][0]["payment_status"],
            "Оплачено",
        )

    def test_client_achievements_return_active_marks(self):
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("api:client_achievements"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["active_count"], 1)
        self.assertTrue(payload["achievements"][0]["active"])

    def test_client_competition_results_return_my_results(self):
        CustumerCompetitionResult.objects.create(
            competition=self.competition,
            customer=self.customer,
            distance=100,
            discipline="Комплекс",
            style="25m",
            result_time_ms=75380,
            place=1,
        )
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("api:client_competition_results"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["results"][0]["competition_id"], self.competition.id)
        self.assertEqual(payload["results"][0]["result_time"], "01:15:380")

    def test_mark_attendance_sets_grade(self):
        response = self.token_client.post(
            reverse("api:mark_attendance", args=[self.attendance.id]),
            data=json.dumps(
                {
                    "status": "attended_5",
                    "comment": "Хорошая работа",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        self.attendance.refresh_from_db()
        self.assertEqual(self.attendance.attendance_status, "attended_5")
        self.assertEqual(self.attendance.comment, "Хорошая работа")
        self.assertEqual(response.json()["attendance"]["display_text"], "5")

    def test_mark_attendance_sets_absent(self):
        response = self.token_client.post(
            reverse("api:mark_attendance", args=[self.attendance.id]),
            data=json.dumps({"status": "not_attended", "comment": ""}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        self.attendance.refresh_from_db()
        self.assertEqual(self.attendance.attendance_status, "not_attended")
        self.assertEqual(response.json()["attendance"]["display_text"], "Н")
