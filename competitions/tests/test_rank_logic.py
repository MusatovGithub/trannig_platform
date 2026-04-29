"""
Тесты для проверки логики присвоения разрядов спортсменам.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from authen.models import Company
from competitions.models import Competitions, CustumerCompetitionResult
from competitions.utils import (
    assign_rank_to_customer,
    can_assign_rank,
    get_customer_with_rank_info,
    get_sport_categories_ordered,
)
from custumer.models import Custumer, SportCategory

CustomUser = get_user_model()


class RankLogicTest(TestCase):
    """Тест логики присвоения разрядов."""

    def setUp(self):
        """Подготовка тестовых данных."""
        # Важно: очищаем кеш справочников, чтобы тест не использовал
        # значения из предыдущих запусков/других БД.
        cache.clear()

        # Создаем компанию
        self.company = Company.objects.create(name="Test Company")

        # Создаем пользователя
        self.user = CustomUser.objects.create(
            username="test@example.com",
            email="test@example.com",
            first_name="Test User",
            company=self.company,
        )

        # Создаем разряды с разными уровнями
        self.novice, _ = SportCategory.objects.get_or_create(
            name="Новичок",
            level=1,
            defaults={"description": "Начинающий спортсмен"},
        )

        self.third_rank, _ = SportCategory.objects.get_or_create(
            name="3-й разряд",
            level=3,
            defaults={"description": "Третий разряд"},
        )

        self.second_rank, _ = SportCategory.objects.get_or_create(
            name="2-й разряд",
            level=5,
            defaults={"description": "Второй разряд"},
        )

        self.first_rank, _ = SportCategory.objects.get_or_create(
            name="1-й разряд",
            level=7,
            defaults={"description": "Первый разряд"},
        )

        self.candidate, _ = SportCategory.objects.get_or_create(
            name="Кандидат в мастера спорта",
            level=9,
            defaults={"description": "КМС"},
        )

        # Создаем клиента без разряда
        self.customer_no_rank = Custumer.objects.create(
            user=self.user, full_name="Customer No Rank", company=self.company
        )

        # Создаем клиента с разрядом
        self.customer_with_rank = Custumer.objects.create(
            user=CustomUser.objects.create(
                username="ranked@example.com",
                email="ranked@example.com",
                first_name="Ranked User",
                company=self.company,
            ),
            full_name="Customer With Rank",
            sport_category=self.third_rank,
            company=self.company,
        )

        # Создаем соревнование
        self.competition = Competitions.objects.create(
            name="Test Competition",
            location="Test Location",
            date="2024-01-01",
            owner=self.user,
        )

        # Создаем результат соревнования
        self.result = CustumerCompetitionResult.objects.create(
            competition=self.competition,
            customer=self.customer_no_rank,
            distance=50.0,
            discipline="Плавание 50м вольный стиль",
            result_time_ms=30000,  # 00:30:000 (30 секунд)
            place=1,
        )

    def test_can_assign_rank_no_current_rank(self):
        """Тест: можно присвоить разряд клиенту без разряда."""
        can_assign, reason = can_assign_rank(
            self.customer_no_rank, self.novice
        )
        self.assertTrue(can_assign)
        self.assertIn("нет разряда", reason)

    def test_can_assign_rank_higher_rank(self):
        """Тест: можно присвоить разряд выше текущего."""
        can_assign, reason = can_assign_rank(
            self.customer_with_rank, self.second_rank
        )
        self.assertTrue(can_assign)
        self.assertIn("выше текущего", reason)

    def test_cannot_assign_rank_same_level(self):
        """Тест: нельзя присвоить разряд того же уровня."""
        can_assign, reason = can_assign_rank(
            self.customer_with_rank, self.third_rank
        )
        self.assertFalse(can_assign)
        self.assertIn("уже есть разряд", reason)

    def test_cannot_assign_rank_lower_level(self):
        """Тест: нельзя присвоить разряд ниже текущего."""
        can_assign, reason = can_assign_rank(
            self.customer_with_rank, self.novice
        )
        self.assertFalse(can_assign)
        self.assertIn("ниже текущего", reason)

    def test_assign_rank_success(self):
        """Тест: успешное присвоение разряда."""
        success, message, customer_updated = assign_rank_to_customer(
            self.customer_no_rank, self.first_rank, self.result
        )
        self.assertTrue(success)
        self.assertTrue(customer_updated)
        self.assertIn("успешно присвоен клиенту", message)

        # Проверяем, что разряд присвоен клиенту
        self.customer_no_rank.refresh_from_db()
        self.assertEqual(self.customer_no_rank.sport_category, self.first_rank)

        # Проверяем, что разряд присвоен результату
        self.result.refresh_from_db()
        self.assertEqual(self.result.sport_category, self.first_rank)

    def test_assign_rank_success_no_result(self):
        """Тест: успешное присвоение разряда без результата (при создании)."""
        success, message, customer_updated = assign_rank_to_customer(
            self.customer_no_rank, self.first_rank, None
        )
        self.assertTrue(success)
        self.assertTrue(customer_updated)
        self.assertIn("успешно присвоен клиенту", message)

        # Проверяем, что разряд присвоен клиенту
        self.customer_no_rank.refresh_from_db()
        self.assertEqual(self.customer_no_rank.sport_category, self.first_rank)

    def test_assign_rank_lower_level_saves_in_result(self):
        """Тест: разряд ниже текущего сохраняется в результате, но не клиенту."""  # noqa: E501
        # Присваиваем разряд ниже текущего (должен сохраниться в результате)
        success, message, customer_updated = assign_rank_to_customer(
            self.customer_with_rank, self.novice, self.result
        )

        # Операция должна быть успешной (разряд сохранен в результате)
        self.assertTrue(success)
        # Но клиенту не присвоен
        self.assertFalse(customer_updated)
        self.assertIn("сохранен в результате, но клиенту не присвоен", message)

        # Проверяем, что разряд сохранен в результате
        self.result.refresh_from_db()
        self.assertEqual(self.result.sport_category, self.novice)

        # Проверяем, что разряд клиента не изменился
        self.customer_with_rank.refresh_from_db()
        self.assertEqual(
            self.customer_with_rank.sport_category, self.third_rank
        )

    def test_get_customer_with_rank_info(self):
        """Тест: получение клиента с информацией о разряде."""
        customer = get_customer_with_rank_info(
            self.customer_with_rank.id, self.company
        )
        self.assertIsNotNone(customer)
        self.assertEqual(customer.sport_category, self.third_rank)

    def test_get_sport_categories_ordered(self):
        """Тест: получение разрядов, отсортированных по уровню."""
        categories = get_sport_categories_ordered()
        # Проверяем, что полный список отсортирован по возрастанию уровня
        all_levels = [cat.level for cat in categories]
        self.assertEqual(all_levels, sorted(all_levels))

        # Проверяем порядок именно тех 5 разрядов, которые используются в тесте
        tracked_ids = {
            self.novice.id,
            self.third_rank.id,
            self.second_rank.id,
            self.first_rank.id,
            self.candidate.id,
        }
        test_categories = [cat for cat in categories if cat.id in tracked_ids]
        self.assertEqual(len(test_categories), 5)
        self.assertEqual(
            [cat.level for cat in test_categories],
            sorted(
                [
                    self.novice.level,
                    self.third_rank.level,
                    self.second_rank.level,
                    self.first_rank.level,
                    self.candidate.level,
                ]
            ),
        )

    def test_rank_hierarchy_consistency(self):
        """Тест: консистентность иерархии разрядов."""
        # Проверяем, что уровни разрядов логичны
        self.assertLess(self.novice.level, self.third_rank.level)
        self.assertLess(self.third_rank.level, self.second_rank.level)
        self.assertLess(self.second_rank.level, self.first_rank.level)
        self.assertLess(self.first_rank.level, self.candidate.level)

    def test_assign_rank_with_competition_result_creation(self):
        """Тест: присвоение разряда при создании результата соревнования."""
        # Проверяем, что можно присвоить разряд (выше текущего 3-го)
        can_assign, reason = can_assign_rank(
            self.customer_with_rank, self.second_rank
        )
        self.assertTrue(can_assign)
        self.assertIn("выше текущего", reason)

        # Проверяем, что нельзя присвоить разряд ниже текущего
        can_assign_lower, reason_lower = can_assign_rank(
            self.customer_with_rank, self.novice
        )
        self.assertFalse(can_assign_lower)
        self.assertIn("ниже текущего", reason_lower)
