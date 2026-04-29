"""
Утилиты для кеширования часто используемых данных в Redis.
"""

from typing import Callable

from django.core.cache import cache

# Время жизни кеша для разных типов данных (в секундах)
CACHE_TIMEOUTS = {
    "reference_data": 3600 * 24,  # Справочники - 24 часа
    "company_data": 3600,  # Данные компании - 1 час
    "today_classes": 300,  # Занятия на сегодня - 5 минут
    "unpaid_summary": 180,  # Сводка неоплаченных - 3 минуты
    "user_permissions": 1800,  # Права пользователя - 30 минут
}


def get_cached_or_set(cache_key: str, callable_func: Callable, timeout: int):
    """
    Получить значение из кеша или выполнить функцию и закешировать результат.
    """
    result = cache.get(cache_key)
    if result is not None:
        return result

    result = callable_func()
    cache.set(cache_key, result, timeout)
    return result


# Функции для кеширования справочников
def get_cached_genders():
    """Получить список полов из кеша."""
    from authen.models import Gender

    cache_key = "reference:genders:all"
    return get_cached_or_set(
        cache_key,
        lambda: list(Gender.objects.all().order_by("-id")),
        CACHE_TIMEOUTS["reference_data"],
    )


def get_cached_sport_categories():
    """Получить список спортивных категорий из кеша."""
    from custumer.models import SportCategory

    cache_key = "reference:sport_categories:all"
    return get_cached_or_set(
        cache_key,
        lambda: list(SportCategory.objects.all().order_by("level")),
        CACHE_TIMEOUTS["reference_data"],
    )


def get_cached_weeks():
    """Получить список дней недели из кеша."""
    from groups_custumer.models import Week

    cache_key = "reference:weeks:all"
    return get_cached_or_set(
        cache_key,
        lambda: list(Week.objects.all()),
        CACHE_TIMEOUTS["reference_data"],
    )


def get_cached_type_sports(company_id: int):
    """Получить типы спорта компании из кеша."""
    from authen.models import TypeSportsCompany

    cache_key = f"company:{company_id}:type_sports"
    return get_cached_or_set(
        cache_key,
        lambda: list(TypeSportsCompany.objects.filter(company_id=company_id)),
        CACHE_TIMEOUTS["company_data"],
    )


# Функции для кеширования данных компании
def get_cached_subscription_templates(company_id: int):
    """Получить шаблоны абонементов компании из кеша."""
    from custumer.models import SubscriptionTemplate

    cache_key = f"company:{company_id}:subscription_templates"
    return get_cached_or_set(
        cache_key,
        lambda: list(
            SubscriptionTemplate.objects.filter(
                company_id=company_id
            ).order_by("name")
        ),
        CACHE_TIMEOUTS["company_data"],
    )


def get_cached_cashiers(company_id: int):
    """Получить кассы компании из кеша."""
    from custumer.models import Cashier

    cache_key = f"company:{company_id}:cashiers"
    return get_cached_or_set(
        cache_key,
        lambda: list(
            Cashier.objects.filter(company_id=company_id).order_by("name")
        ),
        CACHE_TIMEOUTS["company_data"],
    )


def get_cached_company_groups(company_id: int):
    """Получить группы компании из кеша."""
    from groups_custumer.models import GroupsClass

    cache_key = f"company:{company_id}:groups"
    return get_cached_or_set(
        cache_key,
        lambda: list(
            GroupsClass.objects.filter(company_id=company_id).select_related(
                "type_sport"
            )
        ),
        CACHE_TIMEOUTS["company_data"],
    )


def get_cached_company_employees(company_id: int):
    """Получить сотрудников компании из кеша."""
    from employe.models import Employe

    cache_key = f"company:{company_id}:employees"
    return get_cached_or_set(
        cache_key,
        lambda: list(
            Employe.objects.filter(company_id=company_id).order_by("-id")
        ),
        CACHE_TIMEOUTS["company_data"],
    )
